from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.core.errors import AppError
from app.masterdata.models import SourceArea
from app.operations.service import TZ
from app.reports import findings, render
from app.reports.builders import BUILDERS, BY_AREA, TITLES
from app.reports.models import ReportExport
from app.reports.schemas import Format, Kind, RecentExport, Report
from app.users.models import User

PREVIEW_ROWS = 500
MAX_DAYS = 366
COMPARED = ("intake", "segregation", "outgoing", "income")  # composting batches span periods, inventory has none


def _area_name(db: DbSession, area: int | None) -> str:
    if not area:
        return "All puroks"
    a = db.get(SourceArea, area)
    if not a:
        raise AppError(404, "No such source area.")
    return a.name


def _window(from_day: date, to_day: date) -> tuple[datetime, datetime]:
    start = datetime(from_day.year, from_day.month, from_day.day, tzinfo=TZ)
    return start, datetime.combine(to_day + timedelta(days=1), datetime.min.time(), tzinfo=TZ)


def build(db: DbSession, kind: Kind, from_day: date, to_day: date, area: int | None) -> Report:
    if to_day < from_day:
        raise AppError(422, "The end date is before the start date.")
    if (to_day - from_day).days >= MAX_DAYS:
        raise AppError(422, f"Pick a range of at most {MAX_DAYS} days.")
    area = area if kind in BY_AREA else None
    start, end = _window(from_day, to_day)
    r = BUILDERS[kind](db, start, end, area)
    where = f" · {_area_name(db, area)}" if kind in BY_AREA else ""
    r.subtitle = "Stock as of now" if kind == "inventory" else f"{from_day:%b %d, %Y} to {to_day:%b %d, %Y}{where}"
    r.total_rows = len(r.rows)
    prev = None
    if kind in COMPARED:  # the same number of days just before this range
        days = (to_day - from_day).days + 1
        prev = BUILDERS[kind](db, *_window(from_day - timedelta(days=days), from_day - timedelta(days=1)), area)
    r.findings = findings.find(db, r, prev, from_day, to_day, start, end, area)
    return r


def preview(db: DbSession, kind: Kind, from_day: date, to_day: date, area: int | None, actor: User) -> Report:
    r = build(db, kind, from_day, to_day, area)
    log(db, actor.id, f"Viewed {kind} report", r.subtitle)
    db.commit()
    return r.model_copy(update={"rows": r.rows[:PREVIEW_ROWS]})


def export(db: DbSession, kind: Kind, from_day: date, to_day: date, area: int | None, fmt: Format,
           actor: User) -> tuple[bytes, str, str]:
    """Returns (file bytes, media type, filename) and records the export."""
    r = build(db, kind, from_day, to_day, area)
    file = _render(r, from_day, to_day, fmt, actor)
    db.add(ReportExport(kind=kind, from_day=from_day, to_day=to_day, area_id=area or None, format=fmt, user_id=actor.id))
    log(db, actor.id, f"Exported {kind} report as {fmt.upper()}", r.subtitle)
    db.commit()
    return file


def _render(r: Report, from_day: date, to_day: date, fmt: Format, actor: User) -> tuple[bytes, str, str]:
    body = render.to_csv(r) if fmt == "csv" else render.to_pdf(r, actor.name, datetime.now(TZ))
    media = "text/csv; charset=utf-8" if fmt == "csv" else "application/pdf"
    return body, media, f"{r.kind}-report_{from_day}_{to_day}.{fmt}"


def _exported(db: DbSession, export_id: int, hidden: tuple[str, ...]) -> tuple[ReportExport, Report]:
    """A report an admin already exported, rebuilt from the current data. No new export row."""
    e = db.get(ReportExport, export_id)
    if not e:
        raise AppError(404, "Report not found.")
    if e.kind in hidden:
        raise AppError(403, "This report isn't shared with you. Ask the Barangay Administrator.")
    return e, build(db, e.kind, e.from_day, e.to_day, e.area_id)


def view_export(db: DbSession, export_id: int, actor: User, hidden: tuple[str, ...] = ()) -> Report:
    e, r = _exported(db, export_id, hidden)
    log(db, actor.id, f"Viewed {e.kind} report", r.subtitle)
    db.commit()
    return r.model_copy(update={"rows": r.rows[:PREVIEW_ROWS]})


def download_export(db: DbSession, export_id: int, actor: User, hidden: tuple[str, ...] = ()) -> tuple[bytes, str, str]:
    e, r = _exported(db, export_id, hidden)
    file = _render(r, e.from_day, e.to_day, e.format, actor)
    log(db, actor.id, f"Downloaded {e.kind} report as {e.format.upper()}", r.subtitle)
    db.commit()
    return file


def recent(db: DbSession, hidden: tuple[str, ...] = (), limit: int = 10) -> list[RecentExport]:
    rows = db.execute(
        select(ReportExport, User.name, SourceArea.name)
        .outerjoin(User, User.id == ReportExport.user_id)
        .outerjoin(SourceArea, SourceArea.id == ReportExport.area_id)
        .where(ReportExport.kind.not_in(hidden))
        .order_by(ReportExport.created_at.desc(), ReportExport.id.desc())
        .limit(limit)
    )
    return [RecentExport(id=e.id, kind=e.kind, title=TITLES[e.kind], from_day=e.from_day, to_day=e.to_day, area_id=e.area_id,
                         area=area or "All puroks", format=e.format, by=by or "Unknown", created_at=e.created_at)
            for e, by, area in rows]
