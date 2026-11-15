# Ask SapulMRF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An admin-only chat page, "Ask SapulMRF", that answers questions about SapulMRF's own data with number cards, a chart, a table and exports, keeping a per-admin history. There is no AI model.

**Architecture:** A new `api/app/assistant/` module:
- rules pull dates and names out of the question
- a small scikit-learn classifier picks the topic
- one handler per topic calls the functions the Reports, Insights and Operations pages already use, and shapes an `Answer`
- conversations and messages are stored in two new tables

The web gets one page, `web/src/features/assistant/`, with a history sidebar.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, scikit-learn 1.9.1 (already pinned), React 19 + TypeScript, react-query 5, recharts 3, Tailwind v4 tokens.

**Spec:** `docs/superpowers/specs/2026-11-14-ask-sapulmrf-design.md`

## Global Constraints
- No LLM, no new Python or npm dependency, no photos, no uploads.
- Admin only: every route uses `require_role("admin")` (pattern: `admin_only = require_role("admin")` in `reports/router.py:16`).
- Every number in an answer comes from an existing service function. The assistant never writes free text that holds a number it computed itself.
- Answers are in English. Questions may be English, Tagalog or Taglish.
- Dates are local barangay time (`settings.timezone`, the `TZ` used in `operations/service.py`).
- Report ranges go through `reports.service.build(db, kind, from_day, to_day, area)`. Only `intake` and `segregation` honour `area` (a purok / `SourceArea` id). Report kinds: `intake, segregation, inventory, composting, outgoing, income`.
- **Commits:** SapulMRF commits only when the user says "commit". Every task's last step is "stage", not commit.
- **Checks:** run `docker compose exec -T api pytest -q`, `docker compose exec -T api ruff check .`, `cd web; npx tsc -b; npx playwright test`, then `docker compose exec -T api python -m app.cli remove-test-data`.

## Review Focus
1. **Empty, blank or 600-character question:** blank gives 422 "Type a question."; the question is trimmed and limited to 500 characters (pydantic). Test in Task 4.
2. **Gibberish or off-topic** ("asdf", "what's the weather"): a "Did you mean" answer with topic buttons, never a confident wrong answer. Test in Task 2 (score below threshold) and Task 3 (`unsure` answer).
3. **A purok, area or material that doesn't exist** ("purok 99"): the answer covers everyone and its note says "No Purok 99 in SapulMRF, so this covers all puroks." Test in Task 1 and Task 3.
4. **A reversed, future or longer-than-a-year range** ("from Dec 5 to Nov 1", "next month", "last 2 years"): a clarification answer (title "Which dates?") instead of a 422 or a crash. Test in Task 3.
5. **A fresh database with no records:** every handler returns zeros or "nothing yet", not an error. The forecast says "not enough data yet". Test in Task 3 with an empty world.

---

### Task 1: Dates and names pulled from the question

**Files:**
- Create: `api/app/assistant/__init__.py` (empty), `api/app/assistant/dates.py`, `api/app/assistant/slots.py`
- Test: `api/tests/test_assistant_slots.py`

**Interfaces:**
- Produces:
  - `dates.parse_range(text: str, today: date) -> Period | None`, where `Period` is a frozen dataclass `(from_day: date, to_day: date, label: str)` and `to_day` is inclusive.
  - `slots.Names`: a dataclass of `puroks, storage_areas, materials, categories`, each `list[tuple[int, str]]`.
  - `slots.load_names(db) -> Names`, active rows only, from `SourceArea`, `StorageArea`, `Material`, `WasteCategory` in `app.masterdata.models`.
  - `slots.Slots`: a pydantic model with fields `period: Period | None`, `purok: tuple[int, str] | None`, `storage_area`, `material`, `category` (same shape), `unknown: list[str]` (names asked for but not found, e.g. "Purok 99"), `days: int | None` ("last N days").
  - `slots.extract(text: str, names: Names, today: date) -> Slots`.
  - `slots.normalize(text: str) -> str`: lowercase, strip accents (`unicodedata` NFKD), collapse punctuation to spaces.

- [ ] **Step 1: Write the failing tests** (today = `date(2026, 11, 14)`, a Saturday; weeks start on Monday)

