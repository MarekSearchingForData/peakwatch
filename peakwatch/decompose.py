"""Small-batch prototype of the functional decomposition (zone -> town hourly).

1. NMF on the zone's daily 24-hour profiles -> k ingredient shapes
   (typically: overnight base, midday/commercial, evening/thermal).
2. Each town takes a non-negative fraction phi_k of each component:
       town(t) ~= sum_k phi_k * c_k(t)
   fitted at monthly settlement anchors + an annual-energy row (EIA-861).
3. Scored leave-one-anchor-out, same protocol as the zoo, so it competes
   with flat/seasonal/consensus on equal terms.
"""
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF

from .allocator import SLICE_TOWNS, SLICE_ZONE, _monthly_pool_peak_hours
from .peaks import EASTERN
from .store import connect

K = 3
ENERGY_WEIGHT = 3.0  # how strongly the annual-energy constraint counts vs one anchor
HOURS_PER_YEAR = 8766


def _zone_components(zd, zone):
    """NMF over (days x 24) zone matrix -> per-hour component MW series."""
    z = zd[(zd["zone"] == zone)].dropna(subset=["rt_load_mw"]).copy()
    z["local"] = z["ts"].dt.tz_convert(EASTERN)
    z["date"] = z["local"].dt.date
    z["hour"] = z["local"].dt.hour
    mat = z.pivot_table(index="date", columns="hour", values="rt_load_mw")
    mat = mat.dropna()  # complete days only
    model = NMF(n_components=K, init="nndsvda", max_iter=600, random_state=0)
    W = model.fit_transform(mat.values)  # days x K activations
    H = model.components_                # K x 24 shapes
    # per-hour component reconstruction c_k(t), long format
    recs = []
    for di, d in enumerate(mat.index):
        for h in range(24):
            recs.append((d, h, *(W[di, k] * H[k, h] for k in range(K))))
    comp = pd.DataFrame(recs, columns=["date", "hour"] + [f"c{k}" for k in range(K)])
    return comp, H, mat


def run_slice():
    con = connect()
    zd = pd.read_sql("SELECT * FROM clean_zone_demand", con, parse_dates=["ts"])
    zd["ts"] = pd.to_datetime(zd["ts"], utc=True)
    rnl = pd.read_sql("SELECT * FROM clean_town_rnl WHERE zone = ?", con,
                      params=[SLICE_ZONE])
    mix = pd.read_sql("SELECT * FROM town_class_mix", con).set_index("town")

    comp, H, mat = _zone_components(zd, SLICE_ZONE)
    print(f"=== Decomposition prototype: {SLICE_ZONE}, {len(mat)} complete days, "
          f"k={K} components ===")
    print("\nComponent shapes (normalized, peak hour of each):")
    for k in range(K):
        shape = H[k] / H[k].max()
        print(f"  c{k}: peaks at {int(np.argmax(H[k]))}:00 local  "
              f"profile {' '.join(f'{v:.1f}' for v in shape[::3])}")

    # anchor design matrix: component values at each month's settlement hour
    peaks = _monthly_pool_peak_hours(zd)
    local = peaks["ts"].dt.tz_convert(EASTERN)
    anchors = pd.DataFrame({"month": peaks.index,
                            "date": local.dt.date, "hour": local.dt.hour})
    anchors = anchors.merge(comp, on=["date", "hour"], how="inner")

    # annual energy of each component (MWh per year, scaled from sample)
    comp_year = comp[[f"c{k}" for k in range(K)]].sum() * (
        HOURS_PER_YEAR / len(comp))

    print(f"\nusable anchors: {len(anchors)}")
    for town in SLICE_TOWNS:
        t_rnl = rnl[rnl["town"] == town].set_index("month")["rnl_mw"]
        d = anchors.join(t_rnl, on="month", how="inner").dropna(subset=["rnl_mw"])
        if len(d) < 5:
            print(f"{town}: only {len(d)} anchors — skipped")
            continue
        A = d[[f"c{k}" for k in range(K)]].values
        y = d["rnl_mw"].values
        e_row = comp_year.values
        e_target = mix.loc[town, "total_mwh"]

        preds = []
        for i in range(len(y)):
            m = np.arange(len(y)) != i
            A_fit = np.vstack([A[m], ENERGY_WEIGHT * e_row / e_row.mean()])
            y_fit = np.concatenate([y[m], [ENERGY_WEIGHT * e_target / e_row.mean()]])
            phi, *_ = np.linalg.lstsq(A_fit, y_fit, rcond=None)
            phi = np.clip(phi, 0, None)
            preds.append(A[i] @ phi)
        preds = np.array(preds)
        mape = 100 * np.nanmean([abs(p - t) / t for p, t in zip(preds, y) if t])
        mae = float(np.mean(np.abs(preds - y)))

        # full fit for reporting phi + implied annual energy
        A_fit = np.vstack([A, ENERGY_WEIGHT * e_row / e_row.mean()])
        y_fit = np.concatenate([y, [ENERGY_WEIGHT * e_target / e_row.mean()]])
        phi, *_ = np.linalg.lstsq(A_fit, y_fit, rcond=None)
        phi = np.clip(phi, 0, None)
        implied_gwh = float(phi @ e_row) / 1000
        print(f"\n{town}: phi={np.round(phi, 4)}  "
              f"LOO anchor error: MAPE {mape:.1f}%  MAE {mae:.2f} MW  "
              f"implied annual {implied_gwh:.1f} GWh vs EIA {e_target/1000:.1f} GWh")
    con.close()


if __name__ == "__main__":
    run_slice()
