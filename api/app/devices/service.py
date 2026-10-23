import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.errors import AppError
from app.core.security import token_hash
from app.devices.models import Device
from app.devices.schemas import DeviceCreate, DeviceOut, DeviceUpdate, DeviceWithKey
from app.users.models import User

ONLINE_WITHIN = timedelta(minutes=2)


def status(d: Device, now: datetime | None = None) -> str:
    if d.last_seen_at is None:
        return "never"
    return "online" if (now or datetime.now(UTC)) - d.last_seen_at <= ONLINE_WITHIN else "offline"


def out(d: Device) -> DeviceOut:
    return DeviceOut(id=d.id, code=d.code, type=d.type, location=d.location, active=d.active,
                     last_seen_at=d.last_seen_at, status=status(d))


def _new_key() -> tuple[str, str]:
    key = "mrfk_" + secrets.token_urlsafe(24)
    return key, token_hash(key)


def list_devices(db: DbSession) -> list[DeviceOut]:
    return [out(d) for d in db.scalars(select(Device).order_by(Device.code))]


def _check_code(db: DbSession, code: str, except_id: int | None = None) -> None:
    q = select(Device.id).where(func.upper(Device.code) == code.upper())
    if except_id is not None:
        q = q.where(Device.id != except_id)
    if db.scalar(q) is not None:
        raise AppError(409, f"Device ID {code} is already registered.")


def register(db: DbSession, data: DeviceCreate, actor: User) -> DeviceWithKey:
    _check_code(db, data.code)
    key, hashed = _new_key()
    d = Device(code=data.code, type=data.type, location=data.location, key_hash=hashed)
    db.add(d)
    db.flush()
    log(db, actor.id, "Registered device", f"{d.code} · {d.type} · {d.location or 'no location'}")
    db.commit()
    return DeviceWithKey(**out(d).model_dump(), key=key)


def update(db: DbSession, device_id: int, data: DeviceUpdate, actor: User) -> DeviceOut:
    d = db.get(Device, device_id)
    if not d:
        raise AppError(404, "Device not found.")
    if data.code:
        _check_code(db, data.code, except_id=d.id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(d, field, value)
    action = "Deactivated device" if changes.get("active") is False else "Edited device"
    log(db, actor.id, action, f"{d.code} · {', '.join(sorted(changes))}")
    db.commit()
    return out(d)


def new_key(db: DbSession, device_id: int, actor: User) -> DeviceWithKey:
    d = db.get(Device, device_id)
    if not d:
        raise AppError(404, "Device not found.")
    key, d.key_hash = _new_key()
    log(db, actor.id, "Generated new device key", f"{d.code} · the old key no longer works")
    db.commit()
    return DeviceWithKey(**out(d).model_dump(), key=key)


def heartbeat(db: DbSession, key: str | None) -> Device:
    """Called by the device itself. Not logged: it arrives every few seconds."""
    d = db.scalar(select(Device).where(Device.key_hash == token_hash(key))) if key else None
    if not d:
        raise AppError(401, "Unknown device key.")
    if not d.active:
        raise AppError(403, "This device is deactivated.")
    d.last_seen_at = datetime.now(UTC)
    db.commit()
    return d
