"""Parser and rules tests — the cheap insurance against silent API drift
(the failure mode that killed the 2025 pipeline for months unnoticed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pandas as pd
import pytest

from ingest_town_load import match_town, parse_report
from peakwatch.isone import LOCATION_TO_ZONE


MRNL_SAMPLE = """,ISO-NE Public,,,,,,,,,,
C,Monthly Regional Network Load Report,,,,,,,,,,
H,Customer ID,Customer Name,DUNS Number,DUNS Name,Local Network,Regional Network Load ID,Regional Network Load Name,Monthly Regional Network Load Value,Monthly Regional Pool Network Load Value,Reliability Region ID,Reliability Region Name
H,Number,String,String,String,String,Number,String,MW,MW,Number,String
D,72,Hull Municipal Lighting Plant,13-661-7156,Hull Municipal Lighting Plant,BE   ,6,Hull,13.7,23427.224,9006,.R.SEMASS
D,99,Some NH Utility,00-000-0000,Groton NH Coop,NEP,7,Groton,5.0,23427.224,9002,.R.NEWHAMPSHIRE
D,101,West Boylston Municipal,00-000-0001,West Boylston MLP,NEP,8,W. Boylston,10.8,23427.224,9007,.R.WCMASS
D,102,Boylston Municipal,00-000-0002,Boylston MLP,NEP,9,Boylston,8.5,23427.224,9007,.R.WCMASS
D,103,Princeton Municipal,00-000-0003,Princeton MLD,NEP,10,Princeton,0.0,23427.224,9007,.R.WCMASS
"""


def test_parse_report_extracts_ma_towns_only():
    rows = parse_report(MRNL_SAMPLE, "202406")
    towns = {r["Town"] for r in rows}
    assert "Hull" in towns
    assert "Groton" not in towns, "NH Groton must be excluded by region filter"


def test_boylston_west_boylston_no_collision():
    rows = parse_report(MRNL_SAMPLE, "202406")
    by_town = {r["Town"]: r["RNL_MW"] for r in rows}
    assert by_town["West Boylston"] == 10.8
    assert by_town["Boylston"] == 8.5


def test_zero_rnl_is_kept_not_dropped():
    rows = parse_report(MRNL_SAMPLE, "202406")
    princeton = [r for r in rows if r["Town"] == "Princeton"]
    assert princeton and princeton[0]["RNL_MW"] == 0.0


def test_month_formatting():
    rows = parse_report(MRNL_SAMPLE, "202406")
    assert all(r["Month"] == "2024-06" for r in rows)


def test_match_town_guards():
    assert match_town("W. Boylston", "") == "West Boylston"
    assert match_town("Boylston", "") == "Boylston"
    assert match_town("South Hadley Electric", "") == "South Hadley"
    assert match_town("Braintree", "") is None


def test_zone_map_is_the_verified_one():
    # Guard against regression to the 2025 mislabeling (4001 is MAINE, not Boston)
    assert LOCATION_TO_ZONE[4001] == "ME"
    assert LOCATION_TO_ZONE[4004] == "CT"
    assert LOCATION_TO_ZONE[4008] == "NEMA"
    assert len(LOCATION_TO_ZONE) == 8


COMBINED_DEMAND_JSON = {
    "CombinedHourlyDemands": {
        "CombinedHourlyDemand": [
            {"BeginDate": "2024-01-01T00:00:00.000-05:00",
             "Location": {"$": ".Z.CONNECTICUT", "@LocId": "4004"},
             "DaLoad": 2801, "RtLoad": 2660.52},
            {"BeginDate": "2024-01-01T01:00:00.000-05:00",
             "Location": {"$": ".Z.CONNECTICUT", "@LocId": "4004"},
             "DaLoad": 2700},  # RtLoad missing: unsettled hour
        ]
    }
}


RT_CURRENT_JSON = {
    "HourlyRtDemands": {
        "HourlyRtDemand": [
            {"BeginDate": "2026-07-20T23:00:00.000-04:00",
             "Location": {"$": ".Z.WCMASS", "@LocId": "4007"},
             "Load": 1785.615},
            {"BeginDate": "2026-07-20T23:00:00.000-04:00",
             "Location": {"$": ".Z.MAINE", "@LocId": "4001"},
             "Load": 1162.86},
        ]
    }
}


def test_realtime_hourly_current_parse(monkeypatch):
    # the endpoint whose silent format change killed the 2025 pipeline
    from peakwatch.isone import ISONEClient
    client = ISONEClient(user="x", password="y")
    monkeypatch.setattr(client, "_get", lambda ep: RT_CURRENT_JSON)
    df = client.realtime_hourly_demand_current()
    assert set(df["Zone"]) == {"WCMA", "ME"}
    assert df[df["Zone"] == "WCMA"]["RtLoad_MW"].iloc[0] == 1785.615


def test_client_parses_missing_rtload(monkeypatch):
    from peakwatch.isone import ISONEClient
    client = ISONEClient(user="x", password="y")
    monkeypatch.setattr(client, "_get", lambda ep: COMBINED_DEMAND_JSON)
    df = client.combined_hourly_demand("20240101", 4004)
    assert len(df) == 2
    assert df["Zone"].eq("CT").all()
    assert pd.isna(df["RtLoad_MW"].iloc[1])
    assert df["DaLoad_MW"].iloc[0] == 2801
