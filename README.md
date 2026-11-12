# SapulMRF

**SapulMRF: An IoT and AI-Based Material Recovery Facility Management System for Barangay Sapul, Calapan City.**

This repo holds the real system. The admin, operator and staff screens are built, following `docs/roadmap.md`. `docs/deployment.md` covers the production setup, and `docs/device-contract.md` what devices send. The clickable design reference and prototype are in `C:\dev\sapulmrf-prototype`. The ESP32 drop-off kiosk and its camera bridge (separate repo, not yet connected to this API) are in `C:\dev\sapulmrf-kiosk`.

## Stack
FastAPI (Python 3.12), PostgreSQL 16, React + TypeScript + Vite + Tailwind v4, all on Docker.

## Run locally
With Docker Desktop running:

```
copy .env.example .env      (then change DB_PASSWORD)
docker compose up -d
```

| What | Where |
|---|---|
| Web app | http://127.0.0.1:5174 |
| API health | http://localhost:8001/health |
| API docs | http://localhost:8001/docs |
| Adminer (DB) | http://localhost:8081 (server `db`, user/password from `.env`) |

The first `up` takes a few minutes while the web container installs npm packages. The `worker` container runs the alert checks every 30 seconds (`docker compose logs -f worker` shows what it opens and resolves).

Then set up the database and your own administrator account (you'll be asked for a password):
```
docker compose exec api alembic upgrade head
docker compose exec -it api python -m app.cli create-admin
```
Log in at http://127.0.0.1:5174 with that account. After pulling new code, run `alembic upgrade head` again.

Usernames ignore capitals. IoT devices are registered in Settings › IoT devices; each gets a key, shown once, which the device sends in an `X-Device-Key` header to `POST /devices/heartbeat` to show as online.

## Open the app (every time)
**One shot (cmd):** start Docker Desktop, then paste this. It starts only the database, API and website, waits until they're healthy, then opens the browser:
```
cd /d C:\dev\sapulmrf && docker compose up -d --wait web && start http://127.0.0.1:5174
```
With the AI summary too (the model warms up for 1–4 min after this):
```
cd /d C:\dev\sapulmrf && docker compose up -d --wait web && docker compose --profile ai up -d ollama && start http://127.0.0.1:5174
```
Stop: `cd /d C:\dev\sapulmrf && docker compose --profile sim --profile ai down`

Step by step:
1. Start **Docker Desktop** and wait until it says "Engine running".
2. In a terminal in `C:\dev\sapulmrf`:
   ```
   docker compose up -d
   ```
3. Wait until `docker compose ps` shows `api`, `db` and `web` as `healthy` (about 30 s; a few minutes the first time).
4. Open http://127.0.0.1:5174 and log in.

Optional extras:
| For | Run | Notes |
|---|---|---|
| Live simulated data | `docker compose --profile sim up -d sim` | Stop with `docker compose stop sim` |
| AI report summaries | `docker compose --profile ai up -d ollama` | Needs `OLLAMA_URL=http://ollama:11434` in `.env` (then `docker compose up -d api`). Ready when `docker compose exec ollama ls /tmp/ready` prints the file, 1–4 min after start. Close games and Discord first; it needs about 4.6 GB of GPU memory. See `docs/report-findings-plan.md` |

When it doesn't work:
| What you see | Fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop isn't running. Start it, then step 2 again |
| The page doesn't load | Wait for `web` to be healthy; check `docker compose logs web` |
| "Something went wrong" or blank lists | `docker compose restart api`, or `docker compose logs api` for the error |
| Errors after pulling new code | `docker compose exec api alembic upgrade head` |
| "The AI summary isn't available" | The `ollama` service isn't up, isn't ready yet, or `OLLAMA_URL` is missing from `.env`. The findings still show |

Stop everything with `docker compose --profile sim --profile ai down`. Your data is kept.

## Daily commands
```
docker compose ps                         status
docker compose logs -f api                API logs
docker compose exec api pytest            backend tests
docker compose exec api ruff check .      lint
docker compose exec api alembic upgrade head    apply migrations
docker compose down                       stop (data is kept in the db_data volume)
```

## Editor setup (VS Code)
The API runs in Docker, so Windows Python doesn't have its packages and VS Code underlines the imports. Give the editor its own copy (Python 3.12, like the container), once and after `requirements.txt` changes:
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
docker compose --profile sim up -d sim                                     live data
docker compose exec api python -m app.simulator remove                     delete all of it
```
Details in `sim/README.md`.

## Layout
- `api/`: FastAPI app (`app/`), Alembic migrations (`migrations/`), tests (`tests/`)
- `web/`: React admin app. Design tokens live in `src/index.css`.
- `sim/README.md`: the simulator (code in `api/app/simulator.py`) that stands in for the devices, camera and operator
- `docs/roadmap.md`: the plan. `docs/phase-1-plan.md`: what Phase 1 built. `docs/testing.md`: how to run and write tests.

## Tests
```
docker compose exec api pytest          API tests (own _test database)
cd web && npm run test:e2e              browser tests (see docs/testing.md for first-time setup)
```
