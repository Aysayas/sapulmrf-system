from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import current_user, require_role
from app.settings import service
from app.settings.schemas import SettingsIn, SettingsOut
from app.users.models import User

router = APIRouter(prefix="/settings", tags=["ranges and limits"])
admin_only = require_role("admin")


@router.get("", response_model=SettingsOut)
def get_settings(db: DbSession = Depends(get_db), _: User = Depends(current_user)):
    """Any logged-in user may read the ranges (the compost screens show them); only admins change them."""
    return service.get(db)


@router.put("", response_model=SettingsOut)
def save_settings(body: SettingsIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.save(db, body, actor)
