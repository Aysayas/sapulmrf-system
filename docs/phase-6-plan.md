# Phase 6 plan: insights with AI/ML

**Superseded in part:** the `anomaly_sd` z-score below was replaced, see `docs/flags-mad-plan.md`.

## Context
Phase 5 is done in `C:\dev\sapulmrf` (111 API tests, 15 browser tests, worker and live sim running). The repo is on GitHub (`Aysayas/sapulmrf-system`, private), and VS Code uses `api/.venv`. This plan was approved before; this is the same plan with the disk note updated. Phase 6 is the AI/ML part the capstone has to show:
- **ADM-12:** review flagged unusual records.
- **ADM-13:** predicted waste intake and predicted storage status.
- **ADM-14:** suggested pickup or sale schedule.
- **ADM-15:** predicted vs actual (Objective 5).

The data is ready: 40 days of simulated history (about 500 deliveries), with 2% weight outliers and 3% received-vs-sorted gaps planted for exactly this. The settings already have `prediction_min_days` (30) and `anomaly_sd` (2.5). Insights is still a "coming soon" placeholder.

Wireframes:
- admin `04-predictions`: forecast chart by category, storage outlook, schedule, predicted vs actual
- admin `04b-predictions-not-ready`: "12 of 30 days"
- admin `02f` / `02g`: Flagged records as an Approvals tab, marked Valid or Incorrect

## Decisions
Your answers:
- **Stats and ML together now:** a moving-average baseline and a scikit-learn model sit behind the same endpoint. Both are scored on real errors, the page shows both, and the forecast uses whichever has the lower error over the last 14 days. On real data both retrain as records come in.
- **Flags use z-scores and a gap rule:**
  - a weight more than `anomaly_sd` (2.5) standard deviations from that purok's usual weight, shown as "Usual for Purok 2: 6–10 kg"
  - received weight vs separated + sorted kg differing by more than 5% and 0.3 kg
- **Each day's forecast is saved:** errors come from forecasts made before the day happened, not hindsight. The backfill replays the past days the same way, so predicted vs actual isn't empty.

