from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.errors import AppError
from app.devices.models import Device
from app.insights import flags
from app.intake.models import Delivery, SegregationCheck
from app.masterdata.models import Material, StorageArea
from app.sorting.models import Classification, StockMovement
from app.sorting.schemas import ClassificationOut, ConfirmIn, SortIn, SuggestionIn, TransferIn, TransferOut
from app.users.models import User

SORT_TOLERANCE = 1.10  # sorted kg may slightly exceed the dry weight (rounding, bags)


def _name(db: DbSession, material_id: int | None) -> str:
    return db.get(Material, material_id).name if material_id else "Residual"


def out(db: DbSession, c: Classification) -> ClassificationOut:
    final = "Not recyclable" if c.not_recyclable else (_name(db, c.final_material_id) if c.final_material_id else None)
    by = db.get(User, c.confirmed_by) if c.confirmed_by else None
    return ClassificationOut(id=c.id, suggested_at=c.suggested_at, suggested=_name(db, c.suggested_material_id),
                             confidence=c.confidence, model_version=c.model_version, image_url=c.image_url,
                             final=final, changed=c.changed, reason=c.reason, confirmed_by=by.name if by else None,
                             confirmed_at=c.confirmed_at)


def create_suggestion(db: DbSession, device: Device | None, data: SuggestionIn,
                      at: datetime | None = None) -> Classification:
    """A camera suggestion becomes a pending classification for the operator to confirm."""
    material = db.scalar(select(Material).where(func.lower(Material.name) == data.label.lower(), Material.active))
    if not material:
        raise AppError(422, f"Unknown material {data.label!r}. Expected one of the active recyclable materials.")
    c = Classification(device_id=device.id if device else None, image_url=data.image_url,
                       suggested_material_id=material.id, confidence=round(data.confidence, 3),
                       model_version=data.model_version)
    if at:
        c.suggested_at = at
    db.add(c)
    db.commit()
    return c


def pending(db: DbSession, limit: int) -> list[ClassificationOut]:
    rows = db.scalars(select(Classification).where(Classification.confirmed_at.is_(None))
                      .order_by(Classification.suggested_at.desc(), Classification.id.desc()).limit(limit))
    return [out(db, c) for c in rows]


def confirm(db: DbSession, classification_id: int, data: ConfirmIn, actor: User,
            at: datetime | None = None) -> Classification:
    c = db.get(Classification, classification_id, with_for_update=True)
    if not c:
        raise AppError(404, "Classification not found.")
    if c.confirmed_at:
        raise AppError(409, "This item was already confirmed.")
    if data.final_material_id is not None and not db.get(Material, data.final_material_id):
        raise AppError(422, "Pick a recyclable material.")
    c.not_recyclable = data.not_recyclable
    c.final_material_id = None if data.not_recyclable else (data.final_material_id or c.suggested_material_id)
    c.changed = data.not_recyclable or c.final_material_id != c.suggested_material_id
    c.reason, c.confirmed_by, c.confirmed_at = data.reason, actor.id, at or datetime.now(UTC)
    if not at:
        verb = "Changed classification" if c.changed else "Confirmed classification"
        final = "Not recyclable" if c.not_recyclable else _name(db, c.final_material_id)
        log(db, actor.id, verb, f"{_name(db, c.suggested_material_id)} {round(c.confidence * 100)}% → {final}")
    db.commit()
    return c


def stock_kg(db: DbSession, storage_area_id: int) -> float:
    """Current kg in an area: the sum of its ledger rows."""
    q = select(func.coalesce(func.sum(StockMovement.kg), 0.0)).where(StockMovement.storage_area_id == storage_area_id)
    return round(float(db.scalar(q)), 2)


def _of(material_id: int | None, storage_area_id: int):
    same = StockMovement.material_id.is_(None) if material_id is None else StockMovement.material_id == material_id
    return same, StockMovement.storage_area_id == storage_area_id


def material_kg(db: DbSession, material_id: int | None, storage_area_id: int) -> float:
    """Current kg of one material (None = residual) in one area."""
    q = select(func.coalesce(func.sum(StockMovement.kg), 0.0)).where(*_of(material_id, storage_area_id))
    return round(float(db.scalar(q)), 2)


def material_bags(db: DbSession, material_id: int | None, storage_area_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(StockMovement.bags), 0)).where(*_of(material_id, storage_area_id))))


def lock_areas(db: DbSession, area_ids: list[int]) -> dict[int, StorageArea]:
    """Every change that reads a balance and then writes it holds this, in id order so writers can't deadlock."""
    return {a.id: a for a in db.scalars(select(StorageArea).where(StorageArea.id.in_(area_ids))
                                        .order_by(StorageArea.id).with_for_update())}


