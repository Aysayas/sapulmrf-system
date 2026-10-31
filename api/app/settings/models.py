from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Settings(Base):
    """The one row of ranges and limits (id is always 1). Created with the defaults on first read."""

    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    compost_temp_min: Mapped[float] = mapped_column(default=45.0)
    compost_temp_max: Mapped[float] = mapped_column(default=65.0)
    moisture_min: Mapped[float] = mapped_column(default=40.0)
    moisture_max: Mapped[float] = mapped_column(default=60.0)
    prediction_min_days: Mapped[int] = mapped_column(default=30)
    anomaly_pct: Mapped[float] = mapped_column(default=2.0)
