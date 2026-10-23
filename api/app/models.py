"""Imports every model so Base.metadata knows all tables (used by Alembic and the tests)."""
from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.auth.models import Session
from app.core.db import Base
from app.users.models import User

__all__ = ["Base", "User", "Session", "StaffAccess", "ActivityLog"]
