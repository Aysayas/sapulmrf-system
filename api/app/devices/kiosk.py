"""The resident kiosk's side of the API: what it shows and what its light and buzzer do.

The kiosk is a remote terminal. Its laptop polls kiosk_state() and forwards it, so every rule lives here.
"""
import base64
import binascii

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.alerts.models import Alert
from app.core.errors import AppError
from app.devices import schemas as s
from app.devices.models import Device
from app.intake.models import Delivery, DeliveryPhoto
from app.masterdata.models import Material, SourceArea, WasteCategory
from app.operations.service import TZ, area_fill, since
from app.sorting.models import Classification

ALERTS_SHOWN = 5
RECENT_ROWS = 6  # what fits the kiosk's operator table


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
