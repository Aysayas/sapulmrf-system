from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.alerts.models import Alert, ProblemReport
from app.alerts.schemas import AlertOut, AlertSummary, BellItem, ProblemIn, ProblemOut, ResolveIn
from app.core.errors import AppError
from app.devices.models import Device
from app.users.models import User

RESOLVED_SHOWN = timedelta(days=30)


def _name(db: DbSession, user_id: int | None) -> str | None:
    return db.get(User, user_id).name if user_id else None


def alert_out(db: DbSession, a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id,
        kind=a.kind,
        title=a.title,
        details=a.details,
        opened_at=a.opened_at,
        resolved_at=a.resolved_at,
        acknowledged_by=_name(db, a.acknowledged_by),
        acknowledged_at=a.acknowledged_at,
    )


def list_alerts(db: DbSession, state: str) -> list[AlertOut]:
    q = select(Alert)
    if state == "resolved":
        q = q.where(Alert.resolved_at >= datetime.now(UTC) - RESOLVED_SHOWN).order_by(Alert.resolved_at.desc(), Alert.id.desc())
    else:
        seen = Alert.acknowledged_at.is_not(None) if state == "acknowledged" else Alert.acknowledged_at.is_(None)
        q = q.where(Alert.resolved_at.is_(None), seen).order_by(Alert.opened_at.desc(), Alert.id.desc())
    return [alert_out(db, a) for a in db.scalars(q.limit(200))]


def acknowledge(db: DbSession, alert_id: int, actor: User) -> Alert:
    a = db.get(Alert, alert_id)
    if not a:
        raise AppError(404, "Alert not found.")
    if a.resolved_at:
        raise AppError(409, "This alert has already cleared.")
    if a.acknowledged_at:
        raise AppError(409, f"{_name(db, a.acknowledged_by) or 'Someone'} already acknowledged this alert.")
    a.acknowledged_by, a.acknowledged_at = actor.id, datetime.now(UTC)
    log(db, actor.id, "Acknowledged alert", f"{a.title} · {a.details}")
    db.commit()
    return a


def summary(db: DbSession, with_reports: bool) -> AlertSummary:
    open_rows = db.scalars(
        select(Alert).where(Alert.resolved_at.is_(None)).order_by(Alert.opened_at.desc(), Alert.id.desc())
    ).all()
    reports = (
        db.scalars(
            select(ProblemReport)
            .where(ProblemReport.status == "open")
            .order_by(ProblemReport.reported_at.desc(), ProblemReport.id.desc())
        ).all()
        if with_reports
        else []
    )
    by_kind: dict[str, int] = {}
    for a in open_rows:
        by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
    items = [BellItem(type="alert", id=a.id, title=a.title, details=a.details, at=a.opened_at) for a in open_rows]
    items += [
        BellItem(type="report", id=r.id, title=f"Problem report {r.code}", details=r.details, at=r.reported_at) for r in reports
    ]
    return AlertSummary(
        open_alerts=len(open_rows),
        by_kind=by_kind,
        unacknowledged=sum(1 for a in open_rows if not a.acknowledged_at),
        open_reports=len(reports),
        latest=sorted(items, key=lambda i: i.at, reverse=True)[:5],
    )


def open_alert_subjects(db: DbSession, kind: str) -> set[int]:
    return set(db.scalars(select(Alert.subject_id).where(Alert.kind == kind, Alert.resolved_at.is_(None))))


# ---- problem reports ----


def problem_out(db: DbSession, r: ProblemReport) -> ProblemOut:
    device = db.get(Device, r.device_id) if r.device_id else None
    return ProblemOut(
        id=r.id,
        code=r.code,
        kind=r.kind,
        device=device.code if device else None,
        record_ref=r.record_ref,
        details=r.details,
        reported_by=_name(db, r.reported_by),
        reported_at=r.reported_at,
        status=r.status,
        resolved_by=_name(db, r.resolved_by),
        resolved_at=r.resolved_at,
        note=r.note,
    )


def report_problem(db: DbSession, data: ProblemIn, actor: User) -> ProblemReport:
    if data.kind == "device" and not db.get(Device, data.device_id):
        raise AppError(422, "Pick a registered device.")
    r = ProblemReport(
        kind=data.kind,
        device_id=data.device_id if data.kind == "device" else None,
        record_ref=data.record_ref.upper(),
        details=data.details,
        reported_by=actor.id,
    )
    db.add(r)
    db.flush()
    r.code = f"R-{r.id:03d}"
    what = db.get(Device, r.device_id).code if r.device_id else r.record_ref
    log(db, actor.id, "Reported a problem", f"{r.code} · {what} · {r.details}")
    db.commit()
    return r


def list_problems(db: DbSession, status: str) -> list[ProblemOut]:
    q = select(ProblemReport).where(ProblemReport.status == status)
    q = q.order_by(
        ProblemReport.reported_at.desc() if status == "open" else ProblemReport.resolved_at.desc(), ProblemReport.id.desc()
    )
    return [problem_out(db, r) for r in db.scalars(q.limit(200))]


def resolve_problem(db: DbSession, report_id: int, data: ResolveIn, actor: User) -> ProblemReport:
    r = db.get(ProblemReport, report_id)
    if not r:
        raise AppError(404, "Problem report not found.")
    if r.status == "resolved":
        raise AppError(409, f"{r.code} is already resolved.")
    r.status, r.resolved_by, r.resolved_at, r.note = "resolved", actor.id, datetime.now(UTC), data.note
    log(db, actor.id, "Resolved problem report", f"{r.code} · {r.note}")
    db.commit()
    return r
