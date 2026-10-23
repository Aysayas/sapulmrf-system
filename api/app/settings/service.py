from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.errors import AppError
from app.masterdata.models import StorageArea
from app.settings.models import Settings
from app.settings.schemas import SettingsIn, SettingsOut
from app.users.models import User

FIELDS = list(SettingsOut.model_fields)


def get(db: DbSession) -> Settings:
    row = db.get(Settings, 1)
    if row is None:
        row = Settings(id=1)
        db.add(row)
        db.commit()
    return row


def save(db: DbSession, data: SettingsIn, actor: User) -> Settings:
    row = get(db)
    changes = []
    for f in FIELDS:
        new, old = getattr(data, f), getattr(row, f)
        if new != old:
            changes.append(f"{f} {old} → {new}")
            setattr(row, f, new)
    for limit in data.storage_areas:
        area = db.get(StorageArea, limit.id)
        if not area:
            raise AppError(404, "Storage area not found.")
        if (area.capacity_kg, area.alert_pct) != (limit.capacity_kg, limit.alert_pct):
            old, new = f"{area.capacity_kg} kg/{area.alert_pct}%", f"{limit.capacity_kg} kg/{limit.alert_pct}%"
            changes.append(f"{area.name} {old} → {new}")
            area.capacity_kg, area.alert_pct = limit.capacity_kg, limit.alert_pct
    if changes:
        log(db, actor.id, "Changed ranges and limits", "; ".join(changes))
    db.commit()
    return row
