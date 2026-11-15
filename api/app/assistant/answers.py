"""One handler per topic. Each calls the function a SapulMRF page already uses and shapes its result into an Answer."""

from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy.orm import Session as DbSession

from app.alerts import service as alerts
from app.approvals import service as approvals
from app.assistant import guide
from app.assistant.dates import Period
from app.assistant.nlp import INTENTS, Guess, examples
from app.assistant.schemas import Answer, Card, Chart, ExportRef, Series, Table
from app.assistant.slots import Slots
from app.compost import service as compost
from app.core.errors import AppError
from app.insights import service as insights
from app.insights.models import ALL
from app.operations import service as ops
from app.reports import service as reports
from app.reports.schemas import Kind, Report

TOPIC = {
    "today": "Today",
    "intake": "Intake",
    "segregation": "Segregation",
    "storage": "Storage",
    "compost": "Compost",
    "outgoing": "Outgoing",
    "income": "Income",
    "forecast": "Forecast",
    "unusual": "Unusual deliveries",
    "attention": "Needs attention",
    "camera": "Camera accuracy",
    "help": "What I can answer",
    "smalltalk": "Chat",
    "guide": "Using the website",
}
DEFAULT_PERIOD = {
    "intake": "this month",
    "segregation": "this month",
    "outgoing": "this month",
    "income": "this month",
    "camera": "last 30 days",
}
REPORT = {"intake": "intake", "segregation": "segregation", "outgoing": "outgoing", "income": "income"}
VALUE_COLUMNS = ("Weight (kg)", "Amount (PHP)", "Compliance (%)", "Compost (kg)")
MAX_ROWS = 20


def _kg(v: float) -> str:
    return f"{v:,.1f} kg"


def _notes(*parts: str | None) -> str | None:
    text = " ".join(p for p in parts if p)
    return text or None


def _period(intent: str, slots: Slots, today: date) -> tuple[Period, str | None]:
    """The question's dates, or the topic's default with a note saying so."""
    if slots.period:
        return slots.period, None
    if DEFAULT_PERIOD.get(intent) == "last 30 days":
        return Period(today - timedelta(days=29), today, "the last 30 days"), "Assumed the last 30 days."
    return Period(today.replace(day=1), today, "this month"), "Assumed this month."


def _unknown(slots: Slots) -> str | None:
    return " ".join(f"No {u} in SapulMRF, so this covers all puroks." for u in slots.unknown) or None


def _which_dates(intent: str, detail: str) -> Answer:
    return Answer(
        intent=intent,
        title="Which dates?",
        summary=detail,
        suggestions=[f"{TOPIC[intent]} this month", f"{TOPIC[intent]} last month", f"{TOPIC[intent]} last 7 days"],
    )


def _chart(r: Report) -> Chart | None:
    """Bar of the report's first column against its main number, summed per label."""
    col = next((c for c in VALUE_COLUMNS if c in r.columns), None)
    if col is None or not r.rows:
        return None
    i = r.columns.index(col)
    # label by the first text column that varies (one purok's report is charted by its categories),
    # else by the most specific one; a count column is never a label
    text = [j for j in range(i) if all(isinstance(row[j], str) for row in r.rows)] or [0]
    label = next((j for j in text if len({row[j] for row in r.rows}) > 1), text[-1])
    totals: dict[str, float] = {}
    for row in r.rows:
        if isinstance(row[i], int | float):
            totals[str(row[label])] = totals.get(str(row[label]), 0.0) + float(row[i])
    if not totals:
        return None
    return Chart(kind="bar", x=list(totals), series=[Series(name=col, values=[round(v, 2) for v in totals.values()])])


def _report(
    db: DbSession,
    intent: str,
    kind: Kind,
    slots: Slots,
    today: date,
    area: int | None = None,
    extra: str | None = None,
    period: Period | None = None,
) -> Answer:
    p, assumed = (period, None) if period else _period(intent, slots, today)
    if p.from_day > today:
        return _which_dates(intent, "Those dates haven't happened yet. Ask about today or earlier.")
    try:
        r = reports.build(db, kind, p.from_day, min(p.to_day, today), area)
    except AppError as e:
        if e.status_code != 422:
            raise
        return _which_dates(intent, e.detail)
    findings = sorted(r.findings, key=lambda f: f.topic != "compare")[:2]
    return Answer(
        intent=intent,
        title=" · ".join([r.title, *([slots.purok[1]] if area and slots.purok else []), p.label]),
        summary=" ".join(f.text for f in findings) or r.subtitle,
        cards=[Card(label=k, value=v) for k, v in r.summary],
        table=Table(columns=r.columns, rows=r.rows[:MAX_ROWS]) if r.rows else None,
        chart=_chart(r),
        export=ExportRef(kind=kind, from_day=p.from_day, to_day=min(p.to_day, today), area=area),
        note=_notes(assumed, _unknown(slots), extra),
    )


