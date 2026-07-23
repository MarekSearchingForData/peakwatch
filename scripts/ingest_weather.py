"""Refresh weather data for all towns.

1. Meteostat hourly history (2023-01-01 -> today) into raw/weather_v2/.
   Full re-pull per town; cheap and avoids stale-file gaps.
2. NWS hourly forecast (api.weather.gov, free, no key) into raw/forecast_nws/.
   Used by the peak model for look-ahead features.
"""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import requests
from meteostat import Hourly, Point

from peakwatch.config import DATA_DIR, TOWNS

WEATHER_DIR = DATA_DIR / "raw" / "weather_v2"
FORECAST_DIR = DATA_DIR / "raw" / "forecast_nws"
START = datetime(2023, 1, 1)

import os

NWS_HEADERS = {"User-Agent":
               f"PeakWatch ({os.getenv('NWS_CONTACT', 'contact@example.com')})"}


def fetch_meteostat():
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    end = datetime.now()
    for town, lat, lon in TOWNS:
        try:
            df = Hourly(Point(lat, lon), START, end).fetch().reset_index()
            df.to_csv(WEATHER_DIR / f"{town}_meteostat_hourly.csv", index=False)
            print(f"meteostat OK {town}: {len(df)} rows "
                  f"({df['time'].min()} -> {df['time'].max()})", flush=True)
        except Exception as e:
            print(f"meteostat FAIL {town}: {e}", flush=True)


def fetch_nws_forecasts():
    FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    for town, lat, lon in TOWNS:
        try:
            meta = requests.get(f"https://api.weather.gov/points/{lat},{lon}",
                                headers=NWS_HEADERS, timeout=30).json()
            url = meta["properties"]["forecastHourly"]
            periods = requests.get(url, headers=NWS_HEADERS, timeout=30).json()[
                "properties"]["periods"]
            df = pd.json_normalize(periods)
            df["town"] = town
            df["fetched_at"] = pd.Timestamp.utcnow()
            df.to_csv(FORECAST_DIR / f"{town}_nws_hourly.csv", index=False)
            print(f"nws OK {town}: {len(df)} hours", flush=True)
            time.sleep(0.5)
        except Exception as e:
            print(f"nws FAIL {town}: {e}", flush=True)


if __name__ == "__main__":
    if "--forecast-only" not in sys.argv:
        fetch_meteostat()
    fetch_nws_forecasts()
