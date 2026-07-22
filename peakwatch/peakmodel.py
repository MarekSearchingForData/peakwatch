"""ML peak-day probability model (PLProb-inspired, LightGBM implementation).

Morning-of question: P(today's system max exceeds the month-to-date max)?
Method: quantile LightGBMs predict the distribution of today's daily max
from information available in the morning (ISO DA cleared max, weather,
calendar, lags, month-to-date max). The predicted quantiles form an
empirical CDF; the exceedance probability is read off it. Alerts fire
when P >= p*. Scored walk-forward (leave-one-month-out) on the same
capture-vs-alert-budget frontier as the baseline DA-ratio rule.
"""
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from .peaks import EASTERN
from .store import connect

QS = [0.05, 0.25, 0.50, 0.75, 0.95]
CDF_P = np.array(QS)
FEATURES = ["da_max", "tmax", "ghi_max", "dow", "is_weekend", "is_holiday",
            "doy_sin", "doy_cos", "sunset_hour", "lag1_max", "lag7_max",
            "mtd_max", "da_vs_mtd"]


def build_daily(con):
    zd = pd.read_sql("SELECT ts, SUM(da_load_mw) da, SUM(rt_load_mw) rt "
                     "FROM clean_zone_demand GROUP BY ts "
                     "HAVING COUNT(rt_load_mw)=8 OR COUNT(da_load_mw)=8", con)
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    local = zd["ts"].dt.tz_convert(EASTERN)
    zd["date"] = local.dt.date
    d = zd.groupby("date").agg(rt_max=("rt", "max"), da_max=("da", "max"))
    d.index = pd.to_datetime(d.index)

    wx = pd.read_sql("SELECT ts, AVG(temp_c) t, AVG(ghi_wm2) g FROM raw_weather "
                     "GROUP BY ts", con)
    wx["ts"] = pd.to_datetime(wx["ts"], utc=True)
    wx["date"] = wx["ts"].dt.tz_convert(EASTERN).dt.date
    wd = wx.groupby("date").agg(tmax=("t", "max"), ghi_max=("g", "max"))
    wd.index = pd.to_datetime(wd.index)

    cal = pd.read_sql("SELECT * FROM feature_calendar", con)
    cal["date"] = pd.to_datetime(cal["date"])
    cal = cal.set_index("date")[["dow", "is_weekend", "is_holiday",
                                 "doy_sin", "doy_cos", "sunset_hour"]]

    d = d.join(wd).join(cal)
    d["lag1_max"] = d["rt_max"].shift(1)
    d["lag7_max"] = d["rt_max"].shift(7)
    d["month"] = d.index.strftime("%Y-%m")
    # month-to-date max as of THIS morning (prior days only)
    d["mtd_max"] = (d.groupby("month")["rt_max"]
                      .transform(lambda s: s.shift(1).cummax()))
    d["da_vs_mtd"] = d["da_max"] / d["mtd_max"]
    d["is_peak_day"] = (d.groupby("month")["rt_max"].transform("max")
                        == d["rt_max"])
    return d.dropna(subset=["rt_max", "da_max", "tmax", "lag7_max"])


def exceed_prob(quantile_preds, threshold):
    """P(X > threshold) from predicted quantiles via piecewise-linear CDF."""
    v = np.sort(quantile_preds)
    if threshold <= v[0]:
        return 0.99
    if threshold >= v[-1]:
        return 0.01
    return float(1 - np.interp(threshold, v, CDF_P))


def run():
    con = connect()
    d = build_daily(con)
    months = [m for m, g in d.groupby("month") if len(g) >= 25]
    d = d[d["month"].isin(months)]
    print(f"=== Peak-probability model: {len(d)} days, {len(months)} complete "
          f"months ===")

    probs = pd.Series(index=d.index, dtype=float)
    for m in months:
        tr, te = d[d["month"] != m], d[d["month"] == m]
        qmodels = []
        for q in QS:
            mod = LGBMRegressor(objective="quantile", alpha=q, n_estimators=250,
                                learning_rate=0.05, num_leaves=31, verbose=-1)
            mod.fit(tr[FEATURES], tr["rt_max"])
            qmodels.append(mod.predict(te[FEATURES]))
        qarr = np.vstack(qmodels).T  # days x quantiles
        for i, (idx, row) in enumerate(te.iterrows()):
            thr = row["mtd_max"]
            probs[idx] = 0.99 if np.isnan(thr) else exceed_prob(qarr[i], thr)

    d = d.assign(p_exceed=probs)
    print(f"\n{'p*':>5} {'capture':>9} {'capture%':>9} {'alerts/mo':>10}")
    for p_thr in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        alerts = d["p_exceed"] >= p_thr
        per_month = d.groupby("month").apply(
            lambda g: pd.Series({
                "hit": bool(g.loc[g["is_peak_day"], "p_exceed"].max() >= p_thr),
                "n_alerts": int((g["p_exceed"] >= p_thr).sum())}),
            include_groups=False)
        print(f"{p_thr:>5} {int(per_month['hit'].sum()):>4}/{len(per_month):<4} "
              f"{100 * per_month['hit'].mean():>8.1f} "
              f"{per_month['n_alerts'].mean():>10.1f}")
    print("\nBaseline (DA-ratio rule): 100% @ 15.4 alerts/mo, 91% @ 6.5. "
          "The ML frontier must dominate it to earn deployment.")
    con.close()


if __name__ == "__main__":
    run()