My calls (override any):
- **The ML model:** scikit-learn `Ridge` regression per category. Features are day of week (one-hot), the 7-day and 28-day averages up to the day before, and a trend index. It suits 30–60 points of daily data and is easy to explain in Chapter 3. Prophet is skipped: it is a heavy install, and the disk is tight.
- **What gets forecast:** daily kg for the next 7 days, for all waste and for each category (the wireframe's filter). Forecasts start once there are `prediction_min_days` days of records; before that, the page shows "N of 30 days".
- **Error:** mean absolute % error (MAPE) of the 1-day-ahead forecasts over the last 7 and 14 days, shown as "6% off" and per model ("ML 6% · baseline 9%").
- **Storage outlook:** from each area's current kg and its average sorted-in kg per day over the last 14 days: "Full in ~6 days", or "30+ days".
- **Pickup or sale schedule:** a suggestion for each area that reaches its alert % within 14 days, dated the day before it gets there: "Sell paper and cardboard · Area B at 90% by Oct 27", or "Residual pickup". It is a plan only; the operator still records the outgoing request.
- **Flags are checked when a record is made:** the weight check runs when a delivery is recorded, and the gap check when it is sorted. Flags then appear straight away, and the backfill makes them naturally. A weight flag needs at least 10 earlier deliveries from that purok.
- **Flag decisions are marks only:** Valid or Incorrect, logged, with no value changes, the same as the Phase 4 reviews. Flags are an Approvals tab, as in the wireframe, so the Approvals count includes them.
- **Camera accuracy card on Insights:** suggestions kept unchanged, and the changes the admin marked "wrong" (from the Phase 4 marks), over the last 30 days.
- **Saving forecasts:** the worker saves forecasts once a Manila day, the first time it runs after midnight, and does nothing more that day. `simulator remove` also deletes forecasts, since they were built on simulated data; the worker rebuilds them from real records.
- **Who sees what:** admins and operators see Predictions; staff need the existing `predictions` grant. Only admins see and decide flags.
- **Disk (C: had 19 GB free on the last check, up from 6.6 GB):** scikit-learn and numpy add about 150 MB to the API image. `api`, `worker` and `sim` will share one image (`image: sapulmrf-api:dev`), so it is built once, not three times.
- **Editor venv:** add numpy and scikit-learn to `api/.venv` too (the README command), so VS Code resolves the new imports.

## Backend (router → service → models + schemas)
| Module | Tables | Routes |
|---|---|---|
| `insights/` (new) | `flags` (delivery_id FK cascade, kind weight/gap, value_kg, expected_low, expected_high, found_at, status open/valid/incorrect, decided_by/at; unique delivery+kind); `forecasts` (made_on, for_day, category_id null = all, model baseline/ml, kg; unique on all four) | `GET /insights/predictions?category=` (ready, days of records, model errors, model used, last 28 days actual, next 7 days forecast, outlook, schedule, predicted vs actual for the last 7 days, camera accuracy); `GET /insights/flags` and `POST /insights/flags/{id}` `{decision}` (admin) |

- **Files:**
  - `insights/models.py`, `insights/flags.py` (`check_weight(db, delivery)`, `check_gap(db, delivery)`), `insights/forecast.py` (`daily_kg`, `baseline`, `ridge`, `make_forecasts(db, made_on)`, `errors`), `insights/service.py` (predictions view, outlook, schedule, camera accuracy, flag decisions), `insights/router.py`
  - one Alembic migration
- **Hooks into existing code:**
  - `intake.service.record_delivery` calls `check_weight`, and `sorting.service.sort_delivery` calls `check_gap`.
  - `approvals.service.counts` gains `flagged`, and `app/alerts/worker.py` gains the daily `make_forecasts`.
  - `simulator.backfill` replays `make_forecasts` for each past day, and `simulator.remove` clears forecasts.
- **Reuse:**
  - `operations.service.since` / `day_start` / `TZ` for Manila days
  - `operations.service.area_fill` for current fill
  - `settings.service.get` for `prediction_min_days` and `anomaly_sd`
  - the `viewer("predictions")` dependency
  - the `log()` helper
- **requirements.txt:** add `numpy` and `scikit-learn` (pinned major versions).

## Frontend
- **Insights page** (`/admin/insights`, replacing the placeholder), laid out like wireframe `04`:
  - Category tabs (All plus each category).
  - Intake chart: the last 21 days as solid bars and the next 7 days hatched, with a small key ("solid = actual · hatched = predicted"; one series in two states, per the dataviz rules). Tooltips give kg.
  - Model card: "Using the ML model · 6% average error (baseline 9%)".
  - Storage outlook list, schedule table, predicted-vs-actual table with the 7-day average error, and the camera accuracy card.
  - The not-ready state ("12 of 30 days", with a progress bar and a link to Ranges and limits).
- **Approvals:** a fifth tab, "Flagged records": Record, Source, Value, Expected, Why flagged, and Valid / Incorrect buttons, as in wireframe `02f`.
- **Reuse:** `Table`, `kg`, `when` (`features/operations/shared.tsx`), `Kpi` / `FillBar` and the Recharts set-up in `components/charts.tsx`, and the tab pattern from `ApprovalsPage.tsx`.

## Order of work (each step ends working and committed)
1. Dependencies and shared image, the migration, and flags (weight and gap checks wired into intake and sorting), with tests.
2. Forecasting: daily kg, baseline, Ridge, `make_forecasts`, saved forecasts, errors and model choice, with tests.
3. Predictions API: view, outlook, schedule, camera accuracy, flag list and decisions, access, with tests.
4. Worker daily forecasts; simulator backfill replay and `remove`; rebuild the dev data and check the numbers look sensible.
5. Frontend: Insights page, including the not-ready state.
6. Frontend: the Flagged records tab in Approvals, with the count.
7. Browser test `admin-06-insights.spec.ts`:
   - the Insights page shows the forecast, both model errors, the outlook and predicted vs actual
   - an e2e operator records 10 normal deliveries and one 3× outlier for an e2e purok
   - the outlier appears under Flagged records, and marking it Incorrect removes it

   `remove-test-data` already clears deliveries from e2e puroks, and flags cascade with them.
8. Roadmap ticks (including "how many days before ML" answered), README/testing notes, vault session note.

## Tests that must pass
- **Weight flags:** a weight more than 2.5 SD from the purok's usual is flagged with the usual range; fewer than 10 earlier deliveries means no flag; changing `anomaly_sd` changes the outcome.
- **Gap flags:** received 11.3 vs separated + sorted 9.1 is flagged; a 1% difference is not.
- **Flag decisions:** admin only; Valid / Incorrect stop it being listed; deciding twice → 409; logged.
- **Forecasts:**
  - fewer than `prediction_min_days` days gives "not ready" and no forecasts
  - the baseline on a constant series predicts that constant
  - Ridge forecasts are 7 values, never negative, and follow a clear weekday pattern better than the baseline
  - `make_forecasts` run twice changes nothing
  - errors use only forecasts made before the day
  - the model with the lower 14-day error is the one used
- **Outlook and schedule:** an area at 400/500 kg gaining 20 kg a day → "full in ~5 days", and a suggestion before it reaches its alert %; an area with no inflow → "30+ days" and no suggestion.
- **Access:** staff without the `predictions` grant → 403; flags are admin only.
- **Overall:** every Phase 1–5 test still passes, Ruff is clean, `npm run build` passes, all browser tests pass.

## Verification
- Rebuild the image once (`docker compose build api`), then `alembic upgrade head`, `pytest` and `ruff check .`.
- Rebuild the sim data (`simulator remove`, `setup`, `backfill --days 40`) and check that flags find the planted outliers (about 2% of deliveries) and gaps, and that the MAPE values are believable (roughly 10–25% on noisy daily data).
- `npm run test:e2e`, then `remove-test-data`.
- Screenshots of Insights (ready and not-ready), the outlook and schedule, and the Flagged records tab, compared with wireframes `04`, `04b` and `02f`.
- Check free disk space on C: before and after the image build.

## Not in Phase 6
- Prophet or deep-learning models, and retraining on a schedule other than daily.
- Staff Insights screens (the API honours the `predictions` grant).
- Reports and PDF/CSV export (Phase 7).
- Automatically correcting flagged records.
