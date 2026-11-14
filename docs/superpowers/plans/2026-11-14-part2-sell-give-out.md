# Part 2: Sell / Give Out on the Kiosk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** an operator records a sale, compost given out, or residual disposal at the kiosk. Stock leaves at once, the buyer gets a receipt code, and the admin reviews afterwards (OK or Reverse).

**Architecture:**
- **API:** an operator's outgoing record is created already approved, and writes its stock movement at once. New `review` columns let the admin mark it OK or reverse it.
- **Reversal:** a counter stock movement plus a negative income entry on the reversal day; past days don't change.
- **Bridge:** relays `stock`, `recipients` and `outgoing`.
- **Kiosk:** a "Sell / give out" tile with a step-by-step flow and an on-screen keyboard for the buyer's name.

**Tech stack:** FastAPI + SQLAlchemy + Alembic (Postgres); React + TanStack Query, Playwright; Python bridge; ESP32-S3 + LVGL 8.3.

**Spec:** `docs/superpowers/specs/2026-11-14-kiosk-operator-processes-design.md` (section "2. Sell / give out", and "Reversal dates" under "Settled after the builder check").

**Repos:**
- SapulMRF: `C:\dev\sapulmrf`, branch `one-device` (uncommitted until the user says "commit").
- Kiosk: `C:\dev\sapulmrf-kiosk\sapulmrf-kiosk`, branch `kiosk-compost` (continue there).

## Global Constraints
- **Happens now:** a new operator outgoing record is `status='approved'` at creation, with `decided_at` = its creation time, and writes `StockMovement(kind="outgoing", kg=-kg, note=code)` at once.
- **Stock checks:** refuse with today's messages when the area holds less than the kg, or, for compost, when the kg exceeds `compost_on_hand`. Take `lock_areas` / `advisory_lock("compost")` before the check, as `decide_outgoing` does.
- **Existing rules stay:** a sale still needs material, area and price (the existing `OutgoingIn` rule). Compost has no area; residual has no material.
- **Review:** `outgoing.review` ∈ {'ok', 'reversed'}, plus `reviewed_by` and `reviewed_at`. Only admins mark it. Already-`pending` rows keep the old approve/reject flow.
- **Reverse:**
  - A counter `StockMovement(kind="outgoing", kg=+kg, note=f"{code} reversed", at=now)` puts the stock back.
  - Income on the original day stays. Income reports subtract `total` on the `reviewed_at` day for `review='reversed'`.
  - `compost_on_hand` adds reversed compost back.
- **Who:** `POST /outgoing` accepts `operator` and `admin`.
- **Unchanged:** duplicates are stopped by `client_key`, as today.
- **Kiosk:**
  - online only: the tile shows "Selling needs the connection" when SapulMRF is unreachable
  - receipt = the code on screen
  - existing look, strings in both languages
  - never commit `config.h`
- **Commits:** SapulMRF only after the user's "commit". Don't `pio run` during the user's upload.

## Review Focus
1. **Selling more than an area holds** (two operators, or one double tap): the second gets 409, and stock never goes negative. *Task 1 test, with the lock.*
2. **Reversing a sale whose stock was already moved elsewhere:** putting stock back must still work (it adds), and the income report for that day shows the negative entry. *Task 1 test.*
3. **Reversing twice, or reviewing a pending (old-flow) row:** 409 with a clear message. *Task 1 test.*
4. **A kiosk buyer name with Tagalog characters (ñ) or 120+ characters:** the API trims or refuses with its message, and the kiosk shows it. The keyboard is limited to 60 characters. *Task 4 by eye.*
5. **Bridge restart mid-sale:** the kiosk gets no reply. The 10 s busy timeout shows "no answer", and resending reuses the same `client_key`, so it can't double-sell. *Task 3 check.*

---

### Task 1: API: outgoing happens now, admin review and reverse

**Files:**
- Create: `api/migrations/versions/<rev>_outgoing_review.py`, down_revision `83dfb59b4301`:
  - add `review` String(8) nullable, `reviewed_by` FK users SET NULL, `reviewed_at` DateTime nullable
  - `CheckConstraint("review IN ('ok', 'reversed')", name="ck_outgoing_review")`
- Modify: `api/app/approvals/models.py` (`Outgoing` gets the three columns)
- Modify: `api/app/approvals/service.py`:
  - `request_outgoing` becomes immediate
  - new `review_outgoing(db, outgoing_id, data: OutgoingReviewIn, actor) -> Outgoing`
  - `compost_on_hand` adds reversed compost back
  - `counts()` gains `"outgoing_review"`
  - `pending()` lists unreviewed approved rows
- Modify: `api/app/approvals/schemas.py`:
  - `OutgoingReviewIn(decision: Literal["ok", "reverse"], comment: str = "")`
  - `OutgoingOut` gains `review: str | None`
  - `ApprovalsOut` gains `outgoing_review: list[OutgoingOut]`
