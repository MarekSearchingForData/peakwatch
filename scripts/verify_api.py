"""Verify ISO-NE API access and resolve the authoritative location-ID -> zone mapping.

Three conflicting mappings exist in the legacy code; this queries the API's
/locations endpoint to settle it, then cross-checks one day of demand data
against the legacy CSVs so we can relabel historical columns correctly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from requests.auth import HTTPBasicAuth

from peakwatch.config import ISONE_API_USER, ISONE_API_PASS, ISONE_BASE_URL

AUTH = HTTPBasicAuth(ISONE_API_USER, ISONE_API_PASS)
HEADERS = {"Accept": "application/json"}


def get(endpoint):
    r = requests.get(f"{ISONE_BASE_URL}/{endpoint}", auth=AUTH, headers=HEADERS, timeout=60)
    print(f"GET {endpoint} -> HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:300])
        return None
    return r.json()


def main():
    print(f"User: {ISONE_API_USER}")

    # 1. Authoritative location list
    data = get("locations.json")
    if data is None:
        print("FATAL: /locations failed — credentials may be stale.")
        return
    locs = data.get("Locations", {})
    if isinstance(locs, dict):
        locs = locs.get("Location", [])
    zone_rows = [l for l in locs if isinstance(l, dict)]
    print(f"\n{len(zone_rows)} locations returned. IDs 4000-4010:")
    for l in zone_rows:
        lid = l.get("@LocId") or l.get("LocId") or l.get("LocationId")
        name = l.get("$") or l.get("LocationName") or l.get("Name") or str(l)
        try:
            lid_int = int(lid)
        except (TypeError, ValueError):
            continue
        if 4000 <= lid_int <= 4010:
            print(f"  {lid_int}: {name}")

    # 2. Cross-check one day of demand for two IDs against legacy CSVs
    for loc_id in (4001, 4004, 4008):
        d = get(f"combinedhourlydemand/day/20240101/location/{loc_id}.json")
        if not d:
            continue
        rows = d.get("CombinedHourlyDemands", {}).get("CombinedHourlyDemand", [])
        if rows:
            first = rows[0]
            print(f"  loc {loc_id} first hour: BeginDate={first.get('BeginDate')} "
                  f"DaLoad={first.get('DaLoad')} RtLoad={first.get('RtLoad')} "
                  f"keys={sorted(first.keys())}")


if __name__ == "__main__":
    main()
