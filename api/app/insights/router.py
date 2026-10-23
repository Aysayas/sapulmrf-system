from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.insights import service
from app.insights.models import ALL
from app.insights.schemas import FlagDecision, FlagOut, Predictions
from app.operations.router import viewer
from app.users.models import User

router = APIRouter(prefix="/insights", tags=["insights"])
predictions_viewer = viewer("predictions")  # admins and operators; staff with the predictions grant
admin_only = require_role("admin")


@router.get("/predictions", response_model=Predictions)
def predictions(category: int = ALL, db: DbSession = Depends(get_db), _: User = Depends(predictions_viewer)):
    return service.predictions(db, category)


@router.get("/flags", response_model=list[FlagOut])
def flags(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.open_flags(db)


@router.post("/flags/{flag_id}", response_model=FlagOut)
def decide(flag_id: int, body: FlagDecision, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.flag_out(db, service.decide_flag(db, flag_id, body.decision, actor))
