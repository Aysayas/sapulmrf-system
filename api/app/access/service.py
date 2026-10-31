from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.access.models import SCREENS, StaffAccess
from app.access.schemas import LABELS, AccessOverview, StaffAccessOut
from app.activity.service import log
from app.core.errors import AppError
from app.users.models import User


def _grants(db: DbSession, user_id: int) -> dict[str, bool]:
    rows = {r.screen: r.granted for r in db.scalars(select(StaffAccess).where(StaffAccess.user_id == user_id))}
    return {s: rows.get(s, False) for s in SCREENS}  # least privilege: off until granted


def _out(db: DbSession, u: User) -> StaffAccessOut:
    return StaffAccessOut(user_id=u.id, name=u.name, username=u.username, active=u.active, grants=_grants(db, u.id))


def mine(db: DbSession, user: User) -> StaffAccessOut:
    return _out(db, user)


def overview(db: DbSession) -> AccessOverview:
    staff = db.scalars(select(User).where(User.role == "staff").order_by(User.name))
    return AccessOverview(screens=[{"key": s, "label": LABELS[s]} for s in SCREENS], staff=[_out(db, u) for u in staff])


def update(db: DbSession, user_id: int, grants: dict[str, bool], actor: User) -> StaffAccessOut:
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "User not found.")
    if user.role != "staff":
        raise AppError(400, "Only Authorized Barangay Staff have per-person screens.")
    for screen, granted in grants.items():
        row = db.get(StaffAccess, (user.id, screen))
        if row:
            row.granted = granted
        else:
            db.add(StaffAccess(user_id=user.id, screen=screen, granted=granted))
    summary = ", ".join(f"{s} {'on' if g else 'off'}" for s, g in grants.items())
    log(db, actor.id, "Changed staff access", f"{user.name} · {summary}")
    db.commit()
    return _out(db, user)
