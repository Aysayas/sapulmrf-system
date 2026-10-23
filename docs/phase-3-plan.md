# Phase 3 plan: simulators and the live operations view
_Drafted 2026-10-23. Needs a go-ahead before any code._

**Covers:** ADM-07 (intake, sorting and inventory records), ADM-08 (segregation compliance per purok), ADM-09 (compost batches and sensor readings) and ADM-19 (overall monitoring, the Overview dashboard).

**Done looks like:** with the simulator running, the admin opens http://localhost:5174 and sees a live MRF:
- the Overview dashboard: today's totals, a 14-day intake chart, storage fill per area, compost batches with live readings, device status, and the last camera result
- Operations › Intake, Segregation, Sorting, Inventory, Compost and Live camera, all read-only for the admin, as in the mockup

The numbers keep changing as the simulator works. One command creates 40 days of history first, and another removes everything simulated.

## Decisions
- **(You)** Backfill 40 days of history with a one-time command, so the charts aren't empty and Phase 6 has 30+ days to predict from.
- **(You)** Simulated data lives in the dev database, tagged so it can be removed: devices `SIM-…`, the operator account `sim.operator`, and demo puroks and areas named `Demo …`. `python -m app.cli remove-sim-data` removes all of it, including every record it made.
- **(Me) The simulator works through the real API, like a real operator and real devices.** That means Phase 3 also builds the operator's *write* API: record a delivery, its segregation check, confirm or change a camera suggestion, record sorted quantities, start a compost batch, and log activities. The operator *screens* still come later. Building the API now means it's tested before the operator side exists, and the admin views show data that went through the real rules.
- **(Me) The backfill runs inside the API container** and calls the same service functions with past timestamps. The HTTP API doesn't accept back-dated records, so a real operator can't fake dates.
- **(Me) Stock is a ledger**, not a running total. Every change is a row: sorted in, transfer, and later adjustment or outgoing. The current stock is the sum, so every number can be traced to its records. That's useful for the audit trail and for Phase 4 approvals.
- **(Me) Devices send readings with their key:** `POST /devices/readings`, which also counts as a heartbeat. Weighing station: `{kg, stable}`. Compost sensor: `{temp_c, moisture_pct}`, stored against the batch the sensor is linked to. Camera: `POST /devices/cv-suggestions` `{label, confidence, model_version, image_url}`, using the CV-result contract in the roadmap, so Rhendel's model can post the same shape later.
- **(Me) Live camera** shows the latest classification with its image. The simulator uses the same Unsplash stock photos as the mockup (one per material) until the real camera exists. There's no video stream in Phase 3.
- **(Me) Simulator pace** is configurable. The default demo pace is a delivery every 1–2 minutes, compost readings every 30 s and heartbeats every 30 s. It runs only when asked: `docker compose --profile sim up -d`.
- **(Me) Charts use Recharts,** following the dataviz skill's rules: one hue per series, forecasts hatched, colour never on its own.

## Data (new tables, one migration)
| Table | Key columns |
|---|---|
| `deliveries` | code `D-0001`, received_at, source_area, category, weight_kg, weighed_by (scale/manual), scale_kg + correction_reason when corrected, status (awaiting / separated / sorted), recorded_by, device |
| `segregation_checks` | delivery (one each), condition (segregated / mixed), wet_kg, dry_kg, note, checked_by, checked_at |
| `classifications` | suggested material + confidence + model_version + image_url (from the camera), final material (or "not recyclable"), changed, reason, confirmed_by, timestamps |
| `stock_movements` | material (null = residual), storage_area, kg, bags, kind (sorted / transfer; later adjustment / outgoing), delivery, by, at |
| `compost_batches` | code `B-01`, started_at, start_kg, sensor device, finished_at, produced_kg |
| `compost_readings` | batch, device, temp_c, moisture_pct, read_at |
| `compost_activities` | batch, type (turning / watering / inspection), note, by, at |
| `devices` (existing) | + `last_reading` (JSON) for the live readout |

