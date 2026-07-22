"""How much do settlement RNL values move between first publication and
the -drp restatement? Bounds the noise floor for predict-before-publish
scoring: model accuracy chasing below restatement drift is chasing noise.

Downloads the missing counterpart file (original vs -drp) for months where
we only cached one version. Static CDN, no auth, gentle pace.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import requests

from ingest_town_load import RAW_DIR, parse_report

BASE = "https://www.iso-ne.com/static-assets/documents"


def counterpart_url(fname, containers=range(100008, 100048)):
    m = re.match(r"ww-network-load-iso-(\d{6})(-drp)?\.csv", fname)
    ym, is_drp = m.group(1), bool(m.group(2))
    want = f"ww-network-load-iso-{ym}{'' if is_drp else '-drp'}.csv"
    for c in containers:
        url = f"{BASE}/{c}/{want}"
        try:
            if requests.head(url, timeout=15).status_code == 200:
                return url, want
        except requests.RequestException:
            pass
    return None, want


def main():
    pairs = []
    files = sorted(RAW_DIR.glob("ww-network-load-iso-2024*.csv")) + \
        sorted(RAW_DIR.glob("ww-network-load-iso-2025*.csv"))
    for f in files[:14]:
        ym = re.search(r"(\d{6})", f.name).group(1)
        other = list(RAW_DIR.glob(f"*{ym}*"))
        if len(other) >= 2:
            pairs.append(ym)
            continue
        url, want = counterpart_url(f.name)
        if url:
            (RAW_DIR / want).write_text(requests.get(url, timeout=30).text,
                                        encoding="utf-8")
            pairs.append(ym)
            time.sleep(0.5)

    rows = []
    for ym in pairs:
        orig = RAW_DIR / f"ww-network-load-iso-{ym}.csv"
        drp = RAW_DIR / f"ww-network-load-iso-{ym}-drp.csv"
        if not (orig.exists() and drp.exists()):
            continue
        a = pd.DataFrame(parse_report(orig.read_text(encoding="utf-8",
                                                     errors="replace"), ym))
        b = pd.DataFrame(parse_report(drp.read_text(encoding="utf-8",
                                                    errors="replace"), ym))
        m = a.groupby("Town")["RNL_MW"].sum().to_frame("first").join(
            b.groupby("Town")["RNL_MW"].sum().to_frame("restated"), how="inner")
        m["ym"] = ym
        rows.append(m)

    if not rows:
        print("no original/restated pairs available")
        return
    d = pd.concat(rows)
    d = d[d["first"] > 0]
    d["drift_pct"] = 100 * (d["restated"] - d["first"]).abs() / d["first"]
    print(f"pairs analyzed: {d['ym'].nunique()} months x "
          f"{d.index.nunique()} towns = {len(d)} town-months")
    print(f"\nrestatement drift |restated - first| / first:")
    print(f"  median: {d['drift_pct'].median():.2f}%   "
          f"mean: {d['drift_pct'].mean():.2f}%   "
          f"p90: {d['drift_pct'].quantile(0.9):.2f}%   "
          f"max: {d['drift_pct'].max():.2f}%")
    worst = d.sort_values("drift_pct", ascending=False).head(5)
    print("\nlargest moves:")
    print(worst[["ym", "first", "restated", "drift_pct"]].round(2).to_string())


if __name__ == "__main__":
    main()
