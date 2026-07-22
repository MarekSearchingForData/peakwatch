# PeakWatch — ISO-NE Peak Prediction for Municipal Utilities

Predicts the hours that set municipal light plants' capacity tags and
transmission charges in ISO-NE, so members can shave load (batteries, DR)
during exactly the hours that matter.

## Why

A Massachusetts municipal utility's capacity cost is set by its load during
the **single annual ISO-NE coincident peak hour**; transmission charges are
set by the **monthly regional peak hour**. Predicting those hours and shaving
1 MW is worth real money every year — and it is what makes battery fleets
(e.g. MMWEC/Lightshift) pay for themselves.

## What's here

- `peakwatch/` — core package
  - `config.py` — env-based configuration (secrets in `.env`, never committed)
  - `isone.py` — ISO-NE Web Services client with **verified** zone location IDs
- `scripts/`
  - `verify_api.py` — checks API access and the authoritative zone mapping
  - `ingest_load.py` — idempotent backfill of hourly zone demand (DaLoad + RtLoad)
- Data lives outside the repo (default `C:\Project ISO\data`, override with
  `PEAKWATCH_DATA_DIR`).

## Data lineage note

The legacy 2025 dataset used incorrect zone labels (ISO-NE location 4001 is
`.Z.MAINE`, not Boston — verified via `/locations.json`). All new data in
`raw/load_v2` and `cleaned/load/zone_demand_*` uses corrected labels:
ME, NH, VT, CT, RI, SEMA (`.Z.SEMASS`), WCMA (`.Z.WCMASS`), NEMA
(`.Z.NEMASSBOST`). Legacy files also stored day-ahead load only; the new
pipeline stores both day-ahead and actual (RT) load.

## Setup

```
py -m pip install -r requirements.txt
copy .env.example .env   # then fill in credentials
py scripts\verify_api.py
py scripts\ingest_load.py
```
