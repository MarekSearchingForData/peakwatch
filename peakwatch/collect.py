"""Collectors: move source data (already fetched to disk by ingest scripts)
into the raw_* tables. Idempotent upserts; safe to run mid-backfill."""
import pandas as pd

from .config import DATA_DIR
from .store import connect


def load_zone_demand(con):
    files = sorted((DATA_DIR / "raw" / "load_v2").glob("*.csv"))
    if not files:
        return 0
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    rows = [(r.Timestamp, r.Zone, r.DaLoad_MW, r.RtLoad_MW)
            for r in df.itertuples()]
    con.executemany(
        "INSERT INTO raw_zone_demand (ts, zone, da_load_mw, rt_load_mw) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(ts, zone) DO UPDATE SET "
        "da_load_mw=excluded.da_load_mw, rt_load_mw=excluded.rt_load_mw", rows)
    con.commit()
    return len(rows)


def load_town_rnl(con):
    path = DATA_DIR / "cleaned" / "town_load" / "town_monthly_rnl.csv"
    if not path.exists():
        return 0
    df = pd.read_csv(path)
    rows = [(r.Town, r.Month, r.Region, r.RNL_MW, r.PoolTotal_MW)
            for r in df.itertuples()]
    con.executemany(
        "INSERT INTO raw_town_rnl (town, month, region, rnl_mw, pool_total_mw) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(town, month) DO UPDATE SET "
        "rnl_mw=excluded.rnl_mw, pool_total_mw=excluded.pool_total_mw", rows)
    con.commit()
    return len(rows)


def refresh():
    con = connect()
    n1 = load_zone_demand(con)
    n2 = load_town_rnl(con)
    print(f"refresh: {n1:,} zone-hours, {n2} town-months upserted into raw_*")
    con.close()
