from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.approvals.models import AdjustmentRequest, Outgoing
from app.approvals.schemas import (
    AdjustmentIn,
    AdjustmentOut,
    ApprovalsOut,
    DecisionIn,
    OutgoingIn,
    OutgoingOut,
    OutgoingReviewIn,
    ReviewIn,
)
from app.compost.models import CompostBatch
from app.core.db import advisory_lock, preload
from app.core.errors import AppError
from app.corrections import service as corrections
from app.insights.models import Flag
from app.intake import service as intake
from app.intake.models import Delivery
from app.intake.schemas import DeliveryOut
from app.masterdata.models import Material, StorageArea
from app.sorting import service as sorting
from app.sorting.models import Classification, StockMovement
from app.sorting.schemas import ClassificationOut
from app.sorting.service import lock_areas, material_bags, material_kg, stock_kg
from app.users.models import User


def _name(db: DbSession, user_id: int | None) -> str | None:
    return db.get(User, user_id).name if user_id else None


def _material(db: DbSession, material_id: int | None) -> str:
    return db.get(Material, material_id).name if material_id else "Residual"


def _area(db: DbSession, area_id: int) -> StorageArea:
    area = db.get(StorageArea, area_id)
    if not area or not area.active:
        raise AppError(422, "Pick an active storage area.")
    return area


def compost_on_hand(db: DbSession) -> float:
    """What finished batches produced, minus compost already approved to go out."""
    made = db.scalar(select(func.coalesce(func.sum(CompostBatch.produced_kg), 0.0)).where(CompostBatch.finished_at.is_not(None)))
    out = db.scalar(select(func.coalesce(func.sum(Outgoing.kg), 0.0)).where(
        Outgoing.type == "compost", Outgoing.status == "approved", Outgoing.review.is_distinct_from("reversed")))
    return round(float(made) - float(out), 2)


def adjustment_out(db: DbSession, r: AdjustmentRequest) -> AdjustmentOut:
    area = db.get(StorageArea, r.storage_area_id)
    current, area_kg = material_kg(db, r.material_id, area.id), stock_kg(db, area.id)
    return AdjustmentOut(id=r.id, requested_at=r.requested_at, material=_material(db, r.material_id), area=area.name,
                         system_kg=r.system_kg, actual_kg=r.actual_kg, reason=r.reason, details=r.details,
                         current_kg=current, area_kg=area_kg, area_after_kg=round(area_kg + r.actual_kg - current, 2),
                         capacity_kg=area.capacity_kg, status=r.status, requested_by=_name(db, r.requested_by),
                         decided_by=_name(db, r.decided_by), decided_at=r.decided_at, comment=r.comment, review=r.review)


def outgoing_out(db: DbSession, o: Outgoing, balances: bool = True) -> OutgoingOut:
    """balances: the ledger sums the approval screen shows. Lists of past records don't need them."""
    area = db.get(StorageArea, o.storage_area_id) if o.storage_area_id else None
    area_kg = stock_kg(db, area.id) if area and balances else None
    available = None
    if balances:
        available = material_kg(db, o.material_id, area.id) if area else compost_on_hand(db)
    return OutgoingOut(id=o.id, code=o.code, requested_at=o.requested_at, type=o.type,
                       material="Compost" if o.type == "compost" else _material(db, o.material_id),
                       area=area.name if area else None, kg=o.kg, recipient=o.recipient,
                       price_per_kg=float(o.price_per_kg) if o.price_per_kg is not None else None,
                       total=float(o.total) if o.total is not None else None, available_kg=available,
                       area_kg=area_kg,  # an approved row already left the area
                       area_after_kg=round(area_kg - (o.kg if o.status == "pending" else 0), 2) if area_kg is not None else None,
                       capacity_kg=area.capacity_kg if area else None, status=o.status,
                       requested_by=_name(db, o.requested_by), decided_by=_name(db, o.decided_by),
                       decided_at=o.decided_at, comment=o.comment, review=o.review)


