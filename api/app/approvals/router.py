from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.approvals import service
from app.approvals.schemas import AdjustmentIn, AdjustmentOut, ApprovalsOut, DecisionIn, OutgoingIn, OutgoingOut, ReviewIn
from app.core.db import get_db
from app.core.deps import require_role
from app.intake import service as intake
from app.intake.schemas import DeliveryOut
from app.sorting import service as sorting
from app.sorting.schemas import ClassificationOut
from app.users.models import User

router = APIRouter(tags=["approvals"])
operator_only = require_role("operator")
admin_only = require_role("admin")


@router.post("/inventory/adjustments", response_model=AdjustmentOut, status_code=201)
def request_adjustment(body: AdjustmentIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.adjustment_out(db, service.request_adjustment(db, body, actor))


@router.get("/inventory/adjustments/mine", response_model=list[AdjustmentOut])
def my_adjustments(days: int = Query(30, ge=1, le=366), db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.my_adjustments(db, actor, days)


@router.post("/outgoing", response_model=OutgoingOut, status_code=201)
def request_outgoing(body: OutgoingIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.outgoing_out(db, service.request_outgoing(db, body, actor))


@router.get("/approvals", response_model=ApprovalsOut)
def approvals(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.pending(db)


@router.post("/approvals/adjustments/{request_id}", response_model=AdjustmentOut)
def decide_adjustment(request_id: int, body: DecisionIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.adjustment_out(db, service.decide_adjustment(db, request_id, body, actor))


@router.post("/approvals/outgoing/{outgoing_id}", response_model=OutgoingOut)
def decide_outgoing(outgoing_id: int, body: DecisionIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.outgoing_out(db, service.decide_outgoing(db, outgoing_id, body, actor))


@router.get("/reviews/weights", response_model=list[DeliveryOut])
def weights_to_review(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.weights_to_review(db)


@router.get("/reviews/classifications", response_model=list[ClassificationOut])
def changes_to_review(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.changes_to_review(db)


@router.post("/reviews/weights/{delivery_id}", response_model=DeliveryOut)
def review_weight(delivery_id: int, body: ReviewIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return intake.out(db, service.review_weight(db, delivery_id, body, actor))


@router.post("/reviews/classifications/{classification_id}", response_model=ClassificationOut)
def review_change(classification_id: int, body: ReviewIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return sorting.out(db, service.review_change(db, classification_id, body, actor))
