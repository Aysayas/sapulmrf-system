# Backend improvement plan

Group 0 results, measured on 2026-10-31 with simulated data (about 1,080 deliveries). Nothing here changed code or data.

**Labels:** CONFIRMED was reproduced, or shown by reading where noted. PLAUSIBLE follows from the code but needs real concurrency to show. No finding was dropped.

## Baseline timings
Inside the API process, as admin, median of 5 runs. Browser and proxy time aren't included, and the two login queries aren't counted.

| Endpoint | Median ms | Queries | Bytes |
|---|---|---|---|
| `/operations/outgoing?days=30` | 242 | 245 | 19,805 |
| `/approvals` | 185 | 182 | 14,768 |
| `/operations/intake` | 165 | 201 | 20,053 |
| `/operations/camera` | 93 | 59 | 592 |
| `/insights/flags` | 91 | 106 | 12,128 |
| `/operations/sorting` | 85 | 53 | 7,487 |
| `/insights/predictions` | 77 | 31 | 2,934 |
| `/operations/compost` | 55 | 19 | 107,465 |
| `/overview` | 49 | 31 | 8,203 |
| `/operations/segregation` | 17 | 3 | 602 |
| `/operations/inventory` | 15 | 5 | 1,051 |
| `/reports/recent` | 14 | 1 | 2,281 |
| `/alerts/summary` | 13 | 2 | 835 |
| `/alerts` | 11 | 1 | 1,106 |

The six report previews (Sep 21 to Oct 31) each take 13 to 18 ms with 2 to 6 queries, so they need no work.

Everything is under half a second today, so the query counts matter for growth, not as a current fault.

## Findings, by severity

| # | Severity | Finding | Label | Fix | Effort | Risk |
|---|---|---|---|---|---|---|
| 1 | High | Approving a stale adjustment puts sold stock back (`approvals/service.py:128`) | CONFIRMED | 409 if stock differs from `system_kg` | S | Reverses a behaviour a test pins |
| 2 | High | A lost response then a resubmit records twice (`intake/service.py:40`, `sorting/service.py:102`, `approvals/service.py:89`) | CONFIRMED | Nullable unique `client_key`, migration, three API hooks | M | Schema change |
| 3 | High | CSV formula injection (`reports/render.py:21-27`, `activity/service.py:60`) | CONFIRMED, not opened in Excel | Shared helper prefixes `'` on strings only | S | Low |
| 4 | High | Login: repeated relock, unknown names unthrottled, hash runs while holding a connection (`auth/service.py:22`) | CONFIRMED; the count race is PLAUSIBLE | Release the connection, lock the row; per-IP limit at the proxy | M | Relock needs the proxy limit |
| 5 | High | Buffered readings get upload time, retries duplicate, old overwrites new (`compost/service.py:68-83`) | CONFIRMED by reading | `read_at`, unique per device, guard `last_reading` | M | Needs Rhendel's agreement |
| 6 | High | No backups, insecure cookies by default, `--reload` image | CONFIRMED by reading | Group 7 | L | Needs the server |
| 10 | High | Simulator stops recording 8 hours after login; seen live at 15:44 UTC | CONFIRMED live; the double delivery is PLAUSIBLE | Re-login on 401, advance `next_delivery` first | S | Low |
| 7 | Medium | "Scale" label can be forged (`intake/service.py:44`). Narrower than first reported: manual weights skip the review too | CONFIRMED | Require `device_id` when scale | S | Test fixtures change |
| 8 | Medium | Compost approvals can exceed stock (`approvals/service.py:142`) | PLAUSIBLE | Advisory lock | S | Low |
| 9 | Medium | Dead worker invisible, no tracebacks, no catch-all, no restart on `api` or `sim` | CONFIRMED | Traceback, handler, restart policy, worker status in `/health` | S | Low |
| 11 | Medium | Deactivating an area hides its stock from totals and blocks moving it (`masterdata/service.py:61`) | CONFIRMED; reactivating recovers it | 409 while stock remains | S | Low |
| 12 | Medium | "Incorrect" keeps the weight in the baseline, while the wording says the record is wrong (`insights/flags.py:40`). Nine kept 200 kg typos on a short history made 200 kg look normal | CONFIRMED in memory | See the decision below | S | Label change |
| 13 | Medium | Dependencies are ranges with no lock file | CONFIRMED by reading | Lock file; dev tools split out | M | Dev container must keep pytest |
| 14 | Medium | Tests can't catch migration drift or lock contention | CONFIRMED by reading | `alembic check` in CI, one two-connection test | S | Low |
| 15 | Low | Bad input gives 500: null user fields, 0.001 kg, overflowing totals. A 0.001 price gives a sale with no income | CONFIRMED; duplicate segregation race PLAUSIBLE | Validators and `exclude_none`, row lock | S | Low |
| 16 | Low | Ghost bags after adjustments; staff with only predictions see camera accuracy | CONFIRMED | Fix bags; null `camera` unless granted | S | Low |
| 16b | Low | `confirm` has no row lock (`sorting/service.py:56`) | PLAUSIBLE | `with_for_update` | S | Low |
| 17 | Low | Model picked on 14 days and scored on an overlapping 7. No direct leakage; 18 forecast days only, so indicative | CONFIRMED | Pick on days 8-14, show last 7 | S | Low |
| 18 | Low | `image_url` accepts any string; `stable` never enforced; contract says `image_id`, API takes `image_url` | CONFIRMED | Validate https; agree the contract in Group 4 | S | Needs Rhendel |

