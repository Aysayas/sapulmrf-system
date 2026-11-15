# SapulMRF

**SapulMRF: An IoT and AI-Based Material Recovery Facility Management System for Barangay Sapul, Calapan City.**

This repo holds the real system: the admin, operator and staff screens, following `docs/roadmap.md`.

| Other docs | What's in them |
|---|---|
| `docs/start-up.md` | Starting the website and the kiosk together, in order |
| `docs/PROJECT_GUIDE.md` | The whole system explained with diagrams: data model, flows, rules, tests |
| `docs/deployment.md` | The production setup |
| `docs/device-contract.md` | What devices send |
| `docs/testing.md` | Running and writing tests |

The ESP32 drop-off kiosk and its camera bridge are a separate repo, `C:\dev\sapulmrf-kiosk`. The clickable design prototype is in `C:\dev\sapulmrf-prototype`.

## Open and close (every day)

Double-click in `C:\dev\sapulmrf`:

| To | Double-click | What it does |
|---|---|---|
| **Open** | `start.cmd` | Starts Docker Desktop if needed, starts everything (database, API, website, worker, Adminer), waits until it's healthy, then opens http://127.0.0.1:5174 |
| **Close** | `stop.cmd` | Stops every container, including the simulator. Your data is kept |

`start.cmd sim` also starts the simulated live data.

Or paste one line. The `cd` part works from any folder.

| | cmd | PowerShell |
|---|---|---|
| Open | `cd /d C:\dev\sapulmrf && docker compose up -d --wait && start http://127.0.0.1:5174` | `cd C:\dev\sapulmrf; docker compose up -d --wait; start http://127.0.0.1:5174` |
| Close | `cd /d C:\dev\sapulmrf && docker compose --profile sim down` | `cd C:\dev\sapulmrf; docker compose --profile sim down` |

Docker Desktop must be running for the one-liners (`start.cmd` starts it for you). The first start takes a few minutes while the website installs its packages; after that, about 30 seconds.

| What | Where |
|---|---|
| Website | http://127.0.0.1:5174 |
| API health | http://localhost:8001/health |
| API docs | http://localhost:8001/docs |
| Adminer (database) | http://localhost:8081 (server `db`, user and password from `.env`) |

## First time on this computer
1. Copy the settings file, then change `DB_PASSWORD` in `.env`:
   ```
   copy .env.example .env
   ```
2. Double-click `start.cmd`.
3. Set up the database and your own administrator account (it asks for a password):
   ```
   docker compose exec api alembic upgrade head
   docker compose exec -it api python -m app.cli create-admin
   ```
4. Log in at http://127.0.0.1:5174.

After pulling new code, run `docker compose exec api alembic upgrade head` again.

Usernames ignore capitals. IoT devices are registered in Settings › IoT devices. Each gets a key, shown once, which the device sends in an `X-Device-Key` header.

## What runs

| Container | Job |
|---|---|
| `db` | PostgreSQL 16. The data lives in the `db_data` volume, so stopping never deletes it |
| `api` | FastAPI on port 8001. Reloads when you save a file in `api/app` |
| `web` | The React website on port 5174 |
| `worker` | Runs the alert checks every 30 seconds and saves the day's forecasts. See what it does with `docker compose logs -f worker` |
| `adminer` | A database browser on port 8081 |
| `sim` | Only with `--profile sim`. Stands in for the devices and an operator |

**Ask SapulMRF** (Analyze › Ask SapulMRF) answers admins' questions about the MRF's data, explains words and shows how to do things on the website. It needs no extra container and no AI model: it runs inside `api`, offline. The design is in `docs/superpowers/specs/2026-11-14-ask-sapulmrf-design.md`.

## When it doesn't work

| What you see | Fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop isn't running. Use `start.cmd`, or start Docker Desktop and wait for "Engine running" |
| The page doesn't load | Wait until `docker compose ps` shows `web` as healthy; check `docker compose logs web` |
| "Something went wrong" or blank lists | `docker compose restart api`, or read the error in `docker compose logs api` |
| Errors after pulling new code | `docker compose exec api alembic upgrade head` |
| Alerts or forecasts never update | The worker isn't running. `docker compose up -d worker` (`start.cmd` starts it) |

## Daily commands
```
docker compose ps                               what's running, and whether it's healthy
docker compose logs -f api                      API logs
docker compose exec api pytest                  backend tests
docker compose exec api ruff check .            lint
docker compose exec api alembic upgrade head    apply migrations
docker compose --profile sim down               stop everything (data is kept)
```

## Editor setup (VS Code)
The API runs in Docker, so Windows Python doesn't have its packages and VS Code underlines the imports. Give the editor its own copy (Python 3.12, like the container), once and again after `requirements.txt` changes:
```
cd api
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```
`.vscode/settings.json` already points VS Code at `api/.venv`. It's for the editor only: run and test the API in Docker as above.

## Simulated data
Until Rhendel's devices are connected, the simulator fills the Overview and Operations pages:
```
docker compose --profile sim run --rm sim python -m app.simulator setup    once
docker compose exec api python -m app.simulator backfill --days 40         40 days of history
docker compose --profile sim up -d sim                                     live data (or: start.cmd sim)
docker compose exec api python -m app.simulator remove                     delete all of it
```
Details in `sim/README.md`.

## Layout
- `api/`: the FastAPI app (`app/`), Alembic migrations (`migrations/`), tests (`tests/`). Ask SapulMRF is `app/assistant/`.
- `web/`: the React website. Design tokens are in `src/index.css`.
- `sim/README.md`: the simulator (code in `api/app/simulator.py`) that stands in for the devices, camera and operator.
- `docs/roadmap.md`: the plan. `docs/testing.md`: how to run and write tests.

## Tests
```
docker compose exec api pytest          API tests (their own _test database)
cd web && npm run test:e2e              browser tests (see docs/testing.md for first-time setup)
```
