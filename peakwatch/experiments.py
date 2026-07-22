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


def _loo_mape(y, X):
    """Leave-one-out MAPE of least-squares y ~ [1, X]."""
    n = len(y)
    A = np.column_stack([np.ones(n), X]) if X is not None else np.ones((n, 1))
    errs = []
    for i in range(n):
        mask = np.arange(n) != i
        coef, *_ = np.linalg.lstsq(A[mask], y[mask], rcond=None)
        pred = A[i] @ coef
        errs.append(abs(pred - y[i]) / y[i] if y[i] else np.nan)
    return 100 * np.nanmean(errs)


def _loo_mape_seasonal(y, months):
    seasons = np.array([SEASON.get(m, "sh") for m in months])
    errs = []
    for i in range(len(y)):
        mask = np.arange(len(y)) != i
        same = mask & (seasons == seasons[i])
        pool = y[same] if same.any() else y[mask]
        pred = pool.mean()
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

        row = {"Town": town}
        for name, cols in MODELS.items():
            if cols == "SEASONAL":
                mape = _loo_mape_seasonal(y, months)
            else:
                mape = _loo_mape(y, feats[cols].values if cols else None)
            row[name] = mape
            con.execute("INSERT INTO forecast_scorecard VALUES (?, ?, ?, ?, ?, ?)",
                        (run_at, f"zoo_{name}", town,
                         f"{d.index.min()}..{d.index.max()}", "LOO_MAPE_pct", mape))
        scores = {k: v for k, v in row.items() if k != "Town"}
        row["champion"] = min(scores, key=scores.get)
        rows.append(row)
    con.commit()
    out = pd.DataFrame(rows)
    num = out.drop(columns=["Town", "champion"])
    print(pd.concat([out[["Town"]], num.round(1), out[["champion"]]], axis=1)
          .to_string(index=False))
    print("\n(LOO MAPE % predicting each month's settlement share; "
          "champion = current best. All models re-scored every run.)")
    con.close()


if __name__ == "__main__":
    run()
