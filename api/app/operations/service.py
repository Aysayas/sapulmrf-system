"""Read-only views over the operations data, for the admin's Operations pages and Overview."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from app.alerts import service as alerts
from app.approvals import service as approvals
from app.approvals.models import Outgoing
from app.compost import service as compost
from app.compost.models import CompostBatch, CompostReading
from app.core.config import settings
from app.core.db import preload
from app.devices import service as devices
from app.devices.models import Device
from app.intake import service as intake
from app.intake.models import Delivery, SegregationCheck
from app.masterdata.models import Material, SourceArea, StorageArea
from app.operations import schemas as s
from app.settings import service as ranges
from app.sorting import service as sorting
from app.sorting.models import Classification, StockMovement
from app.users.models import User

TZ = ZoneInfo(settings.timezone)


def day_start(days_back: int = 0) -> datetime:
    """Midnight, barangay time, `days_back` days ago, as an aware datetime."""
    today = datetime.now(TZ).date() - timedelta(days=days_back)
    return datetime(today.year, today.month, today.day, tzinfo=TZ)


def since(days: int | None) -> datetime | None:
    return day_start(days - 1) if days else None


def pct(part: float, whole: float) -> int:
    return round(part / whole * 100) if whole else 0


# ---- intake ----


def intake_list(db: DbSession, days: int | None, q: str | None, limit: int, waiting: str | None = None):
    stmt = select(Delivery).join(SourceArea, SourceArea.id == Delivery.source_area_id)
    if waiting == "segregation":
        stmt = stmt.where(Delivery.status == "awaiting")
    elif waiting == "sorting":  # all-wet deliveries stay "separated" but have nothing to sort
        stmt = stmt.join(SegregationCheck, SegregationCheck.delivery_id == Delivery.id).where(
            Delivery.status == "separated", SegregationCheck.dry_kg > 0
        )
    if days:
        stmt = stmt.where(Delivery.received_at >= since(days))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Delivery.code.ilike(like) | SourceArea.name.ilike(like))
    rows = db.scalars(stmt.order_by(Delivery.received_at.desc(), Delivery.id.desc()).limit(limit))
    return intake.out_many(db, list(rows))


# ---- segregation ----


def compliance(db: DbSession, days: int) -> s.Compliance:
    good = func.sum(case((SegregationCheck.condition == "segregated", 1), else_=0))
    rows = db.execute(
        select(SourceArea.name, func.count(SegregationCheck.id), good)
        .join(Delivery, Delivery.source_area_id == SourceArea.id)
        .join(SegregationCheck, SegregationCheck.delivery_id == Delivery.id)
        .where(Delivery.received_at >= since(days))
        .group_by(SourceArea.name)
    ).all()
    seen = {name: (n, int(ok or 0)) for name, n, ok in rows}
    for name in db.scalars(select(SourceArea.name).where(SourceArea.active)):
        seen.setdefault(name, (0, 0))
    out_rows = [
        s.ComplianceRow(source_area=k, deliveries=n, segregated=ok, pct=pct(ok, n)) for k, (n, ok) in sorted(seen.items())
    ]
    total, ok_total = sum(r.deliveries for r in out_rows), sum(r.segregated for r in out_rows)
    wet = db.scalar(
        select(func.coalesce(func.sum(SegregationCheck.wet_kg), 0.0))
        .join(Delivery, Delivery.id == SegregationCheck.delivery_id)
        .where(Delivery.received_at >= since(days), SegregationCheck.condition == "mixed")
    )
    return s.Compliance(
        days=days,
        deliveries=total,
        segregated=ok_total,
        pct=pct(ok_total, total),
        wet_kg_separated=round(float(wet), 2),
        rows=out_rows,
    )


# ---- sorting ----


def _names(db: DbSession, model) -> dict[int, str]:
    return dict(db.execute(select(model.id, model.name)).all())


def sorting_view(db: DbSession, days: int) -> s.SortingView:
    start = since(days)
    confirmed = db.execute(
        select(func.count(), func.sum(case((Classification.changed, 1), else_=0))).where(Classification.confirmed_at >= start)
    ).one()
    classified, changed = confirmed[0], int(confirmed[1] or 0)
    pending = db.scalar(select(func.count()).where(Classification.confirmed_at.is_(None))) or 0
    latest = db.scalars(select(Classification).order_by(Classification.suggested_at.desc(), Classification.id.desc()).limit(15))
    sorted_kg = db.scalar(
        select(func.coalesce(func.sum(StockMovement.kg), 0.0)).where(StockMovement.kind == "sorted", StockMovement.at >= start)
    )
    materials, areas = _names(db, Material), _names(db, StorageArea)
    moves = db.scalars(
        select(StockMovement)
        .where(StockMovement.kind == "sorted")
        .order_by(StockMovement.at.desc(), StockMovement.id.desc())
        .limit(15)
    ).all()
    codes = dict(db.execute(select(Delivery.id, Delivery.code).where(Delivery.id.in_(m.delivery_id for m in moves))).all())
    _ = preload(db, User, Material)
    return s.SortingView(
        classified=classified,
        unchanged=classified - changed,
        changed=changed,
        accepted_pct=pct(classified - changed, classified),
        pending=pending,
        sorted_kg=round(float(sorted_kg), 2),
        classifications=[sorting.out(db, c) for c in latest],
        sorted=[
            s.SortedRow(
                at=m.at,
                delivery=codes.get(m.delivery_id),
                material=materials.get(m.material_id, "Residual"),
                bags=m.bags,
                kg=m.kg,
                area=areas[m.storage_area_id],
            )
            for m in moves
        ],
    )


# ---- inventory ----


def area_fill(db: DbSession) -> list[s.AreaFill]:
    kg = dict(
        db.execute(
            select(StockMovement.storage_area_id, func.sum(StockMovement.kg)).group_by(StockMovement.storage_area_id)
        ).all()
    )
    areas = db.scalars(select(StorageArea).where(StorageArea.active).order_by(StorageArea.name))
    return [
        s.AreaFill(
            id=a.id,
            name=a.name,
            capacity_kg=a.capacity_kg,
            alert_pct=a.alert_pct,
            kg=round(float(kg.get(a.id, 0)), 2),
            pct=pct(float(kg.get(a.id, 0)), a.capacity_kg),
        )
        for a in areas
    ]


def inventory(db: DbSession) -> s.InventoryView:
    materials, areas = _names(db, Material), _names(db, StorageArea)
    rows = db.execute(
        select(
            StockMovement.material_id,
            StockMovement.storage_area_id,
            func.sum(StockMovement.kg),
            func.sum(StockMovement.bags),
            func.max(StockMovement.at),
        ).group_by(StockMovement.material_id, StockMovement.storage_area_id)
    ).all()
    stock = [
        s.StockRow(material=materials.get(m, "Residual"), area=areas[a], kg=round(float(kg), 2), bags=int(bags), last_change=at)
        for m, a, kg, bags, at in rows
        if kg > 0.005
    ]
    return s.InventoryView(areas=area_fill(db), stock=sorted(stock, key=lambda r: (r.area, r.material)))


# ---- compost ----


def _live(db: DbSession, b: CompostBatch, r) -> s.BatchLive:
    reading = db.scalar(
        select(CompostReading).where(CompostReading.batch_id == b.id).order_by(CompostReading.read_at.desc()).limit(1)
    )
    in_range = None
    if reading:
        in_range = (
            r.compost_temp_min <= reading.temp_c <= r.compost_temp_max
            and r.moisture_min <= reading.moisture_pct <= r.moisture_max
        )
    end = b.finished_at or datetime.now(UTC)
    return s.BatchLive(
        **compost.out(db, b).model_dump(),
        temp_c=reading.temp_c if reading else None,
        moisture_pct=reading.moisture_pct if reading else None,
        read_at=reading.read_at if reading else None,
        in_range=in_range,
        day=(end - b.started_at).days + 1,
    )


def compost_batches(db: DbSession, include_recent_finished: bool = True) -> list[s.BatchLive]:
    r = ranges.get(db)
    stmt = select(CompostBatch).order_by(CompostBatch.finished_at.is_not(None), CompostBatch.started_at.desc())
    cutoff = datetime.now(UTC) - timedelta(days=30)
    stmt = stmt.where(
        CompostBatch.finished_at.is_(None) | (CompostBatch.finished_at >= cutoff)
        if include_recent_finished
        else CompostBatch.finished_at.is_(None)
    )
    return [_live(db, b, r) for b in db.scalars(stmt)]


def compost_view(db: DbSession, batch_code: str | None, days: int = 1) -> s.CompostView:
    r = ranges.get(db)
    batches = compost_batches(db)
    pick = next((b for b in batches if b.code == batch_code), None) or next((b for b in batches if not b.finished_at), None)
    series = []
    if pick:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        series = [
            s.Point(at=p.read_at, temp_c=p.temp_c, moisture_pct=p.moisture_pct)
            for p in db.scalars(
                select(CompostReading)
                .where(CompostReading.batch_id == pick.id, CompostReading.read_at >= cutoff)
                .order_by(CompostReading.read_at)
            )
        ]
    return s.CompostView(
        ranges={k: getattr(r, k) for k in ("compost_temp_min", "compost_temp_max", "moisture_min", "moisture_max")},
        batches=batches,
        selected=pick.code if pick else None,
        series=series,
    )


# ---- camera ----


def camera(db: DbSession) -> s.CameraView:
    latest = db.scalar(select(Classification).order_by(Classification.suggested_at.desc(), Classification.id.desc()).limit(1))
    rows = db.execute(
        select(StockMovement.material_id, func.sum(StockMovement.kg), func.sum(StockMovement.bags))
        .where(StockMovement.material_id.is_not(None))
        .group_by(StockMovement.material_id)
    ).all()
    totals = {m: (kg, bags) for m, kg, bags in rows}
    bins = [
        s.MaterialBin(material=m.name, kg=round(float(totals.get(m.id, (0, 0))[0]), 1), bags=int(totals.get(m.id, (0, 0))[1]))
        for m in db.scalars(select(Material).where(Material.active).order_by(Material.id))
    ]
    classified, changed = db.execute(
        select(func.count(), func.coalesce(func.sum(case((Classification.changed, 1), else_=0)), 0))
        .where(Classification.confirmed_at >= since(1))
    ).one()
    return s.CameraView(
        latest=sorting.out(db, latest) if latest else None,
        pending=db.scalar(select(func.count()).where(Classification.confirmed_at.is_(None))) or 0,
        today=classified,
        accepted_pct=pct(classified - changed, classified),
        bins=bins,
    )


# ---- overview ----


def intake_by_day(db: DbSession, days: int) -> list[s.DayKg]:
    local_day = func.date(func.timezone(settings.timezone, Delivery.received_at))
    rows = dict(
        db.execute(
            select(local_day, func.sum(Delivery.weight_kg)).where(Delivery.received_at >= since(days)).group_by(local_day)
        ).all()
    )
    first: date = since(days).date()
    return [
        s.DayKg(day=first + timedelta(days=i), kg=round(float(rows.get(first + timedelta(days=i), 0)), 2)) for i in range(days)
    ]


def overview(db: DbSession) -> s.Overview:
    today = since(1)
    count, kg = db.execute(
        select(func.count(), func.coalesce(func.sum(Delivery.weight_kg), 0.0)).where(Delivery.received_at >= today)
    ).one()
    awaiting = db.scalar(select(func.count()).where(Delivery.status == "awaiting")) or 0
    areas = area_fill(db)
    live = compost_batches(db, include_recent_finished=False)
    latest = db.scalar(select(Classification).order_by(Classification.suggested_at.desc(), Classification.id.desc()).limit(1))
    devs = [
        s.DeviceLive(code=d.code, type=d.type, status=devices.status(d), last_reading=d.last_reading)
        for d in db.scalars(select(Device).where(Device.active).order_by(Device.code))
    ]
    return s.Overview(
        today_deliveries=count,
        today_kg=round(float(kg), 2),
        awaiting_segregation=awaiting,
        compliance_week_pct=compliance(db, 7).pct,
        in_storage_kg=round(sum(a.kg for a in areas), 2),
        active_batches=len(live),
        intake_14d=intake_by_day(db, 14),
        areas=areas,
        compost=live,
        devices=devs,
        latest_classification=sorting.out(db, latest) if latest else None,
        pending_approvals=sum(approvals.counts(db).values()),
        income_month=income_since(db, month_start()),
        open_alerts=alerts.summary(db, with_reports=False).by_kind,
        alert_batch_ids=sorted(alerts.open_alert_subjects(db, "compost")),
    )


# ---- outgoing and income ----


def month_start(months_back: int = 0) -> datetime:
    """The first moment of this month (or months_back earlier), barangay time."""
    today = datetime.now(TZ).date()
    y, m = divmod(today.year * 12 + today.month - 1 - months_back, 12)
    return datetime(y, m + 1, 1, tzinfo=TZ)


APPROVED_SALE = (Outgoing.status == "approved", Outgoing.total.is_not(None))


def income_since(db: DbSession, start: datetime) -> float:
    q = select(func.coalesce(func.sum(Outgoing.total), 0)).where(*APPROVED_SALE, Outgoing.decided_at >= start)
    return float(db.scalar(q))


def outgoing_view(db: DbSession, days: int) -> s.OutgoingView:
    start = month_start()
    kg = dict(db.execute(select(Outgoing.type, func.sum(Outgoing.kg))
                         .where(Outgoing.status == "approved", Outgoing.decided_at >= start).group_by(Outgoing.type)).all())
    month = func.date_trunc("month", func.timezone(settings.timezone, Outgoing.decided_at))
    by_month = {m.date(): float(v) for m, v in db.execute(
        select(month, func.sum(Outgoing.total)).where(*APPROVED_SALE, Outgoing.decided_at >= month_start(5)).group_by(month))}
    months = [month_start(i).date() for i in range(5, -1, -1)]
    _ = preload(db, User, Material, StorageArea)
    rows = db.scalars(select(Outgoing).where(Outgoing.requested_at >= since(days))
                      .order_by(Outgoing.requested_at.desc(), Outgoing.id.desc()).limit(100))
    return s.OutgoingView(
        income_month=income_since(db, start),
        sold_kg_month=round(float(kg.get("sale", 0)), 2),
        compost_kg_month=round(float(kg.get("compost", 0)), 2),
        disposed_kg_month=round(float(kg.get("disposal", 0)), 2),
        pending=db.scalar(select(func.count(Outgoing.id)).where(Outgoing.status == "pending")),
        compost_on_hand_kg=approvals.compost_on_hand(db),
        income_6m=[s.MonthIncome(month=m, income=round(by_month.get(m, 0.0), 2)) for m in months],
        records=[approvals.outgoing_out(db, o, balances=False) for o in rows],
    )
