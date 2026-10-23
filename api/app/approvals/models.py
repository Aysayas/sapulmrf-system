from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

STATUS_CHECK = "status IN ('pending', 'approved', 'rejected')"


class AdjustmentRequest(Base):
    """An operator's count that differs from the ledger. Stock changes only when an admin approves it."""

    __tablename__ = "adjustment_requests"
    __table_args__ = (CheckConstraint(STATUS_CHECK, name="ck_adjustment_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"))  # None means residual
    storage_area_id: Mapped[int] = mapped_column(ForeignKey("storage_areas.id"))
    system_kg: Mapped[float]
    actual_kg: Mapped[float]
    reason: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now())
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    comment: Mapped[str] = mapped_column(String(200), default="")


class Outgoing(Base):
    """Material leaving the MRF: a recyclable sale, compost given out or sold, or residual sent for disposal."""

    __tablename__ = "outgoing"
    __table_args__ = (
        CheckConstraint(STATUS_CHECK, name="ck_outgoing_status"),
        CheckConstraint("type IN ('sale', 'compost', 'disposal')", name="ck_outgoing_type"),
        CheckConstraint("kg > 0", name="ck_outgoing_kg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, default="")
    type: Mapped[str] = mapped_column(String(10))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), default=None)
    storage_area_id: Mapped[int | None] = mapped_column(ForeignKey("storage_areas.id"), default=None)
    kg: Mapped[float]
    recipient: Mapped[str] = mapped_column(String(120))
    price_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    comment: Mapped[str] = mapped_column(String(200), default="")
