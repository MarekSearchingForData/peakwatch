# PeakWatch Methodology & Data Resource Guide

What each resource is, why we trust it, and how it's used. Rule of the
project: **every layer reconciles against an independent published number
before anything is built on it.**

## Data resources

| Resource | What it is | Grain | How we use it | Limits / gotchas |
|---|---|---|---|---|
| ISO-NE Web Services `combinedhourlydemand` | Day-ahead cleared (DaLoad) and actual (RtLoad) demand per load zone | zone-hour | Core load history; DA is the built-in benchmark forecast | Auth required; ~429 rate limits (sequential + backoff); RtLoad settles days late; location IDs verified 4001=ME … 4008=NEMA |
| ISO-NE Monthly Regional Network Load report | Settlement-grade MW of every network customer **at the monthly RNS transmission peak hour** | town-month | Ground truth for town loads; allocator anchor; scoring target | ~2-month publication lag; restated (`-drp`) versions supersede; zero = own generation netted load out (real, keep) |
| ISO-NE `fiveminutesystemload` | Live system load | 5-min | Dashboard live tile | — |
| Meteostat | Station-based hourly weather history | town-hour | Long weather history per town | Occasional station gaps; v1 pin (`meteostat<2`) |
| Open-Meteo archive | Modeled hourly weather incl. **solar radiation (GHI)**, wind, cloud | town-hour | Offset features (BTM PV, wind) for share models | Modeled, not observed; legacy variable names required |
| NWS API (api.weather.gov) | Official hourly forecast | town-hour, 6-day | Forward features for live predictions | Forecast only; no history |
| EIA 860 / 861, MassCEC (via research) | Generator inventory; net-metered PV per utility | asset / town-year | `town_portfolio`: physical coefficients for offset models | Annual; lags reality ~1y |

## Definitions

- **RNL** (Regional Network Load): a customer's load at the hour of the
  monthly RNS peak. Sets transmission charges. The thing peak-shaving reduces.
- **Capacity tag**: load at the single annual ISO-NE system peak hour. Sets
  capacity charges. Same forecasting machinery, one hour per year.
- **alpha (share)**: town RNL ÷ zone RT load at the settlement peak hour.
- **Pool peak approximation**: we take the max of our 8-zone RT sum;
  verified within ~1.3% mean abs difference of the published pool value
  over 2024-01..2024-08. Refinement queued: snap to the hour best matching
  the published pool total.

## Modeling protocol

1. **Champion/challenger zoo.** Every model is scored on every run via
   leave-one-month-out MAPE against settlement truth; per-town champion =
   current winner; all scores persist in `forecast_scorecard`. Challengers
   are never deleted — a loser on 8 months may win on 50.
2. **Features earn admission.** A signal (temp, GHI, cloud, wind, holiday,
   portfolio-scaled offsets) ships only if it beats the incumbent
   out-of-sample. Physics guides the candidate list (GHI matters via BTM-PV
   offset, so its effect should scale with a town's PV MW); the scorecard
   decides.
3. **Honest scoring only.** All evaluations use information available at
   prediction time (morning-of DA data, prior months' truth). No peeking.
4. **Uncertainty is part of the product.** Predictions ship with ranges
   derived from out-of-sample residuals, not point estimates alone.
5. **Benchmarks.** Zone hourly: ISO's own DaLoad. Town monthly: flat share
   (M0). A model that can't beat its benchmark is replaced by it.

### Candidate methods queue (tested, not presumed)

- Quantile regression / gradient boosting (zone hourly) — primary
- Survival framing (Kaplan-Meier style): P(current month-max survives the
  remaining days) — peak-day runway product
- k-means town archetypes (pure-load / solar-heavy / generation-masked) —
  shared model structure across the 20 towns
- Portfolio-scaled offset terms: `net = share·zone − PV_MW·f(GHI) − wind_MW·g(wind)`

## Validation gates (run on every refresh)

zone magnitude ranking (CT largest, VT smallest — label-swap detector) ·
DA↔RT correlation per MA zone > 0.90 · day completeness · RNL region matches
reference mapping · RNL non-negative (zero allowed = own generation) ·
promoted to `clean_*` only if all blocking checks pass, else quarantined.

## Known limitations (current)

- Pool peak hour approximated (±1.3%) pending exact-hour snapping.
- Princeton-class towns (generation ≥ load) need explicit offset terms;
  wide error bands until then.
- 2022 settlement reports before mid-2022 not yet located.
- Weather features currently lose to flat baselines at n≤8 months —
  expected small-sample behavior; re-judged as backfill extends history.
