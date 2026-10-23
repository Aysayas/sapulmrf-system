# Phase 5 plan: alerts

## Context
Phase 4 is done in `C:\dev\sapulmrf` (100 API tests, 13 browser tests). Phase 5 covers:
- **ADM-10:** monitor alerts and notifications.
- **OPR-19 / OPR-20, API only:** operators acknowledge alerts and report device problems or incorrect records. The operator screens come with the operator side.

The data to check already exists: compost ranges and storage alert levels (Settings › Ranges and limits), each storage area's capacity, device heartbeats (online means seen within 2 minutes), and compost readings. Nothing watches them yet.

Wireframes: admin `12-alerts` (Open / Problem reports / Acknowledged), admin `01-overview` ("Open alerts" tile), operator `08b-report-problem`, IoT `44-compost-out-of-range`.

## Decisions
Your answers:
- **Compost alerts wait 10 minutes:** an alert opens only when a batch's readings have stayed outside the range for 10 minutes, and it clears after 10 minutes back in range. A single sensor spike doesn't alert.
- **The bell is a count of open items:** open alerts plus open problem reports, with a short list linking to them. No per-person read/unread.
- **In the app only:** no SMS or email until the server and a provider are chosen.

My calls (override any):
- **Three alert kinds:**
  - `compost`: an open batch above or below its temperature or moisture range.
  - `device`: an active device that has reported before and has now been silent for over 2 minutes ("disconnected").
  - `storage`: an area at or above its alert % of capacity ("almost full").
- **Lifecycle:** at most one open alert per kind and subject (batch, device or area). When the condition clears, the alert is **resolved** automatically ("Reconnected 10:20 AM"). **Acknowledging** records who saw it and when. It moves to the Acknowledged tab but stays open until resolved, so a full area doesn't vanish just because someone clicked.
- **Checks run in a small `worker` service** (same image as the API, `python -m app.alerts.worker`), every 30 seconds. One function, `run_checks(db, now)`, does all three kinds, so tests can call it directly with a fixed time. Running it twice changes nothing, so a restart or a second worker is harmless.
- **Problem reports:** an operator sends `device` (pick a device) or `record` (a record reference such as `D-0139`, plus what it should be). Codes are `R-001`. The admin resolves a report with a note. Fixing the record itself stays a manual step (Phase 4 adjustments, or a later edit screen).
- **Who sees what:** admins and operators see and acknowledge alerts. Staff see them only with the existing `alerts` screen grant (read-only); staff screens come later.
- **Activity log:** acknowledgements, reports and report resolutions are logged. The worker's opening and resolving are not, because they would flood the log; the alert rows keep that history.
- **Overview:** an "Open alerts" tile is added (6 tiles, as in the wireframe), with the sub-text "1 compost · 1 storage". Compost batch rows mark an open alert.
- **Simulator:** the live loop now and then pauses one compost sensor's heartbeat for about 5 minutes, and pushes a batch out of range for about 15 minutes, so alerts open and resolve on their own. No backfilled alert history.

## Backend (router → service → models + schemas)
| Module | Tables | Routes |
|---|---|---|
| `alerts/` (new) | `alerts` (id, kind, subject_id, title, details, opened_at, last_value, resolved_at, acknowledged_by/at); `problem_reports` (id, code, kind device/record, device_id, record_ref, details, reported_by/at, status open/resolved, resolved_by/at, note) | `GET /alerts?state=open/acknowledged/resolved` (admin, operator, staff with grant), `POST /alerts/{id}/acknowledge` (admin, operator), `GET /alerts/summary` (bell and Overview counts plus the latest 5), `POST /problems` (operator), `GET /problems` (admin), `POST /problems/{id}/resolve` (admin, note required) |

- **The checks reuse what exists:** `devices.service.status()` for online/offline, `settings.service.get()` for ranges, `operations.service.area_fill()` for storage %, and `CompostReading` for the readings window.
- **Uniqueness:** a partial unique index on `(kind, subject_id) WHERE resolved_at IS NULL` guarantees one open alert per subject, even with two workers.
- **Docker:** a `worker` service in `docker-compose.yml`, always on like `api` and restarted on failure.

## Frontend
- **Alerts page** (`/admin/alerts`, a new sidebar link under Monitor with the open count), matching wireframe `12`:
  - Open: Alert, Details, Since, Seen by, Acknowledge.
  - Problem reports: Code, What, Device or record, Details, From, When, and a Resolve drawer with a note.
  - Acknowledged, and Resolved (the last 30 days).
- **Bell** in the top bar with the open count. Its menu lists the latest 5 open items, each linking to the Alerts page tab, plus "See all alerts".
- **Overview:** the "Open alerts" tile, and an alert marker on compost batch rows.
- Reuse `Table`, `Period`, `when` (`features/operations/shared.tsx`), `Drawer`, `Toast`, `Badge`, `btn` (`components/ui.tsx`), the tab pattern from `ApprovalsPage.tsx`, and the hook pattern in `api/approvals.ts`.

## Order of work (each step ends working and committed)
1. Alerts table and `run_checks` for the three kinds, with tests at fixed times (opens, doesn't duplicate, waits 10 minutes for compost, resolves).
2. Alerts API (list, acknowledge, summary) and the access rules, with tests.
3. Problem reports API, with tests.
4. Worker service in compose; simulator disturbances; run it against the dev DB and confirm alerts open and resolve.
5. Frontend: Alerts page (four tabs, resolve drawer) and sidebar count.
6. Frontend: bell in the top bar, and the Overview tile and compost marker.
7. Browser test `admin-05-alerts.spec.ts`:
   - an e2e storage area filled past its alert level shows an open alert after a check run
   - the admin acknowledges it and it moves to Acknowledged
   - an operator's problem report shows on the bell and is resolved with a note

   `remove-test-data` clears e2e alerts and reports.
8. Roadmap ticks, README/testing notes, vault session note.

## Tests that must pass
- **Compost:** out of range for under 10 minutes → no alert; at 10 minutes → one alert naming the reading and range; back in range for 10 minutes → resolved.
- **Device:** silent past 2 minutes → "disconnected"; a heartbeat → resolved; a never-connected or inactive device → no alert.
- **Storage:** at the alert % → alert; below → resolved.
- **Lifecycle:** checks run twice → still one alert. Acknowledging doesn't resolve. Acknowledging twice → 409.
- **Access:** staff without the `alerts` grant → 403; staff can't acknowledge; only operators report problems; only admins resolve reports, and a resolve needs a note (422).
- **Overall:** every Phase 1–4 test still passes, Ruff is clean, `npm run build` passes, and all browser tests pass.

## Verification
- `alembic upgrade head`, `pytest`, `ruff check .`
- `docker compose up -d worker`; watch the simulator's disturbances open and resolve alerts on the Alerts page within a few minutes.
- `npm run test:e2e`, then `remove-test-data`.
- Screenshots of the Alerts tabs, the bell menu and the Overview, compared with wireframes `12` and `01`.

## Not in Phase 5
- SMS or email, and per-person read/unread notifications.
- Operator and staff screens (the API is ready for them).
- Anomaly flags and predictions (Phase 6). Alert history in the backfill.