```python
@pytest.mark.parametrize("text,frm,to", [
    ("today", "2026-11-14", "2026-11-14"), ("ngayon", "2026-11-14", "2026-11-14"),
    ("yesterday", "2026-11-13", "2026-11-13"), ("kahapon", "2026-11-13", "2026-11-13"),
    ("this week", "2026-11-09", "2026-11-14"), ("ngayong linggo", "2026-11-09", "2026-11-14"),
    ("last week", "2026-11-02", "2026-11-08"), ("noong isang linggo", "2026-11-02", "2026-11-08"),
    ("this month", "2026-11-01", "2026-11-14"), ("ngayong buwan", "2026-11-01", "2026-11-14"),
    ("last month", "2026-10-01", "2026-10-31"), ("nakaraang buwan", "2026-10-01", "2026-10-31"),
    ("last 7 days", "2026-11-08", "2026-11-14"), ("this year", "2026-01-01", "2026-11-14"),
    ("in october", "2026-10-01", "2026-10-31"), ("noong oktubre", "2026-10-01", "2026-10-31"),
    ("nov 1-5", "2026-11-01", "2026-11-05"), ("from 2026-10-03 to 2026-10-09", "2026-10-03", "2026-10-09"),
    ("december", "2025-12-01", "2025-12-31"),  # a month later than now means last year's
])
def test_parse_range(text, frm, to): ...
def test_no_date_gives_none(): assert parse_range("how much compost", TODAY) is None
def test_purok_material_area_and_unknown(names):  # names fixture: Purok 1..7, "Demo Area A · Plastics", Plastic, Paper
    s = extract("plastic from p3 and purok 99 in area a", names, TODAY)
    assert s.purok == (3, "Purok 3") and s.material[1] == "Plastic"
    assert s.storage_area[1].startswith("Demo Area A") and s.unknown == ["Purok 99"]
def test_typo_material_matches(names): assert extract("platic", names, TODAY).material[1] == "Plastic"
```

- [ ] **Step 2: Run them to make sure they fail:** `docker compose exec -T api pytest -q tests/test_assistant_slots.py`. Expected: ImportError.
- [ ] **Step 3: Implement `dates.py` and `slots.py`.**
  - Ordered regexes over `normalize(text)`, first match wins, with Tagalog synonyms in the same pattern.
  - Month names map English and Tagalog (`enero … disyembre`).
  - Names are matched by: purok number (`purok 3`, `p3`), else `difflib.get_close_matches(word, names, cutoff=0.85)` on single words and on two-word windows. Storage areas also match by their letter ("area a").
- [ ] **Step 4: Run them to make sure they pass.**
- [ ] **Step 5: Stage** `api/app/assistant/ api/tests/test_assistant_slots.py`.

### Task 2: The intent classifier and its examples

**Files:**
- Create: `api/app/assistant/examples.json`, `api/app/assistant/nlp.py`
- Test: `api/tests/test_assistant_nlp.py`

**Interfaces:**
- Consumes: `slots.normalize`.
- Produces:
  - `nlp.INTENTS: tuple[str, ...]` = `("today","intake","segregation","storage","compost","outgoing","income","forecast","unusual","attention","camera","help")`.
  - `nlp.THRESHOLD = 0.45`.
  - `nlp.Guess`, a dataclass of `intent: str, score: float, runner_up: str`.
  - `nlp.classify(text: str) -> Guess`, trained lazily on first call and cached at module level.
  - `nlp.examples(intent: str, n: int = 3) -> list[str]` (for help and suggestions).
- `examples.json` is `{"train": {intent: [questions…]}, "test": {intent: [questions…]}}`. Each intent has 20–30 train questions (English, Tagalog and Taglish mixed) and 5 test questions that aren't in train. Write the test ones first, without looking at train.

- [ ] **Step 1: Write the failing tests**

```python
def test_held_out_accuracy_is_at_least_90_percent():
    test = json.loads(EXAMPLES.read_text())["test"]
    pairs = [(q, i) for i, qs in test.items() for q in qs]
    right = sum(classify(q).intent == i for q, i in pairs)
    assert right / len(pairs) >= 0.90, [(q, i, classify(q).intent) for q, i in pairs if classify(q).intent != i]
def test_every_intent_has_examples(): assert set(json.loads(EXAMPLES.read_text())["train"]) == set(INTENTS)
@pytest.mark.parametrize("text", ["asdf qwer", "what's the weather", "sino ang presidente"])
def test_off_topic_scores_below_threshold(text): assert classify(text).score < THRESHOLD
def test_overlaps(): assert classify("magkano ang kinita ngayong buwan").intent == "income"; \
                     assert classify("kailan mapupuno ang area b").intent == "storage"
```

- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement `nlp.py`.**
  - `Pipeline([("f", FeatureUnion([("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(2,4))), ("w", TfidfVectorizer(ngram_range=(1,2)))])), ("m", LogisticRegression(max_iter=2000, C=10))])` on `normalize(text)`.
  - `score` is the top `predict_proba`. If the off-topic test fails, add an `"other"` training class of off-topic questions (never returned as an intent: it means score 0).
- [ ] **Step 4: Run the tests.** When accuracy is below 90%, widen the train examples (never the test ones) until it passes. Note the final accuracy in a comment at the top of `examples.json`'s loader.
- [ ] **Step 5: Stage.**

### Task 3: Answers, one handler per intent

**Files:**
- Create: `api/app/assistant/schemas.py`, `api/app/assistant/answers.py`
- Test: `api/tests/test_assistant_answers.py`

**Interfaces:**
- Consumes: `Slots`, `Period`, `Guess`, `nlp.examples`.
- Produces (in `schemas.py`):
  - `Card(label: str, value: str, delta: str | None = None)`
  - `Table(columns: list[str], rows: list[list[str | float | int | None]])` (≤ 20 rows)
  - `Series(name: str, values: list[float])`
  - `Chart(kind: Literal["bar","line"], x: list[str], series: list[Series])`
  - `ExportRef(kind: Kind, from_day: date, to_day: date, area: int | None)`
  - `Answer(intent: str, title: str, summary: str, cards: list[Card] = [], table: Table | None = None, chart: Chart | None = None, export: ExportRef | None = None, note: str | None = None, suggestions: list[str] = [])`
- Produces (in `answers.py`):
  - `answer(db, intent: str, slots: Slots, today: date) -> Answer`
  - `unsure(guess: Guess) -> Answer`, intent `"unsure"`, title "Did you mean…", with `suggestions` = an example question for the top two intents plus "What can you answer?"
  - `DEFAULT_PERIOD: dict[str, str]`: `this month` for intake, segregation, outgoing and income, and `last 30 days` for camera. The note says "Assumed this month."
- **Handler sources** (all existing; see the spec table):
  - Report intents use `reports.service.build`. `summary` is `" ".join(f.text for f in r.findings[:2])`, or `r.subtitle` when there are none. `cards` come from `r.summary`. `table` is the first 20 of `r.rows`. `chart` is a bar of the rows' first column against the first numeric column.
  - Catch `AppError` 422 from `build` → `Answer(title="Which dates?", summary=<its detail>)`.
  - Storage: `operations.service.area_fill` + `insights.service.outlook(db, insights.service.today())`; cards per area with pct and days to full; export `inventory`.
  - Compost: `compost.service.wet_waiting` + `operations.service.compost_batches(db, False)`; export `composting`.
  - Today: `operations.service.overview(db)`.
  - Forecast: `insights.service.predictions(db, category or ALL)`. When `not ready`, summary is "Not enough data yet: {days_of_records} of {min_days} days." Otherwise a line chart of history + forecast.
  - Unusual: `insights.service.open_flags(db, 20)`.
  - Attention: `alerts.service.summary(db, True)` + `approvals.service.counts(db)`.
  - Camera: `insights.service.camera_accuracy(db, slots.days or 30)`.
  - Help: one card per topic, using `nlp.examples`.
  - `export` is set for the six report kinds only.
  - A purok on outgoing or income adds the note "Sales and give-aways aren't tracked per purok, so this covers all puroks." `slots.unknown` adds "No {name} in SapulMRF, so this covers all puroks."

