from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


def preload(db: Session, *models) -> list:
    """Loads small lookup tables once. db.get() answers from memory only while something holds the rows, so keep the result."""  # noqa: E501
    return [row for model in models for row in db.scalars(select(model))]


def advisory_lock(db: Session, name: str) -> None:
    """Holds other transactions using this name until commit, for work with no single row to lock."""
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(name))))


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
