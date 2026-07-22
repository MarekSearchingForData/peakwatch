"""SQLite store — the only interface between modules (see ARCHITECTURE.md)."""
import sqlite3
from pathlib import Path

from .config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "peakwatch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_zone_demand (
    ts TEXT NOT NULL, zone TEXT NOT NULL,
    da_load_mw REAL, rt_load_mw REAL,
    PRIMARY KEY (ts, zone)
);
CREATE TABLE IF NOT EXISTS clean_zone_demand (
    ts TEXT NOT NULL, zone TEXT NOT NULL,
    da_load_mw REAL, rt_load_mw REAL,
    PRIMARY KEY (ts, zone)
);
CREATE TABLE IF NOT EXISTS raw_town_rnl (
    town TEXT NOT NULL, month TEXT NOT NULL,
    region TEXT, rnl_mw REAL, pool_total_mw REAL,
    PRIMARY KEY (town, month)
);
CREATE TABLE IF NOT EXISTS clean_town_rnl (
    town TEXT NOT NULL, month TEXT NOT NULL,
    zone TEXT, rnl_mw REAL,
    PRIMARY KEY (town, month)
);
CREATE TABLE IF NOT EXISTS raw_weather (
    town TEXT NOT NULL, ts TEXT NOT NULL,
    temp_c REAL, ghi_wm2 REAL, wind_kmh REAL, cloud_pct REAL, rh_pct REAL,
    PRIMARY KEY (town, ts)
);
CREATE TABLE IF NOT EXISTS town_portfolio (
    town TEXT NOT NULL, tech TEXT NOT NULL,
    nameplate_mw REAL, btm INTEGER, year INTEGER,
    status TEXT, confidence TEXT, source TEXT,
    PRIMARY KEY (town, tech, btm)
);
CREATE TABLE IF NOT EXISTS raw_isone_fcst (
    ts TEXT NOT NULL, created TEXT NOT NULL,
    load_mw REAL, net_load_mw REAL,
    PRIMARY KEY (ts, created)
);
CREATE TABLE IF NOT EXISTS raw_weather_fcst (
    town TEXT NOT NULL, ts TEXT NOT NULL,
    temp_c REAL, ghi_wm2 REAL, wind_kmh REAL, cloud_pct REAL,
    fetched_at TEXT,
    PRIMARY KEY (town, ts)
);
CREATE TABLE IF NOT EXISTS feature_calendar (
    date TEXT PRIMARY KEY, dow INTEGER, is_weekend INTEGER,
    is_holiday INTEGER, holiday_name TEXT, holiday_adjacent INTEGER,
    doy_sin REAL, doy_cos REAL, sunset_hour REAL
);
CREATE TABLE IF NOT EXISTS town_class_mix (
    town TEXT NOT NULL, year INTEGER,
    res_mwh REAL, com_mwh REAL, ind_mwh REAL, other_mwh REAL, total_mwh REAL,
    res_cust INTEGER, com_cust INTEGER, ind_cust INTEGER,
    PRIMARY KEY (town)
);
CREATE TABLE IF NOT EXISTS quality_log (
    run_at TEXT NOT NULL, check_name TEXT NOT NULL,
    target TEXT, passed INTEGER, detail TEXT
);
CREATE TABLE IF NOT EXISTS allocator_alpha (
    town TEXT NOT NULL, month TEXT NOT NULL,
    zone TEXT, alpha REAL, zone_peak_ts TEXT, zone_peak_mw REAL, rnl_mw REAL,
    PRIMARY KEY (town, month)
);
CREATE TABLE IF NOT EXISTS forecast_scorecard (
    run_at TEXT NOT NULL, model TEXT NOT NULL, target TEXT NOT NULL,
    period TEXT, metric TEXT, value REAL
);
"""


def connect():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con
