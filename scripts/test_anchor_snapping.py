"""Does snapping the anchor hour to ISO's published pool value stabilize
town shares?

Method A (current): anchor = hour of max summed-zone RT load.
Method B (snapped): anchor = hour whose summed-zone load is closest to the
published Monthly Regional Pool Network Load Value.

Metric: per-town coefficient of variation of alpha, plus LOO MAPE, under
each method. Lower = more stable anchor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from peakwatch.peaks import EASTERN
from peakwatch.store import connect

TOWNS = ["Chicopee", "Holyoke", "Peabody", "Shrewsbury", "Wakefield"]


def main():
    con = connect()
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    system = zd.groupby("ts")["rt_load_mw"].sum(min_count=8).dropna()
    month = pd.Series(system.index.tz_convert(EASTERN).strftime("%Y-%m"),
                      index=system.index)
    rnl = pd.read_sql("SELECT * FROM raw_town_rnl", con)
    pool = rnl.groupby("month")["pool_total_mw"].max()

    anchors = {}
    for m, g in system.groupby(month):
        a_max = g.idxmax()
        if m in pool.index:
            a_snap = (g - pool[m]).abs().idxmin()
            anchors[m] = (a_max, a_snap, g[a_max], g[a_snap], pool[m])

    rep = pd.DataFrame(anchors, index=["h_max", "h_snap", "mw_max", "mw_snap",
                                       "published"]).T
    moved = (rep["h_max"] != rep["h_snap"]).sum()
    gap_max = 100 * (rep["mw_max"] - rep["published"]).abs() / rep["published"]
    gap_snap = 100 * (rep["mw_snap"] - rep["published"]).abs() / rep["published"]
    print(f"months: {len(rep)}; anchor hour moved by snapping: {moved}")
    print(f"|gap to published|  argmax: {gap_max.mean():.2f}%   "
          f"snapped: {gap_snap.mean():.2f}%")

    zone_rt = zd[zd["zone"] == "WCMA"].set_index("ts")["rt_load_mw"]
    zone_rt_nema = zd[zd["zone"] == "NEMA"].set_index("ts")["rt_load_mw"]
    zones = {"Chicopee": zone_rt, "Holyoke": zone_rt, "Shrewsbury": zone_rt,
             "Peabody": zone_rt_nema, "Wakefield": zone_rt_nema}

    print(f"\n{'town':<12} {'CV% max':>8} {'CV% snap':>9} {'LOO% max':>9} {'LOO% snap':>10}")
    for town in TOWNS:
        t = rnl[rnl["town"] == town].set_index("month")["rnl_mw"]
        rows = []
        for m, (a_max, a_snap, *_ ) in anchors.items():
            if m not in t.index or t[m] == 0:
                continue
            zmax, zsnap = zones[town].get(a_max), zones[town].get(a_snap)
            if pd.notna(zmax) and pd.notna(zsnap):
                rows.append((t[m] / zmax, t[m] / zsnap))
        a = pd.DataFrame(rows, columns=["alpha_max", "alpha_snap"])
        if len(a) < 5:
            continue
        loo = {}
        for c in a.columns:
            v = a[c].values
            loo[c] = 100 * np.mean([abs(np.delete(v, i).mean() - v[i]) / v[i]
                                    for i in range(len(v))])
        print(f"{town:<12} {100 * a['alpha_max'].std() / a['alpha_max'].mean():>8.2f} "
              f"{100 * a['alpha_snap'].std() / a['alpha_snap'].mean():>9.2f} "
              f"{loo['alpha_max']:>9.2f} {loo['alpha_snap']:>10.2f}")
    con.close()


if __name__ == "__main__":
    main()
