from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.core.errors import AppError
from app.intake import service
from app.intake.models import DeliveryPhoto
from app.intake.schemas import DeliveryIn, DeliveryOut, SegregationIn
from app.users.models import User

router = APIRouter(prefix="/deliveries", tags=["intake (operator)"])
operator_only = require_role("operator")
staff_view = require_role("admin", "operator")


@router.post("", response_model=DeliveryOut, status_code=201)
def record_delivery(body: DeliveryIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.out(db, service.record_delivery(db, body, actor))


@router.delete("/{delivery_id}/segregation", response_model=DeliveryOut)
def undo_segregation(delivery_id: int, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.out(db, service.undo_segregation(db, delivery_id, actor))


@router.post("/{delivery_id}/segregation", response_model=DeliveryOut, status_code=201)
def record_segregation(delivery_id: int, body: SegregationIn, db: DbSession = Depends(get_db),
                       actor: User = Depends(operator_only)):
    return service.out(db, service.record_segregation(db, delivery_id, body, actor))


@router.get("/{delivery_id}/photo")
def photo(delivery_id: int, db: DbSession = Depends(get_db), _: User = Depends(staff_view)):
    """The kiosk camera's snapshot of a drop-off."""
    p = db.get(DeliveryPhoto, delivery_id)
    if not p:
        raise AppError(404, "No photo for this delivery.")
    return Response(p.jpeg, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
