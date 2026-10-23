# Phase 1 plan: accounts and access
_Drafted 2026-10-23. Needs a go-ahead before any code._

**Covers:** ADM-01 (log in), ADM-02 (manage accounts), ADM-03 (roles and permissions), ADM-21 (log out securely) and the logging half of ADM-20 (activity log).

**Done looks like:** the admin logs in at http://localhost:5174, sees the green admin layout, creates/edits/disables users in the 3 roles, turns staff screens on or off per person, reads the activity log, and logs out. A wrong password, a disabled account or a non-admin hitting an admin page are all refused.

## Decisions (my calls, override any)
- **Server-side sessions in an httpOnly cookie, not JWT in the browser.** Logout really ends the session (the row is deleted), JavaScript can't read the cookie, and there's no token-refresh logic to build. Sessions expire after 8 hours.
- **Passwords hashed with argon2** (`pwdlib`). The API never returns a password or its hash.
- **No default admin password in the code.** The first admin is created by a command: `docker compose exec api python -m app.cli create-admin`.
- **Lockout:** 5 wrong passwords for a username → locked for 5 minutes.
- **Exactly 3 roles,** as approved: `admin`, `operator`, `staff`. Admin and operator abilities are fixed by role. Staff get per-person grants for the "according to authorization" screens: segregation compliance, predictions, alerts, live camera.
- **Modular monolith layout:** each feature module has `router.py → service.py → models.py`, plus `schemas.py`.

## Backend (`api/app/`)
| Module | Contents |
|---|---|
| `core/` | `config.py` (settings), `db.py` (engine, `get_db` dependency), `security.py` (hash/verify, session tokens), `deps.py` (`current_user`, `require_role("admin")`) |
| `users/` | `User` model (name, unique username, password hash, role, active, last login, failed attempts, locked until). Routes: `GET /users`, `POST /users` (201), `PATCH /users/{id}` (edit, disable, reset password) |
| `auth/` | `Session` model (hashed token, user, expires). Routes: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| `access/` | `StaffAccess` model (user, screen, granted). Routes: `GET /access`, `PUT /access/{user_id}` |
| `activity/` | `ActivityLog` model (when, who, action, record). `log()` helper called by the services. Route: `GET /activity` with user/date filters |
| `cli.py` | `create-admin` command |

- One Alembic migration creates the 4 tables.
- All admin routes use `require_role("admin")`. Everything except login and health needs a session.

## Frontend (`web/src/`)
- **Libraries:** React Router, TanStack Query, react-hook-form + zod.
- **`api/`:** one `fetch` wrapper (sends the cookie, turns 401 into a redirect to login) plus a query hook per resource.
- **`app/`:** routes and an auth guard. `/login` is public; everything under `/admin` needs an admin session.
- **`layout/`:** the admin shell from the mockup: dark-green sidebar (Overview, Approvals, Operations, Insights, Settings), top bar with the user menu and Log out.
- **`features/auth/`:** the existing login page, wired to `/auth/login`, showing the error message on failure.
- **`features/users/`:** Settings › Users table, plus the add/edit drawer (name, username, role, temporary password, active).
- **`features/access/`:** Settings › Roles and permissions, with the per-staff checkboxes.
- **`features/activity/`:** Settings › Activity log, with filters.
- Pages from later phases show a simple "Coming in Phase N" placeholder, so the sidebar already works.

## Order of work (each step ends working)
1. Models + migration + `create-admin`. You can log into Adminer and see your admin row.
2. Auth routes + tests. Log in and log out from `/docs`.
3. Frontend: router, guard, admin layout, working login and logout.
4. Users: API + tests, then the Users page and drawer.
5. Staff access: API + tests, then the Roles page.
6. Activity log: logging in services + `GET /activity`, then the page.
7. One Playwright end-to-end test: log in → create a staff user → grant a screen → log out (set up with the `e2e-setup` skill).

## Tests that must pass
- Login: right password ok; wrong password 401; disabled user refused; 6th try within 5 minutes locked.
- Logout: after logout, `/auth/me` returns 401.
- Roles: an operator or staff session gets 403 on `/users`, `/access` and `/activity`.
- Users: duplicate username → 409; the response never contains a password or hash; new users get 201.
- Activity log: login, user create/edit and access changes each write one row.
- Ruff clean; `npm run build` passes; the Playwright test passes.

## Not in Phase 1
- Password reset by email (the admin resets passwords; email isn't in scope).
- Two-factor login.
- Operator and staff screens.
- Master data and devices (Phase 2).

## Before starting
C: is down to **23 GB free** (it was 32 GB earlier today). Phase 1 adds only small packages, but free space before Phase 3 and Phase 6.
