"""Feature ablation on the allocator slice: does each signal earn its place?

For each town, predict each month's settlement RNL leave-one-month-out under
progressively richer models and compare MAPE:

  M0  flat share:        alpha = mean(alpha of other months)
  M1  + temperature:     alpha ~ a + b*temp_at_peak_hour
  M2  + town signal:     M1 + wind (Princeton: wind turbines)
                         M1 + solar GHI (Holyoke: PV/hydro; Chicopee: control)

Small-n honesty: with few months, extra parameters can LOSE to M0 — LOO
punishes overfitting. A feature is adopted only when it wins here, and
verdicts are re-checked as the backfill adds months.
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .allocator import SLICE_TOWNS, SLICE_ZONE, _monthly_pool_peak_hours
from .store import connect

TOWN_SIGNAL = {"Princeton": "wind_kmh", "Holyoke": "ghi_wm2", "Chicopee": "ghi_wm2"}


def _loo_mape(y, X):
    """Leave-one-out MAPE of a least-squares linear model y ~ X (with bias)."""
    n = len(y)
    errs = []
    A = np.column_stack([np.ones(n), X]) if X is not None else np.ones((n, 1))
    for i in range(n):
        mask = np.arange(n) != i
        coef, *_ = np.linalg.lstsq(A[mask], y[mask], rcond=None)
        pred = A[i] @ coef
        errs.append(abs(pred - y[i]) / y[i] if y[i] else np.nan)
    return 100 * np.nanmean(errs)


def run():
    con = connect()
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl WHERE zone = ?", con,
                      params=[SLICE_ZONE])
    wx = pd.read_sql("SELECT * FROM raw_weather", con, parse_dates=["ts"])
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)

    peaks = _monthly_pool_peak_hours(zd)
    zone_at_peak = (zd[zd["zone"] == SLICE_ZONE].set_index("ts")["rt_load_mw"]
                    .reindex(peaks["ts"]).values)
    peaks = peaks.assign(zone_mw=zone_at_peak).dropna(subset=["zone_mw"])

    run_at = datetime.now(timezone.utc).isoformat()
    print(f"=== Feature ablation: {SLICE_ZONE}, months={len(peaks)} "
          f"({peaks.index.min()} -> {peaks.index.max()}) ===\n")
    rows = []
    for town in SLICE_TOWNS:
        t_rnl = rnl[rnl["town"] == town].set_index("month")["rnl_mw"]
        t_wx = wx[wx["town"] == town].set_index("ts")
        d = peaks.join(t_rnl, how="inner").dropna(subset=["rnl_mw"])
        if len(d) < 4:
            print(f"{town}: only {len(d)} usable months — skipping")
            continue
        feats = t_wx.reindex(d["ts"])
        y = (d["rnl_mw"] / d["zone_mw"]).values  # alpha

        m0 = _loo_mape(y, None)
        m1 = _loo_mape(y, feats[["temp_c"]].values)
        sig = TOWN_SIGNAL[town]
        m2 = _loo_mape(y, feats[["temp_c", sig]].values)
        best = min((m0, "M0 flat"), (m1, "M1 +temp"), (m2, f"M2 +{sig}"))
        rows.append({"Town": town, "M0 flat%": m0, "M1 +temp%": m1,
                     f"M2 +signal%": m2, "winner": best[1]})
        for name, val in [("M0", m0), ("M1", m1), ("M2", m2)]:
            con.execute("INSERT INTO forecast_scorecard VALUES (?, ?, ?, ?, ?, ?)",
                        (run_at, f"ablation_{name}", town,
                         f"{d.index.min()}..{d.index.max()}", "LOO_MAPE_pct", val))
    con.commit()
    print(pd.DataFrame(rows).round(2).to_string(index=False))
    print("\n(MAPE of predicting each month's settlement share, leave-one-out. "
          "Lower is better; a feature only earns adoption by winning here.)")
    con.close()


if __name__ == "__main__":
    run()
