"""Town allocator v0 (vertical slice): zone curves -> town curves.

Model: town_load(h) = alpha_town * zone_load(h).
alpha_town(m) is observed each month from settlement truth:
    alpha = RNL_town(m) / zone_rt_load(at the month's RNS transmission peak hour)

The slice answers the make-or-break question: is alpha stable enough
month-to-month that alpha alone predicts next month's RNL?
Test: leave-one-month-out — predict month m's RNL using the mean alpha of
all OTHER months, score MAPE per town. Results go to forecast_scorecard.

Note: RNL is measured at the POOL transmission peak (regional network peak),
which we approximate with the zone's peak hour of total New England load.
v0 uses the all-zones-summed peak hour; refinement can come after review.
"""
from datetime import datetime, timezone

import pandas as pd

from .store import connect

EASTERN = "America/New_York"

SLICE_ZONE = "WCMA"
SLICE_TOWNS = ["Chicopee", "Holyoke", "Princeton"]


def _monthly_pool_peak_hours(zd):
    """Timestamp of each month's system (sum of zones) RT peak."""
    system = zd.groupby("ts", as_index=False)["rt_load_mw"].sum(min_count=1)
    system["month"] = system["ts"].dt.tz_convert(EASTERN).dt.strftime("%Y-%m")
    idx = system.dropna(subset=["rt_load_mw"]).groupby("month")["rt_load_mw"].idxmax()
    return system.loc[idx].set_index("month")[["ts", "rt_load_mw"]]


def run_slice(zone=SLICE_ZONE, towns=SLICE_TOWNS):
    con = connect()
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    if zd.empty:
        print("allocator: clean_zone_demand is empty — run refresh + validate first")
        return
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql(
        "SELECT * FROM clean_town_rnl WHERE zone = ? AND town IN (%s)"
        % ",".join("?" * len(towns)), con, params=[zone, *towns])

    peaks = _monthly_pool_peak_hours(zd)
    zone_at_peak = (zd[zd["zone"] == zone].set_index("ts")["rt_load_mw"]
                    .reindex(peaks["ts"]).values)
    peaks = peaks.assign(zone_mw_at_peak=zone_at_peak)

    # observed alpha per town-month
    obs = rnl.merge(peaks, left_on="month", right_index=True, how="inner")
    obs = obs.dropna(subset=["zone_mw_at_peak"])
    obs["alpha"] = obs["rnl_mw"] / obs["zone_mw_at_peak"]

    run_at = datetime.now(timezone.utc).isoformat()
    con.execute("DELETE FROM allocator_alpha")
    con.executemany(
        "INSERT INTO allocator_alpha VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(r.town, r.month, zone, r.alpha, str(r.ts), r.zone_mw_at_peak, r.rnl_mw)
         for r in obs.itertuples()])

    print(f"=== Allocator slice: {zone} / {', '.join(towns)} ===")
    print(f"months with both zone data and settlement RNL: "
          f"{obs['month'].nunique()} ({obs['month'].min()} -> {obs['month'].max()})\n")

    results = []
    for town, g in obs.groupby("town"):
        g = g.sort_values("month")
        alphas = g.set_index("month")["alpha"]
        stability = alphas.std() / alphas.mean()

        # leave-one-month-out prediction of RNL
        errs = []
        for m in alphas.index:
            a_others = alphas.drop(m).mean()
            pred = a_others * g.set_index("month").loc[m, "zone_mw_at_peak"]
            actual = g.set_index("month").loc[m, "rnl_mw"]
            errs.append(abs(pred - actual) / actual)
        mape = 100 * pd.Series(errs).mean()
        worst = 100 * pd.Series(errs).max()
        results.append({"Town": town, "mean_alpha": alphas.mean(),
                        "alpha_cv%": 100 * stability,
                        "LOO_MAPE%": mape, "worst_month_err%": worst})
        con.execute("INSERT INTO forecast_scorecard VALUES (?, ?, ?, ?, ?, ?)",
                    (run_at, "allocator_v0_loo", town,
                     f"{alphas.index.min()}..{alphas.index.max()}", "MAPE_pct", mape))

    con.commit()
    res = pd.DataFrame(results)
    print(res.round(3).to_string(index=False))
    print("\nReading guide: alpha_cv% = month-to-month share volatility; "
          "LOO_MAPE% = avg error predicting a month's settlement RNL "
          "from other months' alpha. <10% means the concept works.")

    print("\nPer-month alpha (share of zone load at pool peak):")
    pivot = obs.pivot_table(index="month", columns="town", values="alpha")
    print((100 * pivot).round(2).to_string())
    con.close()
    return res
