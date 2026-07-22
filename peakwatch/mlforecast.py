"""ML zone forecast (Task 6, small batch): LightGBM quantile models per zone.

Day-ahead setup, honestly framed: predicting hour h of day D uses only
information available the prior evening — weather (stand-in for a weather
forecast), calendar, and load lags of >= 24h. Scored on a held-out time
split against ISO-NE's own day-ahead cleared demand on the SAME hours.
Quantile losses at p10/p50/p90 give calibrated uncertainty bands.
"""
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .peaks import EASTERN
from .store import connect

FEATURES = ["hour", "dow", "is_weekend", "is_holiday", "doy_sin", "doy_cos",
            "sunset_hour", "temp_c", "ghi_wm2", "cloud_pct", "wind_kmh",
            "lag24", "lag168"]
TEST_DAYS = 60
WEATHER_PROXY_TOWNS = ["Chicopee", "Holyoke", "Princeton"]  # averaged for WCMA


def build_frame(con, zone="WCMA"):
    zd = pd.read_sql("SELECT ts, rt_load_mw, da_load_mw FROM clean_zone_demand "
                     "WHERE zone = ?", con, params=[zone], parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    zd = zd.sort_values("ts").set_index("ts")

    wx = pd.read_sql("SELECT * FROM raw_weather WHERE town IN (%s)"
                     % ",".join("?" * len(WEATHER_PROXY_TOWNS)), con,
                     params=WEATHER_PROXY_TOWNS, parse_dates=["ts"])
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)
    wxa = wx.groupby("ts")[["temp_c", "ghi_wm2", "cloud_pct", "wind_kmh"]].mean()

    cal = pd.read_sql("SELECT * FROM feature_calendar", con)

    df = zd.join(wxa, how="inner")
    local = df.index.tz_convert(EASTERN)
    df["hour"] = local.hour
    df["dow"] = local.dayofweek
    df["date"] = local.strftime("%Y-%m-%d")
    df = df.merge(cal[["date", "is_weekend", "is_holiday", "doy_sin", "doy_cos",
                       "sunset_hour"]], on="date", how="left")
    df.index = zd.join(wxa, how="inner").index
    df["lag24"] = df["rt_load_mw"].shift(24)
    df["lag168"] = df["rt_load_mw"].shift(168)
    return df.dropna(subset=["rt_load_mw", "lag24", "lag168", "temp_c"])


def run(zone="WCMA"):
    con = connect()
    df = build_frame(con, zone)
    dates = sorted(df["date"].unique())
    if len(dates) < TEST_DAYS + 90:
        print(f"Not enough continuous data yet ({len(dates)} days)")
        return
    split = dates[-TEST_DAYS]
    train, test = df[df["date"] < split], df[df["date"] >= split]
    print(f"=== LightGBM {zone}: train {len(train):,}h "
          f"({train['date'].min()}..{train['date'].max()}), "
          f"test {len(test):,}h ({split}..{test['date'].max()}) ===")

    models = {}
    for q in (0.1, 0.5, 0.9):
        m = LGBMRegressor(objective="quantile", alpha=q, n_estimators=400,
                          learning_rate=0.05, num_leaves=63, verbose=-1)
        m.fit(train[FEATURES], train["rt_load_mw"])
        models[q] = m
    p50 = models[0.5].predict(test[FEATURES])
    p10 = models[0.1].predict(test[FEATURES])
    p90 = models[0.9].predict(test[FEATURES])

    y = test["rt_load_mw"].values
    ours = np.abs(p50 - y)
    iso = np.abs(test["da_load_mw"].values - y)
    both = ~np.isnan(iso)
    cover = np.mean((y >= p10) & (y <= p90))
    blend = np.abs((p50 + test["da_load_mw"].values) / 2 - y)
    print(f"\nMAE  ours: {ours[both].mean():.1f} MW   ISO DA: {iso[both].mean():.1f} MW"
          f"   ({100 * (1 - ours[both].mean() / iso[both].mean()):+.1f}% vs ISO)")
    print(f"MAPE ours: {100 * (ours[both] / y[both]).mean():.2f}%   "
          f"ISO DA: {100 * (iso[both] / y[both]).mean():.2f}%   "
          f"BLEND (ours+ISO)/2: {100 * (blend[both] / y[both]).mean():.2f}%")
    print(f"p10-p90 coverage: {100 * cover:.1f}% (target 80%)")

    # daily peak calling on test days
    t = test.copy()
    t["p50"] = p50
    hit = 0
    days = t.groupby("date")
    for _, g in days:
        if g["rt_load_mw"].idxmax() == g["p50"].idxmax():
            hit += 1
    print(f"exact peak-hour hit rate: {hit}/{len(days)} days "
          f"({100 * hit / len(days):.0f}%)")

    imp = pd.Series(models[0.5].feature_importances_, index=FEATURES)
    print("\ntop features:", ", ".join(imp.sort_values(ascending=False)
                                       .head(6).index))
    con.close()


if __name__ == "__main__":
    run()
