# Plan: finish the operator screens, staff screens and Isolation Forest flags (multi-agent workflow)

## Context
You asked to build all three remaining pieces at once with a multi-agent workflow:
1. the rest of the operator screens
2. the staff screens (STF-02 to 09)
3. Isolation Forest in place of the z-score weight flags

Nothing is built yet. The first workflow step saves this plan as `docs/operator-staff-plan.md`, matching your plan-first rule.

**Not settled with Rhendel:** which screens the IoT floor station covers. Since you said to build, I'd build every web wireframe. If the station later covers a flow too, the web screen is still a usable fallback.

## Decisions (defaults; say if you want any changed)
- **Left out, because they belong to the floor station or need hardware:** offline recording (OPR-09), the floor station PIN, and live scale capture. Web intake uses typed weights, which the API already accepts (`weighed_by: manual`); correcting a scale weight stays as it works today.
- **Phone first:** all new operator screens use the existing `/op` shell. Five bottom tabs: Today, Intake, Sort, Storage, More. More holds Segregation, Compost, Outgoing, Alerts, History and Profile.
- **Staff side is view only, at `/staff`:** Overview, Records (tabs by grant, with the "no access" state from wireframe `02d`), Reports, Notifications. It's laptop-friendly and reuses the Operations page parts. Staff reports use a grant if `access/models.py` SCREENS has one; if it doesn't, they get the exported-reports list only after a grant is added.
- **STF-10 (notifications)** is in-system only, read from alerts. No SMS or email.
- **Isolation Forest replaces only the weight check.** The gap check stays a rule (it's an arithmetic comparison).
  - One model per purok, fitted on that purok's last 100 weights when a delivery is recorded (minimum 10), with a fixed `random_state` so results repeat.
  - The admin's sensitivity setting becomes "% of records to flag" (`anomaly_pct`, default 2%), replacing `anomaly_sd`, with a migration and a Ranges page change.
  - The "usual range" text stays, for explaining a flag.
  - Existing flags stay as they are. New ones use the model.

## API gaps to fill first
- `POST /inventory/transfers` (operator): moves stock between areas as two `StockMovement` rows of kind `transfer`. It refuses more than the source holds or a move past the destination's capacity, and it logs the move. Same material only; bags move with it.
- `GET /activity/mine` (any logged-in user): My operation history.
- `PATCH /auth/me` (name, contact number) and `POST /auth/me/password` (needs the current password, at least 8 characters, and logs it). `users.contact` is a new column, with a migration.
- `GET /access/me`: a staff member's own grants, for hiding tabs. The API's existing checks stay the real enforcement.
- Work lists, if the current routes don't give them: deliveries awaiting segregation, deliveries awaiting sorting, pending classifications, batches for operators.

## Workflow (about 10 agents)
Stages run in this order; only stage 3 is parallel. pytest and the browser tests share one test database and one app, so anything running them is serial.

1. **Backend (1 agent):** the plan doc, the API gaps above, Isolation Forest, tests. Runs `pytest` and `ruff`, then commits.
2. **Shell (1 agent):** role routing for `/staff`, new tabs, More page, `StaffLayout`, a stub page for each screen, and API hooks. Runs `npx tsc --noEmit`, then commits. After this, each slice owns only its own files.
3. **Screens (4 agents in parallel, one set of files each, no commits, type check only):**
   - Operator Today, Intake (`01`, `02`, `02b`, `02c`), Segregation (`03`–`03c`)
   - Operator Sorting (`04`–`04c`), Compost (`06`–`06c`)
   - Operator Storage transfer (`05b`), History (`09`), Profile (`10`)
   - Staff Overview, Records, Reports, Notifications (`staff/01`–`04`)
4. **Integrate and browser-test (1 agent):** runs the build, commits the screens, adds `operator-02-daily-work.spec.ts` (delivery → segregation → sorting → transfer → compost activity → history → password change) and `admin-08-staff.spec.ts` (grant on and off changes what staff can see and reach). Runs the full browser suite and fixes failures.
5. **Review (2 agents, read-only):** one for access control and data rules (staff can't write or see ungranted data, operators see only their own history, transfer and password rules). One for the ML change and whether screens match their wireframes.
6. **Fix (1 agent):** fixes confirmed findings, re-runs the tests, commits, updates the roadmap, `docs/testing.md` and the plan's results.

Rules every agent gets: use `tsc --noEmit` only, never `tsc -b`; use `http://127.0.0.1:5174`; never read or print `.env` values; move files to `_to_delete/` rather than deleting them; commit locally only, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; never push.

`docs/ai-assistant-plan.md` stays untouched and uncommitted, so agents add files by name instead of `git add -A`.

## After the workflow, I check it myself
- Start the stack with the simulator. Run `alembic upgrade head`, `pytest`, `ruff check .`, `npx tsc --noEmit`, `npm run build`, `npm run test:e2e`, then `remove-test-data`.
- **Isolation Forest on real history:** re-run the check over the 40 days of simulated deliveries and report how many of the planted 2% outliers it catches and how many false flags it raises, compared with the z-score. If it does worse, I tell you rather than call it an upgrade.
- Screenshots at 390 × 844 of each operator screen and at 1440 × 900 of each staff screen, compared with the wireframes.
- Write the vault session note.

## Risks
- **Cost:** this is a large run, about 10 agents, each reading and writing many files.
- **Isolation Forest on one number** (weight only) may catch about what the z-score does. It's a learned model and easier to defend as ML, but it may not be more accurate.
- **Scope:** the roadmap lists operator and staff screens as out of scope, and I'd update that line.
