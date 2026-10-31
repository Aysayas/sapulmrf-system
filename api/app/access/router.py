from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.access import service
from app.access.schemas import AccessOverview, AccessUpdate, StaffAccessOut
from app.core.db import get_db
from app.core.deps import require_role
from app.users.models import User

router = APIRouter(prefix="/access", tags=["access"])
admin_only = require_role("admin")
staff_only = require_role("staff")


@router.get("", response_model=AccessOverview)
def overview(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.overview(db)


@router.get("/me", response_model=StaffAccessOut)
def my_access(db: DbSession = Depends(get_db), user: User = Depends(staff_only)):
    """For hiding tabs only; each route still checks its own grant."""
    return service.mine(db, user)


@router.put("/{user_id}", response_model=StaffAccessOut)
def update(user_id: int, body: AccessUpdate, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.update(db, user_id, body.grants, actor)
