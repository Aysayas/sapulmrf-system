# Plan: operator screens for requests and problem reports (phone size)

## Context
Phases 0–7 of the admin side are done (last commit `ea7cc59`). The roadmap still has one open Phase 4 item, "Operator screens to send adjustment and outgoing requests", plus the operator side of Phase 5's problem reports. Until now the simulator and the API stood in for the operator, and an operator who logs in sees "The screens for your role aren't built yet."

Requirements covered:
- **OPR-13** (part): request an inventory adjustment from Storage (`05c`), and see whether it was approved (`05d`).
- **OPR-16, OPR-17:** record outgoing recyclables, compost and residual, with price and total for sales (`07`, `07b`, `07c`).
- **OPR-19** (part): view and acknowledge alerts (`08`).
- **OPR-20:** report a device problem or an incorrect record (`08b`).
- **OPR-01, OPR-22** (part): an operator logs in and out on the web.

Status: **built** (2026-10-23). Approved as drafted: only these screens, phone first, with My requests and My reports. Results and changes are at the end.

What already exists:
- **API, ready:** `POST /inventory/adjustments`, `POST /outgoing`, `POST /problems` (operator only); `GET /operations/inventory` and `GET /operations/outgoing` (admins and operators); `GET /alerts`, `GET /alerts/summary` and `POST /alerts/{id}/acknowledge` (operators allowed); `GET /masterdata/*` (any logged-in user).
- **API gaps:**
  - An operator can't list their own adjustment requests (the inbox is admin only).
  - An operator can't list their own problem reports.
  - `GET /devices` is admin only, so the "which device?" picker has no list.
- **Frontend:** `RequireAdmin` blocks every non-admin. The login always goes to `/admin`.

## Decisions
Open questions (recommendation first):
1. **Scope: only these screens plus a small operator shell (recommended).** That means Storage (with Request adjustment), Outgoing (with Record outgoing), Alerts (with Report a problem), and log out. The other operator screens are left for later: Today, Intake, Segregation, Sorting, Compost, History and Profile. The alternative is to build the whole operator side now, which is about three times the work, and the IoT floor station covers intake, segregation and sorting anyway.
2. **Layout: phone first (recommended).** One column at 390 px with a bottom tab bar (Storage, Outgoing, Alerts). On a laptop it stays a centred column about 480 px wide. The web wireframes are desktop width, but you asked for phone size. The alternative is the wireframes' desktop layout, made responsive.
3. **Operators see their own requests and reports (recommended).** Storage gets a "My requests" list (pending, approved or rejected, with the admin's comment), and Alerts gets a "My reports" list (open or resolved, with the admin's note). This needs two small read routes. The alternative shows only a "sent for approval" toast, so the operator never learns the outcome.

My calls (override any):
- **Login routing:** after login, admins go to `/admin` and operators go to `/op`. Staff still get the "not built yet" screen. Each side checks the role: an admin opening `/op` is sent to `/admin`, and an operator opening `/admin` is sent to `/op`.
- **Request adjustment** (`05c`): tap a stock row to open a bottom sheet with Material and area (fixed), System says (read only), Actual count, Reason, Details, and "Send for approval". The note "Stock changes only after the Barangay Administrator approves" is shown, as in the wireframe.
- **Record outgoing** (`07b`): type is Recyclable sale, Compost or Residual. The fields follow the type, using the same rules as `OutgoingIn`:
  - a sale needs material, area and price
  - residual needs an area and has no material or price
  - compost has neither
  The area picker shows the kg on hand ("Area A · 248.0 kg"). Total = kg × price is shown live. Server errors show inline.
- **Outgoing list:** the operator sees every outgoing record, like the admin page, with status chips. The KPI cards (sold, income, compost, residual this month) are kept as in wireframe `07`, since `/operations/outgoing` already allows operators.
- **Report a problem** (`08b`): pick Device problem or Incorrect record.
  - **Device:** a device picker from `GET /devices`, opened to operators. It lists only code, type, location and online status; keys are never included (`DeviceOut` has no key).
  - **Record:** a code field with suggestions (an HTML `datalist`) from the last 3 days of deliveries, and "What should it be?".
- **Alerts:** open, acknowledged and all, with Acknowledge, using the existing routes.
- **Forms:** react-hook-form + zod, mirroring the server rules, the same as the admin drawers. The server stays the authority.
- **Touch:** buttons and rows are at least 44 px tall, inputs use `inputmode="decimal"` for kg and price, and sheets close with Cancel or Escape.

## Backend (small additions only)
| Module | Change |
|---|---|
| `approvals/` | `GET /inventory/adjustments/mine?days=30` (operator): the operator's own requests, newest first, using the existing `adjustment_out` |
| `alerts/` | `GET /problems/mine?days=30` (operator): the operator's own reports, newest first, using the existing `ProblemOut` |
| `devices/` | `GET /devices` opens to operators (`viewer()`); other device routes stay admin only |

