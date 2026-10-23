from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ReportExport(Base):
    """History of exports. The file is not kept: Download rebuilds it from the current data."""

    __tablename__ = "report_exports"
    __table_args__ = (CheckConstraint("format IN ('csv', 'pdf')", name="ck_report_exports_format"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))
    from_day: Mapped[date]
    to_day: Mapped[date]
    area_id: Mapped[int | None] = mapped_column(ForeignKey("source_areas.id", ondelete="SET NULL"), default=None)
    format: Mapped[str] = mapped_column(String(3))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
