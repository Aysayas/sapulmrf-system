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

## What changed while building

### Isolation Forest: the plan's version did worse, so it changed
The first version (100 trees, `contamination` = the setting, all recent weights as history) did worse than the z-score it replaced. Earlier outliers stayed in the window and hid later ones, and short histories were flagged about 1 time in n + 1 whatever the setting. A review caught this before the change was described as an upgrade.

What ships now:
- Weights already flagged stay out of the history, unless the admin marked the flag incorrect.
- The new weight must also reach a minimum anomaly score: 0.80 minus the setting (0.78 at the default 2%).
- A weight within 0.3 kg of the usual mean is never flagged, which covers near-identical history.
- 50 trees rather than 100: about 0.05 s per delivery, inside its transaction.

Results, 2.5 SD z-score against the shipped check, from one read-only replay per row. "Formula" is 3 seeds x 7 puroks x 74 weights from `delivery_weight`. "Dev database" is the backfilled deliveries (670 rows at the time), treating weights over 2.2 x the purok median as the planted outliers.

| Data | Method | Outliers caught | False flags |
|---|---|---|---|
| Formula | z-score 2.5 SD | 27 of 27 | 14 of 1317 |
| Formula | Isolation Forest, first version (measured before the change) | 22 of 27 | 33 of 1317 |
| Formula | Isolation Forest, shipped, 0.1% | 27 of 27 | 1 of 1317 |
| Formula | Isolation Forest, shipped, 2% (default) | 27 of 27 | 4 of 1317 |
| Formula | Isolation Forest, shipped, 20% | 27 of 27 | 288 of 1317 |
| Dev database | z-score 2.5 SD | 9 of 9 | 5 of 591 |
| Dev database | Isolation Forest, shipped, 2% | 9 of 9 | 1 of 591 |

Read these with care:
- **The minimum score was chosen on this same formula replay**, so the 4 is optimistic. 0.82 dropped to 24 of 27 caught, so the margin is thin.
- **All of this is simulated data**, with outliers 2.5 to 3.5 times the usual weight. It says nothing yet about real deliveries.
- **The forest misses smaller surprises on tight histories.** At the default setting, with 10 weights around 8 kg (SD about 0.3), 10 kg isn't flagged and 12 kg is. The z-score flags 10 kg. So this is fewer false flags on this data, not better in every case.
- **The setting is a sensitivity, not an exact share of records**, so the Ranges page now says "Unusual-weight sensitivity (higher flags more)". The field is still `anomaly_pct`.

### Held-out check, after the build
The table above was tuned on the replay it reports, so I re-ran the shipped code on data it never saw: 10 new seeds x 7 puroks x 74 weights. The z-score here keeps every earlier weight, as it shipped.

| Data | Method | Outliers caught | False flags |
|---|---|---|---|
| Held-out formula | z-score 2.5 SD | 83 of 85 (98%) | 37 of 4395 (0.84%) |
| Held-out formula | Isolation Forest, shipped, 2% | 72 of 85 (85%) | 14 of 4395 (0.32%) |
| Dev database (683 rows) | z-score 2.5 SD | 9 of 9 | 5 of 604 |
| Dev database (683 rows) | Isolation Forest, shipped, 2% | 9 of 9 | 1 of 604 |
| Clean 40-weight history, new weight 1.5 x usual | z-score / Isolation Forest | 37 of 42 / 8 of 42 | not applicable |
| Clean 40-weight history, new weight 1.8 x usual | z-score / Isolation Forest | 42 of 42 / 42 of 42 | not applicable |

**So the forest is not better overall: it raises fewer false flags and misses more real outliers.** The earlier 27 of 27 was optimistic. The misses are mostly one mechanism: an outlier among a purok's first 10 deliveries is never judged, so it stays in the history and hides later weights of similar size (usual 6.6 kg, history holding 20.88 kg, new 20.36 kg not flagged). I did not tune again, because that would use up this held-out set too.