- Modify: `api/app/approvals/router.py`:
  - `POST /outgoing` → `require_role("operator", "admin")`
  - new `POST /approvals/outgoing/{id}/review` (admin)
  - new `GET /outgoing/recipients?type=sale` (operator or admin) → `list[str]`: the 8 most recent distinct `recipient` values for that type
- Modify: income queries in `api/app/operations/service.py:336-347` and `api/app/reports/builders.py:108` to subtract reversed totals on their `reviewed_at` day
- Modify: `api/app/operations/schemas.py` (`StockRow` gains `material_id: int | None` and `storage_area_id: int`), and fill them where `InventoryView` is built
- Test: `api/tests/test_outgoing_now.py` (new); update the existing outgoing and approval tests that assume pending

**Interfaces:**
- Produces:
  - `POST /outgoing` → `OutgoingOut` (status `approved`, `review` null)
  - `POST /approvals/outgoing/{id}/review {"decision": "ok"|"reverse", "comment"}` → `OutgoingOut`
  - `GET /outgoing/recipients?type=` → `["Junkshop Reyes", ...]`
  - `GET /operations/inventory` rows carry `material_id` and `storage_area_id`
  - Approvals JSON: `counts.outgoing_review` and `outgoing_review: [...]`

- [ ] **Step 1: Write the failing tests** (helpers: stock 10 kg of Plastic in Area A through the existing sort route, as current approval tests do).

```python
def test_a_sale_leaves_stock_at_once_and_waits_for_review(...):
    r = client.post("/outgoing", json={"type": "sale", "material_id": plastic, "storage_area_id": area_a, "kg": 4,
                                       "recipient": "Junkshop Reyes", "price_per_kg": 12})
    assert r.status_code == 201 and r.json()["status"] == "approved" and r.json()["review"] is None
    assert material_kg(db, plastic, area_a) == 6.0
    assert admin_client.get("/approvals").json()["counts"]["outgoing_review"] == 1

def test_selling_more_than_the_area_holds_is_refused(...):   # 409, stock unchanged at 10

def test_reverse_puts_stock_back_and_income_drops_on_the_reversal_day(...):
    # sell 4 kg @12 (total 48) "yesterday" (at=), reverse today
    # material_kg back to 10; yesterday's income still 48; today's income -48; review == "reversed"

def test_a_reviewed_or_pending_row_cannot_be_reviewed(...):   # second review -> 409; old pending row -> 409

def test_compost_given_out_then_reversed_is_on_hand_again(...):

def test_recipients_are_the_recent_distinct_names_for_that_type(...):  # 8 max, newest first, per type

def test_admins_can_record_outgoing_too(...):
```

- [ ] **Step 2: Run them and see them fail.**
  - Run: `docker compose exec api pytest tests/test_outgoing_now.py -q`
  - Expected: FAIL (`review` missing / 404 on the new routes).
- [ ] **Step 3: Write the migration, and run it up, down and up again.**
  - Run: `docker compose exec api alembic upgrade head && docker compose exec api alembic downgrade -1 && docker compose exec api alembic upgrade head`
  - Expected: no errors; `alembic check` clean.
- [ ] **Step 4: Implement.**
  - `request_outgoing` reuses `decide_outgoing`'s availability check and its movement-writing code. Factor the shared part into `_take_out(db, o, actor, at)`, used by both.
  - Reversal adds the counter movement. Bags go back as recorded on the original movement (`-movement.bags`).
- [ ] **Step 5: Update the old tests.** Tests that create outgoing and then approve it now expect it approved on creation. Tests for approving or rejecting `pending` rows insert those rows directly as `status='pending'`.
- [ ] **Step 6: Run all API tests and lint.**
  - Run: `docker compose exec api pytest -q; docker compose exec api ruff check .`
  - Expected: all pass, ruff clean.

### Task 2: Web: admin review list, and admins can record outgoing

**Files:**
- Modify: `web/src/api/approvals.ts` (types `review`, `outgoing_review`; mutation `useReviewOutgoing`)
- Modify: `web/src/features/approvals/ApprovalsPage.tsx`:
  - a tab **"Outgoing to review"**, with the badge `counts.outgoing_review`
  - each row: code, type, material/area, kg, buyer, total, operator, time, plus **OK** and **Reverse** (Reverse asks for a comment inline, no modal)
  - the old pending tab stays, and shows only while there are pending rows
