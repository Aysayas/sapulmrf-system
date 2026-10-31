from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.activity import service
from app.activity.schemas import ActivityOut
from app.core.db import get_db
from app.core.deps import current_user, require_role
from app.users.models import User

router = APIRouter(prefix="/activity", tags=["activity"])
admin_only = require_role("admin")

Category = Literal["logins", "users", "approvals", "reports", "records"]


@router.get("", response_model=list[ActivityOut])
def list_activity(
    user_id: int | None = None,
    days: int | None = Query(None, ge=1, le=366),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    category: Category | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: DbSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    return service.list_activity(db, user_id, days, limit, from_day=from_, to_day=to, category=category)


@router.get("/mine", response_model=list[ActivityOut])
def my_activity(days: int | None = Query(None, ge=1, le=366), limit: int = Query(100, ge=1, le=500),
                db: DbSession = Depends(get_db), user: User = Depends(current_user)):
    return service.list_activity(db, user.id, days, limit, skip_logins=True)


@router.get("/export")
def export(
    user_id: int | None = None,
    days: int | None = Query(None, ge=1, le=366),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    category: Category | None = None,
    db: DbSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    items = service.list_activity(db, user_id, days, 10000, from_day=from_, to_day=to, category=category)
    return Response(service.to_csv(items), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="activity-log.csv"'})