def _by_purok(intent: str):
    def handler(db: DbSession, slots: Slots, today: date) -> Answer:
        return _report(db, intent, REPORT[intent], slots, today, area=slots.purok[0] if slots.purok else None)

    return handler


def _all_puroks(intent: str):
    def handler(db: DbSession, slots: Slots, today: date) -> Answer:
        extra = "Sales and give-aways aren't tracked per purok, so this covers all puroks." if slots.purok else None
        return _report(db, intent, REPORT[intent], slots, today, extra=extra)

    return handler


def _today(db: DbSession, slots: Slots, today: date) -> Answer:
    o = ops.overview(db)
    cards = [
        Card(label="Drop-offs today", value=str(o.today_deliveries)),
        Card(label="Received today", value=_kg(o.today_kg)),
        Card(label="Waiting for segregation", value=str(o.awaiting_segregation)),
        Card(label="Wet waste waiting", value=_kg(o.wet_waiting_kg)),
        Card(label="In storage", value=_kg(o.in_storage_kg)),
        Card(label="Income this month", value=f"PHP {o.income_month:,.2f}"),
    ]
    chart = (
        Chart(
            kind="line",
            x=[d.day.isoformat() for d in o.intake_14d],
            series=[Series(name="kg per day", values=[d.kg for d in o.intake_14d])],
        )
        if o.intake_14d
        else None
    )
    return Answer(
        intent="today",
        title="Today at a glance",
        summary=f"{o.today_deliveries} drop-offs and {_kg(o.today_kg)} received so far today.",
        cards=cards,
        chart=chart,
        note=_unknown(slots),
    )


def _material_stock(db: DbSession, slots: Slots, today: date) -> Answer:
    """How much of one material is in storage, area by area."""
    mid, name = slots.material
    rows = [[s.area, s.kg, s.bags] for s in ops.inventory(db).stock if s.material_id == mid and s.kg > 0]
    total = sum(r[1] for r in rows)
    where = f" across {len(rows)} area(s)" if len(rows) > 1 else f" in {rows[0][0]}" if rows else ""
    return Answer(
        intent="storage",
        title=f"{name} in storage",
        summary=f"There is {_kg(total)} of {name.lower()} in storage{where}."
        if rows
        else f"There is no {name.lower()} in storage right now.",
        cards=[Card(label=f"{name} in storage", value=_kg(total)), Card(label="Bags", value=str(sum(r[2] for r in rows)))],
        table=Table(columns=["Storage area", "Stock (kg)", "Bags"], rows=rows) if rows else None,
        chart=Chart(kind="bar", x=[r[0] for r in rows], series=[Series(name="kg", values=[r[1] for r in rows])])
        if rows
        else None,
        export=ExportRef(kind="inventory", from_day=today, to_day=today),
        note=_unknown(slots),
    )


def _smalltalk(db: DbSession, slots: Slots, today: date) -> Answer:
    replies = {
        "thanks": ("You're welcome!", "You're welcome! Ask anytime about intake, storage, compost or sales."),
        "who": (
            "I'm Ask SapulMRF",
            "I'm Ask SapulMRF, a helper on this website. I answer from SapulMRF's own records, "
            "and I can explain what a word means or where to find a page. I don't use an AI model.",
        ),
    }
    title, summary = replies.get(
        slots.chat or "",
        ("Hello!", "Hello! Ask me about today, intake, storage, compost, sales, or how to do something on this website."),
    )
    return Answer(
        intent="smalltalk", title=title, summary=summary, suggestions=[examples(i, 1)[0] for i in ("today", "storage", "income")]
    )


def _guide(db: DbSession, slots: Slots, today: date) -> Answer:
    entry, _ = guide.find(slots.text)
    if entry is None:
        close = guide.nearest(slots.text, 3)
        return Answer(
            intent="guide",
            title="I don't have a guide for that yet",
            summary="These are the closest things I can explain. Pick one, or ask in other words.",
            suggestions=[e.questions[0] for e in close],
            links=[e.link for e in close[:1]],
        )
    return Answer(intent="guide", title=entry.title, summary=entry.text, steps=list(entry.steps), links=[entry.link])


