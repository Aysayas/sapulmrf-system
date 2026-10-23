from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.activity.models import ActivityLog
from app.activity.schemas import ActivityOut
from app.users.models import User


def log(db: Session, user_id: int | None, action: str, record: str = "") -> None:
    """Adds an activity row to the caller's transaction; the caller commits."""
    db.add(ActivityLog(user_id=user_id, action=action, record=record[:255]))


def list_activity(db: Session, user_id: int | None, days: int | None, limit: int) -> list[ActivityOut]:
    q = select(ActivityLog, User.name).outerjoin(User, User.id == ActivityLog.user_id)
    if user_id is not None:
        q = q.where(ActivityLog.user_id == user_id)
    if days is not None:
        q = q.where(ActivityLog.at >= datetime.now(UTC) - timedelta(days=days))
    rows = db.execute(q.order_by(ActivityLog.at.desc(), ActivityLog.id.desc()).limit(limit))
    return [ActivityOut(id=a.id, at=a.at, user_id=a.user_id, who=name or "System", action=a.action, record=a.record)
            for a, name in rows]