def request_adjustment(db: DbSession, data: AdjustmentIn, actor: User, at: datetime | None = None) -> AdjustmentRequest:
    area = _area(db, data.storage_area_id)
    if data.material_id is not None and not db.get(Material, data.material_id):
        raise AppError(422, "Pick a recyclable material, or leave it empty for residual.")
    lock_areas(db, [area.id])  # read the count and change it in one go
    now = at or datetime.now(UTC)
    current = material_kg(db, data.material_id, area.id)
    # It counts at once: stock is set to the count now; the admin reviews it afterwards (ok / reverse).
    r = AdjustmentRequest(material_id=data.material_id, storage_area_id=area.id, system_kg=current,
                          actual_kg=round(data.actual_kg, 2), reason=data.reason, details=data.details,
                          requested_by=actor.id, requested_at=now, status="approved", decided_by=actor.id, decided_at=now)
    if actor.role == "admin":  # the admin's own count needs no review from themselves
        r.review, r.reviewed_by, r.reviewed_at = "ok", actor.id, now
    db.add(r)
    db.flush()
    _apply_count(db, r, current, actor)
    if not at:
        log(db, actor.id, "Recounted stock",
            f"{_material(db, r.material_id)} · {area.name} · {r.system_kg} → {r.actual_kg} kg · {r.reason}")
    db.commit()
    return r


def _apply_count(db: DbSession, r: AdjustmentRequest, current: float, actor: User) -> None:
    """Sets the ledger to the count with one adjustment row (bags follow the kg)."""
    change = round(r.actual_kg - current, 2)
    if change:
        bags = material_bags(db, r.material_id, r.storage_area_id)
        taken = bags if r.actual_kg <= 0 else max(0, min(bags - 1, round(bags * -change / current))) if change < 0 else 0
        db.add(StockMovement(material_id=r.material_id, storage_area_id=r.storage_area_id, kg=change, bags=-taken,
                             kind="adjustment", by=actor.id, note=f"Adjustment #{r.id}: {r.reason}"[:200], at=r.decided_at))


def review_adjustment(db: DbSession, request_id: int, data: OutgoingReviewIn, actor: User) -> AdjustmentRequest:
    """The admin's look at a recount: ok, or reverse it (the change is undone today with a row of its own)."""
    r = db.get(AdjustmentRequest, request_id, with_for_update=True)
    if r is None:
        raise AppError(404, "Recount not found.")
    if r.status != "approved":
        raise AppError(409, f"This recount is {r.status}: approve or reject it instead.")
    if r.review:
        raise AppError(409, f"This recount was already reviewed ({r.review}).")
    if data.decision == "reverse" and not data.comment:
        raise AppError(422, "Say why it's reversed.")
    r.review = "ok" if data.decision == "ok" else "reversed"
    r.reviewed_by, r.reviewed_at = actor.id, datetime.now(UTC)
    if data.comment:
        r.comment = data.comment
    if r.review == "reversed":
        lock_areas(db, [r.storage_area_id])
        made = db.scalar(select(StockMovement).where(StockMovement.kind == "adjustment",
                                                     StockMovement.note.like(f"Adjustment #{r.id}:%")))
        if made:
            later = db.scalar(select(StockMovement.id).where(  # a sale, move or count since: the old figure is stale
                StockMovement.material_id.is_(None) if r.material_id is None else StockMovement.material_id == r.material_id,
                StockMovement.storage_area_id == r.storage_area_id, StockMovement.id > made.id).limit(1))
            if later:
                raise AppError(409, "Stock changed since this recount, so it can't be put back. Recount again instead.")
            db.add(StockMovement(material_id=r.material_id, storage_area_id=r.storage_area_id, kg=-made.kg,
                                 bags=-made.bags, kind="adjustment", by=actor.id,
                                 note=f"Adjustment #{r.id} reversed", at=r.reviewed_at))
    verb = "Marked recount OK" if r.review == "ok" else "Reversed recount"
    log(db, actor.id, verb, f"{_material(db, r.material_id)} · {r.system_kg} → {r.actual_kg} kg {r.comment}".strip())
    db.commit()
    return r


