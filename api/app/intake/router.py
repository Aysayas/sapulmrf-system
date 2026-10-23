from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.intake import service
from app.intake.schemas import DeliveryIn, DeliveryOut, SegregationIn
from app.users.models import User

router = APIRouter(prefix="/deliveries", tags=["intake (operator)"])
operator_only = require_role("operator")


@router.post("", response_model=DeliveryOut, status_code=201)
def record_delivery(body: DeliveryIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.out(db, service.record_delivery(db, body, actor))


@router.post("/{delivery_id}/segregation", response_model=DeliveryOut, status_code=201)
def record_segregation(delivery_id: int, body: SegregationIn, db: DbSession = Depends(get_db),
                       actor: User = Depends(operator_only)):
    return service.out(db, service.record_segregation(db, delivery_id, body, actor))
