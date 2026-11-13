"""The resident kiosk's side of the API: what it shows and what its light and buzzer do.

The kiosk is a remote terminal. Its laptop polls kiosk_state() and forwards it, so every rule lives here.
"""
import base64
import binascii
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.alerts.models import Alert
from app.auth.models import Session
from app.core.errors import AppError
from app.core.security import new_session_token, verify_password
from app.devices import schemas as s
from app.devices.models import Device
from app.intake.models import Delivery, DeliveryPhoto
from app.masterdata.models import Material, SourceArea, WasteCategory
from app.operations.service import TZ, area_fill, since
from app.sorting.models import Classification
from app.users.models import User

ALERTS_SHOWN = 5
RECENT_ROWS = 6  # what fits the kiosk's operator table
PIN_TRIES = 5  # then that operator's kiosk PIN is locked
PIN_LOCK_MIN = 5
SESSION_MIN = 30  # a kiosk sign-in is a normal session, but short: the kiosk is in a public place


def attach_cv(db: DbSession, d: Delivery, body: s.KioskDeliveryIn) -> bool:
    """Keep what the camera saw. Returns False on a resend, so the first drop-off's photo and suggestions stay."""
    if d.cv_category is not None or db.get(DeliveryPhoto, d.id) or db.scalar(
        select(Classification.id).where(Classification.delivery_id == d.id).limit(1)
    ):
        return False
    if body.cv:
        d.cv_category, d.cv_counts, d.cv_confidence = body.cv.category, body.cv.counts.model_dump(), body.cv.confidence
    if body.photo:
        try:
            jpeg = base64.b64decode(body.photo, validate=True)
        except binascii.Error:
            raise AppError(422, "The photo isn't valid base64.") from None
        if not jpeg.startswith(b"\xff\xd8"):
            raise AppError(422, "The photo must be a JPEG.")
        db.add(DeliveryPhoto(delivery_id=d.id, jpeg=jpeg))
    return True


def attach_materials(db: DbSession, d: Delivery, device: Device, body: s.KioskDeliveryIn) -> None:
    """The kiosk camera is also the sorting camera: each material it saw becomes a pending suggestion for the
    operator, with this drop-off's photo. A label SapulMRF doesn't know is skipped, never failing the drop-off."""
    for m in body.materials:
        material = db.scalar(select(Material).where(func.lower(Material.name) == m.label.lower(), Material.active))
        if material:
            db.add(Classification(device_id=device.id, delivery_id=d.id, suggested_material_id=material.id,
                                  confidence=round(m.confidence, 3), model_version="kiosk",
                                  image_url=f"/api/deliveries/{d.id}/photo" if body.photo else ""))


def light(db: DbSession) -> s.Light:
    """Red when a storage area is over capacity, amber for any other open alert, otherwise green."""
    if any(a.pct > 100 for a in area_fill(db)):
        return "red"
    return "amber" if db.scalar(select(Alert.id).where(Alert.resolved_at.is_(None)).limit(1)) else "green"


def kiosk_state(db: DbSession) -> s.KioskState:
    drops, kg = db.execute(
        select(func.count(), func.coalesce(func.sum(Delivery.weight_kg), 0.0)).where(Delivery.received_at >= since(1))
    ).one()
    open_alerts = db.scalars(
        select(Alert).where(Alert.resolved_at.is_(None)).order_by(Alert.opened_at.desc(), Alert.id.desc()).limit(ALERTS_SHOWN)
    )
    return s.KioskState(
        today=s.KioskToday(kg=round(float(kg), 1), drops=drops),
        alerts=[s.KioskAlert(kind=a.kind, title=a.title, details=a.details) for a in open_alerts],
        actuators=s.KioskActuators(light=light(db)),
    )


def kiosk_recent(db: DbSession, device: Device) -> list[s.KioskRow]:
    rows = db.execute(
        select(Delivery, SourceArea.name, WasteCategory.name)
        .join(SourceArea, SourceArea.id == Delivery.source_area_id)
        .join(WasteCategory, WasteCategory.id == Delivery.category_id)
        .where(Delivery.device_id == device.id)
        .order_by(Delivery.received_at.desc(), Delivery.id.desc())
        .limit(RECENT_ROWS)
    ).all()
    return [
        s.KioskRow(code=d.code, time=d.received_at.astimezone(TZ).strftime("%I:%M %p").lstrip("0"),
                   purok=area, cat=cat, kg=f"{d.weight_kg:.1f} kg")
        for d, area, cat in rows
    ]


def _operator(db: DbSession, user_id: int) -> User | None:
    u = db.get(User, user_id)
    return u if u and u.active and u.role == "operator" and u.kiosk_pin_hash else None


def kiosk_operators(db: DbSession) -> list[s.KioskOperator]:
    rows = db.scalars(select(User).where(User.active, User.role == "operator", User.kiosk_pin_hash.is_not(None))
                      .order_by(User.name))
    return [s.KioskOperator(id=u.id, name=u.name) for u in rows]


def kiosk_login(db: DbSession, device: Device, user_id: int, pin: str) -> tuple[User, str]:
    """An operator signs in at the kiosk with their own PIN. Returns them and a session token for their laptop."""
    now = datetime.now(UTC)
    user = _operator(db, user_id)
    if not user:
        raise AppError(401, "That operator can't sign in here. Set a kiosk PIN on the website first.")
    if user.kiosk_locked_until and user.kiosk_locked_until > now:
        minutes = max(1, round((user.kiosk_locked_until - now).total_seconds() / 60))
        raise AppError(423, f"Too many wrong PINs. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")
    if not verify_password(pin, user.kiosk_pin_hash):
        user = db.get(User, user.id, with_for_update=True, populate_existing=True)  # parallel guesses must each count
        user.kiosk_pin_failures += 1
        if user.kiosk_pin_failures >= PIN_TRIES:
            user.kiosk_pin_failures, user.kiosk_locked_until = 0, now + timedelta(minutes=PIN_LOCK_MIN)
            log(db, user.id, "Kiosk PIN locked", f"{PIN_TRIES} wrong PINs on {device.code}")
            db.commit()
            raise AppError(423, f"Too many wrong PINs. Try again in {PIN_LOCK_MIN} minutes.")
        db.commit()
        raise AppError(401, "Wrong PIN.")
    user.kiosk_pin_failures, user.kiosk_locked_until, user.last_login_at = 0, None, now
    token, hashed = new_session_token()
    db.add(Session(token_hash=hashed, user_id=user.id, expires_at=now + timedelta(minutes=SESSION_MIN)))
    log(db, user.id, "Kiosk sign-in", device.code)
    db.commit()
    return user, token
