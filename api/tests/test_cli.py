from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.activity.models import ActivityLog
from app.alerts.models import Alert, ProblemReport
from app.approvals.models import AdjustmentRequest, Outgoing
from app.cli import create_admin, remove_test_data, remove_test_users
from app.core.security import verify_password
from app.devices.models import Device
from app.intake.models import Delivery
from app.masterdata.models import SourceArea, StorageArea, WasteCategory
from app.sorting.models import StockMovement
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
    make_user("e2e.staff.abc123", role="staff")
    db.add_all([SourceArea(name="e2e Purok x1"), SourceArea(name="Purok 1"),
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
                ProblemReport(code="R-902", kind="record", record_ref="D-0139", details="real")])
    db.commit()
    counts = remove_test_data(db)
    assert counts == {"users": 1, "deliveries": 1, "stock movements": 1, "requests": 2, "alerts": 1, "problem reports": 1,
                      "source areas": 1, "storage areas": 1, "devices": 1}
    assert db.scalars(select(ProblemReport.code)).all() == ["R-902"]
    assert db.scalars(select(Delivery.code)).all() == ["D-9002"]
    assert db.scalars(select(StockMovement.storage_area_id)).all() == [real_area]
    assert db.scalars(select(SourceArea.name)).all() == ["Purok 1"]
    assert db.scalars(select(Device.code)).all() == ["WS-01"]
