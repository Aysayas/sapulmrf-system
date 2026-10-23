from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.alerts.checks import run_checks
from app.alerts.models import Alert
from app.compost.models import CompostBatch, CompostReading
from app.devices.models import Device
from app.masterdata.models import StorageArea
from app.sorting.models import StockMovement

NOW = datetime(2026, 10, 23, 2, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)


def readings(db, batch, start, minutes, temp, moisture=50.0):
    db.add_all([CompostReading(batch_id=batch.id, temp_c=temp, moisture_pct=moisture, read_at=start + i * MIN)
                for i in range(minutes)])
    db.commit()


def open_alerts(db, kind):
    return db.scalars(select(Alert).where(Alert.kind == kind, Alert.resolved_at.is_(None))).all()


def test_compost_alerts_wait_ten_minutes_both_ways(db):
    b = CompostBatch(code="B-90", start_kg=50)
    db.add(b)
    db.commit()
    readings(db, b, NOW - 20 * MIN, 15, temp=58)          # in range until 5 minutes ago
    readings(db, b, NOW - 5 * MIN, 12, temp=70.4)          # then too hot, through NOW+6
    run_checks(db, NOW)
    assert open_alerts(db, "compost") == []                # 5 minutes out: a spike, not yet an alert

    run_checks(db, NOW + 6 * MIN)
    [a] = open_alerts(db, "compost")
    assert a.title == "Compost B-90 above range" and a.details == "70.4 °C (range 45–65 °C)"
    run_checks(db, NOW + 6 * MIN)
    assert db.scalar(select(func.count(Alert.id))) == 1    # running again never duplicates

    readings(db, b, NOW + 7 * MIN, 15, temp=60)            # back in range from NOW+7
    run_checks(db, NOW + 12 * MIN)
    assert len(open_alerts(db, "compost")) == 1            # 5 minutes back in range: still open
    run_checks(db, NOW + 18 * MIN)
    assert open_alerts(db, "compost") == [] and a.resolved_at == NOW + 18 * MIN


def test_dry_compost_names_moisture(db):
    b = CompostBatch(code="B-91", start_kg=50)
    db.add(b)
    db.commit()
    readings(db, b, NOW - 12 * MIN, 13, temp=58, moisture=35.0)
    run_checks(db, NOW)
    [a] = open_alerts(db, "compost")
    assert a.title == "Compost B-91 moisture below range" and a.details.startswith("35.0% moisture")


def test_finishing_a_batch_resolves_its_alert(db):
    b = CompostBatch(code="B-92", start_kg=50)
    db.add(b)
    db.commit()
    readings(db, b, NOW - 12 * MIN, 13, temp=70)
    run_checks(db, NOW)
    b.finished_at, b.produced_kg = NOW, 20
    db.commit()
    run_checks(db, NOW + MIN)
    assert open_alerts(db, "compost") == []


def test_a_silent_device_is_disconnected_until_it_reports(db):
    ws = Device(code="WS-09", type="weighing_station", key_hash="a" * 64, last_seen_at=NOW - MIN)
    never = Device(code="CS-09", type="compost_sensor", key_hash="b" * 64)
    off = Device(code="CAM-09", type="sorting_camera", key_hash="c" * 64, active=False, last_seen_at=NOW - 60 * MIN)
    db.add_all([ws, never, off])
    db.commit()
    run_checks(db, NOW)
    assert open_alerts(db, "device") == []
    run_checks(db, NOW + 3 * MIN)
    [a] = open_alerts(db, "device")
    assert a.title == "Weighing station WS-09 disconnected" and a.subject_id == ws.id
    ws.last_seen_at = NOW + 4 * MIN
    db.commit()
    run_checks(db, NOW + 4 * MIN)
    assert open_alerts(db, "device") == []


def test_storage_at_its_alert_level(db, world):
    db.add(StockMovement(material_id=None, storage_area_id=world["area_a"], kg=460, kind="sorted"))  # 92% of 500, alert 90
    db.commit()
    run_checks(db, NOW)
    [a] = open_alerts(db, "storage")
    assert a.title == "Area A almost full" and a.details == "92% of 500 kg (alert at 90%)"
    db.add(StockMovement(material_id=None, storage_area_id=world["area_a"], kg=-100, kind="outgoing"))
    db.commit()
    run_checks(db, NOW + MIN)
    assert open_alerts(db, "storage") == []


def test_an_inactive_area_raises_nothing(db):
    area = StorageArea(name="Old area", capacity_kg=10, alert_pct=50, active=False)
    db.add(area)
    db.flush()
    db.add(StockMovement(material_id=None, storage_area_id=area.id, kg=10, kind="sorted"))
    db.commit()
    run_checks(db, NOW)
    assert open_alerts(db, "storage") == []
