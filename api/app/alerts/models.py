from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Alert(Base):
    """A condition the worker found. Open while resolved_at is null; acknowledging only records who saw it."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("kind IN ('compost', 'device', 'storage')", name="ck_alerts_kind"),
        # one open alert per subject, even if two workers run at once
        Index("uq_alerts_open", "kind", "subject_id", unique=True, postgresql_where=text("resolved_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[int]  # the compost batch, device or storage area
    title: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(String(200), default="")
    opened_at: Mapped[datetime] = mapped_column(index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    acknowledged_at: Mapped[datetime | None] = mapped_column(default=None)


class ProblemReport(Base):
    """An operator's report of a device problem or an incorrect record, for the admin to resolve."""

    __tablename__ = "problem_reports"
    __table_args__ = (
        CheckConstraint("kind IN ('device', 'record')", name="ck_problem_kind"),
        CheckConstraint("status IN ('open', 'resolved')", name="ck_problem_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, default="")
    kind: Mapped[str] = mapped_column(String(8))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), default=None)
    record_ref: Mapped[str] = mapped_column(String(40), default="")
    details: Mapped[str] = mapped_column(String(300))
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reported_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
    note: Mapped[str] = mapped_column(String(200), default="")
