from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NamedItem:
    """Shared columns. Items are deactivated, never deleted, because later records point at them."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WasteCategory(NamedItem, Base):
    __tablename__ = "waste_categories"


class SourceArea(NamedItem, Base):
    """A purok (or other area) that deliveries come from."""

    __tablename__ = "source_areas"


class Material(NamedItem, Base):
    """A recyclable material the camera classifies and storage tracks."""

    __tablename__ = "materials"


class Buyer(NamedItem, Base):
    """A regular buyer or recipient (junkshop, purok gardens, the ENRO truck). The kiosk shows them as buttons."""

    __tablename__ = "buyers"


class StorageArea(NamedItem, Base):
    __tablename__ = "storage_areas"

    capacity_kg: Mapped[int]
    alert_pct: Mapped[int] = mapped_column(default=90)
