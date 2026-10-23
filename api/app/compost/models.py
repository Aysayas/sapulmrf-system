from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CompostBatch(Base):
    __tablename__ = "compost_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, default="")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    start_kg: Mapped[float]
    sensor_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    produced_kg: Mapped[float | None] = mapped_column(default=None)
    started_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)


class CompostReading(Base):
    __tablename__ = "compost_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("compost_batches.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    temp_c: Mapped[float]
    moisture_pct: Mapped[float]
    read_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class CompostActivity(Base):
    __tablename__ = "compost_activities"
    __table_args__ = (CheckConstraint("type IN ('turning', 'watering', 'inspection')", name="ck_compost_activity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("compost_batches.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(12))
    note: Mapped[str] = mapped_column(String(200), default="")
    by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    at: Mapped[datetime] = mapped_column(server_default=func.now())