- [ ] **Step 1: Write the failing tests** (use the `world` fixture from `tests/conftest.py`)
  - `test_intake_answer_matches_the_report`: seed two deliveries; the answer's first card value equals `build(...).summary[0][1]`; `export.kind == "intake"`.
  - `test_purok_filters_intake_but_not_income`: income + purok → note contains "all puroks".
  - `test_reversed_range_asks_which_dates`: `Period(nov 5, nov 1)` → title "Which dates?".
  - `test_default_period_is_noted`: no period → note "Assumed this month."
  - `test_forecast_not_ready_on_empty_db`: summary starts "Not enough data yet".
  - `@pytest.mark.parametrize("intent", INTENTS)` → `test_every_handler_answers_on_an_empty_db`: it returns an `Answer` with a title and doesn't raise.
  - `test_unsure_offers_two_topics_and_help`: `len(suggestions) == 3`.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement `schemas.py` and `answers.py`.**
- [ ] **Step 4: Run them to make sure they pass.**
- [ ] **Step 5: Stage.**

### Task 4: History storage, follow-ups and routes

**Files:**
- Create: `api/app/assistant/models.py`, `api/app/assistant/service.py`, `api/app/assistant/router.py`, `api/migrations/versions/<rev>_assistant.py`
- Modify: `api/app/models.py` (import the models), `api/app/main.py` (`include_router`)
- Test: `api/tests/test_assistant_routes.py`

**Interfaces:**
- Consumes: `classify`, `extract`, `load_names`, `answer`, `unsure`, `Answer`.
- Produces:
  - Tables:
    - `assistant_conversations(id, user_id FK users ondelete CASCADE, title String(60), created_at, updated_at)`
    - `assistant_messages(id, conversation_id FK CASCADE, role String(9) check user|assistant, text String(500), intent String(16) null, score Float null, slots JSON null, answer JSON null, helpful Boolean null, corrected_intent String(16) null, created_at)`
    - `server_default=now()`, in the style of `d19b985ccd91_report_exports.py`.
  - `service.ask(db, user, text: str, conversation_id: int | None, intent: str | None = None) -> AskOut`.
    - `intent` given (a "Did you mean" chip, a 👎 correction, "Ask again") → skip `classify`.
    - **Follow-up rule:** if `guess.score < THRESHOLD` and the question has any slot and the conversation's last assistant message has an intent, use that intent. Every slot the question leaves empty is filled from that message's stored slots.
    - Stores both messages; the assistant message gets `slots` (JSON of `Slots`) and `answer` (JSON of `Answer`).
    - A new conversation's title is the question cut to 60 characters.
  - `service.feedback(db, user, message_id, helpful: bool) -> None`.
  - `AskOut(conversation_id: int, user: MessageOut, assistant: MessageOut)`.
  - `MessageOut(id, role, text, answer: Answer | None, helpful, created_at)`.
  - `ConversationOut(id, title, updated_at)`.
  - `ConversationDetail(ConversationOut + messages: list[MessageOut])`.
  - Routes, all admin only:
    - `POST /assistant/ask {text: str (1–500, trimmed), conversation_id?: int, intent?: str}` → `AskOut`
    - `GET /assistant/conversations` → `list[ConversationOut]`, newest `updated_at` first
    - `GET /assistant/conversations/{id}` → `ConversationDetail`
    - `PATCH /assistant/conversations/{id} {title}`
    - `DELETE /assistant/conversations/{id}` → 204
    - `POST /assistant/messages/{id}/feedback {helpful: bool, corrected_intent?: str}`
    - `GET /assistant/suggestions` → `list[str]`
  - Another admin's conversation or message gives 404.
  - When `corrected_intent` is sent, `feedback` stores it on the 👎 message, and the web then calls `ask` with `intent=corrected_intent`.

- [ ] **Step 1: Write the failing tests**
  - `test_staff_and_operators_get_403`.
  - `test_blank_question_is_422`; `test_long_question_is_422` (501 characters).
  - `test_ask_creates_a_conversation_titled_by_the_question`.
  - `test_follow_up_keeps_topic_and_dates`: ask "intake from purok 3 last month", then "and purok 4?" in the same conversation → the second answer's intent is `intake`, its slots have purok 4 and last month's period.
  - `test_intent_override_skips_the_classifier`.
  - `test_history_is_private`: a second admin gets 404 on GET, PATCH and DELETE, and on feedback.
  - `test_rename_delete_and_feedback`.
  - `test_reopened_conversation_returns_saved_answers_in_order`.
- [ ] **Step 2: Run them to make sure they fail.**
- [ ] **Step 3: Implement.**
  - Write the models, then generate the migration with `docker compose exec -T api alembic revision --autogenerate -m "assistant"` and check it.
  - Apply it with `alembic upgrade head`.
  - Add the service and the router, and register the router in `main.py` like the others.
