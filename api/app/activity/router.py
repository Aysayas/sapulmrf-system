from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.activity import service
from app.activity.schemas import ActivityOut
from app.core.db import get_db
from app.core.deps import require_role
from app.users.models import User

router = APIRouter(prefix="/activity", tags=["activity"])
admin_only = require_role("admin")


@router.get("", response_model=list[ActivityOut])
def list_activity(
    user_id: int | None = None,
    days: int | None = Query(None, ge=1, le=366),
    limit: int = Query(100, ge=1, le=500),
    db: DbSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    return service.list_activity(db, user_id, days, limit)
