from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Classification(Base):
    """A camera suggestion, and the operator's decision once confirmed (pending while confirmed_at is null)."""

    __tablename__ = "classifications"
    __table_args__ = (CheckConstraint("review IN ('ok', 'wrong')", name="ck_classifications_review"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    suggested_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    image_url: Mapped[str] = mapped_column(String(500), default="")
    suggested_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    confidence: Mapped[float]
    model_version: Mapped[str] = mapped_column(String(40), default="")
    final_material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), default=None)
    not_recyclable: Mapped[bool] = mapped_column(default=False)
    changed: Mapped[bool | None] = mapped_column(default=None)
    reason: Mapped[str] = mapped_column(String(200), default="")
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    # The admin's review of an operator's change: ok (the change was right) or wrong. A mark only.
    review: Mapped[str | None] = mapped_column(String(8), default=None)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)


class StockMovement(Base):
    """The stock ledger: current stock in an area is the sum of its rows. material_id null means residual."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("kind IN ('sorted', 'transfer', 'adjustment', 'outgoing')", name="ck_stock_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    storage_area_id: Mapped[int] = mapped_column(ForeignKey("storage_areas.id"), index=True)
    kg: Mapped[float]
    bags: Mapped[int] = mapped_column(default=0)
    kind: Mapped[str] = mapped_column(String(12))
    delivery_id: Mapped[int | None] = mapped_column(ForeignKey("deliveries.id", ondelete="SET NULL"), default=None)
    by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    note: Mapped[str] = mapped_column(String(200), default="")
    client_key: Mapped[str | None] = mapped_column(String(36), unique=True, default=None)  # on a transfer's source row
