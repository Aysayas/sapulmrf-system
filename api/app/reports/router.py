from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.core.db import get_db
from app.core.deps import require_role
from app.reports import service
from app.reports.schemas import Format, Kind, RecentExport, Report
from app.users.models import User

router = APIRouter(prefix="/reports", tags=["reports"])
admin_only = require_role("admin")


@router.get("/recent", response_model=list[RecentExport])
def recent(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
    return service.recent(db)


@router.get("/{kind}", response_model=Report)
def preview(kind: Kind, from_: date = Query(alias="from"), to: date = Query(), area: int | None = None,
            db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.preview(db, kind, from_, to, area, actor)


@router.get("/{kind}/export")
def export(kind: Kind, format: Format, from_: date = Query(alias="from"), to: date = Query(), area: int | None = None,
           db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    body, media, name = service.export(db, kind, from_, to, area, format, actor)
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})
