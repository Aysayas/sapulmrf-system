from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

ALL = 0  # forecasts.category_id for all waste together


class Flag(Base):
    """A record that looks unusual. Never changes the record; the admin marks it valid or incorrect."""

    __tablename__ = "flags"
    __table_args__ = (
        CheckConstraint("kind IN ('weight', 'gap')", name="ck_flags_kind"),
        CheckConstraint("status IN ('open', 'valid', 'incorrect')", name="ck_flags_status"),
        UniqueConstraint("delivery_id", "kind", name="uq_flags_delivery_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    value_kg: Mapped[float]  # the weight received
    expected_low: Mapped[float]  # weight: the purok's usual range; gap: separated + sorted (low = high)
    expected_high: Mapped[float]
    found_at: Mapped[datetime] = mapped_column(server_default=func.now())
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)


class Forecast(Base):
    """One model's prediction, made on made_on (using data up to the day before) for for_day."""

    __tablename__ = "forecasts"
    __table_args__ = (
        CheckConstraint("model IN ('baseline', 'ml')", name="ck_forecasts_model"),
        UniqueConstraint("made_on", "for_day", "category_id", "model", name="uq_forecasts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    made_on: Mapped[date] = mapped_column(index=True)
    for_day: Mapped[date] = mapped_column(index=True)
    category_id: Mapped[int] = mapped_column(default=ALL)  # 0 = all waste; not a foreign key so 0 can mean "all"
    model: Mapped[str] = mapped_column(String(8))
    kg: Mapped[float]
