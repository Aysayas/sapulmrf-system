from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.corrections import service
from app.corrections.schemas import CorrectionOut, Fixable, FixReviewIn, UndoIn
from app.users.models import User

router = APIRouter(prefix="/corrections", tags=["corrections"])
fixes = require_role("operator", "admin")  # operators: today's records only (the service checks)
admin_only = require_role("admin")


@router.post("/undo", response_model=CorrectionOut, status_code=201)
def undo(body: UndoIn, db: DbSession = Depends(get_db), actor: User = Depends(fixes)):
    return service.out(db, service.undo(db, body, actor))


@router.get("/fixable", response_model=list[Fixable])
def fixable(db: DbSession = Depends(get_db), _: User = Depends(fixes)):
    return service.fixable(db)


@router.post("/{correction_id}/review", response_model=CorrectionOut)
def review(correction_id: int, body: FixReviewIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.out(db, service.mark(db, correction_id, body.review, actor))
