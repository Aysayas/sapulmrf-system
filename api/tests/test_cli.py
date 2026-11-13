from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.activity.models import ActivityLog
from app.alerts.models import Alert, ProblemReport
from app.approvals.models import AdjustmentRequest, Outgoing
from app.cli import create_admin, export_photos, remove_test_data, remove_test_users
from app.compost.models import CompostBatch
from app.core.security import verify_password
from app.devices.models import Device
from app.intake.models import Delivery
from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory
from app.sorting.models import Classification, StockMovement
from app.users.models import User


def test_create_admin_stores_a_hash_and_logs_it(db):
    u = create_admin(db, "Maria Santos", "msantos", "long-enough-pw")
    assert u.role == "admin" and u.active
    assert u.password_hash != "long-enough-pw" and verify_password("long-enough-pw", u.password_hash)
    assert db.scalar(select(ActivityLog).where(ActivityLog.action == "Created first administrator"))


def test_create_admin_lowercases_and_checks_the_username(db):
    assert create_admin(db, "Isiah Silla", " Aysaya ", "long-enough-pw").username == "aysaya"
    with pytest.raises(ValueError, match="Usernames are"):
        create_admin(db, "A", "has spaces", "long-enough-pw")
    with pytest.raises(ValueError, match="already taken"):
        create_admin(db, "Other", "AYSAYA", "long-enough-pw")


def test_create_admin_refuses_short_passwords_and_taken_usernames(db):
    with pytest.raises(ValueError, match="8 characters"):
        create_admin(db, "A", "valid.user", "short")
    create_admin(db, "Maria Santos", "msantos", "long-enough-pw")
    with pytest.raises(ValueError, match="already taken"):
        create_admin(db, "Other", "msantos", "long-enough-pw")


def test_remove_test_users_only_touches_e2e_role_accounts(db, make_user):
    make_user("e2e.admin", role="admin")
    make_user("e2e.staff.abc123", role="staff")
    make_user("e2e.operator.xyz", role="operator")
    make_user("rreyes", role="staff")
    assert remove_test_users(db) == 2
    assert sorted(db.scalars(select(User.username))) == ["e2e.admin", "rreyes"]


def test_remove_test_data_keeps_real_areas_and_devices(db, make_user):
    e2e_user = make_user("e2e.staff.abc123", role="staff")
    real_user = make_user("rreyes", role="operator")
    db.add_all([CompostBatch(code="B-901", start_kg=5, started_by=e2e_user.id),
                CompostBatch(code="B-902", start_kg=5, started_by=real_user.id),
                SourceArea(name="e2e Purok x1"), SourceArea(name="Purok 1"),
                StorageArea(name="e2e Area x1", capacity_kg=10), StorageArea(name="Area A", capacity_kg=500),
                Device(code="E2E-X1", type="compost_sensor", key_hash="a" * 64),
                Device(code="WS-01", type="weighing_station", key_hash="b" * 64)])
    db.flush()
    cat = db.scalar(select(WasteCategory.id))
    e2e_purok, real_purok = (db.scalar(select(SourceArea.id).where(SourceArea.name == n)) for n in ("e2e Purok x1", "Purok 1"))
    e2e_area, real_area = (db.scalar(select(StorageArea.id).where(StorageArea.name == n)) for n in ("e2e Area x1", "Area A"))
    db.add_all([Delivery(code="D-9001", source_area_id=e2e_purok, category_id=cat, weight_kg=5, weighed_by="manual"),
                Delivery(code="D-9002", source_area_id=real_purok, category_id=cat, weight_kg=5, weighed_by="manual"),
                StockMovement(material_id=None, storage_area_id=e2e_area, kg=5, kind="sorted"),
                StockMovement(material_id=None, storage_area_id=real_area, kg=5, kind="sorted"),
                Outgoing(code="O-9001", type="disposal", storage_area_id=e2e_area, kg=5, recipient="x"),
                AdjustmentRequest(storage_area_id=e2e_area, system_kg=5, actual_kg=4, reason="x"),
                Alert(kind="storage", subject_id=e2e_area, title="e2e Area x1 almost full", opened_at=datetime.now(UTC)),
                Alert(kind="storage", subject_id=real_area, title="Area A almost full", opened_at=datetime.now(UTC)),
                ProblemReport(code="R-901", kind="record", record_ref="E2E-REC", details="x"),
                ProblemReport(code="R-902", kind="record", record_ref="D-0139", details="real"),
                ProblemReport(code="R-903", kind="record", record_ref="D-9001", details="about an e2e delivery"),
                ProblemReport(code="R-904", kind="record", record_ref="D-9002", details="about a real delivery")])
    db.flush()
    mat = db.scalar(select(Material.id))
    e2e_dev, real_dev = (db.scalar(select(Device.id).where(Device.code == c)) for c in ("E2E-X1", "WS-01"))
    e2e_del, real_del = (db.scalar(select(Delivery.id).where(Delivery.code == c)) for c in ("D-9001", "D-9002"))
    db.add_all([Classification(device_id=e2e_dev, suggested_material_id=mat, confidence=0.5),
                Classification(device_id=real_dev, delivery_id=e2e_del, suggested_material_id=mat, confidence=0.5),
                Classification(device_id=real_dev, delivery_id=real_del, suggested_material_id=mat, confidence=0.9)])
    db.commit()
    counts = remove_test_data(db)
    assert db.scalars(select(CompostBatch.code)).all() == ["B-902"]
    assert counts == {"compost batches": 1, "users": 1, "deliveries": 1, "stock movements": 1, "requests": 2, "alerts": 1,
                      "problem reports": 2, "camera suggestions": 2,
                      "source areas": 1, "storage areas": 1, "devices": 1}
    assert sorted(db.scalars(select(ProblemReport.code)).all()) == ["R-902", "R-904"]
    assert db.scalars(select(Delivery.code)).all() == ["D-9002"]
    assert db.scalars(select(StockMovement.storage_area_id)).all() == [real_area]
    assert db.scalars(select(SourceArea.name)).all() == ["Purok 1"]
    assert db.scalars(select(Device.code)).all() == ["WS-01"]
    assert db.scalars(select(Classification.confidence)).all() == [0.9]


JPEG = b"\xff\xd8 tiny jpeg"


def test_export_photos_writes_each_photo_and_what_it_is(db, world, tmp_path):
    import csv

    from app.intake.models import DeliveryPhoto

    d = Delivery(code="D-0001", source_area_id=world["purok1"], category_id=world["cat"]["Recyclable"], weight_kg=2,
                 weighed_by="manual", cv_category="Recyclable", cv_confidence=0.8)
    db.add(d)
    db.flush()
    db.add(DeliveryPhoto(delivery_id=d.id, jpeg=JPEG))
    db.add(Classification(delivery_id=d.id, suggested_material_id=world["mat"]["Plastic"], confidence=0.9,
                          final_material_id=world["mat"]["Plastic"], changed=False, confirmed_at=datetime.now(UTC)))
    db.commit()
    assert export_photos(db, tmp_path) == 1
    assert (tmp_path / "D-0001.jpg").read_bytes() == JPEG
    row = next(csv.DictReader(open(tmp_path / "labels.csv", encoding="utf-8")))
    assert (row["category"], row["camera_category"], row["materials"]) == ("Recyclable", "Recyclable", "Plastic")
