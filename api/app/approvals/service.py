from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.approvals.models import AdjustmentRequest, Outgoing
from app.approvals.schemas import AdjustmentIn, AdjustmentOut, ApprovalsOut, DecisionIn, OutgoingIn, OutgoingOut, ReviewIn
from app.compost.models import CompostBatch
from app.core.errors import AppError
from app.intake import service as intake
from app.intake.models import Delivery
from app.intake.schemas import DeliveryOut
from app.masterdata.models import Material, StorageArea
from app.sorting import service as sorting
from app.sorting.models import Classification, StockMovement
from app.sorting.schemas import ClassificationOut
from app.sorting.service import material_bags, material_kg, stock_kg
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
    out = db.scalar(select(func.coalesce(func.sum(Outgoing.kg), 0.0)).where(Outgoing.type == "compost",
                                                                            Outgoing.status == "approved"))
    return round(float(made) - float(out), 2)


def adjustment_out(db: DbSession, r: AdjustmentRequest) -> AdjustmentOut:
    area = db.get(StorageArea, r.storage_area_id)
    current, area_kg = material_kg(db, r.material_id, area.id), stock_kg(db, area.id)
    return AdjustmentOut(id=r.id, requested_at=r.requested_at, material=_material(db, r.material_id), area=area.name,
                         system_kg=r.system_kg, actual_kg=r.actual_kg, reason=r.reason, details=r.details,
                         current_kg=current, area_kg=area_kg, area_after_kg=round(area_kg + r.actual_kg - current, 2),
                         capacity_kg=area.capacity_kg, status=r.status, requested_by=_name(db, r.requested_by),
                         decided_by=_name(db, r.decided_by), decided_at=r.decided_at, comment=r.comment)


def outgoing_out(db: DbSession, o: Outgoing) -> OutgoingOut:
    area = db.get(StorageArea, o.storage_area_id) if o.storage_area_id else None
    area_kg = stock_kg(db, area.id) if area else None
    available = material_kg(db, o.material_id, area.id) if area else compost_on_hand(db)
    return OutgoingOut(id=o.id, code=o.code, requested_at=o.requested_at, type=o.type,
                       material="Compost" if o.type == "compost" else _material(db, o.material_id),
                       area=area.name if area else None, kg=o.kg, recipient=o.recipient,
                       price_per_kg=float(o.price_per_kg) if o.price_per_kg is not None else None,
                       total=float(o.total) if o.total is not None else None, available_kg=available,
                       area_kg=area_kg, area_after_kg=round(area_kg - o.kg, 2) if area else None,
                       capacity_kg=area.capacity_kg if area else None, status=o.status,
                       requested_by=_name(db, o.requested_by), decided_by=_name(db, o.decided_by),
                       decided_at=o.decided_at, comment=o.comment)


def request_adjustment(db: DbSession, data: AdjustmentIn, actor: User, at: datetime | None = None) -> AdjustmentRequest:
    area = _area(db, data.storage_area_id)
    if data.material_id is not None and not db.get(Material, data.material_id):
        raise AppError(422, "Pick a recyclable material, or leave it empty for residual.")
    r = AdjustmentRequest(material_id=data.material_id, storage_area_id=area.id,
                          system_kg=material_kg(db, data.material_id, area.id), actual_kg=round(data.actual_kg, 2),
                          reason=data.reason, details=data.details, requested_by=actor.id)
    if at:
        r.requested_at = at
    db.add(r)
    if not at:
        log(db, actor.id, "Requested inventory adjustment",
            f"{_material(db, r.material_id)} · {area.name} · {r.system_kg} → {r.actual_kg} kg · {r.reason}")
    db.commit()
    return r


def request_outgoing(db: DbSession, data: OutgoingIn, actor: User, at: datetime | None = None) -> Outgoing:
    if data.storage_area_id is not None:
        _area(db, data.storage_area_id)
    if data.material_id is not None and not db.get(Material, data.material_id):
        raise AppError(422, "Pick a recyclable material.")
    price = Decimal(str(data.price_per_kg)).quantize(Decimal("0.01")) if data.price_per_kg else None
    o = Outgoing(type=data.type, material_id=data.material_id, storage_area_id=data.storage_area_id,
                 kg=round(data.kg, 2), recipient=data.recipient, price_per_kg=price,
                 total=(price * Decimal(str(round(data.kg, 2)))).quantize(Decimal("0.01")) if price else None,
                 requested_by=actor.id)
    if at:
        o.requested_at = at
    db.add(o)
    db.flush()
    o.code = f"O-{o.id:04d}"
    if not at:
        log(db, actor.id, "Recorded outgoing material", f"{o.code} · {data.type} · {o.kg} kg · {o.recipient}")
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
    r = _pending(db.get(AdjustmentRequest, request_id), "Adjustment")
    _decide(r, data, actor, at)
    change = round(r.actual_kg - material_kg(db, r.material_id, r.storage_area_id), 2)
    if r.status == "approved" and change:
        db.add(StockMovement(material_id=r.material_id, storage_area_id=r.storage_area_id, kg=change, kind="adjustment",
                             by=actor.id, note=f"Adjustment #{r.id}: {r.reason}"[:200], at=r.decided_at))
    if not at:
        verb = "Approved inventory adjustment" if r.status == "approved" else "Rejected inventory adjustment"
        area = db.get(StorageArea, r.storage_area_id).name
        log(db, actor.id, verb, f"{_material(db, r.material_id)} · {area} · {change:+} kg · {r.comment}".rstrip(" ·"))
    db.commit()
    return r


def decide_outgoing(db: DbSession, outgoing_id: int, data: DecisionIn, actor: User, at: datetime | None = None) -> Outgoing:
    o = _pending(db.get(Outgoing, outgoing_id), "Outgoing record")
    if data.decision == "approve":
        available = material_kg(db, o.material_id, o.storage_area_id) if o.storage_area_id else compost_on_hand(db)
        if o.kg > available + 0.001:
            what = f"{_material(db, o.material_id)} in {db.get(StorageArea, o.storage_area_id).name}" \
                if o.storage_area_id else "finished compost"
            raise AppError(409, f"Only {available} kg of {what}. Reject it, or ask the operator for a new count.")
    _decide(o, data, actor, at)
    if o.status == "approved" and o.storage_area_id:
        bags = material_bags(db, o.material_id, o.storage_area_id)
        db.add(StockMovement(material_id=o.material_id, storage_area_id=o.storage_area_id, kg=-o.kg,
                             bags=-min(bags, round(bags * o.kg / available)), kind="outgoing", by=actor.id,
                             note=o.code, at=o.decided_at))
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
    return [intake.out(db, d) for d in rows]


def changes_to_review(db: DbSession, limit: int = 100) -> list[ClassificationOut]:
    rows = db.scalars(select(Classification).where(*UNREVIEWED_CHANGES)
                      .order_by(Classification.confirmed_at.desc()).limit(limit))
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
            "weights": n(Delivery.id, *UNREVIEWED_WEIGHTS),
            "classifications": n(Classification.id, *UNREVIEWED_CHANGES)}


def pending(db: DbSession) -> ApprovalsOut:
    adjustments = db.scalars(select(AdjustmentRequest).where(AdjustmentRequest.status == "pending")
                             .order_by(AdjustmentRequest.requested_at)).all()
    outgoing = db.scalars(select(Outgoing).where(Outgoing.status == "pending").order_by(Outgoing.requested_at)).all()
    return ApprovalsOut(counts=counts(db), adjustments=[adjustment_out(db, r) for r in adjustments],
                        outgoing=[outgoing_out(db, o) for o in outgoing])
