"""Validation gate: raw_* -> clean_* with reconciliation checks.

Every check writes to quality_log. Data is promoted only if the blocking
checks pass; the dashboard and CLI surface failures instead of hiding them.
"""
from datetime import datetime, timezone

import pandas as pd

from .config import PROJECT_ROOT
from .store import connect

REGION_TO_ZONE = {".R.WCMASS": "WCMA", ".R.SEMASS": "SEMA", ".R.NEMASS&BOST": "NEMA"}


def _log(con, check, target, passed, detail):
    con.execute("INSERT INTO quality_log VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), check, target,
                 int(passed), detail))
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {check} ({target}): {detail}")
    return passed


def validate():
    con = connect()
    ok = True
    zd = pd.read_sql("SELECT * FROM raw_zone_demand", con, parse_dates=["ts"])

    # 1. Zone magnitude ranking (label-swap detector)
    means = zd.groupby("zone")["rt_load_mw"].mean().sort_values(ascending=False)
    ranking_ok = len(means) >= 8 and means.index[0] == "CT" and means.index[-1] == "VT"
    ok &= _log(con, "zone_ranking", "raw_zone_demand", ranking_ok,
               f"largest={means.index[0]}, smallest={means.index[-1]}")

    # 2. DA vs RT agreement — blocking only for MA zones (what our products
    # depend on); small outer zones (ME, RI) run looser DA-RT coupling.
    for zone, g in zd.dropna(subset=["da_load_mw", "rt_load_mw"]).groupby("zone"):
        r = g["da_load_mw"].corr(g["rt_load_mw"])
        passed = r > 0.90 or zone not in ("NEMA", "SEMA", "WCMA")
        ok &= _log(con, "da_rt_corr", zone, passed, f"r={r:.3f}")

    # 3. Hourly completeness per zone-day (blocking only if widespread)
    zd["date"] = zd["ts"].dt.date
    counts = zd.groupby(["zone", "date"]).size()
    short_days = int((counts < 23).sum())
    ok &= _log(con, "day_completeness", "raw_zone_demand", short_days <= len(counts) * 0.02,
               f"{short_days} short zone-days of {len(counts)}")

    # 4. Town RNL: region consistent with reference mapping; values positive
    rnl = pd.read_sql("SELECT * FROM raw_town_rnl", con)
    ref = pd.read_csv(PROJECT_ROOT / "reference" / "town_zone_mapping.csv")
    rnl["zone"] = rnl["region"].map(REGION_TO_ZONE)
    merged = rnl.merge(ref[["Town", "Zone"]], left_on="town", right_on="Town")
    mismatch = merged[merged["zone"] != merged["Zone"]]
    ok &= _log(con, "rnl_region_match", "raw_town_rnl", mismatch.empty,
               f"{len(mismatch)} mismatched town-months")
    # Zero RNL is legitimate (town generation can net out load at the peak
    # hour, e.g. Princeton wind); only negative values are invalid.
    zeros = int((rnl["rnl_mw"] == 0).sum())
    ok &= _log(con, "rnl_non_negative", "raw_town_rnl", (rnl["rnl_mw"] >= 0).all(),
               f"min={rnl['rnl_mw'].min():.3f} MW; {zeros} zero town-months (own generation)")

    # Gross-error guard: first-publication files have contained 15x data-entry
    # errors (Groton 2024-06: 199.8 MW vs 13.5 restated). Flag any town-month
    # more than 4x the town's own median.
    med = rnl.groupby("town")["rnl_mw"].transform("median")
    spikes = rnl[(med > 0) & (rnl["rnl_mw"] > 4 * med)]
    ok &= _log(con, "rnl_spike_guard", "raw_town_rnl", spikes.empty,
               "none" if spikes.empty else
               "; ".join(f"{r.town} {r.month}={r.rnl_mw:.1f}MW"
                         for r in spikes.itertuples()))

    # Promote
    if ok:
        con.execute("DELETE FROM clean_zone_demand")
        con.execute("INSERT INTO clean_zone_demand "
                    "SELECT ts, zone, da_load_mw, rt_load_mw FROM raw_zone_demand")
        con.execute("DELETE FROM clean_town_rnl")
        rows = [(r.town, r.month, REGION_TO_ZONE.get(r.region), r.rnl_mw)
                for r in rnl.itertuples()]
        con.executemany("INSERT INTO clean_town_rnl VALUES (?, ?, ?, ?)", rows)
        con.commit()
        print("validate: all blocking checks passed -> promoted to clean_*")
    else:
        print("validate: FAILURES above -> clean_* NOT updated (quarantined)")
    con.close()
    return ok
