from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.core.errors import AppError
from app.operations.router import granted, viewer
from app.reports import service
from app.reports.schemas import Format, Kind, Narrative, RecentExport, Report
from app.users.models import User

router = APIRouter(prefix="/reports", tags=["reports"])
admin_only = require_role("admin")
reports_grant = viewer("reports")


def exports_viewer(user: User = Depends(reports_grant)) -> User:
    """Admins, and staff with the reports grant. viewer() also passes operators, who have no reports."""
    if user.role == "operator":
        raise AppError(403, "Your role can't do this.")
    return user


def hidden_kinds(db: DbSession, user: User) -> tuple[str, ...]:
    """What a viewer of exports can't open: income is never for staff, segregation needs its own grant."""
    if user.role != "staff":
        return ()
    return ("income",) if granted(db, user, "segregation") else ("income", "segregation")


def _file(body: bytes, media: str, name: str) -> Response:
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/recent", response_model=list[RecentExport])
def recent(db: DbSession = Depends(get_db), user: User = Depends(exports_viewer)):
    return service.recent(db, hidden_kinds(db, user))


@router.get("/exports/{export_id}", response_model=Report)
def view_export(export_id: int, db: DbSession = Depends(get_db), actor: User = Depends(exports_viewer)):
    return service.view_export(db, export_id, actor, hidden_kinds(db, actor))


@router.get("/exports/{export_id}/download")
def download_export(export_id: int, db: DbSession = Depends(get_db), actor: User = Depends(exports_viewer)):
    return _file(*service.download_export(db, export_id, actor, hidden_kinds(db, actor)))


@router.get("/exports/{export_id}/narrative", response_model=Narrative)
def export_narrative(export_id: int, db: DbSession = Depends(get_db), actor: User = Depends(exports_viewer)):
    return service.export_narrative(db, export_id, hidden_kinds(db, actor))


@router.get("/{kind}/narrative", response_model=Narrative)
def narrative(kind: Kind, from_: date = Query(alias="from"), to: date = Query(), area: int | None = None,
              db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.narrative(db, kind, from_, to, area)


@router.get("/{kind}", response_model=Report)
def preview(kind: Kind, from_: date = Query(alias="from"), to: date = Query(), area: int | None = None,
            db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.preview(db, kind, from_, to, area, actor)


@router.get("/{kind}/export")
def export(kind: Kind, format: Format, from_: date = Query(alias="from"), to: date = Query(), area: int | None = None,
           db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return _file(*service.export(db, kind, from_, to, area, format, actor))
