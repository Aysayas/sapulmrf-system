# SapulMRF

**SapulMRF: An IoT and AI-Based Material Recovery Facility Management System for Barangay Sapul, Calapan City.**

This repo holds the real system. The admin side is being built first, following `docs/roadmap.md`. The clickable design reference and prototype are in `C:\dev\sapulmrf-prototype`.

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
| Web app | http://localhost:5174 |
| API health | http://localhost:8001/health |
| API docs | http://localhost:8001/docs |
| Adminer (DB) | http://localhost:8081 (server `db`, user/password from `.env`) |

The first `up` takes a few minutes while the web container installs npm packages.

Then set up the database and your own administrator account (you'll be asked for a password):
```
docker compose exec api alembic upgrade head
docker compose exec -it api python -m app.cli create-admin
```
Log in at http://localhost:5174 with that account. After pulling new code, run `alembic upgrade head` again.

## Daily commands
```
docker compose ps                         status
docker compose logs -f api                API logs
docker compose exec api pytest            backend tests
docker compose exec api ruff check .      lint
docker compose exec api alembic upgrade head    apply migrations
docker compose down                       stop (data is kept in the db_data volume)
```

## Layout
- `api/`: FastAPI app (`app/`), Alembic migrations (`migrations/`), tests (`tests/`)
- `web/`: React admin app. Design tokens live in `src/index.css`.
- `sim/`: device, camera and operator simulators (Phase 3)
- `docs/roadmap.md`: the plan. `docs/phase-1-plan.md`: what Phase 1 built. `docs/testing.md`: how to run and write tests.

## Tests
```
docker compose exec api pytest          API tests (own _test database)
cd web && npm run test:e2e              browser tests (see docs/testing.md for first-time setup)
```