def transfer(db: DbSession, data: TransferIn, actor: User) -> TransferOut:
    """Moves stock between areas as two ledger rows. Same material on both sides; bags move with it."""
    if data.from_area_id == data.to_area_id:
        raise AppError(422, "Pick two different storage areas.")
    if data.material_id is not None and not db.get(Material, data.material_id):
        raise AppError(422, "Pick a recyclable material, or leave it empty for residual.")
    areas = lock_areas(db, [data.from_area_id, data.to_area_id])
    source, dest = areas.get(data.from_area_id), areas.get(data.to_area_id)
    kg, material = round(data.kg, 2), _name(db, data.material_id)
    if data.client_key and source and dest:  # the area lock above keeps two sends of one key in order
        first = db.scalar(select(StockMovement).where(StockMovement.client_key == data.client_key))
        if first:
            return TransferOut(material=material, from_area=source.name, to_area=dest.name, kg=-first.kg, bags=-first.bags,
                               from_area_kg=stock_kg(db, source.id), to_area_kg=stock_kg(db, dest.id))
    if not source or not source.active or not dest or not dest.active:
        raise AppError(422, "Pick an active storage area.")
    available, bags_there = material_kg(db, data.material_id, source.id), material_bags(db, data.material_id, source.id)
    if kg > available + 0.001:
        raise AppError(409, f"Only {available} kg of {material} in {source.name}.")
    emptying = kg >= available - 0.001
    if data.bags is not None and data.bags > bags_there:
        raise AppError(409, f"Only {bags_there} bags of {material} in {source.name}.")
    if not emptying and bags_there and data.bags == bags_there:
        raise AppError(409, f"Some {material} stays in {source.name}, so leave it at least one bag.")
    if stock_kg(db, dest.id) + kg > dest.capacity_kg + 0.001:
        raise AppError(409, f"{dest.name} can't take {kg} kg more. It holds {stock_kg(db, dest.id)} of {dest.capacity_kg} kg.")
    if emptying:
        bags = bags_there
    elif data.bags is not None:
        bags = data.bags
    else:  # no count given: in proportion to the kg, as outgoing does, never the last bag
        bags = max(0, min(bags_there - 1, round(bags_there * kg / available)))
    note = f"{source.name} → {dest.name}"[:200]
    for area, sign in ((source, -1), (dest, 1)):
        db.add(StockMovement(material_id=data.material_id, storage_area_id=area.id, kg=sign * kg, bags=sign * bags,
                             kind="transfer", by=actor.id, note=note, client_key=data.client_key if sign < 0 else None))
    log(db, actor.id, "Transferred stock", f"{material} · {note} · {kg} kg · {bags} bags")
    db.commit()
    return TransferOut(material=material, from_area=source.name, to_area=dest.name, kg=kg, bags=bags,
                       from_area_kg=stock_kg(db, source.id), to_area_kg=stock_kg(db, dest.id))


def sort_delivery(db: DbSession, data: SortIn, actor: User, at: datetime | None = None) -> Delivery:
    d = db.get(Delivery, data.delivery_id, with_for_update=True)  # two phones can submit the same delivery
    if not d:
        raise AppError(404, "Delivery not found.")
    if d.status == "awaiting":
        raise AppError(409, f"{d.code} needs its segregation check before sorting.")
    if d.status == "sorted":
        raise AppError(409, f"{d.code} is already sorted.")
    dry = db.scalar(select(SegregationCheck.dry_kg).where(SegregationCheck.delivery_id == d.id)) or 0.0
    total = sum(r.kg for r in data.rows)
    if total > dry * SORT_TOLERANCE + 0.5:
        raise AppError(422, f"Sorted {round(total, 2)} kg is more than the {dry} kg of dry waste from {d.code}.")
    areas = lock_areas(db, [r.storage_area_id for r in data.rows])
    for r in data.rows:
        area = areas.get(r.storage_area_id)
        if not area or not area.active:
            raise AppError(422, "Pick an active storage area for every row.")
        if r.material_id is not None and not db.get(Material, r.material_id):
            raise AppError(422, "Pick a recyclable material, or leave it empty for residual.")
        m = StockMovement(material_id=r.material_id, storage_area_id=area.id, kg=round(r.kg, 2), bags=r.bags,
                          kind="sorted", delivery_id=d.id, by=actor.id)
        if at:
            m.at = at
        db.add(m)
    d.status = "sorted"
    flags.check_gap(db, d)
    if not at:
        parts =", ".join(f"{_name(db, r.material_id)} {r.kg} kg" for r in data.rows)
        log(db, actor.id, "Recorded sorted quantities", f"{d.code} · {parts}"[:255])
    db.commit()
    return d
