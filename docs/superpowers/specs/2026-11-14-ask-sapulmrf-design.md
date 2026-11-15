# Ask SapulMRF: an admin chat over SapulMRF's own data (rule-based NLP, no AI model)

## Context
The admin wants an interactive summary: type a question about the MRF's data (English, Tagalog or Taglish) and get a clear answer, with history, in a good chat UI, on the website only (no kiosk work).
- **No local model:** the Ollama summary (`app/reports/narrate.py`) is too heavy for the laptop.
- **No online AI either:** the user chose rule-based NLP, so it stays free and offline.
- **No photos and no uploads:** answers are page visuals (number cards, table, chart) and offer the existing CSV/PDF export when a report covers the question.
- **Why it's feasible:** most answers already exist as functions behind the Reports, Insights and Operations pages. The chat's job is to understand the question and pick the right function with the right dates and filters.

A camera (CV) review was also done (findings at the end). Fixing those is a separate, later piece of work.

## Decisions (from the user)
- **NLP:** option B, a small trained intent classifier (scikit-learn TF-IDF + logistic regression, already installed) plus rule-based slot extraction. When unsure, it shows "Did you mean…" buttons.
- **Visuals:** no photos. HTML visuals only, and exports through the chat when available.
- **Layout:** a history sidebar (past chats on the left, the thread in the middle, the composer at the bottom with suggestion chips).

## My calls (stated to the user, correctable)
- **Where and who:** a page "Ask SapulMRF" under Analyze in the admin nav (`/admin/assistant`), for admins only.
- **History:** saved in the database per admin. Reopening a chat shows each answer as it was, with its time, plus an "Ask again" button that re-runs it with today's numbers. This changes the earlier "re-run automatically" idea: saved answers are truthful and simpler.
- **Follow-ups:** "and Purok 4?" keeps the previous question's topic and dates and changes only what's new.
- **Missing dates:** a default per topic (e.g. this month), and the answer says what it assumed.
- **Language:** answers are in English, like the rest of the admin site; questions may be English, Tagalog or Taglish.
- **Feedback:** a 👍/👎 on each answer, stored, so mis-understood questions can be added to the examples later. It also gives a real accuracy measure for the thesis.

## Backend: `api/app/assistant/` (new module)
- **`examples.json`:** intents mapped to ~20–30 example questions each (EN/TL/Taglish), plus a held-out test list.
- **Intents:**

  | Intent | Answered by |
  |---|---|
  | `today` | `operations.service.overview` |
  | `intake` | `reports.service.build(kind="intake")` |
  | `segregation` | `build("segregation")` |
  | `storage` | `operations.inventory`, `area_fill`, `insights.outlook` |
  | `compost` | `compost.service.wet_waiting`, `operations.compost_batches` |
  | `outgoing` | `build("outgoing")` |
  | `income` | `build("income")` |
  | `forecast` | `insights.predictions` |
  | `unusual` | `insights.open_flags` |
  | `attention` | `alerts.summary` + `approvals.counts` |
  | `camera` | `insights.camera_accuracy` |
  | `help` | example chips |

- **`nlp.py`:**
  - `normalize` (lowercase, strip accents and punctuation).
  - The classifier is a `FeatureUnion` of char_wb 2–4-grams (typos, Tagalog affixes) and word 1–2-grams, then `LogisticRegression`. It's trained once, lazily, and cached (training takes well under a second).
  - `classify(text) -> (intent, score, runner_up)` with a threshold of about 0.45.
  - **Slots:**
    - Dates in `dates.py`: today/ngayon, yesterday/kahapon, this or last week/linggo, this or last month/buwan, this year, last N days, month names (EN + Enero…Disyembre), "Nov 1–15", ISO dates.
    - Purok ("purok 3", "p3").
    - Material, area or category, matched against master data with difflib (ratio ≥ 0.85).
    - A "compare" flag.
  - **Context:** a low-score question that still has slots reuses the previous intent in the conversation, and missing slots are inherited from the previous turn.
- **`answers.py`:** one handler per intent, `(db, slots) -> Answer`.
  - `Answer` has: `title`, `summary` (one or two sentences, reusing `reports/findings.py` sentences when a report is built), `cards[{label, value, delta?}]`, `table{columns, rows ≤ 20}`, `chart{kind: bar|line, x, series}`, `export{kind, from, to, area}|null`, `note` (assumptions), and `suggestions[]`.
  - Numbers always come from the called function. No free text is generated.
- **`models.py` plus a migration:**
  - `assistant_conversations(id, user_id, title, created_at, updated_at)`
  - `assistant_messages(id, conversation_id, role, text, intent, score, slots JSON, answer JSON, helpful bool|null, corrected_intent str|null, created_at)`
- **`router.py`** (admin only, the `require_role("admin")` pattern):
  - `POST /assistant/ask {conversation_id?, text}` returns the new user and assistant messages.
  - `GET /assistant/conversations` and `GET /assistant/conversations/{id}`. Only your own; another admin's gives 404.
  - `PATCH` (rename) and `DELETE /assistant/conversations/{id}`.
  - `POST /assistant/messages/{id}/feedback {helpful}`.
  - `GET /assistant/suggestions`.
  - Registered in `main.py` like the others.
