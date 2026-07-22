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
               "&start_date=2022-01-01&end_date=" + date.today().isoformat() +
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
             None if pd.isna(r.Year) else int(r.Year), r.Status, r.Confidence,
             r.Source) for r in df.itertuples()]
    con.executemany(
        "INSERT INTO town_portfolio VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(town, tech, btm) DO UPDATE SET "
        "nameplate_mw=excluded.nameplate_mw, year=excluded.year, "
        "status=excluded.status, confidence=excluded.confidence, "
        "source=excluded.source", rows)
    con.commit()
    return len(rows)


def load_class_mix(con):
    """EIA-861 sales by customer class (6 long-form utilities have full
    breakdowns; 14 short-form filers have totals only — their weights get
    initialized from archetype towns instead)."""
    path = Path(__file__).resolve().parent.parent / "reference" / "town_class_mix.csv"
    if not path.exists():
        return 0
    df = pd.read_csv(path)
    rows = [(r.Town, r.Year,
             None if pd.isna(r.Res_MWh) else r.Res_MWh,
             None if pd.isna(r.Com_MWh) else r.Com_MWh,
             None if pd.isna(r.Ind_MWh) else r.Ind_MWh,
             None if pd.isna(r.Other_MWh) else r.Other_MWh,
             r.Total_MWh,
             None if pd.isna(r.Res_Customers) else int(r.Res_Customers),
             None if pd.isna(r.Com_Customers) else int(r.Com_Customers),
             None if pd.isna(r.Ind_Customers) else int(r.Ind_Customers))
            for r in df.itertuples()]
    con.executemany(
        "INSERT OR REPLACE INTO town_class_mix VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows)
    con.commit()
    return len(rows)


def load_openmeteo_forecast(con, towns=WEATHER_TOWNS):
    """7-day hourly forecast — SAME variables and source family as the
    training archive, so live features match training features."""
    coords = {t: (lat, lon) for t, lat, lon in TOWNS}
    fetched = pd.Timestamp.utcnow().isoformat()
    total = 0
    for town in towns:
        lat, lon = coords[town]
        url = ("https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat}&longitude={lon}&forecast_days=7"
               "&hourly=temperature_2m,shortwave_radiation,windspeed_10m,"
               "cloudcover&timezone=UTC")
        h = requests.get(url, timeout=60).json()["hourly"]
        rows = list(zip([town] * len(h["time"]),
                        [t + ":00+00:00" for t in h["time"]],
                        h["temperature_2m"], h["shortwave_radiation"],
                        h["windspeed_10m"], h["cloudcover"],
                        [fetched] * len(h["time"])))
        con.executemany(
            "INSERT INTO raw_weather_fcst VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(town, ts) DO UPDATE SET temp_c=excluded.temp_c, "
            "ghi_wm2=excluded.ghi_wm2, wind_kmh=excluded.wind_kmh, "
            "cloud_pct=excluded.cloud_pct, fetched_at=excluded.fetched_at", rows)
        total += len(rows)
    con.commit()
    return total


def load_isone_forecast(con, days_back=2, days_fwd=3):
    """ISO-NE's own hourly load forecast (their meteorologists' consensus):
    a feature, and the benchmark our zone forecast must beat."""
    from .isone import ISONEClient
    client = ISONEClient()
    total = 0
    for delta in range(-days_back, days_fwd + 1):
        d = (date.today() + pd.Timedelta(days=delta)).strftime("%Y%m%d")
        try:
            data = client._get(f"hourlyloadforecast/day/{d}.json")
        except Exception:
            continue
        recs = (data.get("HourlyLoadForecasts", {}) or {}).get(
            "HourlyLoadForecast", []) or data.get("HourlyLoadForecast", []) or []
        rows = [(r["BeginDate"], r["CreationDate"], r.get("LoadMw"),
                 r.get("NetLoadMw")) for r in recs]
        con.executemany(
            "INSERT OR REPLACE INTO raw_isone_fcst VALUES (?, ?, ?, ?)", rows)
        total += len(rows)
    con.commit()
    return total


def refresh():
    from . import calendar_features
    con = connect()
    n1 = load_zone_demand(con)
    n2 = load_town_rnl(con)
    n3 = load_openmeteo(con)
    n4 = load_portfolio(con)
    n5 = load_openmeteo_forecast(con)
    n6 = load_isone_forecast(con)
    n8 = load_class_mix(con)
    con.close()
    n7 = calendar_features.build()
    print(f"refresh: {n1:,} zone-hours, {n2} town-months, {n3:,} weather-hours, "
          f"{n4} portfolio assets, {n5} fcst-hours, {n6} ISO-fcst-hours, "
          f"{n7} calendar days, {n8} class-mix rows upserted")