- [ ] **Step 4: Run the new tests, then the full suite and ruff.**
- [ ] **Step 5: Stage.**

### Task 5: The Ask SapulMRF page

**Files:**
- Create: `web/src/api/assistant.ts`, `web/src/features/assistant/AssistantPage.tsx`, `web/src/features/assistant/AnswerView.tsx`, `web/src/features/assistant/History.tsx`
- Modify: `web/src/app/App.tsx` (route `assistant` under `/admin`), `web/src/layout/AdminLayout.tsx` (Analyze: `{to: '/admin/assistant', label: 'Ask SapulMRF'}` plus an `ICON` entry)

**Interfaces:**
- Consumes: the Task 4 routes; `api()` from `api/client.ts`; `useExportReport` from `api/reports.ts`; `btn`, `inputCls`, `Badge`, `PageHeader`, `Drawer` from `components/ui.tsx`.
- Produces:
  - Hooks: `useConversations()`, `useConversation(id)`, `useAsk()` (a mutation; on success it invalidates both queries), `useRename()`, `useDelete()`, `useFeedback()`, `useSuggestions()`.
  - TypeScript types mirroring `Answer`, `MessageOut`, `ConversationOut` and `AskOut`.
- **Layout** (from the approved sketch):
  - **Left column (w-64):**
    - "+ New chat"
    - conversations grouped Today / Yesterday / Last 7 days / Older by `updated_at`
    - rename (inline input) and delete (confirm in place, not `window.confirm`)
  - **Centre:**
    - the thread: user bubbles on the right; answers as cards on the left
    - the composer pinned to the bottom: a textarea (Enter sends, Shift+Enter makes a new line), a send button, and the topic chips from `useSuggestions` above it
  - **Below `lg`:** the sidebar sits in `Drawer`, opened by a History button.
  - **Empty state:** "Ask about intake, storage, compost, sales…" with the chips.
  - **While asking:** the user bubble appears at once, and three dots show until the answer arrives.
  - The selected conversation id is in the URL (`?c=<id>`), so a reload keeps it.
- **`AnswerView`:**
  - the title
  - the summary sentence
  - cards in a grid (the delta is green or red by sign)
  - a recharts `BarChart`/`LineChart` (height 220, tokens: `--color-leaf` for bars)
  - the table in a scrollable box
  - the note in muted text
  - "Download CSV" and "Download PDF" (`useExportReport` with `export`)
  - suggestion chips (each one asks, passing `intent` for "Did you mean" answers)
  - 👍/👎. 👎 reveals topic chips; picking one sends feedback with `corrected_intent`, then asks again with that intent.
  - "Ask again" re-sends the question to the same conversation.
- **Accessibility:** the thread is `aria-live="polite"`, the buttons have labels, and focus returns to the composer after sending.

- [ ] **Step 1: Write `assistant.ts`, `AnswerView`, `History` and `AssistantPage`, then wire the route and the nav.**
- [ ] **Step 2: `cd web; npx tsc -b`.** Expected: no errors.
- [ ] **Step 3: Polish with the impeccable skill.** Check it at 1280 px and at 390 px.
- [ ] **Step 4: Check it in the browser:** ask "how many kg from purok 3 last week?", then "and purok 4?", then "asdf". Reload: the history is still there. Download the CSV.
- [ ] **Step 5: Stage.**

### Task 6: Browser test

**Files:**
- Create: `web/e2e/admin-09-assistant.spec.ts` (follow `web/e2e/admin-07-reports.spec.ts` for the login and seed helpers)

- [ ] **Step 1: Write the test** "the admin asks about intake, follows up, sees the history and downloads the CSV". It asserts:
  - a card and the chart (`.recharts-surface`) are visible
  - the follow-up's title mentions the new purok
  - the history list has 1 entry that survives a reload
  - the CSV download's filename starts with `intake-report_`
  - "asdf" shows "Did you mean"
- [ ] **Step 2: Run** `npx playwright test e2e/admin-09-assistant.spec.ts`. Expected: pass.
- [ ] **Step 3: Run all the Global Constraints checks, then `remove-test-data`.**
- [ ] **Step 4: Stage,** then report to the user and wait for "commit".