### Other checks measured (no app code changed)
Same weights in the same order, standard limits with no tuning. MAD is the modified z-score, flagging `|M| > 3.5`. These are read-only replays on simulated data, and each purok keeps its own history. The app still ships Isolation Forest.

| Data | Method | Outliers caught | False flags |
|---|---|---|---|
| Seeds 1000-1009 | z-score 2.5 SD | 83 of 85 | 37 of 4395 |
| Seeds 1000-1009 | Isolation Forest, shipped | 72 of 85 | 14 of 4395 |
| Seeds 1000-1009 | MAD | 85 of 85 | 17 of 4395 |
| Seeds 3000-3009 | z-score 2.5 SD | 69 of 70 | 56 of 4410 |
| Seeds 3000-3009 | Isolation Forest, shipped | 58 of 70 | 10 of 4410 |
| Seeds 3000-3009 | MAD | 70 of 70 | 34 of 4410 |
| Seeds 3000-3009 | IQR 1.5 | 70 of 70 | 249 of 4410 |
| Seeds 3000-3009 | Isolation Forest, weight and wet share | 31 of 70 | 0 of 4410 |
| Dev database (749 rows) | z-score 2.5 SD | 12 of 12 | 5 of 667 |
| Dev database (749 rows) | Isolation Forest, shipped | 12 of 12 | 1 of 667 |
| Dev database (749 rows) | MAD | 12 of 12 | 4 of 667 |
| Dev database (749 rows) | IQR 1.5 | 12 of 12 | 17 of 667 |
| Dev database (749 rows) | Isolation Forest, weight and wet share | 3 of 12 | 0 of 667 |

Moderate outliers on a clean 40-weight history, caught of 42 (z-score / shipped forest / MAD / IQR / two-feature forest): 1.5 x usual 39 / 7 / 5 / 33 / 0; 1.8 x usual 42 / 40 / 38 / 42 / 0; 2.2 x usual 42 / 42 / 42 / 42 / 3.

MAD caught every planted outlier with fewer false flags than the z-score, but it misses most 1.5 x weights. The simulator plants outliers only at 2.5 to 3.5 x, so these results favour methods that are strict on smaller surprises. It also plants nothing in wet share, so the two-feature result shows the extra column hurts weight detection, not its value for odd combinations.

### Access and data rules found in review
- Staff get `/operations/outgoing` without income, price or total. Before, only the screen hid them.
- Staff exports leave out income always, and segregation without its grant. Viewing and downloading an export are now logged, for admins too.
- Approving an outgoing or an adjustment now locks the record and its storage area, the same lock transfers take. Sorting locks the delivery and its areas, so a second submit gets 409 instead of adding stock twice. The tests check that the locks are taken, not a real race, because each test runs in one transaction.
- Wrong current passwords on `/auth/me/password` now count toward the same lockout as login.
- Transfers with no bag count move bags in proportion to the kg. A partial transfer can't take every bag. An explicit count that is otherwise wrong is still accepted, because the operator can see the real bags.

### Wireframe gaps closed
- Today shows the "Predicted" line and each alert's details. The Predicted line appears only once predictions are ready.
- Segregation has Undo, through a new `DELETE /deliveries/{id}/segregation`: only the operator who made the check, within 30 minutes, and before sorting. The saved message stays until dismissed.
- Compost batch detail shows 7 days of readings (`/operations/compost?days=7`). Other pages still get 24 hours.

### Rejected on purpose
- A capacity check on sorting. Sorted waste is already on the floor, so refusing the record wouldn't stop the overfill, it would only hide it. The storage alert covers this. Sorting does now take the area lock.

### Final checks
pytest 190 passed, ruff clean, `tsc --noEmit` clean, web build OK, browser suite 21 of 21 passed, then `remove-test-data` ran. After the workflow I re-ran all of these myself with the same results, then looked at every operator screen at 390 x 844 and every staff screen at 1440 x 900, with and without grants, against the wireframe text. Three small bugs came out of that and were fixed: Today's "tomorrow" figure was really today's forecast, an over-full area read "full in ~0 days", and the period filter and delivery code could be squeezed on the admin and staff Intake table.
