# Design: operator processes on the kiosk: wet → compost, selling, fixing mistakes


## Intent and the why
At the real MRF, **operators work only at the kiosk.** Every step that changes the waste counts must be a clear process they can finish there without waiting for the admin: weigh, segregate, wet → compost, sort, sell or give out, fix a mistake, recount. The admin can do the same actions from the web panel; their usual job is reviewing afterwards.

Three gaps today:
1. **Wet waste goes nowhere:** a compost batch's kg is typed by hand, unlinked to the segregation checks.
2. **Selling or giving out is web-only** and waits for admin approval, so a buyer at the gate has to wait.
3. **Corrections are web-only and partial:** only the weight reason at intake, undoing a segregation check, the camera-change reason, and a recount request. A wrong purok, kind or sort can't be fixed at all.

## Goals
- The operator kiosk Home has tiles for **Compost**, **Sell / give out**, **Fix a mistake** and **Recount**, next to the existing Segregate and Sort.
- **Happens now, admin reviews later:** sales, giving out, recounts and fixes take effect immediately. Each lands in the admin's Approvals as "to review", where the admin marks it OK or reverses it.
- **Fix window:** operators fix only **today's** records (Asia/Manila day of the record). Anything older is fixed by the admin from the panel, which has no day limit.
- **Wet waste balance:**
  - wet waiting = Σ segregation `wet_kg` − Σ batch `start_kg`, never below 0
  - a batch can't use more than is waiting, plus 0.5 kg slack
- The admin panel can perform every operator action: compost, outgoing, undo, recount.

## Non-goals
- Per-delivery tracking of which wet waste went into which batch.
- Printed receipts: the receipt is a code on screen.
- Payments or cash handling beyond recording the price and total.
- Offline selling or fixing: these need SapulMRF reachable (they check stock). Resident drop-off keeps its offline outbox.

## Anti-goals (a failure even if it works)
- The admin becomes a bottleneck: a buyer or operator waits on approval.
- Numbers change with no trace. Every sale, fix and recount has who, when, why, and a review row.
- Stock goes negative, or reports change silently for past days (hence same-day fixes).

## Constraints
- **All rules live in the SapulMRF API.** The bridge only relays; the ESP32 only shows screens and sends taps.
- **The kiosk relays as the operator:** it calls the operator's own SapulMRF routes with that operator's 30-minute session cookie, the same as segregate and sort today (`kiosk_bridge.py` `op` messages).
- **Kiosk display:** LVGL 8.3 at 800×480, touch only. There's no text keyboard in the UI yet, so `lv_keyboard` must be added for buyer names and reasons.
- **Kiosk firmware budget:** about 1.5 MB of a 3 MB app partition, so new screens are affordable but should reuse the existing pick/keypad patterns.
- **Branches:** SapulMRF builds on the `one-device` branch, which must be committed first. Kiosk work goes on a new branch from `camera-voting`.
- The kiosk's look stays the same (cream/green, big buttons, step by step).

## Approaches considered (for fixing mistakes)
- **A. Edit in place:** an edit screen per record type, and the admin sees exact old → new values. About 4 new kiosk screens, plus API edit logic per type, including rewriting stock rows.
- **B. Undo and redo (chosen):**
  - Fix = undo the record with a reason, in chain order (sort → segregation → delivery), then record it again with the screens operators already use.
  - Fewer new screens and less API logic.
  - The admin sees "undone: reason" plus the new record.
  - Chosen for the kiosk's screen budget and familiarity. Same-day-only keeps it rare.
- **C. Fix as a request the admin applies:** rejected, because it contradicts "happens now".

Selling and recount had no real alternative once "happens now, review later" was picked.

## The design

### 1. Wet → compost
- **API (`compost/service.py`):**
  - `wet_waiting(db)`.
  - `start_batch` refuses `start_kg > wet_waiting + 0.5` with: "Only X kg of wet waste is waiting for compost."
  - `wet_waiting_kg` is exposed on `/operations/compost` (`CompostView`) and the overview schema.
