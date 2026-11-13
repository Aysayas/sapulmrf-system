from collections import Counter
from datetime import UTC, date, datetime, timedelta
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.db import preload
from app.core.errors import AppError
from app.insights import forecast as fc
from app.insights import schemas as s
from app.insights.models import ALL, Flag, Forecast
from app.intake.models import Delivery
from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory
from app.operations import service as ops
from app.settings import service as ranges
from app.sorting.models import Classification, StockMovement
from app.users.models import User

HISTORY_DAYS = 21
INFLOW_DAYS = 14
PLAN_DAYS = 14  # suggest a pickup or sale for areas reaching their alert level within this many days


def today() -> date:
    return datetime.now(ops.TZ).date()


# ---- predictions page


def outlook(db: DbSession, on: date) -> list[s.Outlook]:
    since = datetime(on.year, on.month, on.day, tzinfo=ops.TZ) - timedelta(days=INFLOW_DAYS)
    inflow = dict(tuple(r) for r in
        db.execute(
            select(StockMovement.storage_area_id, func.sum(StockMovement.kg))
            .where(StockMovement.kind == "sorted", StockMovement.at >= since)
            .group_by(StockMovement.storage_area_id)
        ).all()
    )
    rows = []
    for a in ops.area_fill(db):
        per_day = round(float(inflow.get(a.id, 0)) / INFLOW_DAYS, 2)
        left_full, left_alert = a.capacity_kg - a.kg, a.capacity_kg * a.alert_pct / 100 - a.kg
        rows.append(
            s.Outlook(
                area=a.name,
                pct=a.pct,
                kg=a.kg,
                capacity_kg=a.capacity_kg,
                alert_pct=a.alert_pct,
                per_day_kg=per_day,
                days_to_full=max(0, ceil(left_full / per_day)) if per_day > 0 else None,
                days_to_alert=max(0, ceil(left_alert / per_day)) if per_day > 0 else (0 if left_alert <= 0 else None),
            )
        )
    return sorted(rows, key=lambda o: (o.days_to_full is None, o.days_to_full or 0))


def schedule(db: DbSession, areas: list[s.Outlook], on: date) -> list[s.Suggestion]:
    """A pickup or sale the day before each area reaches its alert level, for areas getting there within PLAN_DAYS."""
    ids = {a.name: a.id for a in db.scalars(select(StorageArea))}
    out = []
    for o in areas:
        if o.days_to_alert is None or o.days_to_alert > PLAN_DAYS:
            continue
        stock = (
            db.execute(
                select(StockMovement.material_id)
                .where(StockMovement.storage_area_id == ids[o.area])
                .group_by(StockMovement.material_id)
                .having(func.sum(StockMovement.kg) > 0.5)
            )
            .scalars()
            .all()
        )
        names = sorted((db.get(Material, m) or Material(name="")).name.lower() for m in stock if m is not None)
        what = f"Sell {' and '.join(names)}" if names else "Residual pickup"
        reach = on + timedelta(days=o.days_to_alert)
        why = f"{o.area} already at {o.pct}%" if o.days_to_alert == 0 else f"{o.area} at {o.alert_pct}% by {reach:%b %d}"
        out.append(s.Suggestion(on=max(on, reach - timedelta(days=1)), what=what, why=why))
    return sorted(out, key=lambda x: x.on)


def camera_accuracy(db: DbSession, days: int = 30) -> s.CameraAccuracy:
    since = datetime.now(UTC) - timedelta(days=days)
    confirmed, changed, wrong = db.execute(
        select(
            func.count(Classification.id),
            func.count(Classification.id).filter(Classification.changed.is_(True)),
            func.count(Classification.id).filter(Classification.review == "wrong"),
        ).where(Classification.confirmed_at >= since)
    ).one()
    kept = confirmed - changed
    return s.CameraAccuracy(
        confirmed=confirmed, kept=kept, kept_pct=ops.pct(kept, confirmed), changed=changed, reviewed_wrong=wrong,
        by_material=_by_material(db, since), by_confidence=_by_confidence(db, since), kiosk=_kiosk_accuracy(db, since),
    )


def _confirmed(db: DbSession, since: datetime):
    return db.execute(
        select(Classification.suggested_material_id, Classification.final_material_id, Classification.not_recyclable,
               Classification.changed, Classification.confidence)
        .where(Classification.confirmed_at >= since)
    ).all()


def _by_material(db: DbSession, since: datetime) -> list[s.MaterialAccuracy]:
    """Per suggested material: how often operators kept it, and what they chose instead."""
    names = dict(db.execute(select(Material.id, Material.name)).all())
    rows: dict[int, dict] = {}
    for sug, final, not_rec, changed, _ in _confirmed(db, since):
        r = rows.setdefault(sug, {"n": 0, "kept": 0, "to": Counter()})
        r["n"] += 1
        if changed:
            r["to"]["Not recyclable" if not_rec else names.get(final, "?")] += 1
        else:
            r["kept"] += 1
    return sorted(
        (s.MaterialAccuracy(material=names.get(m, "?"), suggested=r["n"], kept=r["kept"], changed=r["n"] - r["kept"],
                            changed_to=r["to"].most_common(1)[0][0] if r["to"] else None) for m, r in rows.items()),
        key=lambda x: -x.suggested,
    )


BANDS = (("Below 60%", 0.0, 0.6), ("60–80%", 0.6, 0.8), ("80% and up", 0.8, 1.01))


def _by_confidence(db: DbSession, since: datetime) -> list[s.ConfidenceBand]:
    """Is "86% sure" worth anything? How often each confidence band was kept by the operator."""
    rows = _confirmed(db, since)
    out = []
    for band, lo, hi in BANDS:
        inside = [changed for *_, changed, conf in rows if lo <= conf < hi]
        if inside:
            out.append(s.ConfidenceBand(band=band, confirmed=len(inside),
                                        kept_pct=ops.pct(sum(1 for c in inside if not c), len(inside))))
    return out


