import pytest
from sqlalchemy import select

from app.activity.models import ActivityLog
from app.cli import create_admin, remove_test_data, remove_test_users
from app.core.security import verify_password
from app.devices.models import Device
from app.masterdata.models import SourceArea, StorageArea
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
    db.commit()
    counts = remove_test_data(db)
    assert counts == {"users": 1, "source areas": 1, "storage areas": 1, "devices": 1}
    assert db.scalars(select(SourceArea.name)).all() == ["Purok 1"]
    assert db.scalars(select(Device.code)).all() == ["WS-01"]