## API
- **Operator writes** (operator role, admin can't post): `POST /deliveries`, `POST /deliveries/{id}/segregation`, `POST /classifications/{id}/confirm` (with an optional changed material and reason), `POST /sorting`, `POST /compost/batches`, `POST /compost/batches/{id}/activities`.
- **Device writes** (device key): `POST /devices/readings`, `POST /devices/cv-suggestions`.
- **Admin and staff reads:**
  - `GET /operations/intake`, `/operations/segregation?days=`, `/operations/sorting`, `/operations/inventory`, `/operations/compost` and `/operations/camera`
  - `GET /overview`
- **Rules enforced in the services:**
  - weights must be above 0
  - wet + dry can't be far above the received weight (the gap itself is a Phase 6 flag)
  - a delivery is checked only once
  - sorting moves the delivery to "sorted"
  - kg can't go negative in an area
  - a compost reading outside the ranges is stored as-is (alerts come in Phase 5)

## Simulator (`sim/`, Python, its own small container)
- `sim setup`: logs in with the test admin from `.env`, then creates `sim.operator` and the `SIM-` devices (scale, 2 compost sensors, camera). It adds `Demo Purok 1–7` and `Demo Area A–D` only if there are no active puroks or areas. Device keys are saved in the sim's own Docker volume.
- `sim run`: the live loop through the API. The devices post heartbeats and readings; the "operator" records deliveries, checks segregation, confirms ~85% of camera suggestions unchanged (and changes the rest), sorts into areas, and logs compost activities. Weights follow each purok's usual range, with occasional outliers for Phase 6.
- `app.cli sim-backfill --days 40` (API container): the same behaviour, with past timestamps.
- `app.cli remove-sim-data`: removes every simulated record, device, account and demo area.

## Frontend
- **Overview** (`/admin`): five KPI tiles, the 14-day intake chart, a camera tile with the latest classification and photo, and Storage, Compost and Devices cards, as in mockup `admin/01`. Refreshes every 30 s.
- **Operations** gets a sub-menu, with one page each:
  - Intake: table with Today / This week / This month and a search
  - Segregation: compliance per purok, with bars
  - Sorting: camera classifications and sorted quantities
  - Inventory: per-area capacity cards and a stock table
  - Compost: batches, plus a selected batch's 24 h temperature/moisture chart against the ranges
  - Live camera: the camera layout from the mockup, read-only
- Reuse `ui.tsx`, the `api()` client and the query-hook pattern. Load the **dataviz** skill before building the charts.

## Order of work (each step ends working and committed)
1. Tables + migration; operator write API for deliveries and segregation + tests.
2. Classifications, sorting and stock ledger + tests.
3. Compost batches, readings and activities; device readings and CV suggestions + tests.
4. Read API (`/operations/*`, `/overview`) + tests.
5. The `sim` service (setup, run), the `sim-backfill` and `remove-sim-data` commands, and a compose profile. Run it and see data flow.
6. Frontend: the Overview dashboard.
7. Frontend: the six Operations pages.
8. Browser test `admin-03-operations.spec.ts`: after a backfill, the dashboard and each Operations page show data, and a delivery posted through the API appears in Intake.
9. Roadmap, README, testing doc and session note.

## Tests that must pass
- **Operator writes:**
  - an admin or staff session gets 403
  - weights must be above 0
  - a segregation check can't happen twice, and wet + dry way over the received weight is refused
  - sorting can't go below zero
  - a confirmed classification records whether it was changed
- **Devices:**
  - a reading with a wrong key gets 401
  - a compost reading lands on the sensor's batch
  - a CV suggestion creates a pending classification
- **Reads:**
  - compliance % per purok is right on known data
  - stock per area equals the sum of its movements
  - the overview KPIs match the records
- **Simulator commands:**
  - the backfill creates about 40 days
  - `remove-sim-data` leaves real data untouched
- **Overall:** all earlier tests still pass, Ruff is clean, the build passes, and all browser tests pass.

## Not in Phase 3
- **Operator and staff screens.** Only the operator *API* is built.
- **Approvals, outgoing sales, adjustments** (Phase 4).
- **Alerts** (Phase 5).
- **Predictions and anomaly flags** (Phase 6). The backfilled data is shaped so they'll have something to find.
- **Offline recording, a real camera stream, MQTT.**

## Before starting
C: has **22 GB free**. Phase 3 adds a small Python image for the simulator (about 150 MB) and some data, which is fine. Phase 6's ML images will need the space freed.
