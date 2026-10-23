# Phase 4 plan: approvals and reviews

## Context
Phase 3 is done and committed in `C:\dev\sapulmrf` (86 API tests, 11 browser tests, live sim running). Phase 4 covers:
- **ADM-16:** approve inventory adjustments and outgoing material transactions.
- **ADM-11:** review corrected weight readings and corrected CV classifications.
- **ADM-17:** income from recyclables (and compost, when priced), counted from approved sales only.

Today stock only ever changes through the ledger (`stock_movements`). Sorting adds to it directly, and the simulator's weekly pickups subtract from it directly. Phase 4 puts a request → approve/reject step in front of every outgoing and adjustment change. The Approvals page is still a "coming soon" placeholder. Approving this plan approves Phase 4 only.

Wireframes: admin `02` approvals inbox, `02b` detail drawer, `02c` approved, `02d` corrected weights, `02e` corrected classifications, `03f` operations outgoing and income; operator `05c` adjustment request, `07b` new outgoing record.

## Decisions
Your answers:
- **Compost stock is tracked:** compost on hand = produced_kg of finished batches − approved compost outgoing. Approval is refused (409) if there isn't enough. A price is optional, so compost can be sold or given free.
- **Review marks are just marks:** "OK", "Ask to recheck" and "Wrong" set a review status, reviewer and time. Values and stock don't change. Phase 6 uses the marks for CV accuracy.
- **Simulated history is rebuilt:** run `simulator remove`, then backfill again with the new flow.

My calls (override any):
- **Operators create requests, admins decide.** Operator API only for now: the operator screens come later, and the simulator stands in.
- **Stock moves on approval, not on request.** Approving writes one ledger row: `adjustment` (actual − current stock at approval time) or `outgoing` (−kg). The current stock is re-checked at approval, so two approved requests can't overdraw an area (409). Rejecting changes nothing. A comment is optional on approve, required on reject.
- **Outgoing types:** `sale` (recyclable material + area, price per kg required), `compost` (no area, optional price), `disposal` (residual from its area, no price). Codes `O-0001`. Money is `Numeric(10,2)` in pesos. Total = kg × price, computed by the server.
- **Adjustments** are per material and storage area (residual = no material): system kg at request time, actual kg counted, a reason and details.
- **Each decision is logged** in the activity log, and each request keeps who asked, who decided, when, and the comment.
- **Flagged records** (wireframe tab `02f`) wait for Phase 6, which creates the flags.
- **Overview:** the KPIs that were waiting for this phase come back: "Pending approvals" and "Income this month" replace "Awaiting segregation" and "Active compost batches". Those two stay visible on the Operations pages.

## Backend (same pattern: router → service → models + schemas)
| Module | Tables / columns | Routes |
|---|---|---|
| `approvals/` (new) | `adjustment_requests` (material_id null = residual, storage_area_id, system_kg, actual_kg, reason, details, status pending/approved/rejected, requested_by/at, decided_by/at, comment); `outgoing` (code, type, material_id, storage_area_id, kg, recipient, price_per_kg, total, status, requested_by/at, decided_by/at, comment) | Operator: `POST /inventory/adjustments`, `POST /outgoing`. Admin: `GET /approvals` (counts per tab and the pending lists), `POST /approvals/adjustments/{id}` and `/approvals/outgoing/{id}` with `{decision, comment}` |
| `intake/` + `sorting/` | `review` (ok/recheck/wrong), `reviewed_by`, `reviewed_at` on deliveries and classifications | Admin: `GET /reviews/weights` and `/reviews/classifications` (corrected/changed and not yet reviewed, newest first), `POST /reviews/weights/{id}` and `/reviews/classifications/{id}` |
| `operations/` | — | `GET /operations/outgoing?days=` (income this month, kg sold, compost given out, residual disposed, income per month for 6 months, records). `/overview` gains `pending_approvals` and `income_month` |

