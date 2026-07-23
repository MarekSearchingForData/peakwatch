"""Zone -> town hourly load: the hybrid product.

Level from the proven settlement-share champions (seasonal alpha per town),
shape from the town's zone curve:

    town(t) = alpha_town(season(t)) * zone(t)

Validated two independent ways, printed with every run:
  1. Anchor test — reconstructed load at each settlement hour vs published
     RNL (should match the champions' known 4-8% error).
  2. Energy closure — integrated annual curve vs EIA-861 annual sales.
     A shortfall marks own-generation netting (Holyoke hydro, Princeton
     wind) and is reported as the town's measured generation wedge, not
     hidden.
Coherence is structural: shares of a zone sum across member towns to less
than 1, and rest-of-zone absorbs the remainder.
"""
import numpy as np
import pandas as pd

from .allocator import _monthly_pool_peak_hours, _pool_series
from .peaks import EASTERN
from .store import connect

SEASON = {12: "w", 1: "w", 2: "w", 6: "s", 7: "s", 8: "s"}


def _seasonal_alphas(con):
    """Per-town seasonal settlement shares from snapped anchors."""
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl", con)
    peaks = _monthly_pool_peak_hours(zd, _pool_series(con))
    zone_ts = {z: zd[zd["zone"] == z].set_index("ts")["rt_load_mw"]
               for z in ("NEMA", "SEMA", "WCMA")}
    rows = []
    for _, r in rnl.iterrows():
        if r["month"] not in peaks.index or r["zone"] not in zone_ts:
            continue
        zmw = zone_ts[r["zone"]].get(peaks.loc[r["month"], "ts"])
        if pd.notna(zmw) and zmw > 0:
            rows.append({"town": r["town"], "zone": r["zone"],
                         "month": r["month"], "rnl": r["rnl_mw"],
                         "season": SEASON.get(int(r["month"][5:]), "sh"),
                         "alpha": r["rnl_mw"] / zmw, "zone_mw": zmw})
    df = pd.DataFrame(rows)
    alphas = df.groupby(["town", "season"])["alpha"].mean()
    return df, alphas


def run():
    con = connect()
    obs, alphas = _seasonal_alphas(con)
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    mix = pd.read_sql("SELECT town, total_mwh FROM town_class_mix", con)\
        .set_index("town")["total_mwh"]

    # validation 1: anchor reconstruction (walk-forward-free sanity: seasonal
    # alpha excluding the month itself)
    errs = []
    for (town, season), g in obs.groupby(["town", "season"]):
        for i in range(len(g)):
            a = g["alpha"].drop(g.index[i]).mean() if len(g) > 1 else np.nan
            if not np.isnan(a) and g["rnl"].iloc[i] > 0:
                errs.append({"town": town,
                             "ape": abs(a * g["zone_mw"].iloc[i]
                                        - g["rnl"].iloc[i]) / g["rnl"].iloc[i]})
    anchor = pd.DataFrame(errs).groupby("town")["ape"].mean() * 100

    # validation 2: energy closure over the last 12 full months
    zd["local"] = zd["ts"].dt.tz_convert(EASTERN)
    zd["season"] = zd["local"].dt.month.map(lambda m: SEASON.get(m, "sh"))
    recent = zd[zd["ts"] >= zd["ts"].max() - pd.Timedelta(days=365)]
    rows = []
    for town in obs["town"].unique():
        zone = obs[obs["town"] == town]["zone"].iloc[0]
        z = recent[recent["zone"] == zone].dropna(subset=["rt_load_mw"])
        a = z["season"].map(lambda s, t=town: alphas.get((t, s), np.nan))
        energy_gwh = float((a.values * z["rt_load_mw"].values).sum()) / 1000
        eia_gwh = mix.get(town, np.nan) / 1000
        rows.append({
            "Town": town,
            "anchor_err_%": round(anchor.get(town, np.nan), 1),
            "est_GWh/yr": round(energy_gwh, 1),
            "EIA_GWh/yr": round(eia_gwh, 1),
            "closure_%": round(100 * energy_gwh / eia_gwh, 1) if eia_gwh else None,
        })
    out = pd.DataFrame(rows).sort_values("est_GWh/yr", ascending=False)
    print("=== Town hourly curves: validation ===")
    print(out.to_string(index=False))
    print("\nReading guide: anchor_err% ~ champions' known error (4-8% = good). "
          "closure% near 100 = clean town; well under 100 = own generation "
          "netting load (the measured generation wedge); ~market-purchases "
          "share for towns with local plants selling to grid.")
    con.close()
    return out


if __name__ == "__main__":
    run()
