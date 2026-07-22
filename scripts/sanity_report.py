"""Data sanity report — catches the class of bug that corrupted the 2025 dataset.

Checks, per zone:
  1. Magnitude ranking (CT must be the largest New England zone, VT smallest —
     if not, labels are wrong again).
  2. Day-ahead vs actual load: correlation and mean bias (should be r > 0.95).
  3. Coverage: missing days and partially-settled recent days.
  4. Peak-hour distribution by season (summer peaks ~17:00-19:00 local,
     winter ~17:00-19:00; anything centered at 3 AM means timezone bugs).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from peakwatch.peaks import load_zone_demand, daily_summary

EXPECT_LARGEST, EXPECT_SMALLEST = "CT", "VT"


def main():
    df = load_zone_demand()
    print(f"Rows: {len(df):,}  span {df['Timestamp'].min()} -> {df['Timestamp'].max()}")

    # 1. Magnitude ranking
    means = df.groupby("Zone")["RtLoad_MW"].mean().sort_values(ascending=False)
    print("\nMean RT load by zone (MW):")
    print(means.round(0).to_string())
    ok = means.index[0] == EXPECT_LARGEST and means.index[-1] == EXPECT_SMALLEST
    print(f"CHECK ranking: {'PASS' if ok else 'FAIL — zone labels suspect!'}")

    # 2. DA vs RT agreement
    print("\nDay-ahead vs actual (per zone):")
    for zone, g in df.dropna(subset=["DaLoad_MW", "RtLoad_MW"]).groupby("Zone"):
        r = g["DaLoad_MW"].corr(g["RtLoad_MW"])
        bias = (g["DaLoad_MW"] - g["RtLoad_MW"]).mean()
        flag = "PASS" if r > 0.95 else "WARN"
        print(f"  {zone}: r={r:.3f}  mean bias={bias:+.0f} MW  {flag}")

    # 3. Coverage
    daily = daily_summary(df)
    expected = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    missing = expected.difference(daily.index)
    unsettled = daily[daily["rt_max"].isna()]
    print(f"\nCoverage: {len(daily)} days, {len(missing)} missing, "
          f"{len(unsettled)} without settled RT yet")
    if len(missing):
        print("  missing:", [str(d.date()) for d in missing[:10]])

    # 4. Peak-hour distribution
    daily["season"] = daily.index.month.map(
        lambda m: "summer" if m in (6, 7, 8) else "winter" if m in (12, 1, 2) else "shoulder")
    print("\nSystem daily peak hour (local) by season — median [25%, 75%]:")
    for season, g in daily.dropna(subset=["rt_peak_hour"]).groupby("season"):
        q = g["rt_peak_hour"].quantile([0.25, 0.5, 0.75]).astype(int)
        print(f"  {season}: {q[0.5]}:00  [{q[0.25]}:00, {q[0.75]}:00]")


if __name__ == "__main__":
    main()
