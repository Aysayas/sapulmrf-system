from sqlalchemy.orm import Session

from app.activity.models import ActivityLog


def log(db: Session, user_id: int | None, action: str, record: str = "") -> None:
    """Adds an activity row to the caller's transaction; the caller commits."""
    db.add(ActivityLog(user_id=user_id, action=action, record=record[:255]))
