# Part 1: Wet Waste → Compost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** wet waste recorded in segregation checks becomes a "waiting for compost" balance. Compost batches draw from it. Operators run compost from the kiosk.

**Architecture:**
- The SapulMRF API computes the balance and enforces it in `start_batch`.
- The web operator and admin pages show it.
- The PC bridge relays four new kiosk `op` actions to the existing compost routes, using the operator's session.
- The ESP32 kiosk gets a third operator tile and one Compost screen.

**Tech stack:**
- API: FastAPI + SQLAlchemy (Postgres), pytest
- Web: React + TanStack Query, Playwright
- Bridge: Python
- Kiosk: ESP32-S3 Arduino + LVGL 8.3

**Spec:** `docs/superpowers/specs/2026-11-14-kiosk-operator-processes-design.md` (section "1. Wet → compost").

**Repos:**
- SapulMRF: `C:\dev\sapulmrf`, branch `one-device` (commit it first; the user says "commit").
- Kiosk: `C:\dev\sapulmrf-kiosk\sapulmrf-kiosk`, a new branch `kiosk-compost` from `camera-voting`.

## Global Constraints
- **The balance:** wet waiting = Σ `segregation_checks.wet_kg` − Σ `compost_batches.start_kg`, floored at 0 and rounded to 2 decimals.
- **The cap:** `start_batch` refuses `start_kg > wet_waiting + 0.5` with 422 and the exact message `Only {x} kg of wet waste is waiting for compost.`, where `{x}` is formatted with `:g`.
- **Who:** the compost routes accept `operator` and `admin`. Staff still get 403.
- **Where rules live:** all rules are in the API. The bridge only maps actions to routes; the kiosk only shows screens.
- **Kiosk look:** the existing style (cream/green, big buttons, `T_TAP` heights, `atk_*` fonts). Strings go in the `Str` table in `ui.cpp`, in both languages.
- **Never commit** the kiosk's `SapulMRF_Kiosk/config.h` (Wi-Fi password) or `pc_bridge/kiosk_intake.csv`.
- **Commits:** SapulMRF commits only when the user says "commit".
- **Build safety:** don't run `pio run` while the user is uploading from VS Code. Say when a build is done.

## Review Focus
1. **Undoing a segregation check after its wet kg went into a batch:** the balance must floor at 0, not go negative, and nothing crashes. *Test in Task 1.*
2. **Two batches started at once** (double tap on the kiosk) mustn't both pass the cap. *Task 1 takes an advisory lock before checking.*
3. **Old batches from before this rule** (the demo backfill): the balance stays ≥ 0, and starting a batch with nothing waiting gives the 422 message, not a 500. *Test in Task 1.*
4. **The kiosk with no open batches and 0 kg waiting:** the Start button is disabled and the screen says so, with no blank list. *Task 4 by eye.*
5. **The operator session expiring on the Compost screen:** the kiosk returns Home with "signed out", the same as segregate and sort. *Task 3 bridge check; Task 4 adds `scrCompost` to `isOpScreen`.*

---

### Task 1: API: the wet balance, the cap, admins allowed, the balance exposed

**Files:**
- Modify: `api/app/compost/service.py` (add `wet_waiting`; the cap in `start_batch`)
- Modify: `api/app/compost/router.py:11` (`operator_only` → `require_role("operator", "admin")`, renamed `can_compost`)
- Modify: `api/app/operations/schemas.py` (`CompostView.wet_waiting_kg: float`; `Overview.wet_waiting_kg: float` next to `active_batches`)
- Modify: `api/app/operations/service.py` (fill both from `compost.wet_waiting(db)`)
- Modify: `api/app/simulator.py` (live run: start a batch only when a bay is free and `view["wet_waiting_kg"] >= 10`, with `start_kg` = that number)
- Test: `api/tests/test_compost_balance.py` (new); update `api/tests/test_compost_and_devices.py`

**Interfaces:**
- Produces:
  - `compost.service.wet_waiting(db: DbSession) -> float`
  - JSON fields `wet_waiting_kg` on `GET /operations/compost` and `GET /overview`
  - `POST /compost/batches` and `POST /compost/batches/{id}/activities` are open to admins

- [ ] **Step 1: Write the failing tests** in `api/tests/test_compost_balance.py`.
  - A helper `check(db, world, wet)` adds a `Delivery` plus a `SegregationCheck(wet_kg=wet, dry_kg=0)`.

