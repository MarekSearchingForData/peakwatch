"""Backfill / refresh ISO-NE hourly zone demand (DaLoad + RtLoad) into raw/load_v2.

Idempotent: skips days already on disk, except the trailing 3 days which are
re-fetched because RtLoad settles late. Run with no args to backfill
2024-01-01 -> today, then consolidate to cleaned/load/zone_demand_long.csv
plus wide RtLoad/DaLoad matrices.
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from threading import Lock, local

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from peakwatch.config import DATA_DIR
from peakwatch.isone import ISONEClient, LOCATION_TO_ZONE

RAW_DIR = DATA_DIR / "raw" / "load_v2"
CLEAN_DIR = DATA_DIR / "cleaned" / "load"
START = date(2024, 1, 1)
REFETCH_TRAILING_DAYS = 3
WORKERS = 6

_tls = local()


def _client():
    if not hasattr(_tls, "client"):
        _tls.client = ISONEClient()
    return _tls.client


def _fetch_one(ymd, loc_id, zone, path):
    df = _client().combined_hourly_demand(ymd, loc_id)
    if df.empty:
        return "empty"
    df.to_csv(path, index=False)
    return "ok"


def backfill():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    refetch_cutoff = today - timedelta(days=REFETCH_TRAILING_DAYS)

    work = []
    stats = {"ok": 0, "skip": 0, "empty": 0, "fail": 0}
    for d in pd.date_range(START, today, freq="D").date:
        ymd = d.strftime("%Y%m%d")
        for loc_id, zone in LOCATION_TO_ZONE.items():
            path = RAW_DIR / f"{ymd}_{zone}.csv"
            if path.exists() and d < refetch_cutoff:
                stats["skip"] += 1
            else:
                work.append((ymd, loc_id, zone, path))

    print(f"{len(work)} fetches queued, {stats['skip']} already on disk", flush=True)
    failures = []
    lock = Lock()
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_fetch_one, *w): w for w in work}
        for fut in as_completed(futures):
            ymd, _, zone, _ = futures[fut]
            try:
                stats[fut.result()] += 1
            except Exception as e:
                stats["fail"] += 1
                failures.append((ymd, zone, str(e)[:120]))
            with lock:
                done += 1
                if done % 500 == 0:
                    print(f"{done}/{len(work)} {stats}", flush=True)

    print(f"\nDone: {stats}")
    for f in failures[:20]:
        print("FAIL:", f)
    return stats


def consolidate():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        print("No raw files found.")
        return
    parts = [pd.read_csv(f, parse_dates=["Timestamp"]) for f in files]
    df = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["Timestamp", "Zone"])
    df = df.sort_values(["Timestamp", "Zone"])
    df.to_csv(CLEAN_DIR / "zone_demand_long.csv", index=False)

    for col, name in [("RtLoad_MW", "zone_demand_rt_wide.csv"),
                      ("DaLoad_MW", "zone_demand_da_wide.csv")]:
        wide = df.pivot_table(index="Timestamp", columns="Zone", values=col)
        wide.sort_index().to_csv(CLEAN_DIR / name)
        print(f"Wrote {CLEAN_DIR / name}  rows={len(wide)}  "
              f"span={wide.index.min()} -> {wide.index.max()}")


if __name__ == "__main__":
    if "--consolidate-only" not in sys.argv:
        backfill()
    consolidate()