- Modify: `web/src/features/operations/OutgoingPage.tsx`: an admin "+ Record outgoing" drawer, reusing the operator's outgoing form component from `web/src/features/operator/` (import it; don't copy)
- Modify: `web/src/features/operator/OutgoingPage.tsx` (or the operator's equivalent): the success toast says "O-0123 recorded · stock updated" instead of "sent for approval"
- Test: `web/e2e/admin-04-approvals.spec.ts`:
  - the operator records a 2 kg sale; stock drops at once
  - the admin sees it under "Outgoing to review", reverses it with a comment, and stock is back

- [ ] **Step 1: Update the e2e test** (it fails on the missing tab).
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run checks.**
  - Run: `cd web; npx tsc -b; npx playwright test`
  - Expected: tsc 0; all pass. Then `remove-test-data`.
- [ ] **Step 4: Screenshots, by eye:** the Approvals review tab, the admin record drawer, the operator toast.

### Task 3: Bridge: stock, recipients, outgoing

**Files:**
- Modify: `pc_bridge/kiosk_bridge.py` (`op_request` and the protocol comment)
- Test: the scratchpad `check_outgoing.py`

**Interfaces:**

| `do` | Kiosk sends | Route | Reply `data` |
|---|---|---|---|
| `stock` | — | `GET /operations/inventory` | `[{"material_id","material","area_id","area","kg"}]` (kg > 0 only, at most `LIST_MAX`, biggest first) |
| `compost_on_hand` | — | `GET /operations/outgoing` (already has `compost_on_hand_kg`) | `{"kg": float}` |
| `recipients` | `kind` (sale/compost/disposal) | `GET /outgoing/recipients?type=` | `[str]` |
| `outgoing` | `kind`, `material_id`?, `area_id`?, `kg`, `recipient`, `price`?, `key` | `POST /outgoing` with `client_key=key` | `{"code","kg","recipient","total"}` |

- The message's own `"type"` is `"op"`, so the outgoing type travels as `kind`.
- `key` is made once per sale on the kiosk (`millis()` + operator id), so a resend reuses it.

- [ ] **Step 1: Write `check_outgoing.py`**, asserting each mapping above, the shapes, and that `key` becomes `client_key`.
- [ ] **Step 2: Run it and see it fail.** Expected: `ValueError: unknown operator task 'stock'`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run all checks** (`check_outgoing`, `check_compost`, `check_operator`, `check_api_link`, `check_voting`). Expected: all pass.
- [ ] **Step 5: Commit** on `kiosk-compost`: `Bridge: selling and giving out from the kiosk`.

### Task 4: Kiosk: "Sell / give out" tile and flow

**Files:**
- Modify: `SapulMRF_Kiosk/ui.cpp`:
  - the operator Home gets a 4th tile. Tiles become 56 px tall, at y 164 + i·60. The title and count stay on separate lines, the count in r18.
  - new strings in both languages
  - new screens:
    - `scrSell1` (pick what): **Sale** / **Compost** / **Residual**, then a list of stock rows (material · area · kg) or, for compost, the kg on hand
    - `scrSell2` (form): kg field + price field (sale only) + the keypad, the total, and a recipient chip that opens `scrBuyer`
    - `scrBuyer`: the recent recipients as buttons, plus **New**, which shows `lv_textarea` + `lv_keyboard` (max 60 characters, font `atk_r24`)
    - `scrSold`: the receipt: code in `atk_b72`, kg, buyer, total, and **Done**
  - `isOpScreen`, `buildAll` lists, `uiOnOp` handling (`stock`, `compost_on_hand`, `recipients`, `outgoing`), the busy timeout repaint, and dev `uiGoto` names `sell` and `sold`
- Modify: `SapulMRF_Kiosk/lv_conf.h` only if `LV_USE_TEXTAREA`/`LV_USE_KEYBOARD` turn out to be off (LVGL's defaults are on)

- [ ] **Step 1: Implement**, following the Compost screen's patterns: `NumField`, `formKeys`, `setBusy`/`paintSave`, `opAsk`.
  - Save is enabled only when kg > 0, kg ≤ the row's kg (or compost on hand), a recipient is set, and, for a sale, price > 0.
- [ ] **Step 2: Build.**
  - Run: `pio run`
  - Expected: SUCCESS. Then tell the user it's built so they can upload.
- [ ] **Step 3: Live check** (sign in with dev `/signin?user_id=593&pin=1234`):
  1. Sell 2 kg Plastic from Demo Area A to a new buyer at ₱12.
  2. The receipt shows the O- code and ₱24.
  3. The Home storage bar and the website inventory show 2 kg less.
  4. The admin sees it under "Outgoing to review" and reverses it; stock is back.
  - Screenshots in EN and TL: the pick screen, the form, the keyboard, the receipt.
- [ ] **Step 4: Commit** on `kiosk-compost`: `Kiosk: Sell / give out — stock, buyer, receipt code`.

---

## Follow-up
- **Part 3:** Fix a mistake (undo and redo) and Recount.
