from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.approvals import service
from app.approvals.schemas import AdjustmentIn, AdjustmentOut, ApprovalsOut, DecisionIn, OutgoingIn, OutgoingOut
from app.core.db import get_db
from app.core.deps import require_role
from app.users.models import User

router = APIRouter(tags=["approvals"])
operator_only = require_role("operator")
admin_only = require_role("admin")


@router.post("/inventory/adjustments", response_model=AdjustmentOut, status_code=201)
def request_adjustment(body: AdjustmentIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.adjustment_out(db, service.request_adjustment(db, body, actor))


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
