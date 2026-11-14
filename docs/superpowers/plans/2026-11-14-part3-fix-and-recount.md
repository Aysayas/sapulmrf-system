# Part 3: Fix a Mistake and Recount Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** an operator fixes today's mistakes at the kiosk by undoing (sort → wet/dry → delivery) with a reason and recording again. They recount storage with an immediate adjustment. The admin reviews fixes and recounts afterwards, and can undo any day from Intake.

**Architecture:**
- **API:** one undo endpoint walks the chain down to the chosen step and writes a `corrections` row.
- **Recounts:** they become immediate, with `review` (ok / reversed), the same pattern as outgoing in Part 2.
- **Bridge:** relays `fixable`, `undo`, `area_stock` and `recount`.
- **Kiosk Home:** gets a 5th tile, **Fix / recount**. It opens a chooser: Fix a record, or Recount storage.

**Tech stack:** FastAPI + SQLAlchemy + Alembic; React + TanStack Query, Playwright; Python bridge; ESP32-S3 + LVGL 8.3.

**Spec:** `docs/superpowers/specs/2026-11-14-kiosk-operator-processes-design.md` (section 3, plus "Settled after the builder check", including the 2026-11-14 change: admin undo only, no back-dated redo).

**Repos:** SapulMRF `C:\dev\sapulmrf` branch `one-device`; kiosk `C:\dev\sapulmrf-kiosk\sapulmrf-kiosk` branch `kiosk-compost`.

## Global Constraints
- **Undo chain:** `to` ∈ {"sort", "segregation", "delivery"} undoes from the newest step down to `to` inclusive.
  - "delivery" on a sorted delivery undoes the sort, then the wet/dry check, then the delivery.
  - A step that doesn't exist is skipped. Undoing a delivery's "sort" when it isn't sorted is 409.
