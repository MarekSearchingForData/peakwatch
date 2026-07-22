"""Collectors: move source data (already fetched to disk by ingest scripts)
into the raw_* tables. Idempotent upserts; safe to run mid-backfill."""
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from .config import DATA_DIR, TOWNS
from .store import connect

# Vertical-slice towns (see allocator.SLICE_TOWNS); full list after review
WEATHER_TOWNS = ["Chicopee", "Holyoke", "Princeton"]


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


def load_openmeteo(con, towns=WEATHER_TOWNS):
    """Hourly temp / solar radiation (GHI) / wind / cloud / humidity from the
    free Open-Meteo archive. Legacy variable names — the archive API rejects
    the newer snake_case aliases."""
    coords = {t: (lat, lon) for t, lat, lon in TOWNS}
    total = 0
    for town in towns:
        lat, lon = coords[town]
        url = ("https://archive-api.open-meteo.com/v1/archive"
               f"?latitude={lat}&longitude={lon}"
               "&start_date=2024-01-01&end_date=" + date.today().isoformat() +
               "&hourly=temperature_2m,shortwave_radiation,windspeed_10m,"
               "cloudcover,relativehumidity_2m&timezone=UTC")
        h = requests.get(url, timeout=60).json()["hourly"]
        rows = list(zip([town] * len(h["time"]),
                        [t + ":00+00:00" for t in h["time"]],
                        h["temperature_2m"], h["shortwave_radiation"],
                        h["windspeed_10m"], h["cloudcover"],
                        h["relativehumidity_2m"]))
        con.executemany(
            "INSERT INTO raw_weather VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(town, ts) DO UPDATE SET temp_c=excluded.temp_c, "
            "ghi_wm2=excluded.ghi_wm2, wind_kmh=excluded.wind_kmh, "
            "cloud_pct=excluded.cloud_pct, rh_pct=excluded.rh_pct", rows)
        total += len(rows)
    con.commit()
    return total


def load_portfolio(con):
    """Town generation-asset reference (compiled from EIA 860/861, MassCEC)."""
    path = Path(__file__).resolve().parent.parent / "reference" / "town_portfolio.csv"
    if not path.exists():
        return 0
    df = pd.read_csv(path)
    rows = [(r.Town, r.Tech, r.Nameplate_MW, 1 if str(r.Type).lower() == "btm" else 0,
             r.Year, r.Confidence, r.Source) for r in df.itertuples()]
    con.executemany(
        "INSERT INTO town_portfolio VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(town, tech, btm) DO UPDATE SET "
        "nameplate_mw=excluded.nameplate_mw, year=excluded.year, "
        "confidence=excluded.confidence, source=excluded.source", rows)
    con.commit()
    return len(rows)


def refresh():
    con = connect()
    n1 = load_zone_demand(con)
    n2 = load_town_rnl(con)
    n3 = load_openmeteo(con)
    n4 = load_portfolio(con)
    print(f"refresh: {n1:,} zone-hours, {n2} town-months, "
          f"{n3:,} weather-hours, {n4} portfolio assets upserted into raw_*")
    con.close()