No migrations: every table already has `requested_by` / `reported_by`.

## Frontend
- `web/src/app/RequireRole.tsx`, replacing `RequireAdmin` (`role` prop; wrong role → redirect to that role's home; staff → the existing "not built yet" card).
- `web/src/layout/OperatorLayout.tsx`: a top bar with the name and Log out, the page, and a bottom tab bar (Storage, Outgoing, Alerts with the open count).
- `web/src/features/operator/`: `StoragePage.tsx` (areas with fill bars, stock list, adjustment sheet, My requests), `OutgoingPage.tsx` (KPIs, record list, new-record sheet), `AlertsPage.tsx` (tabs, acknowledge, report sheet, My reports).
- A `Sheet` component in `components/ui.tsx`: the existing `Drawer` as a bottom sheet on phones. If a style switch on `Drawer` is enough, no new component.
- **Reuse:** `FillBar`/`Kpi` (`components/charts.tsx`), `kg`, `peso` and `when` (`features/operations/shared.tsx`), `Toast`, `btn`/`inputCls`, and the hooks in `api/operations.ts`, `api/alerts.ts` and `api/masterdata.ts`.

## Order of work (each step ends working, tested and committed)
1. Backend: the two "mine" routes and opening `GET /devices` to operators, with tests.
2. Role routing (`RequireRole`, login redirect) and `OperatorLayout`, with an empty page per tab.
3. Storage: areas, stock, the adjustment sheet, My requests.
4. Outgoing: KPIs, list, the new-record sheet with live total.
5. Alerts: list, acknowledge, the report sheet, My reports.
6. Browser test `operator-01-requests.spec.ts` on the `mobile` project (390 × 844), see below.
7. Roadmap ticks, README/testing notes, vault session note.

## Tests that must pass
- **Mine routes:** an operator sees only their own requests and reports, newest first, within the day range. Other operators' rows are hidden. Admins and staff → 403.
- **Devices:** an operator can list devices, and no key or key hash appears in the response. Creating or editing a device is still admin only.
- **Overall:** every existing test still passes, Ruff is clean, `npm run build` passes, and all browser tests pass (the admin tests keep running on desktop).

### Browser test `operator-01-requests.spec.ts` (phone size)
- An e2e operator logs in and lands on `/op/storage`. Opening `/admin` sends them back.
- They request an adjustment on an e2e area's stock. It shows as Pending under My requests, and it appears in the admin's Approvals inbox.
- The admin approves it, and the operator's list shows Approved.
- They record a residual disposal from the e2e area. It shows Pending approval with its O-code.
- They report an incorrect record using a delivery code, and it appears under My reports and on the admin's Alerts › Problem reports tab.
- They log out.

`remove-test-data` already clears e2e users, e2e areas with their stock and requests, and problem reports about e2e records.

## Verification
- `pytest`, `ruff check .`, `tsc -b`, `npm run build`, then `npm run test:e2e` (mobile and desktop) and `remove-test-data`.
- Screenshots at 390 × 844 of Storage (with the sheet open), Outgoing (with the new-record sheet and live total), and Alerts (with the report sheet). Also one at desktop width to check the centred column. Compare them with wireframes `05`, `05c`, `05d`, `07`, `07b`, `07c`, `08` and `08b`.

## Not in this plan
- **Other operator screens:** Today, Intake, Segregation, Sorting, Compost, History and Profile (OPR-02, 03–12, 14, 15, 18, 21).
- **Storage actions:** transfer between areas (`05b`) and "Add to storage".
- **Offline recording (OPR-09)** and the PIN sign-in (that is the IoT floor station).
- **Editing or cancelling** a request after it is sent.
- **Staff screens.**

## What changed while building
- **No new sheet component:** the existing `Drawer` already fills the screen on a phone (`max-w-full`), so it is used as is. On a laptop it opens at the right edge, outside the centred column.
- **`GET /devices` opens to admins and operators only** (`require_role`), not `viewer()`, so staff stay out.
- **The old test `test_only_admins_manage_devices`** now expects an operator to list devices (200) and still not register one (403).
- **Alerts tabs are Open, Acknowledged and Resolved** (the API's states), not "All".
- **`remove-test-data` also deletes problem reports about e2e deliveries.** Before, it only caught `E2E-…` references, so the operator test would have left reports behind.
- **The `Period` toggle** (`features/operations/shared.tsx`) now takes string values as well as numbers.
- **Results:** 149 API tests and 19 browser tests (18 desktop, 1 phone) pass; Ruff, `tsc -b` and `npm run build` are clean. Screenshots at 390 × 844 (Storage, the adjustment sheet with errors, the new sale with live total, Alerts, the device report) and at 1440 × 900 (the centred column) were checked against the wireframes.
