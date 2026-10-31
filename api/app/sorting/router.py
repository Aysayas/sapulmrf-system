from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.intake import service as intake
from app.intake.schemas import DeliveryOut
from app.sorting import service
from app.sorting.schemas import ClassificationOut, ConfirmIn, SortIn, TransferIn, TransferOut
from app.users.models import User

router = APIRouter(tags=["sorting (operator)"])
operator_only = require_role("operator")


@router.get("/classifications/pending", response_model=list[ClassificationOut])
def pending(limit: int = Query(50, ge=1, le=200), db: DbSession = Depends(get_db), _: User = Depends(operator_only)):
    return service.pending(db, limit)


@router.post("/inventory/transfers", response_model=TransferOut, status_code=201)
def transfer(body: TransferIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.transfer(db, body, actor)


@router.post("/classifications/{classification_id}/confirm", response_model=ClassificationOut)
def confirm(classification_id: int, body: ConfirmIn, db: DbSession = Depends(get_db),
            actor: User = Depends(operator_only)):
    return service.out(db, service.confirm(db, classification_id, body, actor))


@router.post("/sorting", response_model=DeliveryOut, status_code=201)
def sort_delivery(body: SortIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return intake.out(db, service.sort_delivery(db, body, actor))
