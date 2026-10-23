from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.alerts import service
from app.alerts.schemas import AlertOut, AlertSummary, ProblemIn, ProblemOut, ResolveIn
from app.core.db import get_db
from app.core.deps import require_role
from app.operations.router import viewer
from app.users.models import User

router = APIRouter(tags=["alerts"])
alerts_viewer = viewer("alerts")  # admins and operators; staff with the alerts grant
can_acknowledge = require_role("admin", "operator")
operator_only = require_role("operator")
admin_only = require_role("admin")


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    state: Literal["open", "acknowledged", "resolved"] = "open", db: DbSession = Depends(get_db), _: User = Depends(alerts_viewer)
):
    return service.list_alerts(db, state)


@router.get("/alerts/summary", response_model=AlertSummary)
def summary(db: DbSession = Depends(get_db), user: User = Depends(alerts_viewer)):
    return service.summary(db, with_reports=user.role == "admin")


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, db: DbSession = Depends(get_db), actor: User = Depends(can_acknowledge)):
    return service.alert_out(db, service.acknowledge(db, alert_id, actor))


@router.post("/problems", response_model=ProblemOut, status_code=201)
def report_problem(body: ProblemIn, db: DbSession = Depends(get_db), actor: User = Depends(operator_only)):
    return service.problem_out(db, service.report_problem(db, body, actor))


@router.get("/problems", response_model=list[ProblemOut])
def list_problems(status: Literal["open", "resolved"] = "open", db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.list_problems(db, status)


@router.post("/problems/{report_id}/resolve", response_model=ProblemOut)
def resolve_problem(report_id: int, body: ResolveIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.problem_out(db, service.resolve_problem(db, report_id, body, actor))
