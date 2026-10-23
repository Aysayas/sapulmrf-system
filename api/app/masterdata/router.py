from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import current_user, require_role
from app.masterdata import service
from app.masterdata.schemas import ItemCreate, ItemOut, ItemUpdate, Kind
from app.users.models import User

router = APIRouter(prefix="/masterdata", tags=["master data"])
admin_only = require_role("admin")


@router.get("/{kind}", response_model=list[ItemOut])
def list_items(kind: Kind, active: bool = False, db: DbSession = Depends(get_db), _: User = Depends(current_user)):
    """Any logged-in user may read the lists (the operator's forms need them); only admins change them."""
    return service.list_items(db, kind, active)


@router.post("/{kind}", response_model=ItemOut, status_code=201)
def create_item(kind: Kind, body: ItemCreate, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.create_item(db, kind, body, actor)


@router.patch("/{kind}/{item_id}", response_model=ItemOut)
def update_item(kind: Kind, item_id: int, body: ItemUpdate, db: DbSession = Depends(get_db),
                actor: User = Depends(admin_only)):
    return service.update_item(db, kind, item_id, body, actor)
