from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.errors import AppError
from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory
from app.masterdata.schemas import ItemCreate, ItemUpdate, Kind
from app.sorting.service import lock_areas, stock_kg
from app.users.models import User

MODELS = {"categories": WasteCategory, "puroks": SourceArea, "materials": Material, "storage-areas": StorageArea}
LABELS = {
    "categories": "waste category",
    "puroks": "source area",
    "materials": "material",
    "storage-areas": "storage area",
}


def list_items(db: DbSession, kind: Kind, active_only: bool):
    model = MODELS[kind]
    q = select(model).order_by(model.name)
    if active_only:
        q = q.where(model.active.is_(True))
    return list(db.scalars(q))


def _check_name(db: DbSession, kind: Kind, name: str, except_id: int | None = None) -> None:
    model = MODELS[kind]
    q = select(model.id).where(func.lower(model.name) == name.lower())
    if except_id is not None:
        q = q.where(model.id != except_id)
    if db.scalar(q) is not None:
        raise AppError(409, f"There is already a {LABELS[kind]} named {name!r}.")


def create_item(db: DbSession, kind: Kind, data: ItemCreate, actor: User):
    _check_name(db, kind, data.name)
    if kind == "storage-areas":
        if data.capacity_kg is None:
            raise AppError(422, "Enter the storage area's capacity in kg.")
        item = StorageArea(name=data.name, capacity_kg=data.capacity_kg, alert_pct=data.alert_pct or 90)
    else:
        item = MODELS[kind](name=data.name)
    db.add(item)
    log(db, actor.id, f"Added {LABELS[kind]}", _describe(kind, item))
    db.commit()
    return item


def update_item(db: DbSession, kind: Kind, item_id: int, data: ItemUpdate, actor: User):
    item = db.get(MODELS[kind], item_id)
    if not item:
        raise AppError(404, f"That {LABELS[kind]} doesn't exist.")
    if data.name:
        _check_name(db, kind, data.name, except_id=item.id)
    if kind == "storage-areas" and data.active is False:
        lock_areas(db, [item.id])
        if (held := stock_kg(db, item.id)) > 0.005:
            raise AppError(409, f"{item.name} still holds {held} kg. Move it out before deactivating.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if kind != "storage-areas":
        changes.pop("capacity_kg", None)
        changes.pop("alert_pct", None)
    before = item.name
    for field, value in changes.items():
        setattr(item, field, value)

    if changes.get("active") is False:
        action = f"Deactivated {LABELS[kind]}"
    elif changes.get("active") is True and len(changes) == 1:
        action = f"Reactivated {LABELS[kind]}"
    else:
        action = f"Edited {LABELS[kind]}"
    record = _describe(kind, item) + (f" (was {before})" if item.name != before else "")
    log(db, actor.id, action, record)
    db.commit()
    return item


def _describe(kind: Kind, item) -> str:
    if kind == "storage-areas":
        return f"{item.name} · {item.capacity_kg} kg, alert at {item.alert_pct or 90}%"
    return item.name
