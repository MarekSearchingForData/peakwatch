"""Pooled ('global') town model: ONE LightGBM over all towns x anchor months.

49 anchors per town is too thin for per-town ML, but ~20 towns x anchors
pooled is enough — the model borrows strength across towns through shared
features (class mix, portfolio, weather at the peak hour, zone state).
Scored leave-one-MONTH-out (all towns of month m held out together, so no
within-month leakage) and compared per town against the flat-share baseline.
"""
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .allocator import _monthly_pool_peak_hours
from .store import connect

TECH_BUCKETS = {"solar": "pv_mw", "hydro": "hydro_mw", "wind": "wind_mw",
                "bess": "bess_mw"}


def _portfolio_features(con):
    pf = pd.read_sql("SELECT * FROM town_portfolio WHERE status='operational'", con)
    pf["bucket"] = pf["tech"].str.lower().map(
        lambda t: next((v for k, v in TECH_BUCKETS.items() if k in t), None))
    agg = (pf.dropna(subset=["bucket"])
             .pivot_table(index="town", columns="bucket", values="nameplate_mw",
                          aggfunc="sum", fill_value=0.0))
    return agg


def build_frame(con):
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl", con)
    mix = pd.read_sql("SELECT * FROM town_class_mix", con).set_index("town")
    pf = _portfolio_features(con)
    wx = pd.read_sql("SELECT * FROM raw_weather", con, parse_dates=["ts"])
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)

    peaks = _monthly_pool_peak_hours(zd)
    zone_at_peak = {}
    for zone in ("NEMA", "SEMA", "WCMA"):
        zone_at_peak[zone] = (zd[zd["zone"] == zone].set_index("ts")["rt_load_mw"]
                              .reindex(peaks["ts"]).values)

    rows = []
    for _, r in rnl.iterrows():
        if r["month"] not in peaks.index or r["zone"] not in zone_at_peak:
            continue
        i = list(peaks.index).index(r["month"])
        ts = peaks["ts"].iloc[i]
        z_mw = zone_at_peak[r["zone"]][i]
        if pd.isna(z_mw):
            continue
        w = wx[(wx["town"] == r["town"]) & (wx["ts"] == ts)]
        m = mix.loc[r["town"]] if r["town"] in mix.index else None
        p = pf.loc[r["town"]] if r["town"] in pf.index else None
        total = m["total_mwh"] if m is not None else np.nan
        rows.append({
            "town": r["town"], "month": r["month"], "y": r["rnl_mw"],
            "zone_mw": z_mw,
            "total_mwh": total,
            "res_share": (m["res_mwh"] / total) if m is not None and pd.notna(m["res_mwh"]) else np.nan,
            "ind_share": (m["ind_mwh"] / total) if m is not None and pd.notna(m["ind_mwh"]) else np.nan,
            "pv_mw": p["pv_mw"] if p is not None and "pv_mw" in p else 0.0,
            "wind_mw": p["wind_mw"] if p is not None and "wind_mw" in p else 0.0,
            "hydro_mw": p["hydro_mw"] if p is not None and "hydro_mw" in p else 0.0,
            "temp_c": w["temp_c"].iloc[0] if len(w) else np.nan,
            "ghi_wm2": w["ghi_wm2"].iloc[0] if len(w) else np.nan,
            "wind_kmh": w["wind_kmh"].iloc[0] if len(w) else np.nan,
            "mon": int(r["month"][5:]),
        })
    return pd.DataFrame(rows)


FEATURES = ["zone_mw", "total_mwh", "res_share", "ind_share", "pv_mw", "wind_mw",
            "hydro_mw", "temp_c", "ghi_wm2", "wind_kmh", "mon"]


def run():
    con = connect()
    df = build_frame(con)
    months = sorted(df["month"].unique())
    print(f"=== Pooled town model: {df['town'].nunique()} towns x "
          f"{len(months)} months = {len(df)} rows ===")

    preds = pd.Series(index=df.index, dtype=float)
    flat = pd.Series(index=df.index, dtype=float)
    for m in months:
        tr, te = df[df["month"] != m], df[df["month"] == m]
        model = LGBMRegressor(n_estimators=300, learning_rate=0.05,
                              num_leaves=31, min_child_samples=10, verbose=-1)
        model.fit(tr[FEATURES], tr["y"])
        preds[te.index] = model.predict(te[FEATURES])
        # flat baseline: town's mean share of its zone across training months
        for i, r in te.iterrows():
            g = tr[tr["town"] == r["town"]]
            share = (g["y"] / g["zone_mw"]).mean() if len(g) else np.nan
            flat[i] = share * r["zone_mw"]

    df["pred"], df["flat"] = preds, flat
    df["ae_pool"] = (df["pred"] - df["y"]).abs()
    df["ae_flat"] = (df["flat"] - df["y"]).abs()
    by_town = df.groupby("town")[["ae_pool", "ae_flat", "y"]].mean()
    by_town["pool_MAPE%"] = 100 * df.groupby("town").apply(
        lambda g: (g["ae_pool"] / g["y"].replace(0, np.nan)).mean(),
        include_groups=False)
    by_town["flat_MAPE%"] = 100 * df.groupby("town").apply(
        lambda g: (g["ae_flat"] / g["y"].replace(0, np.nan)).mean(),
        include_groups=False)
    by_town["winner"] = np.where(by_town["ae_pool"] < by_town["ae_flat"],
                                 "POOLED", "flat")
    out = by_town.rename(columns={"ae_pool": "pool_MAE_MW", "ae_flat": "flat_MAE_MW",
                                  "y": "mean_RNL_MW"}).round(2)
    print(out.sort_values("mean_RNL_MW", ascending=False).to_string())
    wins = int((by_town["winner"] == "POOLED").sum())
    print(f"\nPooled model wins {wins}/{len(by_town)} towns on MAE. "
          f"Overall MAE: pooled {df['ae_pool'].mean():.2f} MW "
          f"vs flat {df['ae_flat'].mean():.2f} MW")
    con.close()


if __name__ == "__main__":
    run()