def _storage(db: DbSession, slots: Slots, today: date) -> Answer:
    if slots.material and not slots.storage_area:
        return _material_stock(db, slots, today)
    fill = ops.area_fill(db)
    look = {o.area: o for o in insights.outlook(db, insights.today())}
    if slots.storage_area:
        fill = [a for a in fill if a.id == slots.storage_area[0]] or fill
    rows, cards = [], []
    for a in fill:
        o = look.get(a.name)
        full = f"{o.days_to_full} days" if o and o.days_to_full is not None else "not filling"
        rows.append([a.name, a.kg, a.capacity_kg, a.pct, full])
        cards.append(
            Card(label=a.name, value=f"{a.pct}% full", delta=f"full in {full}" if o and o.days_to_full is not None else None)
        )
    soonest = min((o for o in look.values() if o.days_to_full is not None), key=lambda o: o.days_to_full, default=None)
    summary = (
        f"{soonest.area} fills first, in about {soonest.days_to_full} days."
        if soonest
        else "No storage area is filling up right now."
    )
    return Answer(
        intent="storage",
        title="Storage",
        summary=summary,
        cards=cards[:6],
        table=Table(columns=["Storage area", "Stock (kg)", "Capacity (kg)", "Full (%)", "Full in"], rows=rows),
        chart=Chart(kind="bar", x=[a.name for a in fill], series=[Series(name="Full (%)", values=[a.pct for a in fill])])
        if fill
        else None,
        export=ExportRef(kind="inventory", from_day=today, to_day=today),
        note=_unknown(slots),
    )


def _compost(db: DbSession, slots: Slots, today: date) -> Answer:
    waiting = compost.wet_waiting(db)
    batches = ops.compost_batches(db, False)
    rows = [[b.code, f"day {b.day}", b.start_kg] for b in batches]
    p, assumed = _period("compost", slots, today)
    return Answer(
        intent="compost",
        title="Compost",
        summary=f"{_kg(waiting)} of wet waste is waiting, with {len(batches)} batch(es) in progress.",
        cards=[Card(label="Wet waste waiting", value=_kg(waiting)), Card(label="Batches in progress", value=str(len(batches)))],
        table=Table(columns=["Batch", "Age", "Started with (kg)"], rows=rows) if rows else None,
        export=ExportRef(kind="composting", from_day=p.from_day, to_day=min(p.to_day, today)),
        note=_notes(_unknown(slots)) if slots.period else None,
    )


def _forecast(db: DbSession, slots: Slots, today: date) -> Answer:
    cat = slots.category[0] if slots.category else ALL
    p = insights.predictions(db, cat)
    if not p.ready:
        return Answer(
            intent="forecast",
            title="Forecast",
            summary=f"Not enough data yet: {p.days_of_records} of {p.min_days} days of records.",
        )
    nxt = sum(d.kg for d in p.forecast)
    x = [d.day.isoformat() for d in p.history] + [d.day.isoformat() for d in p.forecast]
    hist = [d.kg for d in p.history] + [0.0] * len(p.forecast)
    ahead = [0.0] * len(p.history) + [d.kg for d in p.forecast]
    error = p.errors_7d.get(p.model_used)
    return Answer(
        intent="forecast",
        title=f"Forecast · {slots.category[1] if slots.category else 'all waste'}",
        summary=f"About {_kg(nxt)} expected over the next 7 days.",
        cards=[
            Card(label="Next 7 days", value=_kg(nxt)),
            Card(label="Model", value="Machine learning" if p.model_used == "ml" else "Moving average"),
            Card(label="Error (last 7 days)", value=f"{error:.0f}%" if error is not None else "-"),
        ],
        chart=Chart(kind="line", x=x, series=[Series(name="Recorded", values=hist), Series(name="Forecast", values=ahead)]),
    )


def _unusual(db: DbSession, slots: Slots, today: date) -> Answer:
    flags = insights.open_flags(db, MAX_ROWS)
    rows = [
        [f.code, f.received_at.date().isoformat(), f.source_area, f.kind, f.value_kg, f"{f.expected_low:g}-{f.expected_high:g}"]
        for f in flags
    ]
    return Answer(
        intent="unusual",
        title="Unusual deliveries",
        summary=f"{len(flags)} open flag(s) to check." if flags else "Nothing unusual is open right now.",
        cards=[Card(label="Open flags", value=str(len(flags)))],
        table=Table(columns=["Code", "Date", "Purok", "Kind", "Value (kg)", "Expected (kg)"], rows=rows) if rows else None,
    )