Effort: S under an hour, M a few hours, L a day or more.

## Decisions
- **#1:** the approved plan returns 409, so the operator recounts. This replaces "the count wins" in `test_approvals.py:122`.
- **#12:** the approved default stands: "Incorrect" means "false alarm, the weight is real". It stays in the baseline and in forecasts, so the label changes to match. A real typo is corrected through a problem report. This is why the verifier's alternative, excluding every flagged weight, isn't used, and why #17 doesn't drop these records from forecast training.

## Not doing
Everything listed under "Not doing" in the approved plan. Also: no per-table `updated_at` versioning for #1, since comparing with `system_kg` is enough.

## Assumed, not shown
- All timings and accuracy come from simulated data on this laptop.
- Races labelled PLAUSIBLE were never run concurrently.
- CSV behaviour wasn't checked in real Excel.

## Group 5 results
Same method as the baseline, measured after the fixes. Medians in ms; simulated data had grown slightly between the two runs.

| Endpoint | Before ms | After ms | Before queries | After queries |
|---|---|---|---|---|
| `/operations/outgoing?days=30` | 242 | 22 | 245 | 10 |
| `/operations/intake` | 165 | 19 | 201 | 5 |
| `/insights/flags` | 91 | 29 | 106 | 5 |
| `/operations/sorting` | 85 | 21 | 53 | 10 |
| `/operations/camera` | 93 | 19 | 59 | 8 |
| `/approvals` | 185 | 161 | 182 | 86 |
| `/insights/predictions` | 77 | 67 | 31 | 31 |
| `/overview` | 49 | 45 | 31 | 31 |

- **Admin shell:** now polls `/approvals/counts` (5 queries, 21 ms) instead of the whole `/approvals`.
- **`/approvals`:** barely faster, because the approval screen does need its ledger sums. Left as it is.
- **`/insights/predictions`:** the date bounds on `daily_kg` didn't change the timing at this size. They only matter once there's much more history.
- **First-load script:** one 1,015 KB file became a 465 KB main file, plus 394 KB of charts loaded only by pages that use them. Other pages load as small separate files.
- **Indexes added:** `compost_readings (batch_id, read_at)`, `stock_movements (delivery_id)`. Their effect wasn't measured separately.

## Final check
Re-measured after all changes, with the simulator running. Data keeps growing, so small differences mean little.