def _kiosk_accuracy(db: DbSession, since: datetime) -> s.KioskAccuracy | None:
    """Kiosk drop-offs: was the camera's category the one recorded? None until the kiosk has sent any."""
    total, matched = db.execute(
        select(func.count(Delivery.id), func.count(Delivery.id).filter(Delivery.cv_category == WasteCategory.name))
        .join(WasteCategory, WasteCategory.id == Delivery.category_id)
        .where(Delivery.cv_category.is_not(None), Delivery.received_at >= since)
    ).one()
    return s.KioskAccuracy(with_camera=total, matched=matched, matched_pct=ops.pct(matched, total)) if total else None


def predictions(db: DbSession, category: int = ALL, on: date | None = None) -> s.Predictions:
    on = on or today()
    yesterday = on - timedelta(days=1)
    cats = [s.Category(id=ALL, name="All")] + [
        s.Category(id=c.id, name=c.name)
        for c in db.scalars(select(WasteCategory).where(WasteCategory.active).order_by(WasteCategory.id))
    ]
    if category not in {c.id for c in cats}:
        raise AppError(404, "Unknown waste category.")
    errs7, errs14 = fc.errors(db, category, on, 7), fc.errors(db, category, on, 14)
    model = fc.pick_model(db, category, on)
    made_on = db.scalar(select(func.max(Forecast.made_on)).where(Forecast.made_on <= on, Forecast.category_id == category))
    forecast = (
        [
            s.DayKg(day=d, kg=kg)
            for d, kg in db.execute(
                select(Forecast.for_day, Forecast.kg)
                .where(
                    Forecast.made_on == made_on, Forecast.category_id == category, Forecast.model == model, Forecast.for_day >= on
                )
                .order_by(Forecast.for_day)
            )
        ]
        if made_on
        else []
    )
    rows = fc.comparison(db, category, model, on - timedelta(days=7), yesterday)
    start = on - timedelta(days=HISTORY_DAYS)
    areas = outlook(db, on)
    return s.Predictions(
        ready=fc.ready(db, on),
        days_of_records=fc.days_of_records(db, yesterday),
        min_days=ranges.get(db).prediction_min_days,
        categories=cats,
        category=category,
        model_used=model,
        errors_7d=errs7,
        errors_14d=errs14,
        history=[
            s.DayKg(day=start + timedelta(days=i), kg=round(kg, 2))
            for i, kg in enumerate(fc.daily_kg(db, category, start, yesterday))
        ],
        forecast=forecast,
        made_on=made_on,
        compared=[
            s.Compared(
                day=d,
                predicted=p,
                actual=round(a, 2),
                diff=round(a - p, 2),
                pct=round(abs(a - p) / a * 100, 1) if a > 0 else None,
            )
            for d, p, a in reversed(rows)
        ],
        missing_days=7 - len(rows),
        avg_error_pct=fc.wape(rows),
        outlook=areas,
        schedule=schedule(db, areas, on),
        camera=camera_accuracy(db),
    )


# ---- flagged records


def flag_out(db: DbSession, f: Flag) -> s.FlagOut:
    d = db.get(Delivery, f.delivery_id)
    assert d, "flag without delivery"  # the foreign key cascades
    area = (db.get(SourceArea, d.source_area_id) or SourceArea(name="")).name
    if f.kind == "weight":
        why, expected = "Unusual weight", f"Usual for {area}: {f.expected_low:.1f}–{f.expected_high:.1f} kg"
    else:
        why = f"Received vs sorted gap {abs(f.value_kg - f.expected_low):.1f} kg"
        expected = f"Separated + sorted {f.expected_low:.1f} kg"
    by = db.get(User, f.decided_by) if f.decided_by else None
    return s.FlagOut(
        id=f.id,
        kind=f.kind,
        delivery_id=d.id,
        code=d.code,
        received_at=d.received_at,
        source_area=area,
        category=(db.get(WasteCategory, d.category_id) or WasteCategory(name="")).name,
        value_kg=f.value_kg,
        expected_low=f.expected_low,
        expected_high=f.expected_high,
        why=why,
        expected=expected,
        status=f.status,
        decided_by=by.name if by else None,
        decided_at=f.decided_at,
    )


def open_flags(db: DbSession, limit: int = 200) -> list[s.FlagOut]:
    rows = db.scalars(select(Flag).where(Flag.status == "open").order_by(Flag.found_at.desc(), Flag.id.desc()).limit(limit))
    rows = list(rows)
    _ = preload(db, User, SourceArea, WasteCategory)
    held = db.scalars(select(Delivery).where(Delivery.id.in_(f.delivery_id for f in rows))).all()  # noqa: F841
    return [flag_out(db, f) for f in rows]


def decide_flag(db: DbSession, flag_id: int, decision: str, actor: User) -> Flag:
    f = db.get(Flag, flag_id)
    if not f:
        raise AppError(404, "Flag not found.")
    if f.status != "open":
        raise AppError(409, f"This flag was already marked {'a false alarm' if f.status == 'incorrect' else f.status}.")
    f.status, f.decided_by, f.decided_at = decision, actor.id, datetime.now(UTC)
    out = flag_out(db, f)
    # "incorrect" is the stored value: the weight was fine, so it stays in the usual weights (flags.check_weight).
    word = "a false alarm" if decision == "incorrect" else decision
    log(db, actor.id, f"Marked flagged record {word}", f"{out.code} · {out.why} · {out.value_kg} kg")
    db.commit()
    return f