- **Exports:** the answer carries `export`, and the web links to the existing `GET /api/reports/{kind}/export?format=csv|pdf&from&to&area`, which already logs the export.

## Web: `web/src/features/assistant/`
- **`AssistantPage.tsx`:**
  - Left: History, grouped by Today / Yesterday / Last 7 days / Older, with rename, delete and "+ New chat".
  - Centre: the thread.
  - Bottom: the composer (Enter sends, Shift+Enter makes a new line) with topic chips.
  - On a phone, the sidebar becomes the existing `Drawer`.
- **`AnswerView.tsx`:**
  - number cards with deltas
  - a Recharts bar or line chart
  - a compact table
  - the summary sentence and the assumption note
  - "Download CSV / PDF" buttons
  - "Did you mean" chips and 👍/👎
- **Empty state:** a greeting plus example chips per topic.
- **`web/src/api/assistant.ts`:** react-query hooks on the `api()` client.
- **Routing:** the route in `app/App.tsx`, and a nav item in `layout/AdminLayout.tsx` under Analyze.
- **Styling:** the `index.css` tokens and the `components/ui.tsx` pieces. Polish with the impeccable skill during the build.

## Settled after the builder check
- **Compare:** previous period only, as the user chose. `build()` already returns the previous-period comparison, so the cards show +/- %. There's no two-purok comparison.
- **Two kinds of area:**
  - A **purok** (`SourceArea`) filters only intake and segregation (`builders.py:24` `BY_AREA`). For outgoing and income, the answer covers all puroks and the `note` says so.
  - A **storage area** (`StorageArea`) is its own slot, for storage/outlook.
  - **Category** (`WasteCategory`, `ALL = 0`) is only for the forecast.
- **Call details:**
  - `outlook(db, insights.service.today())`
  - `alerts.summary(db, True)`
  - `camera_accuracy(db, days)` (default 30)
  - `open_flags(db, limit)` (no dates)
  - `overview(db)` (today only)
  - Use `r.findings[:2]` from `build()` for the summary.
  - For `predictions()`, check `ready`/`days_of_records`/`min_days` and say "not enough data yet" when it isn't ready.
  - Catch `build()`'s 422 (bad or over-366-day range) and turn it into a clarification answer.
- **Exports:**
  - Kinds: intake, segregation, inventory (storage), composting (compost), outgoing, income.
  - The web uses the existing `useExportReport` in `web/src/api/reports.ts`, which calls `/reports/{kind}/export` through `download()`; there's no `/api` prefix in the API itself.
- **Wiring:** import the new models in `api/app/models.py`; use sqlalchemy `JSON` (as `devices/models.py` does); add `ICON['/admin/assistant']` in `AdminLayout.tsx`; follow the migration style of `d19b985ccd91_report_exports.py`.
- **My calls:**
  - Default dates: this month (intake, segregation, outgoing, income), last 30 days (camera).
  - The chart's x-axis and series come from the report rows.
  - The conversation title is the first question, cut to 60 characters.
  - **"Ask again"** adds a new answer message and keeps the old one.
  - **👎** shows the "Did you mean" topic buttons; picking one re-answers and stores the corrected intent (`corrected_intent` column) for retraining.
- **Build order:**
  1. `dates.py` and slots, with tests.
  2. `examples.json`, the classifier and the held-out accuracy test. **This is the riskiest part;** measure it early, especially the overlapping intents (today vs intake, storage vs forecast).
  3. The answer handlers.
  4. Models, migration and routes.
  5. Web: API hooks, `AnswerView`, the page, the nav.
  6. Playwright.

## Tests
- **pytest:**
  - intent accuracy on the held-out list ≥ 90%
  - date parsing and slot extraction cases
  - each handler against the test world
  - routes: admin only, history is private, delete/rename, feedback, and a follow-up inheriting slots
- **Playwright:** ask → cards + chart visible → history entry → export link correct → reopen the chat.

## Not in scope
- Photos and uploads.
- An online or local LLM.
- Staff access.
- Charts beyond bar and line.
- The camera fixes (separate, after).

## Camera review findings (for the later piece of work)
- "Kept" counts as correct even when the admin marked it wrong.
- There's no full confusion table, only the top correction (`insights/service.py:123`). Missed items are invisible.
- `model_version` is stored but never compared.
- There's no low-confidence queue: the 0.6 threshold is only in `operator/SortingPage.tsx:12`, and the list is sorted by time.
- Photos are small thumbnails that can't be enlarged. `cv_counts` and `cv_confidence` are never shown.
- Unknown kiosk labels are dropped silently (`devices/kiosk.py:56`).

## Verification
1. Run `docker compose exec -T api pytest -q` and `ruff check .`; `cd web; npx tsc -b; npx playwright test`; then `remove-test-data`.
2. Open the page in the browser and ask 10 real questions across topics, in English and Tagalog: check the numbers match the Reports and Insights pages, the follow-up works, "Did you mean" appears for nonsense, the history survives a reload, and the export downloads.
