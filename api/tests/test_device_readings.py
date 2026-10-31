from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.compost.models import CompostBatch, CompostReading
from app.core.security import token_hash as key_hash
from app.devices.models import Device


def device(db, kind="compost_sensor", code="SENSE-1", key="sensor-key"):
    d = Device(code=code, type=kind, key_hash=key_hash(key))
    db.add(d)
    db.commit()
    return d


def sensor_with_batch(db):
    d = device(db)
    db.add(CompostBatch(code="B-1", start_kg=100, sensor_id=d.id))
    db.commit()
    return d


def send(client, key="sensor-key", **body):
    return client.post("/devices/readings", headers={"X-Device-Key": key}, json={"temp_c": 55, "moisture_pct": 50, **body})


def ago(**kw):
    return (datetime.now(UTC) - timedelta(**kw)).isoformat()


def test_a_resent_reading_is_stored_once(client, db):
    sensor_with_batch(db)
    at = ago(hours=1)
    assert send(client, read_at=at).status_code == send(client, read_at=at).status_code == 200
    assert db.scalar(select(func.count(CompostReading.id))) == 1


def test_a_buffered_reading_keeps_its_time_and_doesnt_replace_a_newer_one(client, db):
    d = sensor_with_batch(db)
    assert send(client, temp_c=60).status_code == 200
    assert send(client, temp_c=40, read_at=ago(hours=6)).status_code == 200
    db.expire_all()
    assert d.last_reading["temp_c"] == 60
    times = db.scalars(select(CompostReading.read_at).order_by(CompostReading.read_at)).all()
    assert len(times) == 2 and datetime.now(UTC) - times[0] > timedelta(hours=5)


def test_a_late_upload_still_counts_as_a_heartbeat(client, db):
    d = sensor_with_batch(db)
    assert send(client, read_at=ago(hours=6)).status_code == 200
    db.expire_all()
    assert datetime.now(UTC) - d.last_seen_at < timedelta(minutes=1)


def test_readings_from_the_future_and_without_a_timezone_are_refused(client, db):
    sensor_with_batch(db)
    assert send(client, read_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()).status_code == 422
    assert send(client, read_at="2026-11-01T08:30:00").status_code == 422


def test_readings_without_a_time_use_the_servers_clock(client, db):
    sensor_with_batch(db)
    assert send(client).status_code == send(client).status_code == 200
    assert db.scalar(select(func.count(CompostReading.id))) == 2


def test_a_scale_weight_needs_a_stable_reading(client, db, world, as_operator):
    d = device(db, "weighing_station", "SCALE-1", "scale-key")
    r = client.post("/devices/readings", headers={"X-Device-Key": "scale-key"}, json={"kg": 12.4, "stable": False})
    assert r.status_code == 200
    body = {"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"], "weight_kg": 12.4,
            "weighed_by": "scale", "device_id": d.id}
    r = client.post("/deliveries", json=body)
    assert r.status_code == 422 and "settled" in r.json()["detail"]
