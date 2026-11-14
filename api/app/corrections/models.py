from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Correction(Base):
    """A record an operator (today's only) or the admin (any day) undid with a reason. The undone rows are gone;
    `summary` keeps what they said. The admin marks it ok or wrong afterwards."""

    __tablename__ = "corrections"
    __table_args__ = (
        CheckConstraint("kind IN ('sort', 'segregation', 'delivery')", name="ck_corrections_kind"),
        CheckConstraint("review IN ('ok', 'wrong')", name="ck_corrections_review"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))  # the deepest step undone
    record_code: Mapped[str] = mapped_column(String(12), index=True)
    summary: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(String(120))
    by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    redone_as: Mapped[str | None] = mapped_column(String(12), default=None)  # the drop-off recorded again in its place
    review: Mapped[str | None] = mapped_column(String(8), default=None)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
