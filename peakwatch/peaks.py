"""Peak identification and peak-day prediction.

v1 philosophy: transparent and auditable. The day-ahead predictor is ISO-NE's
own cleared day-ahead demand (DaLoad) — known every morning — compared against
the month-to-date actual maximum. Every backtest number can be traced by hand.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DATA_DIR

EASTERN = "America/New_York"


def load_zone_demand():
    """Long-format hourly demand from the store, with local-time helpers."""
    from .store import connect
    con = connect()
    df = pd.read_sql(
        "SELECT ts AS Timestamp, zone AS Zone, da_load_mw AS DaLoad_MW, "
        "rt_load_mw AS RtLoad_MW FROM clean_zone_demand", con)
    con.close()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True)
    df["Local"] = df["Timestamp"].dt.tz_convert(EASTERN)
    df["Date"] = df["Local"].dt.date
    df["Hour"] = df["Local"].dt.hour
    df["Month"] = df["Local"].dt.to_period("M")
    return df


def daily_summary(df, zone=None):
    """One row per day: DA/RT max and the hour of the RT max.

    zone=None aggregates all zones (system proxy = sum across the 8 zones).
    """
    if zone:
        d = df[df["Zone"] == zone].copy()
    else:
        d = (df.groupby(["Timestamp", "Local", "Date", "Hour", "Month"], as_index=False)
               [["DaLoad_MW", "RtLoad_MW"]].sum(min_count=1))
    grp = d.groupby("Date")
    out = pd.DataFrame({
        "da_max": grp["DaLoad_MW"].max(),
        "rt_max": grp["RtLoad_MW"].max(),
        "rt_hours": grp["RtLoad_MW"].count(),
    })
    peak_hour = d.loc[d.groupby("Date")["RtLoad_MW"].idxmax().dropna()]
    out["rt_peak_hour"] = peak_hour.set_index("Date")["Hour"]
    out.index = pd.to_datetime(out.index)
    out["month"] = out.index.to_period("M")
    return out


def monthly_peaks(daily):
    """Actual monthly coincident peak day/value from RT load."""
    complete = daily[daily["rt_hours"] >= 20]  # ignore partially-settled days
    idx = complete.groupby("month")["rt_max"].idxmax()
    peaks = complete.loc[idx, ["rt_max", "rt_peak_hour"]].copy()
    peaks["peak_day"] = idx.values
    peaks.index = complete.loc[idx, "month"].values
    return peaks


@dataclass
class BacktestResult:
    zone: str
    threshold: float
    months: int
    hits: int
    alert_days_per_month: float
    detail: pd.DataFrame

    @property
    def hit_rate(self):
        return self.hits / self.months if self.months else float("nan")


def backtest_rule(daily, zone_label, threshold=0.97):
    """Would 'alert when DA-forecast max >= threshold x running month max' have
    flagged each month's actual peak day?

    Uses only information available on the morning of each day:
    the DA cleared max for today and actual RT maxes from prior days.
    """
    daily = daily.sort_index()
    rows = []
    for month, m in daily.groupby("month"):
        if m["rt_max"].isna().all():
            continue
        peak_day = m["rt_max"].idxmax()
        running_max = 0.0
        for day, r in m.iterrows():
            alert = bool(r["da_max"] >= threshold * running_max) if running_max else True
            rows.append({"month": str(month), "day": day, "da_max": r["da_max"],
                         "rt_max": r["rt_max"], "alert": alert,
                         "is_peak_day": day == peak_day})
            if not np.isnan(r["rt_max"]):
                running_max = max(running_max, r["rt_max"])
    detail = pd.DataFrame(rows)
    # exclude the current (incomplete) month from scoring
    complete_months = [m for m, g in detail.groupby("month")
                       if g["rt_max"].notna().sum() >= 25]
    scored = detail[detail["month"].isin(complete_months)]
    per_month = scored.groupby("month").apply(
        lambda g: pd.Series({
            "hit": bool(g.loc[g["is_peak_day"], "alert"].any()),
            "alert_days": int(g["alert"].sum()),
        }), include_groups=False)
    return BacktestResult(
        zone=zone_label,
        threshold=threshold,
        months=len(per_month),
        hits=int(per_month["hit"].sum()),
        alert_days_per_month=float(per_month["alert_days"].mean()) if len(per_month) else float("nan"),
        detail=detail,
    )