def request_outgoing(db: DbSession, data: OutgoingIn, actor: User, at: datetime | None = None) -> Outgoing:
    if data.client_key:
        advisory_lock(db, data.client_key)
        first = db.scalar(select(Outgoing).where(Outgoing.client_key == data.client_key))
        if first:
            return first
    if data.storage_area_id is not None:
        _area(db, data.storage_area_id)
    if data.material_id is not None and not db.get(Material, data.material_id):
        raise AppError(422, "Pick a recyclable material.")
    price = Decimal(str(data.price_per_kg)).quantize(Decimal("0.01")) if data.price_per_kg else None
    now = at or datetime.now(UTC)
    # It counts at once: approved now, stock leaves now, the admin reviews it afterwards (ok / reverse).
    o = Outgoing(type=data.type, material_id=data.material_id, storage_area_id=data.storage_area_id,
                 kg=round(data.kg, 2), recipient=data.recipient, price_per_kg=price,
                 total=(price * Decimal(str(round(data.kg, 2)))).quantize(Decimal("0.01")) if price else None,
                 requested_by=actor.id, client_key=data.client_key, status="approved", decided_by=actor.id,
                 requested_at=now, decided_at=now)
    if actor.role == "admin":  # the admin's own record needs no review from themselves
        o.review, o.reviewed_by, o.reviewed_at = "ok", actor.id, now
    available = _available(db, o)
    db.add(o)
    db.flush()
    o.code = f"O-{o.id:04d}"
    _move_out(db, o, available, actor)
    if not at:
        money = f" · ₱{o.total}" if o.total is not None else ""
        log(db, actor.id, "Recorded outgoing material", f"{o.code} · {data.type} · {o.kg} kg · {o.recipient}{money}")
    db.commit()
    return o


def _available(db: DbSession, o: Outgoing) -> float:
    """Locks the area (or compost) and checks there is enough. Two at once can't both take the last kg."""
    if o.storage_area_id:
        lock_areas(db, [o.storage_area_id])
    else:
        advisory_lock(db, "compost")  # compost has no area row to lock
    available = material_kg(db, o.material_id, o.storage_area_id) if o.storage_area_id else compost_on_hand(db)
    if o.kg > available + 0.001:
        what = f"{_material(db, o.material_id)} in {db.get(StorageArea, o.storage_area_id).name}" \
            if o.storage_area_id else "finished compost"
        raise AppError(409, f"Only {available} kg of {what}. Check the count, or take it from another area.")
    return available


def _move_out(db: DbSession, o: Outgoing, available: float, actor: User) -> None:
    if o.storage_area_id:
        bags = material_bags(db, o.material_id, o.storage_area_id)
        db.add(StockMovement(material_id=o.material_id, storage_area_id=o.storage_area_id, kg=-o.kg,
                             bags=-min(bags, round(bags * o.kg / available)) if available > 0 else 0,
                             kind="outgoing", by=actor.id, note=o.code, at=o.decided_at))


def review_outgoing(db: DbSession, outgoing_id: int, data: OutgoingReviewIn, actor: User) -> Outgoing:
    """The admin's look at outgoing an operator recorded: ok, or reverse it (the stock goes back today; the day it
    went out keeps its record, and income reports subtract it on the day of the reversal)."""
    o = db.get(Outgoing, outgoing_id, with_for_update=True)
    if o is None:
        raise AppError(404, "Outgoing record not found.")
    if o.status != "approved":
        raise AppError(409, f"{o.code} is {o.status}: approve or reject it instead.")
    if o.review:
        raise AppError(409, f"{o.code} was already reviewed ({o.review}).")
    if data.decision == "reverse" and not data.comment:
        raise AppError(422, "Say why it's reversed.")
    o.review = "ok" if data.decision == "ok" else "reversed"
    o.reviewed_by, o.reviewed_at = actor.id, datetime.now(UTC)
    if data.comment:
        o.comment = data.comment
    if o.review == "reversed" and o.storage_area_id:
        lock_areas(db, [o.storage_area_id])
        went = db.scalar(select(StockMovement).where(StockMovement.kind == "outgoing", StockMovement.note == o.code))
        db.add(StockMovement(material_id=o.material_id, storage_area_id=o.storage_area_id, kg=o.kg,
                             bags=-went.bags if went else 0, kind="outgoing", by=actor.id,
                             note=f"{o.code} reversed", at=o.reviewed_at))
    verb = "Marked outgoing OK" if o.review == "ok" else "Reversed outgoing"
    log(db, actor.id, verb, f"{o.code} · {o.kg} kg · {o.recipient} {o.comment}".strip())
    db.commit()
    return o