| Endpoint | Baseline ms | Final ms | Baseline queries | Final queries |
|---|---|---|---|---|
| `/operations/outgoing?days=30` | 242 | 33 | 245 | 10 |
| `/operations/intake` | 165 | 28 | 201 | 5 |
| `/approvals` | 185 | 118 | 182 | 88 |
| `/insights/flags` | 91 | 19 | 106 | 5 |
| `/operations/camera` | 93 | 21 | 59 | 8 |
| `/operations/sorting` | 85 | 27 | 53 | 10 |
| `/insights/predictions` | 77 | 56 | 31 | 31 |
| `/overview` | 49 | 49 | 31 | 31 |
| `/operations/compost` | 55 | 70 | 19 | 19 |

**Got slower:** `/operations/compost` went from 55 to 70 ms with the same queries, while its response grew from 107 KB to 121 KB as readings piled up. It's still fast, and it sends every reading in range, so it will keep growing with the data.

**Slightly slower by design:** a few fast endpoints (`/operations/inventory`, 15 to 20 ms) are within measurement noise.

Passing: `alembic check`, 241 API tests, `ruff`, `tsc --noEmit`, build, 30 of 30 browser tests.

**Review findings fixed after the first pass:** a failed page load blanking the app, buffered readings landing on the wrong batch, deploy skipping a backup, and unsafe characters in the database password.

## Algorithm review (2026-11-01)
Measured read-only on the same replays before and after. All data is simulated or synthetic.

| Test | Before | After |
|---|---|---|
| Lasting weight change (8 to 16 kg), of the next 100 deliveries flagged | 100 | 41 |
| Same, last 20 flagged | 20 | 0 |
| Held-out seeds, planted outliers caught, 1 delivery a day | 160 of 160 | 160 of 160 |
| Held-out seeds, false flags, 1 delivery a day | 71 of 8,800 | 65 of 8,800 |
| Same, 3 deliveries a day | 71 of 8,800 | 70 of 8,800 |
| 500 kg typo, Ridge day-7 forecast (true about 72 kg) | 400 kg | 81 kg |
| Regular 10x typos, Ridge error against true values | 9,122% | 14.4% |
| 14 days of history, forecast vs true average | 0.11 to 2.20 x | 0.92 to 1.06 x |
| 21 days of history | 0.00 to 1.98 x | 0.98 to 1.10 x |

**Got slightly worse:** on clean synthetic data, 1-day error went from 13.4% to 14.6% and total error from 13.2% to 13.4%, because the first two weeks now use the moving average. Accepted for the stability above.

**Clean backfill history (39 days to Oct 22), total error:** old Ridge 18.7%, new Ridge 16.0%, moving average 15.5%. 1-day error is 16.9% and 7-day error is 16.5% for new Ridge; 16.8% and 15.5% for the moving average. So the two are about level, and the moving average is slightly ahead. **Quote these for your defence, with their limits, not the current live figures:** the database still holds the 4,307 and 3,742 kg simulator days.

**What changed:**
- Undecided flags rejoin the usual weights after 14 days. The review proposed 30, but 14 measured better on every row. "Valid" flags stay out, so an admin should mark a real new normal "False alarm".
- `capped()` compares a day with the same weekday up to 4 weeks either side. The first version compared with the whole 90 days and clipped real Saturdays, which the independent check caught.
- Ridge needs 28 days. Removing its trend input didn't measure better overall, so it stays.
- The model is picked on days 8 to 14 back by total kg error, with at least 5 scored days. The page still shows average % error, so a chosen model can show the higher figure; the page says how it was chosen.
- The simulator defaults to about 20 deliveries a day.
- Alert titles follow the current problem.

**Known limits:**
- The first two weeks of a real lasting rise are held to about 1.5 x (a 100 to 200 kg rise forecasts 150 kg), then it passes.
- A typo on a weekday that is usually closed isn't capped.
- Saved forecasts aren't recalculated; new ones use the new code.
- `mad == 0` still flags anything past 0.3 kg, as approved in `docs/flags-mad-plan.md`: history 5, 5, 5, 5, 5, 5, 5, 6, 4, 5 flags 5.4 kg. Real scales give varied decimals, so re-check on real data.
