# Plan: switch the unusual-weight flags to the modified z-score (MAD)

## Why
On unseen simulated data, the modified z-score caught every planted outlier with about half the z-score's false flags. Isolation Forest missed about 1 in 6. Results are in `docs/operator-staff-plan.md`.

## The check
For one purok's earlier weights:

`M = 0.6745 x |weight - median| / MAD`, flag if `M > limit`

MAD is the median distance of the earlier weights from their median.

- **Stays the same:** 10 earlier deliveries minimum, last 100 as history, flagged weights left out of the history unless marked incorrect, one check per purok, and the gap check.
- **Noise allowance stays:** a weight within 0.3 kg of the median is never flagged.
- **Identical history (MAD = 0):** anything past the 0.3 kg allowance is flagged.
- **Usual-range text on a flag:** unchanged (mean +/- SD of the clean history), so admins see the same wording.
- **Existing flags:** stay as they are. Only new deliveries use the new check.

## Decision for you: the default limit
Measured read-only on 20 more unseen seeds (160 planted outliers, 8,800 normal deliveries), with the 0.3 kg allowance. The last two columns are new weights on a clean 40-weight history, of 210.

| Limit | Planted caught | False flags | 1.5 x usual caught | 1.8 x usual caught |
|---|---|---|---|---|
| 2.5 | 160 | 439 (4.99%) | 157 | 210 |
| 3.0 | 160 | 192 (2.18%) | 91 | 207 |
| **3.5** | **160** | **71 (0.81%)** | **33** | **191** |
| 4.0 | 160 | 23 (0.26%) | 12 | 145 |
| 5.0 | 160 | 8 (0.09%) | 3 | 54 |

**Recommended: 3.5.** It's the published standard, so it's easy to defend and wasn't tuned on this project's data. The admin can change it. Choosing 3.0 catches more moderate weights for about 2.7 times the false flags.

## Changes
- **`api/app/insights/flags.py`:** `is_unusual` becomes the formula above. Remove the Isolation Forest code and its constants.
- **Setting:** `anomaly_pct` becomes `anomaly_limit`, default 3.5, allowed 2 to 6. Lower now flags more, the opposite direction from today. Changes go in `settings/models.py`, `settings/schemas.py`, `web/src/api/settings.ts`, a new migration, and `RangesPage.tsx`, labelled "Unusual-weight limit (lower flags more)".
- **Migration:** every saved value resets to 3.5, because a percentage has no equivalent limit. The downgrade restores `anomaly_pct` at 2.
- **Dependency:** scikit-learn stays, because the Ridge forecasts use it.
- **Tests, `test_flags.py` and `test_settings.py`:**
  - Rewrite the sensitivity test for the limit. With the test's usual weights (median 8.0, MAD 0.2), 9.0 kg gives M of about 3.4: not flagged at 3.5, flagged at 3.
  - Add a test for the hand-worked example: an old outlier in the history doesn't hide a new one.
  - Keep the rest, adjusting any that assumed the forest.
- **Docs:** roadmap lines 16 and 117, and a note in `operator-staff-plan.md` that this replaced Isolation Forest. `docs/ai-assistant-plan.md` stays untouched.

## Effects
- **Faster deliveries:** no model is fitted on each delivery, so the roughly 0.05 s per delivery goes away.
- **AI wording for your defence:** the weight flags are now statistics. The ML in the system is the Ridge forecasts.
- **Accepted weakness:** a weight 1.5 x the usual is usually not flagged at 3.5.

## Verification
`alembic upgrade head`, then downgrade and upgrade again; `pytest`; `ruff check .`; `npx tsc --noEmit`; `npm run build`; `npm run test:e2e`; `remove-test-data`. Replay the shipped code on unseen seeds and confirm it matches the table above. Screenshot the Ranges page. Commit locally only.

## Results
Built at limit 3.5. Replaying the shipped `is_unusual`: seeds 5000-5019 caught 160 of 160 with 71 of 8800 false flags, matching the table. Dev database (806 rows): caught 15 of 15 with 4 of 704 false flags. `pytest` 190 passed, `ruff` clean, migration run up, down and up, `tsc --noEmit` clean, build OK, browser suite 21 of 21, `remove-test-data` ran. Ranges page screenshot checked. The replay uses the first deliveries in time order, so a record kept before this change is judged here by the new check only.

## Limits
All numbers come from simulated data, where planted outliers are 2.5 to 3.5 x usual. Re-check the limit once real deliveries exist.
