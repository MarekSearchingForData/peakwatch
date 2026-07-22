"""Dollarization: convert each town's peak-hour MW into annual dollars.

- Transmission: RNS is billed monthly at 1/12 of the annual $/kW-yr rate
  against each month's Regional Network Load. Annual exposure =
  mean(last 12 monthly RNL) x RNS rate.
- Capacity: annual cost = ICAP tag x FCA clearing price x 12. We proxy the
  tag with the town's RNL in the month containing the annual system peak
  (July/August), clearly labeled as a proxy until tag data is available.
- Shave value: 1 MW held off across the 12 monthly peaks = full RNS rate;
  1 MW off the single annual peak hour = FCA price x 12.
"""
from pathlib import Path

import pandas as pd

from .store import connect

RATES = Path(__file__).resolve().parent.parent / "reference" / "rates.csv"


def run(rns_year="2026", fca="FCA18"):
    rates = pd.read_csv(RATES)
    rns = float(rates[(rates["metric"] == "RNS")
                      & (rates["period"] == rns_year)]["value"].iloc[0])
    fca_rate = float(rates[rates["metric"] == fca]["value"].iloc[0])

    con = connect()
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl", con)
    rows = []
    for town, g in rnl.groupby("town"):
        g = g.sort_values("month")
        last12 = g.tail(12)
        avg_rnl = last12["rnl_mw"].mean()
        summer = g[g["month"].str[5:7].isin(["07", "08"])]
        tag_proxy = summer["rnl_mw"].tail(2).max() if len(summer) else float("nan")
        trans = avg_rnl * 1000 * rns
        cap = tag_proxy * 1000 * fca_rate * 12 if tag_proxy == tag_proxy else float("nan")
        rows.append({"Town": town, "avg RNL MW": avg_rnl,
                     "tag proxy MW": tag_proxy,
                     "transmission $/yr": trans, "capacity $/yr": cap,
                     "total $/yr": trans + (cap if cap == cap else 0)})
    df = pd.DataFrame(rows).sort_values("total $/yr", ascending=False)

    print(f"=== Dollar exposure (RNS {rns_year}: ${rns}/kW-yr; "
          f"{fca}: ${fca_rate}/kW-mo) ===\n")
    fmt = df.copy()
    for c in ["transmission $/yr", "capacity $/yr", "total $/yr"]:
        fmt[c] = fmt[c].map(lambda v: f"${v:,.0f}" if v == v else "—")
    for c in ["avg RNL MW", "tag proxy MW"]:
        fmt[c] = fmt[c].round(1)
    print(fmt.to_string(index=False))
    total = df["total $/yr"].sum()
    print(f"\nMembership total exposure: ${total:,.0f}/yr")
    print(f"Value of 1 MW shaved: all 12 monthly peaks = ${rns * 1000:,.0f}/yr; "
          f"annual peak hour only = ${fca_rate * 1000 * 12:,.0f}/yr")
    con.close()
    return df


if __name__ == "__main__":
    run()