- **Who and when:**
  - Operators may undo only steps made today (Asia/Manila day of that step: sort = its movements' `at`, segregation = `checked_at`, delivery = `received_at`). Otherwise 403: "Only today's records can be fixed at the kiosk. Ask the admin."
  - Admins may undo any day.
  - Staff get 403.
- **Undoing a sort:**
  - Deletes that delivery's `kind='sorted'` movements, after `lock_areas`.
  - It's refused (409, naming the area and material) if any material/area would drop below 0.
  - The delivery's classifications go back to unconfirmed (`confirmed_at`, `confirmed_by`, `final_material_id` → null; `changed`, `not_recyclable` → false; review fields → null).
  - Status becomes `separated`.
- **Undoing segregation:** deletes the check; status becomes `awaiting`. The wet balance (Part 1) follows automatically.
- **Undoing a delivery:** deletes its `DeliveryPhoto`, classifications and flags, then the delivery. This is allowed only once it has no check.
- **Every undo** writes a `corrections` row and an activity-log line, in one transaction:
  - `kind` = the deepest step undone
  - `record_code`
  - `summary`: what was removed, e.g. "D-4502 · Purok 3 · Mixed household · 2.4 kg · wet 1.0 · dry 1.4 · sorted: Plastic 0.8, Paper 0.6"
  - `reason`, `by`, `at`
- **Linking a redo:** a kiosk drop-off may carry `replaces: "D-4502"`. The API sets `corrections.redone_as` on that correction row.
- **Recount:**
  - `POST /inventory/adjustments` is immediate: `status='approved'`, decided by the actor, and the movement is written at once.
  - `adjustment_requests.review` ∈ {'ok', 'reversed'}.
  - Reverse adds a counter movement `-change`, refused if stock would go below 0.
  - The migration marks already-decided rows `review='ok'`. Old pending rows keep approve/reject.
- **Reasons:**
  - **Fix:** Wrong purok / Wrong kind / Wrong weight / Wrong wet/dry / Wrong sort / Other
  - **Recount:** Spilled / Miscounted / Moved without recording / Other
  - The kiosk sends the label text; "Other" sends "Other".
- **Kiosk:** online only. Existing look. Strings in both languages. Never commit `config.h`. Don't `pio run` during the user's upload. SapulMRF commits only on the user's "commit".

## Review Focus
1. **Undoing a sort whose stock was partly sold or moved:** 409 naming the area; nothing deleted. *Task 1 test.*
2. **An operator undoing yesterday's step** (e.g. a delivery received yesterday but sorted today: undoing the sort is allowed, undoing the delivery is not). *Task 1 test.*
3. **Two undo taps at once on the same delivery:** the second gets 404/409, not a crash. The delivery row is taken FOR UPDATE. *Task 1 test.*
4. **A recount to 0 kg, then reversing it:** stock and bags return; reversing twice is 409. *Task 1 test.*
5. **A kiosk Fix list with no deliveries today** shows a plain empty message, and Back works. *Task 4 by eye.*

---

### Task 1: API: corrections, the undo chain, immediate recounts

**Files:**
- Create: `api/migrations/versions/b3d4f6a8c201_corrections_and_recount_review.py`, down_revision `a7c2e91b4d10`:
  - table `corrections`: id, kind String(12) with CHECK in (sort, segregation, delivery), record_code String(12) indexed, summary String(300), reason String(120), by FK users SET NULL, at DateTime tz default now, review String(8) with CHECK in (ok, wrong), reviewed_by FK SET NULL, reviewed_at, redone_as String(12)
  - `adjustment_requests` gets review / reviewed_by / reviewed_at with CHECK in (ok, reversed), backfilled `review='ok'` where status != 'pending'
- Create: `api/app/corrections/{__init__,models,schemas,service,router}.py`:
  - `Correction` model
  - `UndoIn(delivery_id: int, to: Literal["sort","segregation","delivery"], reason: Required)`
  - `CorrectionOut`
  - `service.undo(db, data, actor) -> Correction`
  - `service.mark(db, id, review: Literal["ok","wrong"], actor)`
  - routes: `POST /corrections/undo` (operator|admin), `POST /corrections/{id}/review` (admin), `GET /corrections/fixable` (operator|admin: today's deliveries with any step today, newest first, max 8: id, code, source_area, category, weight_kg, stage)
- Modify: `api/app/main.py` (include the router)
- Modify: `api/app/devices/schemas.py` + `kiosk.py` (`KioskDeliveryIn.replaces: str | None`; after the drop-off is saved, set `Correction.redone_as` on the newest correction with that `record_code`)
- Modify: `api/app/approvals/{models,schemas,service,router}.py`:
  - `request_adjustment` becomes immediate: reuse `decide_adjustment`'s movement code via a shared `_apply_count(db, r, actor)`
  - `review_adjustment(db, id, OutgoingReviewIn-like body, actor)`: ok / reverse
  - `counts()` gets `adjustments_review` and `fixes`; `pending()` lists them
  - route `POST /approvals/adjustments/{id}/review`; `/inventory/adjustments` allows operator and admin
- Test: `api/tests/test_corrections.py` (new), `api/tests/test_recount_now.py` (new); update adjustment tests that assume pending, as Part 2 did

- [ ] **Step 1: Write the failing tests.**
  - **corrections:**
    - `test_undo_sort_puts_the_delivery_back_to_be_sorted_and_logs_a_fix`
    - `test_undo_to_delivery_walks_the_whole_chain` (sorted → nothing left; correction kind delivery; summary contains code, purok, kg, wet/dry, sorted parts)
    - `test_undo_sort_is_refused_when_its_stock_was_sold` (409, nothing deleted)
    - `test_operators_fix_only_todays_steps_admins_any_day` (delivery received yesterday, sorted today: operator undo sort OK, undo delivery 403; admin OK)
    - `test_a_second_undo_of_the_same_step_is_409`
    - `test_fixable_lists_todays_deliveries_with_their_stage`
    - `test_a_kiosk_drop_off_that_replaces_one_links_the_fix`
    - `test_admin_marks_a_fix_ok_or_wrong_once`
  - **recount:**
    - `test_a_recount_applies_at_once_and_waits_for_review`
    - `test_reverse_puts_the_old_count_back_once`
    - `test_recount_to_zero_then_reverse_restores_bags`
    - `test_old_pending_adjustment_still_approves`
- [ ] **Step 2: Run them and see them fail** (ImportError / 404).
- [ ] **Step 3: Migration up, down, up; then `alembic check`.** Expected: clean.
- [ ] **Step 4: Implement.** Take the delivery `with_for_update` first, then `lock_areas` for the sort's areas.
- [ ] **Step 5: Update old adjustment tests and the simulator.**
  - The simulator's recounts become immediate. Older ones are marked `review='ok'` directly, as `give_out` does.
  - `remove()` also deletes the sim's corrections and "Adjustment #n reversed" movements.
- [ ] **Step 6: Run the full suite and lint.** Expected: all pass, ruff clean.

### Task 2: Web: fixes and recounts to review; admin undo from Intake

**Files:**
- `web/src/api/approvals.ts`: `Counts` + `adjustments_review`, `fixes`; types; `useReviewAdjustment`, `useMarkFix`
- `web/src/features/approvals/ApprovalsPage.tsx`:
  - tabs **"Recounts to review"** (OK / Reverse… with a reason, the same component pattern as `OutgoingReviews`) and **"Fixes to review"** (summary, reason, by, when, redone as; OK / Wrong)
  - the old Adjustments tab shows only while pending ones exist
- `web/src/api/corrections.ts` (new): `useUndo`
- `web/src/features/operations/IntakePage.tsx`: each row's "Undo…" opens an inline chooser with the step (sort / wet-dry / delivery, only those that apply) and a reason, then calls `/corrections/undo`
- Operator web recount form: the toast says "Recount saved · stock updated"
- e2e: `admin-04-approvals.spec.ts` gets a recount → reverse and an undo-from-Intake → Fixes tab → OK; update operator-01's adjustment expectations

- [ ] **Step 1: Update the e2e tests.**
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run checks.** `tsc -b`, full Playwright (expected all pass), then `remove-test-data`.
- [ ] **Step 4: Screenshots, by eye.**

### Task 3: Bridge: fixable, undo, area_stock, recount (+ replaces)

| `do` | Kiosk sends | Route | Reply `data` |
|---|---|---|---|
| `fixable` | — | `GET /corrections/fixable` | `[{"id","code","label","stage"}]` (label "D-4502 · Purok 3 · 2.4 kg") |
| `undo` | `delivery_id`, `to`, `reason` | `POST /corrections/undo` | `{"code","to"}` |
| `area_stock` | `area_id` | `GET /operations/inventory` | `[{"material_id","material","kg"}]` for that area, residual included |
| `recount` | `material_id`?, `area_id`, `kg`, `reason` | `POST /inventory/adjustments` `{material_id, storage_area_id, actual_kg, reason}` | None |

- The kiosk drop-off (`intake`) may carry `replaces`. The bridge passes it into the `/devices/deliveries` body.
- Test: the scratchpad `check_fix.py`. All other checks must still pass.
- Commit on `kiosk-compost`.

### Task 4: Kiosk: Fix / recount

**Operator Home:**
- 5 tiles, 52 px tall, from y 108 in steps of 58 (108 … 398).
- The alert banner moves into the right column's top (x 392, y 108).
- The 5th tile is **Fix / recount** with the sub-line "Fix a record, recount storage".

**Screens:**
- `scrFixMenu`: two big buttons, **Fix a record** and **Recount storage**, plus Back.
- `scrFix`: up to 6 rows from `fixable`, each with its stage badge. Empty: "Nothing recorded today."
- `scrFixHow`, for one delivery:
  - the reason buttons (6, two columns)
  - then "how far" buttons by stage:
    - **Sorted:** Redo the sort / Redo wet-dry and sort / Redo everything
    - **Separated:** Redo wet-dry / Redo everything
    - **Awaiting:** Redo everything
  - then **Undo** (`btnFixGo`), enabled once a reason and an option are picked
- **After a successful `undo`:**
  - to sort: `choose(L_SORT)`
  - to segregation: `choose(L_SEG)`
  - to delivery: toast "D-4502 removed. Record it again as a drop-off.", set `replacing = code`, then `goTo(scrPurok)`. The operator is signed out by leaving staff screens, as today. The next drop-off's `intake` message carries `replaces` and then clears it.
- **Recount:**
  - `scrRecount` lists areas (the existing `areas[]`).
  - Tapping one asks `area_stock`, and the screen lists the materials with system kg.
  - Tapping one opens `scrRecountForm`: the counted-kg `NumField` + `formKeys` keypad + 4 reason buttons + Save → `recount`.
  - Then toast "Saved" and back to that area's list, refreshed.
- **Also:** `isOpScreen`, `buildAll` lists, `uiOnOp` handling, the busy timeout repaint, and dev `uiGoto` names `fix` and `recount`.

**Steps:**
- [ ] **Step 1: Implement.**
- [ ] **Step 2: Build;** say it's built.
- [ ] **Step 3: Live check** (dev `/signin` and `/op`):
  1. Undo a test delivery's sort through `/op`. Expected: the Sort list shows it again, and the website's Fixes tab lists it.
  2. Recount 1 kg off in a demo area, then reverse it on the website.
  - Screenshots of every new screen, in EN and TL.
- [ ] **Step 4: Commit.**

---

Rulings to carry:
- **Fix and Recount share one tile,** because Home has room for 5 tiles, not 6.
- **"Redo everything" leaves operator mode for the drop-off flow,** which signs the operator out, as any exit from staff screens does today.
