from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Delivery(Base):
    """One household delivery weighed at intake."""

    __tablename__ = "deliveries"
    __table_args__ = (
        CheckConstraint("weighed_by IN ('scale', 'manual')", name="ck_deliveries_weighed_by"),
        CheckConstraint("status IN ('awaiting', 'separated', 'sorted')", name="ck_deliveries_status"),
        CheckConstraint("weight_kg > 0", name="ck_deliveries_weight"),
        CheckConstraint("review IN ('ok', 'recheck')", name="ck_deliveries_review"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, default="")
    received_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    source_area_id: Mapped[int] = mapped_column(ForeignKey("source_areas.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("waste_categories.id"))
    weight_kg: Mapped[float]
    weighed_by: Mapped[str] = mapped_column(String(6))
    scale_kg: Mapped[float | None] = mapped_column(default=None)  # set when the operator corrected the scale
    correction_reason: Mapped[str | None] = mapped_column(String(120), default=None)
    status: Mapped[str] = mapped_column(String(10), default="awaiting", index=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), default=None)
    client_key: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)
    # The admin's review of a corrected weight: ok or recheck. A mark only; the weight stays as recorded.
    review: Mapped[str | None] = mapped_column(String(8), default=None)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)


class SegregationCheck(Base):
    __tablename__ = "segregation_checks"
    __table_args__ = (CheckConstraint("condition IN ('segregated', 'mixed')", name="ck_segregation_condition"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"), unique=True)
    condition: Mapped[str] = mapped_column(String(10))
    wet_kg: Mapped[float]
    dry_kg: Mapped[float]
    note: Mapped[str] = mapped_column(String(200), default="")
    checked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    checked_at: Mapped[datetime] = mapped_column(server_default=func.now())