- **Who:** the compost routes accept operators **and admins** (today `operator_only`).
- **Kiosk Compost tile:** shows "X kg wet waiting" and the open batches.
  - **Start batch:** kg prefilled with the waiting kg; a keypad to lower it; confirm.
  - **Open batch:** Log turning / watering / inspection (one tap each), or **Finish** (keypad for kg of compost made).
- **Bridge:** `op` actions `compost` (the view), `compost_start`, `compost_log`, `compost_finish`.
- **Web:** the operator Compost page and the admin Compost page show the balance. The segregation toast reads "wet X kg → waiting for compost".

### 2. Sell / give out (outgoing)
- **The rule changes:** an operator's outgoing record takes effect immediately.
  - Stock leaves the area at once: the same movement the admin's approval writes today.
  - It is checked against the kg available in that area, or against the compost on hand for compost, with today's error messages.
- **Model:** add `review` ('ok' | 'reversed'), `reviewed_by` and `reviewed_at` to `outgoing`, following the deliveries/classifications pattern.
  - New records are created as `approved`, with `review` null.
  - Rows that are already `pending` keep the old approve/reject flow until they're decided.
- **Admin:** Approvals › "Outgoing to review" lists rows with `review` null.
  - **OK:** marks the row.
  - **Reverse** (with a comment): adds a counter stock movement that puts the stock back, and sets `review='reversed'`. Income reports exclude reversed rows.
- **Admin panel:** Operations › Outgoing gets "+ Record outgoing", using the same API.
- **Kiosk "Sell / give out" tile, as steps:**
  1. **Type:** Sale of recyclables / Compost given out / Residual for disposal.
  2. **What and where:** material and storage area. Each choice shows the kg available. Compost has no area; residual = no material.
  3. **Kg:** keypad, capped at the kg available.
  4. **Buyer or recipient:** tap one of the recent recipients (from past outgoing records), or "New" opens a keyboard.
  5. **Price per kg:** sales only, keypad; may be left blank (given free).
  6. **Confirm:** shows the total, then a **receipt screen** with the code `O-0123`, kg, buyer and total.
- **Online only:** when SapulMRF is unreachable, the tile shows "Selling needs the connection".
- **Duplicates:** `client_key` stops double submits.

### 3. Fix a mistake (undo and redo) and recount
- **A new `corrections` table:**
  - `kind` (delivery | segregation | sort), `record_code`, `summary` (what was removed, e.g. "D-4502 · Purok 3 · Recyclable · 2.4 kg · sorted: Plastic 1.2, Paper 0.8"), `reason`
  - `by`, `at`
  - `review` ('ok' | 'wrong'), `reviewed_by`, `reviewed_at`
- **Undo endpoints:** each takes a reason. **Operators only for records created today; admins any day.**
  - **Undo sort** (`DELETE /sorting/{delivery_id}`): removes that delivery's sorted stock movements.
    - It's refused if the area would go below zero (part was already sold or moved). The message names the area.
    - The delivery's confirmed camera classifications go back to unconfirmed, so the redo sort confirms them again.
  - **Undo segregation** (existing `DELETE /deliveries/{id}/segregation`): gains the reason, the same-day rule and a correction row.
  - **Undo delivery** (`DELETE /deliveries/{id}`): only once it has no segregation check. It removes the delivery with its photo, unconfirmed classifications and flags. The summary keeps what it was.
  - Each undo writes the correction row and an activity-log line.
- **Kiosk "Fix a mistake" tile:**
  1. **List:** today's deliveries (code, purok, kg, and stage: Recorded / Segregated / Sorted).
  2. **Pick one:** the screen says what will be undone, e.g. "This removes the sort and the wet/dry check of D-4502".
  3. **Pick what was wrong:** Wrong purok, Wrong kind, Wrong weight, Wrong wet/dry, Wrong sort, or Other (keyboard).
  4. **Choose how far to undo**, by stage:
     - **Sorted delivery:** "Redo the sort", "Redo wet/dry and sort", or "Redo everything".
     - **Segregated delivery:** "Redo wet/dry" or "Redo everything".
     - **Recorded delivery:** "Redo everything".
  5. **Confirm:** the kiosk then opens the matching existing flow:
     - the Sort screen for that delivery
     - the Segregate screen
     - or a new intake: purok → kind → weight, which gets a new D- code
