"""Champion/challenger model zoo on the allocator slice.

Every model predicts each month's settlement share leave-one-month-out;
every model is scored on every run; the champion per town is whichever
currently wins. Nothing is discarded — challengers keep getting re-scored
as the backfill adds months, so a feature that loses on 7 months can still
take the crown on 30.

Physics rationale for the solar features: cloud/GHI don't change gross
consumption much — they change how much behind-the-meter PV offsets it.
Low GHI at the peak hour -> PV underdelivers -> higher net load. Effect
should scale with a town's PV penetration (strong in Holyoke, weak in
Chicopee) — the zoo tests exactly that.
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .allocator import SLICE_TOWNS, SLICE_ZONE, _monthly_pool_peak_hours
from .store import connect

SEASON = {12: "w", 1: "w", 2: "w", 6: "s", 7: "s", 8: "s"}  # else shoulder

# name -> weather feature columns (None = intercept-only)
MODELS = {
    "flat": None,
    "seasonal": "SEASONAL",          # same-season mean share
    "temp": ["temp_c"],
    "ghi": ["ghi_wm2"],
    "cloud": ["cloud_pct"],
    "wind": ["wind_kmh"],
    "temp+ghi": ["temp_c", "ghi_wm2"],
    "temp+cloud": ["temp_c", "cloud_pct"],
    "temp+wind": ["temp_c", "wind_kmh"],
}


def _loo_preds(y, X):
    """Leave-one-out per-fold predictions of least-squares y ~ [1, X]."""
    n = len(y)
    A = np.column_stack([np.ones(n), X]) if X is not None else np.ones((n, 1))
    preds = np.empty(n)
    for i in range(n):
        mask = np.arange(n) != i
        coef, *_ = np.linalg.lstsq(A[mask], y[mask], rcond=None)
        preds[i] = A[i] @ coef
    return preds


def _loo_preds_seasonal(y, months):
    seasons = np.array([SEASON.get(m, "sh") for m in months])
    preds = np.empty(len(y))
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        same = mask & (seasons == seasons[i])
        pool = y[same] if same.any() else y[mask]
        preds[i] = pool.mean()
    return preds


def _mape(y, preds):
    errs = [abs(p - t) / t for p, t in zip(preds, y) if t]
    return 100 * np.nanmean(errs) if errs else np.nan


def _mae_mw(y, preds, zone_mw):
    """Absolute error in MW — the honest metric for micro towns whose
    settlement value can be ~0 (percent error explodes there)."""
    return float(np.nanmean(np.abs((np.array(preds) - np.array(y)) * zone_mw)))


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
    print(f"=== Model zoo: {SLICE_ZONE}, months={len(peaks)} "
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
        months = [int(m.split("-")[1]) for m in d.index]
        y = (d["rnl_mw"] / d["zone_mw"]).values  # settlement share

        zone_mw = d["zone_mw"].values
        micro = (d["rnl_mw"].mean() < 3.0)  # micro town: score in MW, not %
        metric = "LOO_MAE_MW" if micro else "LOO_MAPE_pct"
        score = ((lambda p: _mae_mw(y, p, zone_mw)) if micro
                 else (lambda p: _mape(y, p)))

        row, fold_preds = {"Town": town}, {}
        for name, cols in MODELS.items():
            if cols == "SEASONAL":
                preds = _loo_preds_seasonal(y, months)
            else:
                preds = _loo_preds(y, feats[cols].values if cols else None)
            fold_preds[name] = preds
            row[name] = score(preds)
        # consensus: mean of all members' fold predictions, scored identically
        row["consensus"] = score(np.mean(list(fold_preds.values()), axis=0))
        # consensus-top3: mean of the 3 currently best members
        top3 = sorted(fold_preds, key=lambda k: row[k])[:3]
        row["consensus3"] = score(np.mean([fold_preds[k] for k in top3], axis=0))
        for name in list(MODELS) + ["consensus", "consensus3"]:
            con.execute("INSERT INTO forecast_scorecard VALUES (?, ?, ?, ?, ?, ?)",
                        (run_at, f"zoo_{name}", town,
                         f"{d.index.min()}..{d.index.max()}", metric, row[name]))
        scores = {k: v for k, v in row.items() if k != "Town"}
        row["champion"] = min(scores, key=scores.get)
        row["metric"] = "MAE MW" if micro else "MAPE %"
        rows.append(row)
    con.commit()
    out = pd.DataFrame(rows)
    num = out.drop(columns=["Town", "champion", "metric"])
    print(pd.concat([out[["Town", "metric"]], num.round(2), out[["champion"]]],
                    axis=1).to_string(index=False))
    print("\n(Leave-one-out score per model — MAPE % for normal towns, "
          "MAE in MW for micro towns; champion = current best.)")
    con.close()


if __name__ == "__main__":
    run()