- One Alembic migration for the tables and the review columns.
- Reuse `sorting.service.stock_kg` style ledger sums for the stock check (add a per material + area helper beside it), `log()` from `app/activity/service.py`, `AppError`, and the `require_role` dependency variables.
- **Simulator** (`app/simulator.py`): weekly pickups become `sale` requests with placeholder prices per material (plus a monthly `disposal` and occasional `compost` give-outs and adjustments). The backfill approves the older ones as the e2e admin and leaves the last few days pending. The live loop sends an occasional request so the inbox isn't empty.

## Frontend
- **Approvals** (`/admin/approvals`), replacing the placeholder, with the wireframe's tabs and counts: Adjustments, Outgoing, Corrected weights, Corrected classifications.
  - Adjustment and Outgoing rows open a `Drawer` with the details and "After approval: Area A 310 → 190 kg (38% full)". The buttons are Reject and Approve, with a comment box. A `Toast` confirms the result.
  - The review tabs are tables with per-row OK / Ask to recheck (weights) and OK / Wrong (classifications) buttons. Reviewed rows leave the list.
  - The sidebar's Approvals link shows the pending count.
- **Operations › Outgoing** (new 7th sub-page, before Live camera): KPI tiles, an income-per-month bar chart (`IntakeChart` pattern in `components/charts.tsx`, one hue), and the records table with status badges.
- **Overview:** the two swapped KPIs, linking to Approvals and Operations › Outgoing.
- Reuse `Drawer`, `Toast`, `Badge`, `btn`, `inputCls`, `PageHeader` (`components/ui.tsx`), `Table`, `Period`, `kg` (`features/operations/shared.tsx`), `Kpi` (`components/charts.tsx`), and the hook pattern in `api/operations.ts` (mutations invalidate `['approvals']`, `['ops']` and `['overview']`).

## Order of work (each step ends working and committed)
1. Adjustment and outgoing requests: tables, operator create API, admin decide API with the stock and compost checks, tests.
2. Reviews: columns, list and mark API, tests.
3. Outgoing and income read API, plus the overview additions, tests.
4. Simulator: new pickup flow, then `remove` + `backfill --days 40` on the dev DB, tests.
5. Frontend: Approvals page (four tabs and the drawer), sidebar count.
6. Frontend: Operations › Outgoing page, and the Overview KPI swap.
7. Browser test `admin-04-approvals.spec.ts`: an e2e operator requests a sale through the API → the admin approves it in the drawer → the area's stock drops and the income shows in Operations › Outgoing; rejecting a second request leaves stock unchanged; marking a corrected weight OK removes it from the list. `remove-test-data` also clears e2e requests.
8. Roadmap ticks, README/testing notes, vault session note.

## Tests that must pass
- **Requests:** only operators create them (403 otherwise); a sale without a price gets 422; codes are sequential.
- **Decisions:**
  - only admins decide
  - approving writes exactly one ledger row and the stock changes by the right amount; rejecting writes none
  - deciding twice gets 409
  - approving more than is in stock (or in compost) gets 409
  - rejecting without a comment gets 422
  - each decision is logged
- **Reviews:** only corrected or changed records are listed; a mark removes them from the list and is logged; marking twice gets 409.
- **Income:** counts approved sales only, grouped by Manila month.
- **Overall:** every Phase 1–3 test still passes, Ruff is clean, `npm run build` passes, all browser tests pass.

## Verification
- `docker compose exec api alembic upgrade head`, then `pytest` and `ruff check .`
- Rebuild the sim data: `python -m app.simulator remove`, `setup`, `backfill --days 40`, restart the live sim.
- `cd web && npm run test:e2e`, then `remove-test-data`.
- Screenshots of the Approvals tabs, the drawer and Operations › Outgoing, compared with wireframes `02`–`02e` and `03f`.

## Not in Phase 4
- Operator screens for these requests (the simulator and the API stand in).
- Flagged records (Phase 6), alerts (Phase 5), reports (Phase 7).
- Stock transfers between areas.
