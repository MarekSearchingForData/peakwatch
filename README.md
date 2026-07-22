# PeakWatch — peak intelligence for Massachusetts municipal utilities

Predicts the ISO-NE hours that set municipal light plants' **capacity tags**
and **RNS transmission charges** — a ~$105M/yr cost surface across the 20
MMWEC member towns — and tracks every town's settlement-grade load history.

Built solo from public data (ISO-NE web services + settlement reports, EIA,
NWS/Open-Meteo weather, MassGIS), as an independent rebuild of the kind of
peak-forecasting service MMWEC operates for its members — with three things
added: town-level settlement analytics, published alert-budget economics,
and predict-before-publish scoring against ISO-NE's own settlement reports.

## Measured results (walk-forward, out-of-sample)

- **Peak-day capture:** 95.5% of monthly system peaks at 6.8 alert-days/month
  (ML probability model); 100% at 15.4 alert-days (transparent rule).
  Held-out July 2026: alerted on the annual peak day (25,321 MW, July 2)
  with zero false alarms the rest of the month.
- **Zone forecast:** LightGBM quantile model blended 50/50 with ISO-NE's own
  day-ahead forecast beats ISO alone on every window tested (e.g. 2.80% vs
  3.81% MAPE). Bands calibrated to 81.7% coverage vs 80% target.
- **Town settlement prediction:** per-town champion models (leave-one-month-
  out): Chicopee 4.3%, Holyoke 7.0% (top-3 consensus), Princeton ±0.63 MW
  (temperature+wind model — the town's wind turbines mask its load).
- Industry reference points: VPPSA contracts battery dispatch at 90% capture;
  Enel X issues ~6-9 alert days per summer.

## Architecture (7 modules, database-only interfaces)

collectors → SQLite store → validation gate → {analytics, forecast engine,
town allocator} → Streamlit dashboard, orchestrated by one CLI. Modules
communicate only through tables; data is promoted raw → clean only after
reconciliation checks against independently published numbers. See
[ARCHITECTURE.md](ARCHITECTURE.md) and [METHODOLOGY.md](METHODOLOGY.md).

## Operating rhythms

```
py -m peakwatch daily     # ops loop: refresh -> validate -> risk flags -> peak probability
py -m peakwatch monthly   # settlement loop: new RNL -> re-score model zoo -> dollar table
streamlit run app.py      # dashboard: Peak Risk / Towns / Zones / Health
py -m pytest tests        # 12 regression tests (one per bug ever hit)
```

Individual verbs: `refresh validate analyze allocate experiment decompose
dollars peakprob`.

## Data lineage rules

Every layer reconciles against an independent published number before
anything is built on it: zone labels verified against `/locations`, town
zone assignments against settlement reports, computed pool peaks against
published pool values (±0.84%), town estimates against EIA-861 annual sales.
Settlement values use ISO's restated (`-drp`) files; a spike guard catches
first-publication data errors (a 15x error has occurred in the wild).

## Setup

```
py -m pip install -r requirements.txt
copy .env.example .env    # ISO-NE credentials (free registration)
py scripts\verify_api.py
py scripts\ingest_load.py && py scripts\ingest_town_load.py
py -m peakwatch daily
```
