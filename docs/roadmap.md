# SapulMRF Admin Side Roadmap
_Updated 2026-11-01_

## Destination
By the end of this semester, the **Barangay Administrator side** of SapulMRF runs on a real backend and database, on local Docker. It covers all 21 admin requirements (ADM-01 to ADM-21) and shows the four emerging technologies (AI, ML, IoT, computer vision) with live data. Until Rhendel's devices and CV model are ready, that data comes from simulators. Isiah builds it. The designs already exist in `C:\dev\sapulmrf-prototype` (wireframes, mockups, working HTML prototype). After the semester, the same Docker stack moves to the group's home server.

## Decisions so far
- **Python everywhere: a FastAPI backend that also runs the ML and CV logic.** ML and CV libraries are native to Python, so there's one backend language. (source: user, round 2)
- **PostgreSQL.** It's good for time-series sensor readings and analytics queries, and works well with Python. (user, round 2)
- **React frontend (Vue considered and set aside).** It's the frontend in the chosen option, and the team already knows React from Vencio's. The user is learning both React and Vue at school, so Vue offers no extra benefit, and switching would mean re-picking the libraries while FastAPI is still new. (user, round 2 and 2026-10-23 follow-up)
- **The system must show four emerging technologies: AI, ML, IoT, CV.** This is a capstone requirement as the user stated it. (user, round 1)
- **No required language or framework from the course or panel.** (user, round 1)
- **Local Docker for development; the group's own home server for production.** No paid hosting. (user, round 3)
- **Isiah builds the admin side alone this semester, both frontend and backend.** Christina isn't on the admin frontend this time, so there's no hand-off and one person owns the API contract on both ends. (user, round 3 and follow-up)
- **Rhendel owns the hardware side: IoT devices, CV model training and the server.** So the admin side needs clear data contracts with him. (user, round 4)
- **Predictions start as statistics and become ML later.** Moving averages, storage outlook and z-score anomaly flags came first, because no real MRF data exists yet. The weight flags now use the modified z-score (MAD), chosen over Isolation Forest by measurement, and the forecasts use a scikit-learn Ridge model next to the moving average. (user, round 4)
- **Simulators in Docker stand in for the devices and the CV model.** They're swapped for Rhendel's real ones later. (user, round 5)
- **Scope: all 21 admin requirements, laid out in detail.** (user, round 5: "be detailed about this")
- **Containers use Python 3.12, not the laptop's Python 3.14.** Many ML libraries don't support 3.14 yet. (verified: `python --version` = 3.14.4)

## Resources

