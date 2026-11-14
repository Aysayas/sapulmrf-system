"""Fixing a mistake = undo with a reason, then record it again. Undo walks back from the newest step:
sort, then the wet/dry check, then the delivery. Operators fix today's steps only; the admin, any day."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.config import settings
from app.core.errors import AppError
from app.corrections.models import Correction
from app.corrections.schemas import CorrectionOut, Fixable, UndoIn
from app.insights.models import Flag
from app.intake.models import Delivery, DeliveryPhoto, SegregationCheck
from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory
from app.sorting.models import Classification, StockMovement
from app.sorting.service import lock_areas, material_bags, material_kg
from app.users.models import User

TZ = ZoneInfo(settings.timezone)
STEPS = ("sort", "segregation", "delivery")


def _day(t: datetime):
    return t.astimezone(TZ).date()


def _kg(v: float) -> str:
    return f"{round(v, 2):g}"


def undo(db: DbSession, data: UndoIn, actor: User) -> Correction:
    d = db.get(Delivery, data.delivery_id, with_for_update=True)  # two taps at once: the second waits, then finds less
    if not d:
        raise AppError(404, "That record is gone already.")
    check = db.scalar(select(SegregationCheck).where(SegregationCheck.delivery_id == d.id))
    moves = db.scalars(select(StockMovement).where(StockMovement.kind == "sorted", StockMovement.delivery_id == d.id)
                       .order_by(StockMovement.id)).all()
    upto = STEPS.index(data.to)
    if data.to == "sort" and not moves:
        raise AppError(409, f"{d.code} isn't sorted.")
    if data.to == "segregation" and not check:
        raise AppError(409, f"{d.code} has no wet/dry check.")
    if actor.role != "admin":  # the kiosk fixes today's work; older records are the admin's
        when = {"sort": moves[0].at if moves else None, "segregation": check.checked_at if check else None,
                "delivery": d.received_at}
        today = datetime.now(TZ).date()
        if any(when[s] is not None and _day(when[s]) != today for s in STEPS[:upto + 1]):
            raise AppError(403, "Only today's records can be fixed at the kiosk. Ask the admin.")

    mats = dict(db.execute(select(Material.id, Material.name)).all())
    parts = [d.code, db.get(SourceArea, d.source_area_id).name, db.get(WasteCategory, d.category_id).name,
             f"{_kg(d.weight_kg)} kg"]
    if check:
        parts.append(f"wet {_kg(check.wet_kg)} · dry {_kg(check.dry_kg)}")
    if moves:
        parts.append("sorted: " + ", ".join(f"{mats.get(m.material_id, 'Residual')} {_kg(m.kg)}" for m in moves))
    summary = " · ".join(parts)[:300]

    if moves:  # the sort's stock leaves its areas, if it's still there
        lock_areas(db, sorted({m.storage_area_id for m in moves}))
        need: dict[tuple[int | None, int], list[float]] = {}  # (material, area) -> [kg, bags] the sort added
        for m in moves:
            row = need.setdefault((m.material_id, m.storage_area_id), [0.0, 0])
            row[0] += m.kg
            row[1] += m.bags
        for (mat, area), (kg, bags) in need.items():
            have, have_bags = material_kg(db, mat, area), material_bags(db, mat, area)
            if have < kg - 0.001 or have_bags < bags:
                left = f"{_kg(have)} kg" if have < kg - 0.001 else f"{have_bags} bags"
                raise AppError(409, f"{mats.get(mat, 'Residual')} in {db.get(StorageArea, area).name} has only "
                                    f"{left} left: some of {d.code} was sold or moved. Recount it instead.")
        for m in moves:
            db.delete(m)
        for c in db.scalars(select(Classification).where(Classification.delivery_id == d.id)):
            c.confirmed_at = c.confirmed_by = c.final_material_id = None  # the redo sort answers the camera again
            c.changed, c.not_recyclable, c.reason = False, False, ""
            c.review = c.reviewed_by = c.reviewed_at = None
        db.execute(delete(Flag).where(Flag.delivery_id == d.id, Flag.kind == "gap"))
        d.status = "separated"
    if upto >= 1 and check:
        db.delete(check)
        d.status = "awaiting"
    if upto == 2:
        db.execute(delete(Classification).where(Classification.delivery_id == d.id))
        db.execute(delete(DeliveryPhoto).where(DeliveryPhoto.delivery_id == d.id))
        db.execute(delete(Flag).where(Flag.delivery_id == d.id))
        db.flush()
        db.delete(d)
    c = Correction(kind=data.to, record_code=d.code, summary=summary, reason=data.reason, by=actor.id)
    if actor.role == "admin":  # the admin's own fix needs no review from themselves
        c.review, c.reviewed_by, c.reviewed_at = "ok", actor.id, datetime.now(UTC)
    db.add(c)
    what = {"sort": "the sort of", "segregation": "the wet/dry check of", "delivery": ""}[data.to]
    log(db, actor.id, "Undid a record", f"{what} {summary} · {data.reason}".strip()[:255])
    db.commit()
    return c


def fixable(db: DbSession, limit: int = 8) -> list[Fixable]:
    """Deliveries with any step done today, newest first: what an operator can fix at the kiosk."""
    start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    ids = set(db.scalars(select(Delivery.id).where(Delivery.received_at >= start)))
    ids |= set(db.scalars(select(SegregationCheck.delivery_id).where(SegregationCheck.checked_at >= start)))
    ids |= set(db.scalars(select(StockMovement.delivery_id).where(StockMovement.kind == "sorted",
                                                                   StockMovement.at >= start,
                                                                   StockMovement.delivery_id.is_not(None))))
    if not ids:
        return []
    rows = db.execute(select(Delivery, SourceArea.name, WasteCategory.name)
                      .join(SourceArea, SourceArea.id == Delivery.source_area_id)
                      .join(WasteCategory, WasteCategory.id == Delivery.category_id)
                      .where(Delivery.id.in_(ids)).order_by(Delivery.received_at.desc()).limit(limit)).all()
    stage = {"awaiting": "recorded", "separated": "separated", "sorted": "sorted"}
    return [Fixable(id=d.id, code=d.code, source_area=p, category=c, weight_kg=d.weight_kg, stage=stage[d.status])
            for d, p, c in rows]


def mark(db: DbSession, correction_id: int, review: str, actor: User) -> Correction:
    c = db.get(Correction, correction_id, with_for_update=True)
    if not c:
        raise AppError(404, "Fix not found.")
    if c.review:
        raise AppError(409, f"This fix of {c.record_code} was already marked {c.review}.")
    c.review, c.reviewed_by, c.reviewed_at = review, actor.id, datetime.now(UTC)
    log(db, actor.id, "Reviewed a fix", f"{c.record_code} · {review}")
    db.commit()
    return c


def link_redo(db: DbSession, replaces: str | None, new_code: str) -> None:
    """A kiosk drop-off recorded again in place of an undone one: the fix says what replaced it."""
    # a resend of the same drop-off links nothing more; only a removed delivery is recorded again
    if not replaces or db.scalar(select(Correction.id).where(Correction.redone_as == new_code).limit(1)):
        return
    c = db.scalar(select(Correction).where(Correction.record_code == replaces, Correction.kind == "delivery",
                                           Correction.redone_as.is_(None)).order_by(Correction.at.desc()).limit(1))
    if c:
        c.redone_as = new_code


def to_review(db: DbSession) -> list[Correction]:
    return list(db.scalars(select(Correction).where(Correction.review.is_(None)).order_by(Correction.at)))


def count_to_review(db: DbSession) -> int:
    return db.scalar(select(func.count(Correction.id)).where(Correction.review.is_(None))) or 0


def out(db: DbSession, c: Correction) -> CorrectionOut:
    who = db.get(User, c.by) if c.by else None
    return CorrectionOut(id=c.id, kind=c.kind, record_code=c.record_code, summary=c.summary, reason=c.reason,
                         by=who.name if who else None, at=c.at, redone_as=c.redone_as, review=c.review)