```python
def test_wet_waiting_is_wet_minus_batches_and_never_negative(db, world):
    check(db, world, 12.0); check(db, world, 8.0)
    assert wet_waiting(db) == 20.0
    db.add(CompostBatch(code="B-1", start_kg=15)); db.commit()
    assert wet_waiting(db) == 5.0
    db.add(CompostBatch(code="B-2", start_kg=50)); db.commit()   # older batches from before the rule
    assert wet_waiting(db) == 0.0

def test_a_batch_cannot_use_more_than_is_waiting(client, db, world, make_user, login):
    check(db, world, 10.0)
    make_user("op", role="operator"); login("op")
    assert client.post("/compost/batches", json={"start_kg": 10.4}).status_code == 201   # 0.5 kg slack
    r = client.post("/compost/batches", json={"start_kg": 1})
    assert r.status_code == 422 and r.json()["detail"] == "Only 0 kg of wet waste is waiting for compost."

def test_undoing_a_check_lowers_the_balance(client, db, world, make_user, login): ...
    # record a check through the API, undo it with DELETE /deliveries/{id}/segregation, assert wet_waiting falls by its wet_kg

def test_admins_can_start_batches_and_see_the_balance(client, db, world, make_user, login):
    check(db, world, 6.0)
    make_user("boss", role="admin"); login("boss")
    assert client.get("/operations/compost").json()["wet_waiting_kg"] == 6.0
    assert client.get("/overview").json()["wet_waiting_kg"] == 6.0
    assert client.post("/compost/batches", json={"start_kg": 6}).status_code == 201
```

- [ ] **Step 2: Run them and see them fail.**
  - Run: `docker compose exec api pytest tests/test_compost_balance.py -q`
  - Expected: FAIL (`ImportError: wet_waiting`).

- [ ] **Step 3: Implement.**
  - `wet_waiting(db)`: two `coalesce(sum(...), 0)` scalars, `max(0.0, round(wet − batches, 2))`.
  - In `start_batch`: first `advisory_lock(db, "compost-start")` (from `app.core.db`, as `request_outgoing` uses it), then the cap check, before the sensor checks.
  - Widen the role. Add the two schema fields and fill them.

- [ ] **Step 4: Update existing tests.**
  - In `test_compost_and_devices.py`, `setup_devices` gains `db, world` and records a 100 kg wet check, so its batch tests pass the cap.
  - `test_operator_staff_api.py:234` (staff get 403) must still pass unchanged.

- [ ] **Step 5: Run all API tests and lint.**
  - Run: `docker compose exec api pytest -q` and `docker compose exec api ruff check .`
  - Expected: all pass (287 + 4 new), ruff clean. `test_simulator` still passes, because the backfill starts batches from its own `wet_pool * 0.8`.

