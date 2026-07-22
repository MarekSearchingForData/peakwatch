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
