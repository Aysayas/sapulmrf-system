from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.db import advisory_lock, preload
from app.core.errors import AppError
from app.devices.models import Device
from app.insights import flags
from app.intake.models import Delivery, SegregationCheck
from app.intake.schemas import DeliveryIn, DeliveryOut, SegregationIn, SegregationOut
from app.masterdata.models import SourceArea, WasteCategory
from app.users.models import User

# Wet + dry may come out a little heavier than the bag was (wet waste, rounding), but not by this much.
SEGREGATION_TOLERANCE = 1.10
UNDO_WINDOW = timedelta(minutes=30)
READING_MAX_AGE = timedelta(minutes=10)


def out(db: DbSession, d: Delivery, checks: dict[int, SegregationCheck] | None = None) -> DeliveryOut:
    one = select(SegregationCheck).where(SegregationCheck.delivery_id == d.id)
    seg = checks.get(d.id) if checks is not None else db.scalar(one)
    by = db.get(User, d.recorded_by) if d.recorded_by else None
    return DeliveryOut(
        id=d.id, code=d.code, received_at=d.received_at, source_area=db.get(SourceArea, d.source_area_id).name,
        category=db.get(WasteCategory, d.category_id).name, weight_kg=d.weight_kg, weighed_by=d.weighed_by,
        scale_kg=d.scale_kg, corrected=d.scale_kg is not None, correction_reason=d.correction_reason, status=d.status,
        recorded_by=by.name if by else None,
        segregation=SegregationOut(condition=seg.condition, wet_kg=seg.wet_kg, dry_kg=seg.dry_kg, note=seg.note,
                                   checked_at=seg.checked_at) if seg else None,
    )


def out_many(db: DbSession, rows: list[Delivery]) -> list[DeliveryOut]:
    _ = preload(db, User, SourceArea, WasteCategory)
    found = db.scalars(select(SegregationCheck).where(SegregationCheck.delivery_id.in_(d.id for d in rows)))
    checks = {c.delivery_id: c for c in found}
    return [out(db, d, checks) for d in rows]


def _active(db: DbSession, model, item_id: int, what: str):
    item = db.get(model, item_id)
    if not item or not item.active:
        raise AppError(422, f"Pick an active {what}.")
    return item


def _fresh_reading(db: DbSession, device_id: int | None) -> float:
    dev = db.get(Device, device_id) if device_id is not None else None
    if not dev or dev.type != "weighing_station":
        raise AppError(422, "A scale weight needs its weighing station. Otherwise record it as manual.")
    reading = dev.last_reading or {}
    if "kg" not in reading or datetime.now(UTC) - datetime.fromisoformat(reading["at"]) > READING_MAX_AGE:
        raise AppError(422, f"{dev.code} has no recent reading. Weigh it again, or record it as manual.")
    if not reading.get("stable"):
        raise AppError(422, f"{dev.code} hasn't settled. Wait for a stable reading.")
    return reading["kg"]


def by_name(db: DbSession, model, name: str, what: str) -> int:
    """The id of a purok or category a device named, ignoring capitals."""
    item_id = db.scalar(select(model.id).where(func.lower(model.name) == name.strip().lower()))
    if item_id is None:
        raise AppError(422, f"Unknown {what}: {name}.")
    return item_id


def record_delivery(db: DbSession, data: DeliveryIn, actor: User | None, at: datetime | None = None) -> Delivery:
    """at is only passed by the history backfill; live records always use the server's clock.
    actor is None when a device (the kiosk) records it; data.device_id then names that device."""
    if data.client_key:
        advisory_lock(db, data.client_key)
        first = db.scalar(select(Delivery).where(Delivery.client_key == data.client_key))
        if first:
            return first
    area = _active(db, SourceArea, data.source_area_id, "source area")
    _active(db, WasteCategory, data.category_id, "waste category")
    scale_kg = data.scale_kg
    if data.weighed_by == "scale" and not at:  # the scale's own reading, not what the request claims it said
        scale_kg = _fresh_reading(db, data.device_id)
    corrected = scale_kg is not None and abs(scale_kg - data.weight_kg) > 0.001
    if corrected and not data.correction_reason:
        raise AppError(422, "Say why you corrected the scale reading.")
    if data.device_id is not None:
        dev = db.get(Device, data.device_id)
        if not dev or dev.type != "weighing_station":
            raise AppError(422, "That isn't a registered weighing station.")
    d = Delivery(
        source_area_id=area.id, category_id=data.category_id, weight_kg=round(data.weight_kg, 2),
        weighed_by=data.weighed_by, scale_kg=round(scale_kg, 2) if corrected else None,
        correction_reason=data.correction_reason if corrected else None, recorded_by=actor.id if actor else None,
        device_id=data.device_id,
        client_key=data.client_key,
    )
    if at:
        d.received_at = at
    db.add(d)
    db.flush()
    d.code = f"D-{d.id:04d}"
    flags.check_weight(db, d)
    if not at:
        note = " (corrected)" if corrected else ""
        by = "" if actor else f" · by {db.get(Device, d.device_id).code}"
        log(db, actor.id if actor else None, "Recorded delivery", f"{d.code} · {area.name} · {d.weight_kg} kg{note}{by}")
    db.commit()
    return d


def undo_segregation(db: DbSession, delivery_id: int, actor: User) -> Delivery:
    """Takes back a mistyped check: only the operator who made it, soon after, and before anything was sorted from it."""
    d = db.get(Delivery, delivery_id, with_for_update=True)
    check = db.scalar(select(SegregationCheck).where(SegregationCheck.delivery_id == delivery_id)) if d else None
    if not check:
        raise AppError(404, "No segregation check on this delivery.")
    if check.checked_by != actor.id or datetime.now(UTC) - check.checked_at > UNDO_WINDOW:
        raise AppError(409, f"The check on {d.code} can't be undone any more. Report a problem with this record instead.")
    if d.status != "separated":
        raise AppError(409, f"{d.code} is already sorted, so its check can't be undone.")
    db.delete(check)
    d.status = "awaiting"
    log(db, actor.id, "Undid segregation check", f"{d.code} · wet {check.wet_kg} kg · dry {check.dry_kg} kg")
    db.commit()
    return d


def record_segregation(db: DbSession, delivery_id: int, data: SegregationIn, actor: User,
                       at: datetime | None = None) -> Delivery:
    d = db.get(Delivery, delivery_id, with_for_update=True)  # two phones can check the same delivery
    if not d:
        raise AppError(404, "Delivery not found.")
    if db.scalar(select(SegregationCheck.id).where(SegregationCheck.delivery_id == d.id)):
        raise AppError(409, f"{d.code} already has a segregation check.")
    if data.wet_kg + data.dry_kg > d.weight_kg * SEGREGATION_TOLERANCE + 0.5:
        raise AppError(422, f"Wet and dry add up to more than the {d.weight_kg} kg received. Weigh them again.")
    check = SegregationCheck(delivery_id=d.id, condition=data.condition, wet_kg=round(data.wet_kg, 2),
                             dry_kg=round(data.dry_kg, 2), note=data.note, checked_by=actor.id)
    if at:
        check.checked_at = at
    db.add(check)
    d.status = "separated"
    if not at:
        record = f"{d.code} · {data.condition} · wet {check.wet_kg} kg · dry {check.dry_kg} kg"
        log(db, actor.id, "Segregation check", record)
    db.commit()
    return d
