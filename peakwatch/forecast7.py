"""Multi-day hourly zone forecast (1-7 days, selectable) for the dashboard.

Uses only features knowable at any horizon (forecast weather + calendar —
no load lags), so the same model serves day 1 through day 7. Bands are
residual-calibrated on a holdout slice. ISO's own published forecast is
overlaid where it exists (~3 days) as the benchmark line.
"""
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .peaks import EASTERN
from .store import connect

FEATURES = ["hour", "dow", "is_weekend", "is_holiday", "doy_sin", "doy_cos",
            "sunset_hour", "temp_c", "ghi_wm2", "cloud_pct", "wind_kmh",
            "recent_same_hour", "recent_max"]


def _calendar(con):
    cal = pd.read_sql("SELECT * FROM feature_calendar", con)
    cal["date"] = pd.to_datetime(cal["date"])
    return cal.set_index("date")


def train_and_forecast(zone: str, days: int = 7):
    """Returns (history_tail, forecast_df) — forecast has p10/p50/p90."""
    con = connect()
    zd = pd.read_sql("SELECT ts, rt_load_mw FROM clean_zone_demand "
                     "WHERE zone=? AND rt_load_mw IS NOT NULL", con,
                     params=[zone])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    wx = pd.read_sql("SELECT ts, AVG(temp_c) temp_c, AVG(ghi_wm2) ghi_wm2, "
                     "AVG(cloud_pct) cloud_pct, AVG(wind_kmh) wind_kmh "
                     "FROM raw_weather GROUP BY ts", con)
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)
    cal = _calendar(con)

    df = zd.merge(wx, on="ts", how="inner").sort_values("ts")
    local = df["ts"].dt.tz_convert(EASTERN)
    df["hour"], df["dow"] = local.dt.hour, local.dt.dayofweek
    dkey = pd.to_datetime(local.dt.date)
    for c in ("is_weekend", "is_holiday", "doy_sin", "doy_cos", "sunset_hour"):
        df[c] = dkey.map(cal[c]).values
    # recent-usage anchors, knowable at any horizon: same-hour mean and daily
    # max over the trailing 14 settled days (shifted — no leakage)
    df["recent_same_hour"] = (df.groupby("hour")["rt_load_mw"]
                                .transform(lambda s: s.rolling(14).mean().shift(1)))
    df["recent_max"] = df["rt_load_mw"].rolling(24 * 14).max().shift(1)
    df = df.dropna(subset=FEATURES + ["rt_load_mw"])

    cut = df["ts"].max() - pd.Timedelta(days=45)
    fit, calib = df[df["ts"] < cut], df[df["ts"] >= cut]
    models = {}
    for qv in (0.1, 0.5, 0.9):
        m = LGBMRegressor(objective="quantile", alpha=qv, n_estimators=200,
                          learning_rate=0.06, num_leaves=63, verbose=-1)
        m.fit(fit[FEATURES], fit["rt_load_mw"])
        models[qv] = m
    res = calib["rt_load_mw"].values - models[0.5].predict(calib[FEATURES])
    lo, hi = np.quantile(res, 0.1), np.quantile(res, 0.9)

    # forecast frame: starts at the LAST SETTLED HOUR (fills the settlement
    # gap by hindcasting with observed weather) and runs to now + days.
    # Weather: observed where available, forecast beyond.
    last_rt = df["ts"].max()
    now = pd.Timestamp.now(tz="UTC")
    hours = pd.date_range(last_rt + pd.Timedelta(hours=1),
                          now + pd.Timedelta(days=days), freq="h", tz="UTC")
    wf = pd.DataFrame({"ts": hours})
    wfx = pd.read_sql("SELECT ts, AVG(temp_c) temp_c, AVG(ghi_wm2) ghi_wm2, "
                      "AVG(cloud_pct) cloud_pct, AVG(wind_kmh) wind_kmh "
                      "FROM raw_weather_fcst GROUP BY ts", con)
    wfx["ts"] = pd.to_datetime(wfx["ts"], utc=True)
    wf = (wf.merge(wx, on="ts", how="left")
            .merge(wfx, on="ts", how="left", suffixes=("", "_f")))
    for c in ("temp_c", "ghi_wm2", "cloud_pct", "wind_kmh"):
        wf[c] = wf[c].fillna(wf[f"{c}_f"])
    flocal = wf["ts"].dt.tz_convert(EASTERN)
    wf["hour"], wf["dow"] = flocal.dt.hour, flocal.dt.dayofweek
    fkey = pd.to_datetime(flocal.dt.date)
    for c in ("is_weekend", "is_holiday", "doy_sin", "doy_cos", "sunset_hour"):
        wf[c] = fkey.map(cal[c]).values
    same_hour = df.groupby("hour")["rt_load_mw"].apply(lambda s: s.tail(14).mean())
    wf["recent_same_hour"] = wf["hour"].map(same_hour)
    wf["recent_max"] = df["rt_load_mw"].tail(24 * 14).max()
    wf = wf.dropna(subset=FEATURES)

    p50 = models[0.5].predict(wf[FEATURES])
    fc = pd.DataFrame({
        "ts": wf["ts"].values,
        "p50": p50,
        "p10": np.minimum(models[0.1].predict(wf[FEATURES]), p50 + lo),
        "p90": np.maximum(models[0.9].predict(wf[FEATURES]), p50 + hi),
    })

    iso = pd.read_sql("SELECT ts, MAX(load_mw) iso_fcst FROM raw_isone_fcst "
                      "GROUP BY ts", con)
    iso["ts"] = pd.to_datetime(iso["ts"], utc=True, format="ISO8601")
    fc["ts"] = pd.to_datetime(fc["ts"], utc=True)
    fc = fc.merge(iso, on="ts", how="left")
    if "iso_fcst" in fc.columns:
        # ISO forecast is system-wide; scale to zone by recent share
        share = (zd["rt_load_mw"].tail(24 * 30).sum()
                 / pd.read_sql("SELECT SUM(rt_load_mw) s FROM clean_zone_demand "
                               "WHERE rt_load_mw IS NOT NULL AND "
                               "ts >= date('now', '-30 days')", con)["s"].iloc[0])
        fc["iso_fcst_zone"] = fc["iso_fcst"] * share

    tail = df[df["ts"] >= now - pd.Timedelta(days=7)][["ts", "rt_load_mw"]]
    con.close()
    return tail, fc
