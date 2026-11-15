"""Imports every model so Base.metadata knows all tables (used by Alembic and the tests)."""
from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.alerts.models import Alert, ProblemReport
from app.approvals.models import AdjustmentRequest, Outgoing
from app.assistant.models import ChatMessage, Conversation
from app.auth.models import Session
from app.compost.models import CompostActivity, CompostBatch, CompostReading
from app.core.db import Base
from app.corrections.models import Correction
from app.devices.models import Device
from app.insights.models import Flag, Forecast
from app.intake.models import Delivery, SegregationCheck
from app.masterdata.models import Buyer, Material, SourceArea, StorageArea, WasteCategory
from app.reports.models import ReportExport
from app.settings.models import Settings
from app.sorting.models import Classification, StockMovement
from app.users.models import User

__all__ = ["Base", "User", "Session", "StaffAccess", "ActivityLog", "WasteCategory", "SourceArea", "Material",
           "StorageArea", "Device", "Settings", "Delivery", "SegregationCheck", "Classification", "StockMovement",
           "CompostBatch", "CompostReading", "CompostActivity", "AdjustmentRequest", "Outgoing", "Alert", "ProblemReport",
           "Flag", "Forecast", "ReportExport", "Correction", "Buyer",
           "Conversation", "ChatMessage"]
