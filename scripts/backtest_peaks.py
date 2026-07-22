"""Backtest the peak-day alert rule across zones and thresholds.

Prints a per-zone summary and writes detail CSVs to data/reports/peakwatch/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from peakwatch.config import DATA_DIR
from peakwatch.isone import MA_ZONES
from peakwatch.peaks import load_zone_demand, daily_summary, monthly_peaks, backtest_rule

REPORT_DIR = DATA_DIR / "reports" / "peakwatch"


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_zone_demand()
    print(f"Loaded {len(df):,} zone-hours "
          f"({df['Timestamp'].min()} -> {df['Timestamp'].max()})\n")

    targets = [(None, "SYSTEM")] + [(z, z) for z in MA_ZONES]
    for zone, label in targets:
        daily = daily_summary(df, zone)
        peaks = monthly_peaks(daily)
        print(f"=== {label} ===")
        print("Monthly peaks (last 6):")
        print(peaks.tail(6).to_string())
        for threshold in (0.95, 0.97, 0.99):
            r = backtest_rule(daily, label, threshold)
            print(f"  threshold={threshold:.2f}: hit {r.hits}/{r.months} monthly peaks, "
                  f"avg {r.alert_days_per_month:.1f} alert-days/month")
        r = backtest_rule(daily, label, 0.97)
        r.detail.to_csv(REPORT_DIR / f"backtest_{label}.csv", index=False)
        print()


if __name__ == "__main__":
    main()
