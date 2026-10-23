import pytest
from sqlalchemy import select

from app.activity.models import ActivityLog
from app.cli import create_admin
from app.core.security import verify_password


def test_create_admin_stores_a_hash_and_logs_it(db):
    u = create_admin(db, "Maria Santos", "msantos", "long-enough-pw")
    assert u.role == "admin" and u.active
    assert u.password_hash != "long-enough-pw" and verify_password("long-enough-pw", u.password_hash)
    assert db.scalar(select(ActivityLog).where(ActivityLog.action == "Created first administrator"))


def test_create_admin_refuses_short_passwords_and_taken_usernames(db):
    with pytest.raises(ValueError, match="8 characters"):
        create_admin(db, "A", "a", "short")
    create_admin(db, "Maria Santos", "msantos", "long-enough-pw")
    with pytest.raises(ValueError, match="already taken"):
        create_admin(db, "Other", "msantos", "long-enough-pw")