- **Recount:** the kiosk "Recount" tile, which takes effect immediately.
  1. Pick the storage area: each material shows its system kg.
  2. Tap a material and enter the counted kg.
  3. Pick a reason: Spilled / Miscounted / Moved without recording / Other.
  4. The difference is applied as an adjustment movement at once.
  - **Model:** `adjustment_requests` gets `review` ('ok' | 'reversed') and `reviewed_by`/`reviewed_at`, the same as outgoing. New rows are created `approved`. The admin can Reverse, which puts the old kg back.
- **Admin Approvals:** the tabs become review lists:
  - Outgoing
  - Recounts
  - Fixes (corrections)
  - Corrected weights
  - Camera changes
  - Flagged weights

  The navigation badge counts unreviewed items. The admin's Intake page gets row actions to undo sort, segregation or delivery (any day).

## Decided calls (mine, not discussed: check these)
- **Kiosk `op` action names:** `compost*`, `outgoing`, `recipients`, `stock`, `undo`, `recount`.
- **Recent recipients:** the 8 most recent distinct `recipient` values for that type.
- **The kiosk lists all of today's deliveries, not just this operator's,** because operators share the kiosk.
- **Undoing a delivery deletes it.** The `corrections.summary` row plus the activity log keep the trace; there's no soft-delete column, since that would touch every query.
- **Reversing a sale** keeps the row as `review='reversed'` rather than deleting it.

## Settled after the builder check (my calls: check these)
- **"Redo everything" on the kiosk runs the resident drop-off flow** (purok → camera scan → kind → weight), so the new delivery gets its photo, camera result and offline queue like any drop-off. The bridge links it to the fix by sending the undone code in the drop-off body (`replaces: "D-4502"`). The API stores that on the correction row.
- **Which day counts for "today only":** the date of the step being undone. A sort made today on yesterday's delivery can be fixed at the kiosk. The kiosk list shows deliveries with any step done today.
- **Admin fixes of older records (changed 2026-11-14, the user's choice):** the admin can undo any record, any day, from the Intake page, with a reason. Re-recording happens the normal way, by an operator at the kiosk, dated today. There's no back-dated admin redo.
- **Reversal dates:**
  - Reversing a sale or recount is a **negative entry on the day it's reversed.** The original row and day stay as they were, so past income and stock reports don't shift silently.
  - `compost_on_hand` and stock checks count reversals.
- **Reversing a recount** puts back the difference, not the old total. It's refused if that would make stock negative.
- **Undoing a sort** clears the admin's review marks on those camera classifications, since the redo makes fresh ones.

## Before building
The `one-device` branch (19 files: one device type, manual compost) is still uncommitted, and Part 1 builds on it. **Waiting for the user's "commit"** before starting.

## Left to the builder
- Exact screen layout within the existing kiosk style.
- Migration naming.
- How existing `pending` adjustments and outgoing rows show (the old approve/reject buttons stay for those only).
- Test cases, following the existing per-area test files.

## Build order (three parts, each shippable)
1. Wet → compost: API, web and kiosk.
2. Sell / give out: API with migration, admin web, kiosk.
3. Fix a mistake and recount: API with migration, admin web, kiosk.

## Verification (each part)
- API `pytest` and `ruff`; web `tsc` and Playwright; bridge self-checks (scratchpad `check_*.py`) for new `op` actions.
- Kiosk build, then the user uploads, then a live run with the dev control screenshots (`/shot`).
- **Part 2:** sell 2 kg Plastic, stock drops at once, the admin sees it to review, Reverse puts it back.
- **Part 3:** undo a sorted delivery's sort, redo it, the admin sees the fix; a recount applies at once and the admin can reverse it.
