from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.compost import service
from app.compost.schemas import ActivityIn, BatchIn, BatchOut
from app.core.db import get_db
from app.core.deps import require_role
from app.users.models import User

router = APIRouter(prefix="/compost/batches", tags=["compost (operator)"])
operator_only = require_role("operator")


@router.post("", response_model=BatchOut, status_code=201)
def start_batch(body: BatchIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.out(db, service.start_batch(db, body, actor))


@router.post("/{batch_id}/activities", response_model=BatchOut, status_code=201)
def log_activity(batch_id: int, body: ActivityIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.out(db, service.log_activity(db, batch_id, body, actor))