def _pending(row, what: str):
    if row is None:
        raise AppError(404, f"{what} not found.")
    if row.status != "pending":
        raise AppError(409, f"This {what.lower()} was already {row.status}.")
    return row


def _decide(row, data: DecisionIn, actor: User, at: datetime | None) -> None:
    row.status = "approved" if data.decision == "approve" else "rejected"
    row.decided_by, row.decided_at, row.comment = actor.id, at or datetime.now(UTC), data.comment


def decide_adjustment(db: DbSession, request_id: int, data: DecisionIn, actor: User,
                      at: datetime | None = None) -> AdjustmentRequest:
    r = _pending(db.get(AdjustmentRequest, request_id, with_for_update=True), "Adjustment")
    area = lock_areas(db, [r.storage_area_id])[r.storage_area_id]
    current = material_kg(db, r.material_id, r.storage_area_id)
    if data.decision == "approve" and not area.active and r.actual_kg > 0:
        raise AppError(409, f"{area.name} is no longer active. Reject this count, or reactivate the area first.")
    if data.decision == "approve" and abs(current - r.system_kg) > 0.005:
        raise AppError(409, f"Stock changed since this count: {r.system_kg} kg then, {current} kg now. "
                            "Reject it and ask for a new count.")
    _decide(r, data, actor, at)
    change = round(r.actual_kg - current, 2)
    if r.status == "approved":  # the admin decided it, so it needs no review after
        r.review, r.reviewed_by, r.reviewed_at = "ok", actor.id, r.decided_at
        _apply_count(db, r, current, actor)
    if not at:
        verb = "Approved inventory adjustment" if r.status == "approved" else "Rejected inventory adjustment"
        area = db.get(StorageArea, r.storage_area_id).name
        log(db, actor.id, verb, f"{_material(db, r.material_id)} · {area} · {change:+} kg · {r.comment}".rstrip(" ·"))
    db.commit()
    return r


def decide_outgoing(db: DbSession, outgoing_id: int, data: DecisionIn, actor: User, at: datetime | None = None) -> Outgoing:
    o = _pending(db.get(Outgoing, outgoing_id, with_for_update=True), "Outgoing record")
    available = _available(db, o) if data.decision == "approve" else 0.0
    _decide(o, data, actor, at)
    if o.status == "approved":  # the admin decided it, so it needs no review after
        o.review, o.reviewed_by, o.reviewed_at = "ok", actor.id, o.decided_at
        _move_out(db, o, available, actor)
    if not at:
        verb = f"{'Approved' if o.status == 'approved' else 'Rejected'} outgoing {o.type}"
        money = f" · ₱{o.total}" if o.total is not None else ""
        log(db, actor.id, verb, f"{o.code} · {o.kg} kg · {o.recipient}{money} {o.comment}".strip())
    db.commit()
    return o


# ---- reviews of operator corrections ----

UNREVIEWED_WEIGHTS = (Delivery.scale_kg.is_not(None), Delivery.review.is_(None))
UNREVIEWED_CHANGES = (Classification.changed.is_(True), Classification.review.is_(None))


def weights_to_review(db: DbSession, limit: int = 100) -> list[DeliveryOut]:
    rows = db.scalars(select(Delivery).where(*UNREVIEWED_WEIGHTS).order_by(Delivery.received_at.desc()).limit(limit))
    return intake.out_many(db, list(rows))


def changes_to_review(db: DbSession, limit: int = 100) -> list[ClassificationOut]:
    rows = db.scalars(select(Classification).where(*UNREVIEWED_CHANGES)
                      .order_by(Classification.confirmed_at.desc()).limit(limit))
    _ = preload(db, User, Material)
    return [sorting.out(db, c) for c in rows]


