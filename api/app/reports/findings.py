"""Plain-language findings for a report, computed from its own rows and the previous period of the same length.

Every number here comes from the data, so the page, PDF, CSV and the optional AI summary can trust them.
"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.insights import service as insights
from app.insights.models import Flag
from app.intake.models import Delivery
from app.operations.service import pct
from app.reports.schemas import Finding, Report
from app.settings import service as ranges

LOW_COMPLIANCE = 80  # below this a purok is worth a reminder or visit
FILL_SOON_DAYS = 14  # warn about areas filling up within this many days


def _kg(x: float) -> str:
    return f"{x:,.2f} kg"


def _php(x: float) -> str:
    return f"PHP {x:,.2f}"


def _col(r: Report, name: str) -> list:
    """One column's values, or [] when the report has no such column."""
    if name not in r.columns:
        return []
    i = r.columns.index(name)
    return [row[i] for row in r.rows]


def _total(r: Report, name: str) -> float:
    return sum(float(v) for v in _col(r, name) if v != "")


def _by(r: Report, key: str, value: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in zip(_col(r, key), _col(r, value), strict=False):
        out[k] = out.get(k, 0) + float(v)
    return out


def _period(days: int) -> str:
    return "the day before" if days == 1 else f"the previous {days} days"


def _change(what: str, now: float, before: float, days: int, fmt) -> str | None:
    if now == 0 and before == 0:
        return None
    if before == 0:
        return f"{what} was {fmt(now)}, with none in {_period(days)}."
    if now == before:
        return f"{what} was {fmt(now)}, the same as {_period(days)}."
    word = "up" if now > before else "down"
    change = pct(abs(now - before), before)
    if word == "down" and now > 0:
        change = min(change, 99)  # rounding must not say "down 100%" while some is left
    return f"{what} was {fmt(now)}, {word} {change}% from {fmt(before)} in {_period(days)}."


def _share(r: Report, key: str, value: str, what: str, fmt) -> str | None:
    by = _by(r, key, value)
    total = sum(by.values())
    if len(by) < 2 or total <= 0:
        return None
    top, v = max(by.items(), key=lambda kv: kv[1])
    return f"{top} {what} the most: {fmt(v)} ({pct(v, total)}% of the total)."


def _intake(db, r, prev, days, start, end, area):
    out = [("compare", _change("Intake", _total(r, "Weight (kg)"), _total(prev, "Weight (kg)"), days, _kg)),
           ("compare", _share(r, "Source area", "Weight (kg)", "brought", _kg))]
    q = (select(func.count(Flag.id)).join(Delivery, Delivery.id == Flag.delivery_id)
         .where(Flag.status == "open", Delivery.received_at >= start, Delivery.received_at < end))
    if area:
        q = q.where(Delivery.source_area_id == area)
    n = db.scalar(q) or 0
    if n:
        word = "delivery has" if n == 1 else "deliveries have"
        out.append(("attention", f"{n} {word} an unusual weight or sorting gap still waiting for review."))
        out.append(("next", "Review the flagged records in Approvals so the forecasts and reports stay accurate."))
    return out


def _compliance(r: Report) -> tuple[int, int]:
    return int(_total(r, "Deliveries")), int(_total(r, "Segregated"))


def _segregation(db, r, prev, days, start, end, area):
    (n, ok), (pn, pok) = _compliance(r), _compliance(prev)
    out = []
    if n and pn:
        now, before = pct(ok, n), pct(pok, pn)
        diff = now - before
        how = "the same as" if diff == 0 else f"{'up' if diff > 0 else 'down'} {abs(diff)} points from {before}% in"
        out.append(("compare", f"Compliance was {now}%, {how} {_period(days)}."))
    checked = [row for row in r.rows if row[1]]
    if len(checked) > 1:
        name, total, good, p = min(checked, key=lambda row: (row[3], -row[1]))
        noun = "delivery" if total == 1 else "deliveries"
        out.append(("attention", f"{name} had the lowest compliance: {p}% ({good} of {total} {noun} segregated)."))
        if p < LOW_COMPLIANCE:
            out.append(("next", f"Plan a segregation reminder or visit for {name}."))
    empty = [row[0] for row in r.rows if not row[1]]
    if empty and checked:
        out.append(("attention", f"No checked deliveries from {', '.join(empty)}."))
    return out


def _inventory(db, r, prev, days, start, end, area):
    today = insights.today()
    areas = insights.outlook(db, today)
    out = []
    for o in areas:
        if o.pct >= o.alert_pct:
            out.append(("attention", f"{o.area} is at {o.pct}%, past its {o.alert_pct}% alert level."))
        elif o.days_to_full is not None and o.days_to_full <= FILL_SOON_DAYS:
            out.append(("attention", f"At the current pace, {o.area} is full in about {o.days_to_full} days."))
    for sg in insights.schedule(db, areas, today):
        out.append(("next", f"{sg.what} by {sg.on:%b %d}: {sg.why}."))
    return out


def _composting(db, r, prev, days, start, end, area):
    lim = ranges.get(db)
    out = []
    for row in r.rows:
        code, status, temp, wet = row[0], row[2], row[5], row[6]
        if status != "Active":
            continue
        if temp != "" and not lim.compost_temp_min <= temp <= lim.compost_temp_max:
            side = f"above the {lim.compost_temp_max} C limit" if temp > lim.compost_temp_max else \
                f"below the {lim.compost_temp_min} C minimum"
            out.append(("attention", f"Batch {code} is at {temp} C, {side}."))
            out.append(("next", f"Turn batch {code} and log the activity." if temp > lim.compost_temp_max else
                        f"Check batch {code}: it may need more green material or turning to heat up."))
        if wet != "" and not lim.moisture_min <= wet <= lim.moisture_max:
            dry = wet < lim.moisture_min
            out.append(("attention", f"Batch {code} moisture is {wet}%, {'below' if dry else 'above'} the "
                                     f"{lim.moisture_min if dry else lim.moisture_max}% {'minimum' if dry else 'limit'}."))
            out.append(("next", f"Add water to batch {code}." if dry else f"Turn batch {code} or add dry material."))
    done = [row for row in r.rows if row[2] == "Finished" and row[4] != ""]
    raw, made = sum(row[3] for row in done), sum(row[4] for row in done)
    if raw > 0:
        out.append(("compare", f"Finished batches turned {_kg(raw)} of raw waste into {_kg(made)} of compost "
                               f"({pct(made, raw)}% yield)."))
    return out


def _outgoing(db, r, prev, days, start, end, area):
    out = [("compare", _change("Outgoing waste", _total(r, "Weight (kg)"), _total(prev, "Weight (kg)"), days, _kg))]
    by = _by(r, "Kind", "Weight (kg)")
    total, dumped = sum(by.values()), by.get("Residual disposal", 0)
    if total > 0:
        kept = total - dumped
        out.append(("compare", f"{pct(kept, total)}% of outgoing waste was sold or composted, "
                               f"{pct(dumped, total)}% went to residual disposal."))
        if dumped * 2 > total:
            out.append(("attention", "More than half of outgoing waste went to residual disposal."))
            out.append(("next", "Check sorting for recyclables and compostables before the next disposal."))
    return out


def _income(db, r, prev, days, start, end, area):
    return [("compare", _change("Income", _total(r, "Amount (PHP)"), _total(prev, "Amount (PHP)"), days, _php)),
            ("compare", _share(r, "Material", "Amount (PHP)", "earned", _php))]


RULES = {"intake": _intake, "segregation": _segregation, "inventory": _inventory,
         "composting": _composting, "outgoing": _outgoing, "income": _income}


def find(db: DbSession, r: Report, prev: Report | None, from_day: date, to_day: date,
         start: datetime, end: datetime, area: int | None) -> list[Finding]:
    days = (to_day - from_day).days + 1
    prev = prev or r.model_copy(update={"rows": []})
    found = RULES[r.kind](db, r, prev, days, start, end, area)
    return [Finding(topic=t, text=x) for t, x in found if x]
