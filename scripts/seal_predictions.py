"""Seal predict-before-publish RNL predictions for the current month.

For each of the 20 towns: predicted settlement RNL for the target month,
with an honest interval from that town's own historical leave-one-out
errors. Sealed = written to predictions/ and committed; the git timestamp
proves the prediction predates ISO-NE's publication (~2-month lag).

Method (deliberately the boring, proven champion): same-season mean share
x zone load at the month's anchor hour so far. Caveat recorded in the
file: if a later hour in the month sets a new pool peak, the anchor moves.
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from peakwatch.allocator import _monthly_pool_peak_hours, _pool_series
from peakwatch.peaks import EASTERN
from peakwatch.store import connect

SEASON = {12: "w", 1: "w", 2: "w", 6: "s", 7: "s", 8: "s"}
OUT = Path(__file__).resolve().parent.parent / "predictions"


def season_of(month_str):
    return SEASON.get(int(month_str[5:7]), "sh")


def main(target=None):
    target = target or date.today().strftime("%Y-%m")
    con = connect()
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl", con)

    peaks = _monthly_pool_peak_hours(zd, _pool_series(con))
    if target not in peaks.index:
        print(f"no {target} zone data yet")
        return
    anchor_ts = peaks.loc[target, "ts"]
    zone_at = {z: zd[(zd["zone"] == z) & (zd["ts"] == anchor_ts)]["rt_load_mw"].max()
               for z in ("NEMA", "SEMA", "WCMA")}

    # historical alphas per town at snapped anchors (excluding target month)
    hist = peaks[peaks.index < target]
    rows = []
    for town, g in rnl[rnl["month"] < target].groupby("town"):
        zone = g["zone"].mode()[0]
        zl = zd[zd["zone"] == zone].set_index("ts")["rt_load_mw"]
        m = g.set_index("month").join(hist, how="inner")
        m["zone_mw"] = zl.reindex(m["ts"]).values
        m = m.dropna(subset=["zone_mw"])
        m["alpha"] = m["rnl_mw"] / m["zone_mw"]
        same = m[[season_of(x) == season_of(target) for x in m.index]]
        pool = same if len(same) >= 3 else m
        alpha_hat = pool["alpha"].mean()
        # LOO error distribution of this predictor on its own history
        errs = []
        for i in range(len(pool)):
            a = pool["alpha"].drop(pool.index[i]).mean()
            errs.append(a * pool["zone_mw"].iloc[i] - pool["rnl_mw"].iloc[i])
        lo, hi = (np.quantile(errs, 0.1), np.quantile(errs, 0.9)) if errs else (0, 0)
        pred = alpha_hat * zone_at[zone]
        rows.append({"Town": town, "Zone": zone,
                     "Predicted_RNL_MW": round(pred, 2),
                     "Low_MW": round(max(0, pred + lo), 2),
                     "High_MW": round(pred + hi, 2),
                     "n_history_months": len(pool)})

    df = pd.DataFrame(rows).sort_values("Predicted_RNL_MW", ascending=False)
    OUT.mkdir(exist_ok=True)
    path = OUT / f"sealed_{target}.csv"
    header = (f"# PeakWatch sealed prediction — target month {target}\n"
              f"# sealed_at_utc: {datetime.now(timezone.utc).isoformat()}\n"
              f"# anchor hour so far: {anchor_ts} (local "
              f"{anchor_ts.tz_convert(EASTERN)})\n"
              f"# method: same-season mean settlement share x zone load at anchor\n"
              f"# caveat: anchor moves if a later hour sets a new pool peak\n"
              f"# scored when ISO-NE publishes ww-network-load-iso-"
              f"{target.replace('-', '')} (~2-month lag)\n")
    path.write_text(header + df.to_csv(index=False), encoding="utf-8")
    print(header)
    print(df.to_string(index=False))
    print(f"\nsealed -> {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
