from datetime import datetime

from sqlalchemy import CheckConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

TYPES = ("weighing_station", "compost_sensor", "sorting_camera")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("type IN ('weighing_station', 'compost_sensor', 'sorting_camera')", name="ck_devices_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    type: Mapped[str] = mapped_column(String(20))
    location: Mapped[str] = mapped_column(String(80), default="")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
