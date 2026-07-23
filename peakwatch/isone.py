"""ISO-NE Web Services client — the one source of truth for zone identifiers.

Location IDs verified against /locations.json on 2026-07-22. The legacy
dataset (C:\\Project ISO) used incorrect labels; do not reuse them.
"""
import time
import random

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

from .config import ISONE_API_USER, ISONE_API_PASS, ISONE_BASE_URL

# LocationID -> short zone code used throughout this project
LOCATION_TO_ZONE = {
    4001: "ME",
    4002: "NH",
    4003: "VT",
    4004: "CT",
    4005: "RI",
    4006: "SEMA",   # .Z.SEMASS
    4007: "WCMA",   # .Z.WCMASS
    4008: "NEMA",   # .Z.NEMASSBOST (includes Boston)
}
ZONE_TO_LOCATION = {v: k for k, v in LOCATION_TO_ZONE.items()}
MA_ZONES = ["NEMA", "SEMA", "WCMA"]


class ISONEClient:
    def __init__(self, user=None, password=None):
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(user or ISONE_API_USER, password or ISONE_API_PASS)
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, endpoint, retries=6):
        url = f"{ISONE_BASE_URL}/{endpoint}"
        for attempt in range(retries):
            try:
                r = self.session.get(url, timeout=60)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 429:
                    # ISO-NE rate limit: wait out the penalty window
                    time.sleep(60 * (attempt + 1))
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(2 ** attempt + random.random())
                    continue
                r.raise_for_status()
            except requests.RequestException:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt + random.random())
        raise RuntimeError(f"Failed after {retries} attempts: {endpoint}")

    def combined_hourly_demand(self, day: str, location_id: int) -> pd.DataFrame:
        """One day of hourly demand for one load zone.

        Returns columns: Timestamp (UTC), LocationID, Zone, DaLoad_MW, RtLoad_MW.
        RtLoad is missing for future/incomplete hours.
        """
        data = self._get(f"combinedhourlydemand/day/{day}/location/{location_id}.json")
        rows = data.get("CombinedHourlyDemands", {}).get("CombinedHourlyDemand", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["Timestamp"] = pd.to_datetime(df["BeginDate"], utc=True, errors="coerce")
        df["DaLoad_MW"] = pd.to_numeric(df.get("DaLoad"), errors="coerce")
        df["RtLoad_MW"] = pd.to_numeric(df.get("RtLoad"), errors="coerce")
        df["LocationID"] = location_id
        df["Zone"] = LOCATION_TO_ZONE.get(location_id)
        return df[["Timestamp", "LocationID", "Zone", "DaLoad_MW", "RtLoad_MW"]].dropna(
            subset=["Timestamp"]
        )

    def realtime_hourly_demand_current(self) -> pd.DataFrame:
        """Latest published preliminary RT hourly demand, all zones.
        Note: the public feed lags ~2 days. Format re-verified 2026-07
        (the 2025 pipeline died on a silent format change here)."""
        data = self._get("realtimehourlydemand/current.json")
        rows = (data.get("HourlyRtDemands", {}) or {}).get("HourlyRtDemand", [])
        out = []
        for r in rows:
            loc = r.get("Location", {})
            lid = int(loc.get("@LocId", 0)) if isinstance(loc, dict) else 0
            out.append({"Timestamp": pd.to_datetime(r.get("BeginDate")),
                        "Zone": LOCATION_TO_ZONE.get(lid),
                        "RtLoad_MW": r.get("Load")})
        return pd.DataFrame(out).dropna(subset=["Zone"])

    def five_minute_system_load_current(self) -> dict:
        data = self._get("fiveminutesystemload/current.json")
        loads = data.get("FiveMinSystemLoad", [])
        if not loads:
            return {}
        latest = loads[-1]
        return {
            "load_mw": float(latest.get("LoadMw", 0)),
            "native_load_mw": float(latest.get("NativeLoad", 0)),
            "btm_pv_mw": float(latest.get("SystemLoadBtmPv", 0)),
            "timestamp": pd.to_datetime(latest.get("BeginDate")),
        }
