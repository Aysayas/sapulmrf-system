# Report findings and AI summary

Built 2026-11-11. Covers ADM-18 reports, and adds the "report feedback" and "report support" ideas.

## What it does
- **Findings:** each report gets a few sentences computed from its own data: how it compares with the previous period of the same length, what needs attention, and what to do next. They're always correct, because the app computes them. They show on the report page, in the PDF and in the CSV (above the table).
- **Suggested questions:** "How does this compare to last period?", "What needs attention?" and "What should we do next?" filter the findings. These are on the admin report preview and the staff "View" sheet.
- **AI summary (optional):** "Explain this report" asks a local LLM to reword the comparison and attention findings as one paragraph. The paragraph is dropped if it contains any number, in digits or words, that isn't in the findings. The findings are always shown, so a failed summary hides nothing.

## Where it lives
| Part | File |
|---|---|
| Findings rules per report | `api/app/reports/findings.py` |
| Hooked into every report | `build()` in `api/app/reports/service.py` |
| PDF and CSV output | `api/app/reports/render.py` |
| AI summary and number check | `api/app/reports/narrate.py` |
| Routes | `GET /reports/{kind}/narrative` (admin), `GET /reports/exports/{id}/narrative` (admin and staff with the reports grant, income and segregation rules unchanged) |
| Screen | `web/src/features/reports/ReportFindings.tsx` |

## Turning on the AI summary
1. Run `docker compose --profile ai up -d ollama`. On the first run, pull the model: `docker compose exec ollama ollama pull qwen2.5:7b` (4.7 GB).
2. Set `OLLAMA_URL=http://ollama:11434` in `.env`, then run `docker compose up -d api`.
3. Wait for `docker compose exec ollama ls /tmp/ready` to succeed. This takes 1–4 minutes after a start, because the container loads the model and answers once so the first click is quick.

While it's off or still warming up, the button says the summary isn't available. The findings stay on the page.

## Model check (Step 0)
Both candidates got the same 9 real reports from the dev data (6 kinds, 7 and 30 days; only 9 had distinct findings). Every paragraph was then checked by hand.

| Model | Numbers correct | Meaning correct (by hand) | Time per paragraph | Licence |
|---|---|---|---|---|
| **qwen2.5:7b** (chosen) | 9/9 | 9/9 | 4–11 s | Apache 2.0 |
| llama3.2:3b | 8/9 (wrote "zero" for 0%) | 7/9 (garbled a purok name, misread "none in the previous 7 days") | 5–13 s* | Llama 3.2 Community |

*Measured while qwen was also loaded. Alone, llama3.2:3b took about 1–2 s.

What changed during the check:
- **Advice isn't sent to the model.** With advice included, qwen twice rewrote "Plan a reminder" as "a reminder is planned". Advice now stays in the findings and under "What should we do next?".
- **No examples in the prompt.** An example phrase ("plan a visit") was copied into most paragraphs as made-up advice.
- **Findings never say "down 100%"** while some is left. Rounding is capped at 99%.

## Limits
- The number check catches wrong figures, but not every change in meaning (for example, "up" written as "down"). The paragraph is labelled as an AI summary, and the findings above it are the source of truth.
- On this laptop (RTX 4050, 6 GB), the model runs about 75% on the GPU and 25% on the CPU, and holds about 4.6 GB of GPU memory while the `ai` profile is up.
- The summary cache is in memory, per API process (marked `shortcut:` in the code).
- The home server's hardware is unknown, so production runs with the summary off until it's checked.
