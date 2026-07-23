"""Walk-forward robustness test: stricter than leave-one-out.

LOO lets a model 'see' months after the target; walk-forward only uses the
past (expanding window, first 18 months warm-up). If champions hold up
here, the LOO scores aren't an artifact of peeking.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from peakwatch.allocator import (SLICE_TOWNS, SLICE_ZONE,
                                 _monthly_pool_peak_hours, _pool_series)
from peakwatch.experiments import SEASON
from peakwatch.store import connect

WARMUP = 18


def main():
    con = connect()
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl WHERE zone=?", con,
                      params=[SLICE_ZONE])
    wx = pd.read_sql("SELECT * FROM raw_weather", con, parse_dates=["ts"])
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)
    peaks = _monthly_pool_peak_hours(zd, _pool_series(con))
    zmw = (zd[zd["zone"] == SLICE_ZONE].set_index("ts")["rt_load_mw"]
           .reindex(peaks["ts"]))
    peaks = peaks.assign(zone_mw=zmw.values).dropna(subset=["zone_mw"])

    print(f"{'town':<10} {'model':<10} {'LOO-style n/a':<0}walk-forward MAPE% "
          f"(n predictions)")
    for town in SLICE_TOWNS:
        t = rnl[rnl["town"] == town].set_index("month")["rnl_mw"]
        d = peaks.join(t, how="inner").dropna(subset=["rnl_mw"]).sort_index()
        f = wx[wx["town"] == town].set_index("ts").reindex(d["ts"])
        d = d.assign(temp=f["temp_c"].values, ghi=f["ghi_wm2"].values,
                     season=[SEASON.get(int(m[5:]), "sh") for m in d.index],
                     alpha=(d["rnl_mw"] / d["zone_mw"]))
        res = {}
        for name in ("flat", "seasonal", "temp+ghi"):
            errs = []
            for i in range(WARMUP, len(d)):
                tr, te = d.iloc[:i], d.iloc[i]
                if te["rnl_mw"] == 0:
                    continue
                if name == "flat":
                    a = tr["alpha"].mean()
                elif name == "seasonal":
                    same = tr[tr["season"] == te["season"]]
                    a = (same if len(same) >= 3 else tr)["alpha"].mean()
                else:
                    A = np.column_stack([np.ones(len(tr)), tr[["temp", "ghi"]]])
                    coef, *_ = np.linalg.lstsq(A, tr["alpha"], rcond=None)
                    a = np.array([1, te["temp"], te["ghi"]]) @ coef
                errs.append(abs(a * te["zone_mw"] - te["rnl_mw"]) / te["rnl_mw"])
            res[name] = (100 * np.mean(errs), len(errs))
        for name, (m, n) in res.items():
            print(f"{town:<10} {name:<10} {m:>6.2f}  (n={n})")
    con.close()


if __name__ == "__main__":
    main()
