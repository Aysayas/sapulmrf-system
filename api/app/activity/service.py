import codecs
import csv
import io
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.activity.models import ActivityLog
from app.activity.schemas import ActivityOut
from app.core.config import settings
from app.users.models import User

TZ = ZoneInfo(settings.timezone)


def log(db: Session, user_id: int | None, action: str, record: str = "") -> None:
    """Adds an activity row to the caller's transaction; the caller commits."""
    db.add(ActivityLog(user_id=user_id, action=action, record=record[:255]))


# Filter groups, matched on the action text (several actions are built from a verb, so a pattern, not a list).
CATEGORIES = {
    "logins": ["Logged in", "Logged out", "Account locked"],
    "users": ["Created first administrator", "% user", "Reset password", "Changed own password", "Updated own profile",
              "Changed staff access"],
    "approvals": ["Approved %", "Rejected %", "Reviewed %", "Marked flagged record %"],
    "reports": ["Viewed % report", "Exported % report as %", "Downloaded % report as %"],
}


def list_activity(db: Session, user_id: int | None = None, days: int | None = None, limit: int = 100, *,
                  from_day: date | None = None, to_day: date | None = None, category: str | None = None,
                  skip_logins: bool = False) -> list[ActivityOut]:
    q = select(ActivityLog, User.name).outerjoin(User, User.id == ActivityLog.user_id)
    if user_id is not None:
        q = q.where(ActivityLog.user_id == user_id)
    if days is not None:
        q = q.where(ActivityLog.at >= datetime.now(UTC) - timedelta(days=days))
    if from_day:
        q = q.where(ActivityLog.at >= datetime(from_day.year, from_day.month, from_day.day, tzinfo=TZ))
    if to_day:
        q = q.where(ActivityLog.at < datetime.combine(to_day + timedelta(days=1), time.min, tzinfo=TZ))
    if skip_logins:
        q = q.where(~or_(*(ActivityLog.action.like(p) for p in CATEGORIES["logins"])))
    if category:
        named = or_(*(ActivityLog.action.like(p) for ps in CATEGORIES.values() for p in ps))
        match = or_(*(ActivityLog.action.like(p) for p in CATEGORIES[category])) if category in CATEGORIES else ~named
        q = q.where(match)
    rows = db.execute(q.order_by(ActivityLog.at.desc(), ActivityLog.id.desc()).limit(limit))
    return [ActivityOut(id=a.id, at=a.at, user_id=a.user_id, who=name or "System", action=a.action, record=a.record)
            for a, name in rows]


def to_csv(items: list[ActivityOut]) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["When", "Who", "Action", "Record"])
    w.writerows([i.at.astimezone(TZ).strftime("%Y-%m-%d %H:%M"), i.who, i.action, i.record] for i in items)
    return codecs.BOM_UTF8 + out.getvalue().encode()