### Your laptop (scanned 2026-10-23)
| Item | Found | Verdict / action |
|---|---|---|
| CPU | Ryzen 7 7735HS, 8 cores / 16 threads | Plenty |
| RAM | 16 GB (only 2.1 GB free at scan time) | OK. Close heavy apps while the stack runs |
| GPU | RTX 4050 Laptop, 6 GB (driver 582.05) | Enough for small model training (Rhendel's call) |
| Disk C: | **33 GB free of 475 GB** | **Biggest risk.** Free up to 80 GB+ before pulling ML images; datasets and Postgres volumes grow |
| Docker | Engine 29.6.2, Compose v5.3.1, WSL2 | Installed. **Limited to 4 CPUs / 5.8 GB.** Raise it to 6 CPUs / 8 GB in `%UserProfile%\.wslconfig` |
| Node / Git | Node 25.8.1, Git 2.55 | OK. The web container pins Node 22 LTS |

### Docker services (local `docker compose`)
| Service | Image / tool | Why |
|---|---|---|
| `db` | `postgres:16` + named volume | Main database: records, readings, audit log |
| `api` | `python:3.12-slim` + FastAPI, Uvicorn | Admin API, auth, stats/ML jobs, reports |
| `web` | `node:22` + Vite dev server | React admin app with hot reload |
| `sim` | `python:3.12-slim`, small script | Fake scale, compost sensors, camera suggestions, device heartbeats, and operator actions so approvals have data |
| `adminer` (or pgAdmin) | `adminer` | Look inside the database while developing |
| `mosquitto` *(only if MQTT is picked)* | `eclipse-mosquitto:2` | IoT message broker; see fog of war |

### Backend libraries (Python, `api`)
- **FastAPI, Uvicorn:** the API and the auto-generated `/docs` test page.
- **SQLAlchemy 2, Alembic, psycopg:** database models and migrations.
- **Pydantic v2:** request and response validation.
- **pwdlib (argon2) or passlib/bcrypt, plus PyJWT or signed session cookies:** login and roles (ADM-01, 02, 03, 21).
- **pandas and numpy now, scikit-learn later (Prophet was skipped, see Phase 6):** forecasts and anomaly flags (ADM-12 to 15).
- **APScheduler (or a FastAPI background task):** periodic checks for alerts and predictions.
- **ReportLab, plus the csv module:** PDF and CSV reports (ADM-18). WeasyPrint was set aside in Phase 7: it needs Pango/Cairo system libraries in the image.
- **pytest, httpx, Ruff:** tests and lint.

### Frontend libraries (`web`)
- **React, TypeScript, Vite, Tailwind CSS v4:** same as Vencio's. Port the colours and type from `mockup.css`.
- **React Router, TanStack Query:** pages and data fetching/caching.
- **react-hook-form + zod:** forms and validation.
- **Recharts (or Chart.js):** intake chart, compost readings, forecast.
- **Playwright:** end-to-end tests (the `e2e-setup` skill sets it up the same way as Vencio's).

### Tools and accounts
- VS Code with the Python/Pylance, Ruff, ESLint, Prettier, Docker and Tailwind extensions.
- A GitHub private repo under Aysayas (exists), with CI running the tests.
- FastAPI's `/docs` page, or Bruno/Postman, for trying the API.
- No paid services needed.

### Learning (official docs)
- FastAPI tutorial (fastapi.tiangolo.com)
- SQLAlchemy 2.0 unified tutorial and Alembic tutorial
- Docker Compose docs, and Docker Desktop WSL2 GPU support (for Rhendel)
- PostgreSQL docs on time-series indexing
- TanStack Query, React Router, Tailwind v4
- scikit-learn time series and anomaly detection (for the ML-later step)

### Things to agree with Rhendel (contracts)
- **Device reading and CV result:** the current API, retry rules and open questions are in `docs/device-contract.md`, which replaces the earlier draft here.
- **Camera images:** still open with Rhendel: where photos live, and whether `image_id` and `taken_at` replace `image_url`.
- **Server:** the home server's CPU, RAM, OS and network (LAN only, or reachable from the barangay hall?).

## Phases
Each phase ends in something you can demo in the browser. The ADM numbers are from the Notice of Title Approval.

### Phase 0: Workstation and skeleton (target: week 1)
- [ ] Free up C: to 80 GB+ (you do this; the reclaimable space is measured in the 2026-10-23 session note)
- [x] Raise Docker to 6 CPUs / 8 GB (applied: `docker info` shows 6 CPUs / 8.3 GB)
- [x] New repo `C:\dev\sapulmrf` (`api/`, `web/`, `sim/`, `docs/`). The prototype stays as the design reference. First commit `6f0e4aa`
- [x] `docker compose up` brings up db, api, web and adminer. `/health` reports API and DB OK, and the web app shows the login page. Ports: web 5174, API 8001, Adminer 8081 (Vencio's already uses 5173/8000/8080)
- [ ] CI runs the backend tests and the frontend build on every push. The workflow exists, but the last pushed runs (Oct 23) failed in the browser job. A fix is committed locally and unproven until it is pushed.

### Phase 1: Accounts and access (ADM-01, 02, 03, 21, 20 logging)
- [x] Admin logs in and out with a hashed password (argon2). Sessions are server-side, in an httpOnly cookie, and expire after 8 h. 5 wrong passwords lock the account for 5 min
- [x] Admin creates, edits and disables users in the 3 roles. Usernames are unique. Admins can't disable or demote themselves
- [x] Admin grants the staff "according to authorization" screens per person (all off until granted)
- [x] Every login, logout, user change and access change is written to the activity log, with an admin screen to read it (approvals get logged when Phase 4 adds them)

### Phase 2: Setup data (ADM-04, 05, 06)
- [x] Waste categories (RA 9003, seeded), puroks/source areas, recyclable materials (the 4 CV ones, seeded), and storage areas with capacity limits. Deactivate instead of delete
- [x] Register IoT devices. Each gets a device key (shown once, stored hashed) and shows online/offline from its heartbeat (`POST /devices/heartbeat`, `X-Device-Key` header, online = within 2 min)
- [x] Compost temperature and moisture ranges, storage alert levels, the prediction start threshold (days of records), and the unusual-weight limit

### Phase 3: Simulators and live operations view (ADM-07, 08, 09, 19)
- [x] The `sim` service sends deliveries, segregation results, sorted quantities, compost readings, camera suggestions and heartbeats (built into `api/app/simulator.py`, with a 40-day backfill; since Phase 4 its pickups are sale and disposal requests)
- [x] Admin sees intake, sorting and inventory records, segregation compliance per purok, and compost batches with live readings
- [x] Overview dashboard: today's totals, storage capacity, compost status, device status and the last camera result (approvals, income and alerts KPIs wait for Phases 4–5; awaiting segregation, in storage and active batches stand in)

### Phase 4: Approvals and reviews (ADM-11, 16, 17)
- [x] One approvals inbox covering inventory adjustments and outgoing transactions. Approving changes stock; rejecting doesn't (stock is re-checked at approval; compost on hand is tracked from finished batches)
- [x] Review corrected weights and corrected CV classifications (OK / ask to recheck, OK / wrong: marks only, for Phase 6's accuracy numbers)
- [x] Income from recyclables (and compost, if priced) shown from approved sales only (Operations › Outgoing, and the Overview)
- [x] Operator screens to send adjustment and outgoing requests (phone first, at `/op`: Storage, Outgoing and Alerts, with My requests and My reports; see `docs/operator-requests-plan.md`. The rest followed; see Operator and staff screens below)

### Phase 5: Alerts (ADM-10)
- [x] Scheduled checks raise alerts for compost out of range, devices that stop reporting, and storage at its limit (the `worker` service, every 30 s; compost waits 10 minutes both ways; alerts resolve on their own)
- [x] Bell count, an alerts page, acknowledge, and the operator's problem reports (operators send them from `/op/alerts`)
- SMS or email delivery: out of scope for now, per the approved Limitations, and it needs a paid provider.

### Phase 6: Insights with AI/ML (ADM-12, 13, 14, 15)
- [x] Unusual weights (modified z-score per purok; measured comparison in `docs/operator-staff-plan.md`, switch in `docs/flags-mad-plan.md`) and received-vs-sorted gaps are flagged. Admin marks each one valid or incorrect (checked when the record is made; Approvals › Flagged records)
- [x] Intake forecast per category, plus the storage outlook ("Area B full in ~6 days"), shown only after N days of records (Insights; N is `prediction_min_days`, 30)
- [x] Suggested pickup or sale schedule, and predicted vs actual with the percentage error (Objective 5) (forecasts are saved daily, so the error is never hindsight)
- [x] Swap in an ML model behind the same endpoint and compare its error with the stats baseline: done from the start. A scikit-learn Ridge model and the 7-day moving average both run, and the one with the lower 14-day error is used. Prophet was skipped (heavy install, not needed at this data size)

### Phase 7: Reports and audit (ADM-18, 20)
- [x] Intake, segregation, inventory, composting, outgoing and income reports by date range and purok, as PDF and CSV (Insights › Reports; the purok filter applies to intake and segregation, inventory is stock as of now; "Excel" is CSV; export history is kept, and Download rebuilds the file from current data)
- [x] Activity log screen with filters by user and date (plus a custom date range, action groups and Export CSV; report views and exports are logged)

### Phase 8: Hand-off to the real hardware and server (after the core is done)
- [ ] Replace `sim` with Rhendel's devices and CV service, using the agreed contracts
- [ ] Production setup on the home server. `docker-compose.prod.yml`, Caddy, nightly backups and `scripts/deploy.sh` are built and tested on a throwaway local stack (`docs/deployment.md`). Waiting on the server.

### Operator and staff screens (see `docs/operator-staff-plan.md`)
- [x] Operator screens at `/op`: Today, Intake, Segregation (with Undo), Sorting, Storage transfer, Compost, History and Profile
- [x] Staff screens at `/staff`, view only: Overview, Records, Reports and Notifications. No income, and grants decide the rest
- [ ] Settle with Rhendel which of these the IoT floor station covers. Offline recording, the station PIN and live scale capture are left to the station

## Backend improvement pass (2026-11-01)
Findings, measurements and decisions are in `docs/backend-improvement-plan.md`.
- [x] Group 0: findings verified, baselines measured
- [x] Group 1: resend keys, stale counts, locks, input limits
- [x] Group 2: CSV escaping, login limits, verified scale weights, camera grant
- [x] Group 3: worker status, simulator re-login, pinned dependencies
- [x] Group 4: readings survive offline retries. Camera changes wait for Rhendel
- [x] Group 5: fewer queries, smaller first load
- [x] Group 6: phone fit, error states, accessibility, more browser tests
- [x] Group 7: production setup, tested locally only
- [x] Algorithm review: flags, forecasts, scoring, simulator pace, alert titles. Results are in the same doc
- [ ] Group 8: installable phone app and offline recording. Not started; needs HTTPS, a real phone, and to know which phones operators use

## Not yet specified (fog of war)
- The exact end-of-semester date and the Capstone 1 defense date. Blocks: setting phase targets.
- How devices connect: MQTT broker or HTTP POST. Blocks: Phase 3 simulator transport and Phase 8 (the sim speaks HTTP until this is decided).
- The home server's CPU, RAM, OS and network reach (LAN only or internet). Blocks: Phase 8.
- Where CV inference runs (on a device, on the server, or in the API container) and the model format. Blocks: Phase 8, and partly Phase 3's camera view.
- ~~Who builds the operator and staff sides, and when~~ Built; see above.
- ~~How many days of real records before switching from stats to ML~~ Answered in Phase 6: no fixed switch. Both models run once there are `prediction_min_days` (30) days of records, and whichever has the lower error over the last 14 days is used.
- Whether to keep the prototype repo or fold it into `sapulmrf/docs`. Blocks: nothing.

## Out of scope (for this roadmap)
- **Floor station flows on the web:** offline recording (OPR-09), the station PIN and live scale capture. Web intake uses typed weights.
- **IoT firmware, sensor wiring, CV model training:** Rhendel's work.
- **SMS or email notifications:** alerts are in-system only, per the approved Limitations.
- **Accounting:** income tracking is not an accounting system, per the Limitations.
- **Paid cloud hosting:** production runs on the group's home server.
