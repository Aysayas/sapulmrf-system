from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.auth import service as auth
from app.core.db import get_db
from app.core.deps import require_role
from app.core.errors import AppError
from app.users import service
from app.users.models import User
from app.users.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
admin_only = require_role("admin")


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.list_users(db)


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.create_user(db, body, actor)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.update_user(db, user_id, body, actor)


@router.delete("/{user_id}/kiosk-pin", status_code=204)
def clear_kiosk_pin(user_id: int, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    """For a forgotten PIN. The admin never sees it; the operator sets a new one."""
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "User not found.")
    auth.clear_kiosk_pin(db, user, actor)