def _mark(row, data: ReviewIn, allowed: tuple[str, str], actor: User, what: str) -> None:
    if data.review not in allowed:
        raise AppError(422, f"Mark a {what} as {' or '.join(allowed)}.")
    if row.review:
        raise AppError(409, f"This {what} was already reviewed.")
    row.review, row.reviewed_by, row.reviewed_at = data.review, actor.id, datetime.now(UTC)


def review_weight(db: DbSession, delivery_id: int, data: ReviewIn, actor: User) -> Delivery:
    d = db.get(Delivery, delivery_id)
    if not d or d.scale_kg is None:
        raise AppError(404, "No corrected weight with that id.")
    _mark(d, data, ("ok", "recheck"), actor, "corrected weight")
    log(db, actor.id, "Reviewed corrected weight", f"{d.code} · scale {d.scale_kg} → {d.weight_kg} kg · {d.review}")
    db.commit()
    return d


def review_change(db: DbSession, classification_id: int, data: ReviewIn, actor: User) -> Classification:
    c = db.get(Classification, classification_id)
    if not c or not c.changed:
        raise AppError(404, "No changed classification with that id.")
    _mark(c, data, ("ok", "wrong"), actor, "changed classification")
    final = "Not recyclable" if c.not_recyclable else sorting._name(db, c.final_material_id)
    log(db, actor.id, "Reviewed changed classification", f"{sorting._name(db, c.suggested_material_id)} → {final} · {c.review}")
    db.commit()
    return c


def counts(db: DbSession) -> dict[str, int]:
    """What waits for the admin, per inbox tab."""
    n = lambda col, *where: db.scalar(select(func.count(col)).where(*where))  # noqa: E731
    return {"adjustments": n(AdjustmentRequest.id, AdjustmentRequest.status == "pending"),
            "outgoing": n(Outgoing.id, Outgoing.status == "pending"),
            "outgoing_review": n(Outgoing.id, Outgoing.status == "approved", Outgoing.review.is_(None)),
            "adjustments_review": n(AdjustmentRequest.id, AdjustmentRequest.status == "approved",
                                    AdjustmentRequest.review.is_(None)),
            "fixes": corrections.count_to_review(db),
            "weights": n(Delivery.id, *UNREVIEWED_WEIGHTS),
            "classifications": n(Classification.id, *UNREVIEWED_CHANGES),
            "flagged": n(Flag.id, Flag.status == "open")}


def pending(db: DbSession) -> ApprovalsOut:
    _ = preload(db, User, Material, StorageArea)
    adjustments = db.scalars(select(AdjustmentRequest).where(AdjustmentRequest.status == "pending")
                             .order_by(AdjustmentRequest.requested_at)).all()
    outgoing = db.scalars(select(Outgoing).where(Outgoing.status == "pending").order_by(Outgoing.requested_at)).all()
    to_review = db.scalars(select(Outgoing).where(Outgoing.status == "approved", Outgoing.review.is_(None))
                           .order_by(Outgoing.decided_at)).all()
    return ApprovalsOut(counts=counts(db), adjustments=[adjustment_out(db, r) for r in adjustments],
                        outgoing=[outgoing_out(db, o) for o in outgoing],
                        outgoing_review=[outgoing_out(db, o, balances=False) for o in to_review],
                        adjustments_review=[adjustment_out(db, r) for r in db.scalars(
                            select(AdjustmentRequest).where(AdjustmentRequest.status == "approved",
                                                            AdjustmentRequest.review.is_(None))
                            .order_by(AdjustmentRequest.decided_at))],
                        fixes=[corrections.out(db, c) for c in corrections.to_review(db)])


def my_adjustments(db: DbSession, actor: User, days: int) -> list[AdjustmentOut]:
    rows = db.scalars(select(AdjustmentRequest)
                      .where(AdjustmentRequest.requested_by == actor.id,
                             AdjustmentRequest.requested_at >= datetime.now(UTC) - timedelta(days=days))
                      .order_by(AdjustmentRequest.requested_at.desc(), AdjustmentRequest.id.desc()).limit(100))
    return [adjustment_out(db, r) for r in rows]