def _attention(db: DbSession, slots: Slots, today: date) -> Answer:
    s = alerts.summary(db, True)
    c = approvals.counts(db)
    waiting = {
        "Sales to review": c["outgoing_review"],
        "Recounts to review": c["adjustments_review"],
        "Fixes to review": c["fixes"],
        "Weights to review": c["weights"],
        "Camera changes to review": c["classifications"],
        "Flags": c["flagged"],
        "Requests": c["adjustments"] + c["outgoing"],
    }
    total = s.open_alerts + s.open_reports + sum(waiting.values())
    cards = [Card(label="Open alerts", value=str(s.open_alerts)), Card(label="Problem reports", value=str(s.open_reports))]
    cards += [Card(label=k, value=str(v)) for k, v in waiting.items() if v]
    rows = [[i.type, i.title, i.details] for i in s.latest]
    return Answer(
        intent="attention",
        title="Needs your attention",
        summary=f"{total} item(s) are waiting for you." if total else "Nothing is waiting for you.",
        cards=cards,
        table=Table(columns=["Type", "Title", "Details"], rows=rows) if rows else None,
    )


def _camera(db: DbSession, slots: Slots, today: date) -> Answer:
    days = slots.days or 30
    a = insights.camera_accuracy(db, days)
    rows = [[m.material, m.suggested, m.kept, m.changed, m.changed_to or "-"] for m in a.by_material]
    return Answer(
        intent="camera",
        title=f"Camera accuracy · last {days} days",
        summary=(
            f"Operators kept {a.kept_pct}% of {a.confirmed} camera suggestions."
            if a.confirmed
            else "No camera suggestions were confirmed in that time."
        ),
        cards=[
            Card(label="Kept as suggested", value=f"{a.kept_pct}%"),
            Card(label="Confirmed", value=str(a.confirmed)),
            Card(label="Changed", value=str(a.changed)),
            Card(label="Changes marked wrong", value=str(a.reviewed_wrong)),
        ],
        table=Table(columns=["Camera said", "Suggested", "Kept", "Changed", "Usually changed to"], rows=rows) if rows else None,
        chart=Chart(
            kind="bar",
            x=[m.material for m in a.by_material],
            series=[
                Series(name="Kept (%)", values=[round(100 * m.kept / m.suggested) if m.suggested else 0 for m in a.by_material])
            ],
        )
        if a.by_material
        else None,
        note=None if slots.days else "Assumed the last 30 days.",
    )


def _help(db: DbSession, slots: Slots, today: date) -> Answer:
    topics = [i for i in INTENTS if i not in ("help", "smalltalk")]  # guide included: "how do I…"
    return Answer(
        intent="help",
        title="What I can answer",
        summary="Ask about any of these, in English or Tagalog. Add a purok, a material or dates to narrow it down.",
        cards=[Card(label=TOPIC[i], value=examples(i, 1)[0]) for i in topics],
        suggestions=[examples(i, 1)[0] for i in ("today", "intake", "storage", "income")],
    )


HANDLERS: dict[str, Callable[[DbSession, Slots, date], Answer]] = {
    "today": _today,
    "intake": _by_purok("intake"),
    "segregation": _by_purok("segregation"),
    "storage": _storage,
    "compost": _compost,
    "outgoing": _all_puroks("outgoing"),
    "income": _all_puroks("income"),
    "forecast": _forecast,
    "unusual": _unusual,
    "attention": _attention,
    "camera": _camera,
    "help": _help,
    "smalltalk": _smalltalk,
    "guide": _guide,
}


def answer(db: DbSession, intent: str, slots: Slots, today: date) -> Answer:
    if slots.bad_dates and (intent in DEFAULT_PERIOD or intent == "compost"):
        return _which_dates(intent, "That date doesn't exist. Check the day and the month.")
    a = HANDLERS[intent](db, slots, today)
    has = {"chart": a.chart is not None, "table": a.table is not None, "export": a.export is not None}
    return a.model_copy(update={"show": [w for w in slots.wants if has[w]]})


def unsure(guess: Guess) -> Answer:
    return Answer(
        intent="unsure",
        title="Did you mean…",
        summary="I'm not sure what you're asking. Pick one, or ask in other words.",
        suggestions=[examples(guess.intent, 1)[0], examples(guess.runner_up, 1)[0], "What can you answer?"],
    )
