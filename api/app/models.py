"""Imports every model so Base.metadata knows all tables (used by Alembic and the tests)."""
from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.approvals.models import AdjustmentRequest, Outgoing
from app.auth.models import Session
from app.compost.models import CompostActivity, CompostBatch, CompostReading
from app.core.db import Base
from app.devices.models import Device
from app.intake.models import Delivery, SegregationCheck
from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory
from app.settings.models import Settings
from app.sorting.models import Classification, StockMovement
from app.users.models import User

__all__ = ["Base", "User", "Session", "StaffAccess", "ActivityLog", "WasteCategory", "SourceArea", "Material",
           "StorageArea", "Device", "Settings", "Delivery", "SegregationCheck", "Classification", "StockMovement",
           "CompostBatch", "CompostReading", "CompostActivity", "AdjustmentRequest", "Outgoing"]
