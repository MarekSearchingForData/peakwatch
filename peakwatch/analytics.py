"""Track 1: statistical peak climatology + interpretable risk flags.

No models here — counted historical truth: when do peaks happen (hour,
day-of-month, temperature), and a KM-style 'runway': P(monthly peak still
ahead | day of month), from the empirical survival of peak days.
"""
import pandas as pd

from .allocator import _monthly_pool_peak_hours, _pool_series
from .peaks import EASTERN
from .store import connect


def climatology(con):
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    peaks = _monthly_pool_peak_hours(zd, _pool_series(con))
    local = peaks["ts"].dt.tz_convert(EASTERN)
    out = pd.DataFrame({
        "month": peaks.index,
        "peak_day": local.dt.day.values,
        "peak_hour": local.dt.hour.values,
        "peak_dow": local.dt.dayofweek.values,
        "peak_mw": peaks["rt_load_mw"].values,
    })
    return out


def survival_runway(clim):
    """P(monthly peak still ahead | today is day d) by season, empirical."""
    clim = clim.copy()
    clim["season"] = clim["month"].str[5:7].astype(int).map(
        lambda m: "summer" if m in (6, 7, 8) else
                  "winter" if m in (12, 1, 2) else "shoulder")
    rows = []
    for season, g in clim.groupby("season"):
        for d in (5, 10, 15, 20, 25):
            rows.append({"season": season, "day_of_month": d,
                         "P_peak_still_ahead": (g["peak_day"] >= d).mean(),
                         "n_months": len(g)})
    return pd.DataFrame(rows)


def risk_flags(con, threshold=0.95):
    """Next-days risk table from ISO's forecast vs month-to-date max,
    with weather context. Interpretable by construction."""
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    system = zd.groupby("ts")["rt_load_mw"].sum(min_count=8).dropna()
    now = pd.Timestamp.now(tz="UTC")
    this_month = system[system.index.tz_convert(EASTERN).strftime("%Y-%m")
                        == now.tz_convert(EASTERN).strftime("%Y-%m")]
    mtd_max = this_month.max() if len(this_month) else float("nan")

    fc = pd.read_sql("SELECT * FROM raw_isone_fcst", con)
    if fc.empty:
        return pd.DataFrame(), mtd_max
    fc["ts"] = pd.to_datetime(fc["ts"])
    fc = fc.sort_values("created").drop_duplicates("ts", keep="last")
    fc["date"] = fc["ts"].dt.date
    wx = pd.read_sql("SELECT * FROM raw_weather_fcst WHERE town='Chicopee'", con)
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)
    wx["date"] = wx["ts"].dt.tz_convert(EASTERN).dt.date
    wx_daily = wx.groupby("date").agg(tmax_c=("temp_c", "max"),
                                      ghi_max=("ghi_wm2", "max"))

    rows = []
    for d, g in fc.groupby("date"):
        peak = g.loc[g["load_mw"].idxmax()]
        ratio = peak["load_mw"] / mtd_max if mtd_max == mtd_max else float("nan")
        w = wx_daily.reindex([d])
        rows.append({
            "date": str(d),
            "iso_fcst_peak_mw": round(peak["load_mw"]),
            "fcst_peak_hour": peak["ts"].hour,
            "vs_mtd_max": round(ratio, 3) if ratio == ratio else None,
            "tmax_C": None if w["tmax_c"].isna().all() else round(float(w["tmax_c"].iloc[0]), 1),
            "flag": "PEAK RISK" if ratio == ratio and ratio >= threshold else "",
        })
    return pd.DataFrame(rows), mtd_max


def run():
    con = connect()
    clim = climatology(con)
    print(f"=== Peak climatology ({len(clim)} months of hourly history) ===")
    print("\nPeak hour distribution (local):")
    print(clim.groupby("peak_hour").size().to_string())
    print("\nPeak day-of-week distribution (0=Mon):")
    print(clim.groupby("peak_dow").size().to_string())
    print("\n=== Runway: P(monthly peak still ahead | day of month) ===")
    print(survival_runway(clim).round(2).to_string(index=False))
    flags, mtd = risk_flags(con)
    print(f"\n=== Next-days risk (month-to-date max: {mtd:,.0f} MW) ===")
    if len(flags):
        print(flags.to_string(index=False))
    con.close()


if __name__ == "__main__":
    run()
