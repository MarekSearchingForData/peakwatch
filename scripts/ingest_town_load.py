"""Pull real per-town monthly load from ISO-NE's Monthly Regional Network Load
reports (settlement-grade: each MLP's MW at the monthly transmission peak).

Files live under static-assets/documents/<container>/ww-network-load-iso-<YYYYMM>[-drp].csv
where <container> is a sequential publication folder we discover by probing.
'-drp' versions are post-reconciliation restatements and are preferred.

Output:
  raw/town_load/       one CSV per month, as published
  cleaned/town_load/town_monthly_rnl.csv   Town, Month, RNL_MW, Region, PoolTotal_MW
"""
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import requests

from peakwatch.config import DATA_DIR

RAW_DIR = DATA_DIR / "raw" / "town_load"
CLEAN_DIR = DATA_DIR / "cleaned" / "town_load"
BASE = "https://www.iso-ne.com/static-assets/documents"
CONTAINERS = range(100008, 100048)
MONTHS = [f"{y}{m:02d}" for y in (2022, 2023, 2024, 2025, 2026) for m in range(1, 13)][:54]  # 202201..202606

# RNL-name matching rules per town (lowercase substring; 'exclude' guards collisions)
TOWN_PATTERNS = {
    "Ashburnham": {"any": ["ashburnham"]},
    "West Boylston": {"any": ["west boylston", "w. boylston", "w boylston"]},
    "Boylston": {"any": ["boylston"], "exclude": ["west", "w."]},
    "Chicopee": {"any": ["chicopee"]},
    "Groton": {"any": ["groton"]},
    "Holden": {"any": ["holden"]},
    "Holyoke": {"any": ["holyoke"]},
    "Hull": {"any": ["hull"]},
    "Ipswich": {"any": ["ipswich"]},
    "Mansfield": {"any": ["mansfield"]},
    "Marblehead": {"any": ["marblehead"]},
    "Paxton": {"any": ["paxton"]},
    "Peabody": {"any": ["peabody"]},
    "Princeton": {"any": ["princeton"]},
    "Russell": {"any": ["russell"]},
    "Shrewsbury": {"any": ["shrewsbury"]},
    "South Hadley": {"any": ["south hadley", "s. hadley"]},
    "Sterling": {"any": ["sterling"]},
    "Templeton": {"any": ["templeton"]},
    "Wakefield": {"any": ["wakefield"]},
}

session = requests.Session()


def discover(ym, hint=None):
    """Find the URL for a month's report; prefer restated (-drp) files.

    Two publication layouts: sequential containers (~100008+, 2024 onward)
    and dated folders documents/YYYY/MM/ (pre-2024, published 1-10 months
    after the data month).
    """
    candidates = []
    year, month = int(ym[:4]), int(ym[4:])
    if year >= 2024:
        containers = list(CONTAINERS)
        if hint:
            near = [c for c in range(hint - 2, hint + 8) if c in CONTAINERS]
            containers = near + [c for c in containers if c not in near]
        for suffix in ("-drp", ""):
            candidates += [(f"{BASE}/{c}/ww-network-load-iso-{ym}{suffix}.csv", c)
                           for c in containers]
    else:
        pub = [(year + (month + k - 1) // 12, (month + k - 1) % 12 + 1)
               for k in range(1, 11)]
        for suffix in ("-drp", ""):
            candidates += [(f"{BASE}/{py}/{pm:02d}/ww-network-load-iso-{ym}{suffix}.csv",
                            hint) for py, pm in pub]
    for url, c in candidates:
        try:
            if session.head(url, timeout=15).status_code == 200:
                return url, c
        except requests.RequestException:
            continue
    return None, None


def match_town(rnl_name, customer_name):
    text = f"{rnl_name} {customer_name}".lower()
    for town, rule in TOWN_PATTERNS.items():
        if any(p in text for p in rule["any"]):
            if not any(x in text for x in rule.get("exclude", [])):
                return town
    return None


def parse_report(content, ym):
    rows, header = [], None
    for rec in csv.reader(io.StringIO(content)):
        if not rec:
            continue
        if rec[0] == "H" and header is None:
            header = rec[1:]
        elif rec[0] == "D" and header:
            rows.append(dict(zip(header, rec[1:])))
    MA_REGIONS = {".R.WCMASS", ".R.SEMASS", ".R.NEMASS&BOST"}
    out = []
    for r in rows:
        if r.get("Reliability Region Name", "").strip() not in MA_REGIONS:
            continue  # e.g. Groton NH would otherwise collide with Groton MA
        town = match_town(r.get("Regional Network Load Name", ""),
                          r.get("Customer Name", ""))
        if town:
            out.append({
                "Town": town,
                "Month": f"{ym[:4]}-{ym[4:]}",
                "RNL_MW": float(r["Monthly Regional Network Load Value"] or 0),
                "Region": r.get("Reliability Region Name", "").strip(),
                "PoolTotal_MW": float(r["Monthly Regional Pool Network Load Value"] or 0),
                "RNL_Name": r.get("Regional Network Load Name", "").strip(),
            })
    return out


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    all_rows, hint = [], None
    for ym in MONTHS:
        cached = list(RAW_DIR.glob(f"ww-network-load-iso-{ym}*.csv"))
        if cached:
            content = cached[0].read_text(encoding="utf-8", errors="replace")
            print(f"{ym}: cached {cached[0].name}", flush=True)
        else:
            url, hint = discover(ym, hint)
            if not url:
                print(f"{ym}: NOT FOUND (may not be published yet)", flush=True)
                continue
            content = session.get(url, timeout=30).text
            (RAW_DIR / url.rsplit("/", 1)[1]).write_text(content, encoding="utf-8")
            print(f"{ym}: downloaded {url}", flush=True)
        month_rows = parse_report(content, ym)
        # a town can have multiple RNL lines (e.g. NYPA + NU slices) — sum them
        all_rows.extend(month_rows)

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("No data parsed.")
        return
    monthly = (df.groupby(["Town", "Month", "Region"], as_index=False)
                 .agg(RNL_MW=("RNL_MW", "sum"), PoolTotal_MW=("PoolTotal_MW", "first")))
    monthly.to_csv(CLEAN_DIR / "town_monthly_rnl.csv", index=False)
    print(f"\nWrote {CLEAN_DIR / 'town_monthly_rnl.csv'}: "
          f"{monthly['Town'].nunique()} towns x {monthly['Month'].nunique()} months")
    print("\nTowns found:", sorted(monthly["Town"].unique()))
    missing = set(TOWN_PATTERNS) - set(monthly["Town"].unique())
    if missing:
        print("Towns NOT matched:", sorted(missing))


if __name__ == "__main__":
    main()
