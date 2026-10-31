from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.compost.models import CompostActivity, CompostBatch, CompostReading
from app.compost.schemas import ActivityIn, ActivityOut, BatchIn, BatchOut, ReadingIn
from app.core.errors import AppError
from app.devices.models import Device
from app.users.models import User

CLOCK_SLACK = timedelta(minutes=5)


def out(db: DbSession, b: CompostBatch) -> BatchOut:
    acts = db.scalars(select(CompostActivity).where(CompostActivity.batch_id == b.id).order_by(CompostActivity.at.desc()))
    names = {}
    activities = []
    for a in acts:
        if a.by and a.by not in names:
            names[a.by] = db.get(User, a.by).name
        activities.append(ActivityOut(type=a.type, note=a.note, by=names.get(a.by), at=a.at))
    sensor = db.get(Device, b.sensor_id) if b.sensor_id else None
    return BatchOut(id=b.id, code=b.code, started_at=b.started_at, start_kg=b.start_kg, sensor=sensor.code if sensor else None,
                    finished_at=b.finished_at, produced_kg=b.produced_kg, activities=activities)


def start_batch(db: DbSession, data: BatchIn, actor: User, at: datetime | None = None) -> CompostBatch:
    if data.sensor_id is not None:
        sensor = db.get(Device, data.sensor_id)
        if not sensor or sensor.type != "compost_sensor":
            raise AppError(422, "That isn't a registered compost sensor.")
        busy = db.scalar(select(CompostBatch.code).where(CompostBatch.sensor_id == sensor.id, CompostBatch.finished_at.is_(None)))
        if busy:
            raise AppError(409, f"{sensor.code} is already in batch {busy}. Finish that batch or pick another sensor.")
    b = CompostBatch(start_kg=round(data.start_kg, 2), sensor_id=data.sensor_id, started_by=actor.id)
    if at:
        b.started_at = at
    db.add(b)
    db.flush()
    b.code = f"B-{b.id:02d}"
    if not at:
        log(db, actor.id, "Started compost batch", f"{b.code} · {b.start_kg} kg wet waste")
    db.commit()
    return b


def log_activity(db: DbSession, batch_id: int, data: ActivityIn, actor: User, at: datetime | None = None) -> CompostBatch:
    b = db.get(CompostBatch, batch_id)
    if not b:
        raise AppError(404, "Compost batch not found.")
    if b.finished_at:
        raise AppError(409, f"{b.code} is finished.")
    a = CompostActivity(batch_id=b.id, type=data.type, note=data.note, by=actor.id)
    if at:
        a.at = at
    db.add(a)
    if data.finished_kg is not None:
        b.finished_at, b.produced_kg = at or datetime.now(UTC), round(data.finished_kg, 2)
    if not at:
        done = f" · finished with {b.produced_kg} kg compost" if data.finished_kg is not None else ""
        log(db, actor.id, "Logged compost activity", f"{b.code} · {data.type}{done}")
    db.commit()
    return b


def record_reading(db: DbSession, device: Device, data: ReadingIn, at: datetime | None = None) -> str | None:
    """Stores a device reading. Returns the batch code a compost reading went to, or None."""
    now = datetime.now(UTC)
    when = at or data.read_at or now
    if when > now + CLOCK_SLACK:
        raise AppError(422, "read_at is in the future. Check the device's clock.")
    shown = device.last_reading
    newest = not shown or when >= datetime.fromisoformat(shown["at"])  # a buffered reading mustn't replace a newer one
    if device.type == "weighing_station":
        if data.kg is None:
            raise AppError(422, "A weighing station sends kg.")
        if newest:
            device.last_reading = {"kg": round(data.kg, 2), "stable": bool(data.stable), "at": when.isoformat()}
        stored = None
    elif device.type == "compost_sensor":
        if data.temp_c is None or data.moisture_pct is None:
            raise AppError(422, "A compost sensor sends temp_c and moisture_pct.")
        temp, moisture = round(data.temp_c, 1), round(data.moisture_pct, 1)
        if newest:
            device.last_reading = {"temp_c": temp, "moisture_pct": moisture, "at": when.isoformat()}
        batch = db.scalar(select(CompostBatch).where(CompostBatch.sensor_id == device.id, CompostBatch.finished_at.is_(None)))
        stored = None
        if batch:
            db.execute(insert(CompostReading).values(batch_id=batch.id, device_id=device.id, temp_c=temp, moisture_pct=moisture,
                                                     read_at=when).on_conflict_do_nothing())  # a resend stores nothing new
            stored = batch.code
    else:
        raise AppError(422, "Cameras send suggestions to /devices/cv-suggestions.")
    if not at:
        device.last_seen_at = now  # it's talking now, even when the reading is old
    elif not device.last_seen_at or at > device.last_seen_at:
        device.last_seen_at = at
    db.commit()
    return stored