- [ ] **Step 6: Commit** (only after the user's "commit"): `Wet waste waits for compost: a balance, a cap on new batches, admins can compost`.

### Task 2: Web: show the balance and prefill the batch

**Files:**
- Modify: `web/src/api/operations.ts` (`wet_waiting_kg: number` on `CompostView` and the overview type)
- Modify: `web/src/features/operator/CompostPage.tsx`:
  - under the header: "{kg} wet waste waiting for compost"
  - `StartSheet` gets a `waiting` prop, prefills `start_kg`, and has the hint "Up to {kg} waiting"
- Modify: `web/src/features/operator/TodayPage.tsx:44` (the Compost tile sub-label shows `${kg(o.data.wet_waiting_kg)} wet waiting`)
- Modify: `web/src/features/operator/SegregationPage.tsx:98` (the toast's `→ compost` becomes `→ waiting for compost`)
- Modify: `web/src/features/operations/CompostPage.tsx` (the subtitle adds ` · {kg} wet waste waiting`)
- Test: `web/e2e/operator-02-daily-work.spec.ts` (compost part)

**Interfaces:** consumes `wet_waiting_kg` from Task 1.

- [ ] **Step 1: Update the e2e test first.**
  - In the compost section, the operator opens Compost and reads the waiting text.
  - The start sheet's `Wet waste (kg)` input has a value > 0 (prefilled). Fill `5` and start.
  - The test already recorded a delivery and a segregation check earlier in the same run, so the balance covers 5 kg on the shared dev DB. Assert the toast `started · 5 kg wet waste`.
- [ ] **Step 2: Implement the five web changes.**
- [ ] **Step 3: Run checks.**
  - Run: `cd web; npx tsc -b; npx playwright test`
  - Expected: tsc exit 0; 30/30 pass. Then `docker compose exec api python -m app.cli remove-test-data`.
- [ ] **Step 4: Screenshots, by eye** (the temporary `e2e/zz-shots.spec.ts` pattern, deleted after): operator Home tile, operator Compost header plus start sheet, admin Compost subtitle.
- [ ] **Step 5: Commit** (after the user's "commit"): `Show wet waste waiting for compost; prefill new batches`.

### Task 3: Bridge: four compost actions for the kiosk

**Files:**
- Modify: `C:\dev\sapulmrf-kiosk\sapulmrf-kiosk\pc_bridge\kiosk_bridge.py` (`op_request`, plus the protocol comment near line 27)
- Test: the scratchpad `check_compost.py` (new; same style as `check_operator.py`)

**Interfaces:** `op_request(do, m)` returns `(method, path, body, shape)`. New `do` values:

| `do` | Kiosk sends | Route | Reply `data` (shape) |
|---|---|---|---|
| `compost` | — | `GET /operations/compost` | `{"waiting": float, "batches": [{"id","code","day","start_kg"} ...]}` (open batches only, at most `LIST_MAX`) |
| `compost_start` | `kg` | `POST /compost/batches` `{"start_kg": kg, "sensor_id": None}` | None |
| `compost_log` | `batch_id`, `type` ∈ turning/watering/inspection | `POST /compost/batches/{id}/activities` `{"type": type}` | None |
| `compost_finish` | `batch_id`, `kg` | same route, `{"type": "inspection", "finished_kg": kg}` | None |

- [ ] **Step 1: Write `check_compost.py`.**
  - Assert `op_request` for each action returns the exact method, path and body above.
  - The `compost` shape drops finished batches.
  - An unknown `type` in `compost_log` raises `ValueError`.
- [ ] **Step 2: Run it and see it fail.**
  - Run: `py <scratchpad>\check_compost.py`
  - Expected: `ValueError: unknown operator task 'compost'`.
- [ ] **Step 3: Implement the four branches in `op_request`, and add `"waiting": o["wet_waiting_kg"]` to the `today` reply shape.**
- [ ] **Step 4: Run the new and existing checks.**
  - Run: `py check_compost.py; py check_operator.py; py check_api_link.py; py check_voting.py`
  - Expected: every one prints `all passed`.
- [ ] **Step 5: Commit** on kiosk branch `kiosk-compost`: `Bridge: compost actions for the kiosk operator`.

### Task 4: Kiosk: Compost tile and screen

**Files:**
- Modify: `C:\dev\sapulmrf-kiosk\sapulmrf-kiosk\SapulMRF_Kiosk\ui.cpp`:
  - `Str` enum and table: `S_T_COMPOST`, `S_WET_WAITING` ("%s kg wet waiting"), `S_START_BATCH`, `S_NOTHING_WAITING`, `S_TURNING`, `S_WATERING`, `S_INSPECT`, `S_FINISH`, `S_COMPOST_MADE`; English and Tagalog
  - `buildOperator`: 3 tiles, each 72 px tall at y 164/244/324, with the Lock button staying at 404
  - `paintHome`: `tileCount[2]` from `o["waiting"]`, which comes through the bridge `today` shape. **Add `"waiting": o["wet_waiting_kg"]` to the bridge `today` reply in Task 3.**
  - New `scrCompost`, `buildCompost()`, `paintCompost(JsonObject)`:
    - left: "{kg} wet waiting", a `NumField fCompost` (prefilled with the waiting kg), the `formKeys` keypad, and **Start batch**
    - right: up to 4 open batches, each a card "B-12 · day 9 · 18 kg" with three small buttons (Turning / Watering / Inspection) and **Finish**
    - **Finish** reuses `fCompost` for the kg made: the card's Finish switches the field label to `S_COMPOST_MADE` and the main button to "Save finished"
  - `isOpScreen` includes `scrCompost`
  - `uiOnOp`: handles `compost` (paint) and `compost_*` (save: toast `S_SAVED_OK`, then `opAsk("compost")` to refresh)
- [ ] **Step 1: Implement the screen and wiring.** Follow `buildSeg`/`onSegSave` for the field, keypad, busy and toast.
  - Start is disabled when the field is 0 or above the waiting kg.
  - With nothing waiting, show `S_NOTHING_WAITING` and a disabled Start.
- [ ] **Step 2: Build.**
  - Run: `$env:USERPROFILE\.platformio\penv\Scripts\pio.exe run`, in the kiosk repo, from PowerShell.
  - Expected: `[SUCCESS]`, firmware under 3 MB. Then tell the user the build is done, so they upload from VS Code.
- [ ] **Step 3: Live check** (bridge running with `--dev`; operator signed in on the kiosk):
  1. Record a drop-off.
  2. Segregate it with 3 kg wet.
  3. Open the Compost tile: it shows `3 kg wet waiting`.
  4. Start a 3 kg batch: the waiting kg shows 0, and the batch card appears.
  5. Tap Watering: the toast says saved.
  6. Finish with 1.5 kg.
  7. Screenshot each step with `/shot?label=compost-N`.
  - The website's Compost page shows the same batch and activities.
- [ ] **Step 4: Commit** on `kiosk-compost`: `Kiosk: Compost tile — wet waiting, start batch, log work, finish` (not `config.h`).

---

## Follow-up plans (written after Part 1 ships)
- **Part 2:** sell / give out on the kiosk, with "happens now, admin reviews". The migration adds `outgoing.review`.
- **Part 3:** fix a mistake (undo and redo) and recount. The migration adds a `corrections` table and `adjustment_requests.review`.
