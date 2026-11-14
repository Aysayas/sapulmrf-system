"""One function per report: (db, start, end, area) -> Report. start/end are aware datetimes, end exclusive."""

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from app.approvals.models import Outgoing
from app.compost.models import CompostBatch
from app.intake.models import Delivery, SegregationCheck
from app.masterdata.models import Material, SourceArea, WasteCategory
from app.operations import service as ops
from app.reports.schemas import Report

TITLES = {
    "intake": "Intake Report",
    "segregation": "Segregation Compliance Report",
    "inventory": "Inventory Report",
    "composting": "Composting Report",
    "outgoing": "Outgoing Material Report",
    "income": "Income Report",
}
# Only these can be narrowed to one purok; the others ignore the source area.
BY_AREA = ("intake", "segregation")


def _local(dt: datetime) -> str:
    return dt.astimezone(ops.TZ).strftime("%Y-%m-%d %H:%M")


def _in_range(col, start, end):
    return (col >= start) & (col < end)


def intake(db: DbSession, start, end, area: int | None) -> Report:
    q = (
        select(SourceArea.name, WasteCategory.name, func.count(Delivery.id), func.sum(Delivery.weight_kg))
        .join(SourceArea, SourceArea.id == Delivery.source_area_id)
        .join(WasteCategory, WasteCategory.id == Delivery.category_id)
        .where(_in_range(Delivery.received_at, start, end))
        .group_by(SourceArea.name, WasteCategory.name)
        .order_by(SourceArea.name, WasteCategory.name)
    )
    if area:
        q = q.where(Delivery.source_area_id == area)
    rows = db.execute(q).all()
    n, kg = sum(r[2] for r in rows), sum(float(r[3]) for r in rows)
    return Report(kind="intake", title=TITLES["intake"], subtitle="",
                  summary=[("Deliveries", str(n)), ("Total weight", f"{kg:,.2f} kg")],
                  columns=["Source area", "Waste category", "Deliveries", "Weight (kg)"],
                  rows=[[a, c, int(k), round(float(w), 2)] for a, c, k, w in rows])


def segregation(db: DbSession, start, end, area: int | None) -> Report:
    good = func.sum(case((SegregationCheck.condition == "segregated", 1), else_=0))
    q = (
        select(SourceArea.name, func.count(SegregationCheck.id), good)
        .join(Delivery, Delivery.source_area_id == SourceArea.id)
        .join(SegregationCheck, SegregationCheck.delivery_id == Delivery.id)
        .where(_in_range(Delivery.received_at, start, end))
        .group_by(SourceArea.name)
    )
    if area:
        q = q.where(SourceArea.id == area)
    seen = {name: (n, int(ok or 0)) for name, n, ok in db.execute(q)}
    names = select(SourceArea.name).where(SourceArea.active)
    for name in db.scalars(names.where(SourceArea.id == area) if area else names):
        seen.setdefault(name, (0, 0))
    total, ok_total = sum(v[0] for v in seen.values()), sum(v[1] for v in seen.values())
    return Report(kind="segregation", title=TITLES["segregation"], subtitle="",
                  summary=[("Deliveries", str(total)), ("Segregated", str(ok_total)),
                           ("Compliance", f"{ops.pct(ok_total, total)}%")],
                  columns=["Source area", "Deliveries", "Segregated", "Compliance (%)"],
                  rows=[[k, n, ok, ops.pct(ok, n)] for k, (n, ok) in sorted(seen.items())])


def inventory(db: DbSession, start, end, area: int | None) -> Report:
    view = ops.inventory(db)  # a snapshot of stock now: the date range does not apply
    fill = {a.name: a for a in view.areas}
    total = sum(r.kg for r in view.stock)
    return Report(kind="inventory", title=TITLES["inventory"], subtitle="",
                  summary=[("Stock on hand", f"{total:,.2f} kg"), ("As of", _local(datetime.now(ops.TZ)))],
                  columns=["Storage area", "Material", "Weight (kg)", "Bags", "Area full (%)"],
                  rows=[[r.area, r.material, r.kg, r.bags, fill[r.area].pct if r.area in fill else 0] for r in view.stock])


def composting(db: DbSession, start, end, area: int | None) -> Report:
    batches = db.scalars(
        select(CompostBatch)
        .where(CompostBatch.started_at < end, CompostBatch.finished_at.is_(None) | (CompostBatch.finished_at >= start))
        .order_by(CompostBatch.started_at)
    ).all()
    rows, made = [], 0.0
    for b in batches:  # logged by hand: there is no compost sensor, so no temperature or moisture
        made += b.produced_kg or 0
        rows.append([b.code, _local(b.started_at)[:10], "Finished" if b.finished_at else "Active", round(b.start_kg, 2),
                     round(b.produced_kg, 2) if b.produced_kg is not None else ""])
    return Report(kind="composting", title=TITLES["composting"], subtitle="",
                  summary=[("Batches", str(len(rows))), ("Compost produced", f"{made:,.2f} kg")],
                  columns=["Batch", "Started", "Status", "Raw waste (kg)", "Compost (kg)"],
                  rows=rows)


def _approved(db: DbSession, start, end, *extra):
    q = (
        select(Outgoing, Material.name)
        .outerjoin(Material, Material.id == Outgoing.material_id)
        .where(Outgoing.status == "approved", _in_range(Outgoing.decided_at, start, end), *extra)
        .order_by(Outgoing.decided_at, Outgoing.id)
    )
    return db.execute(q).all()


def _reversed(db: DbSession, start, end, *extra):
    """Outgoing the admin reversed in the range: a negative entry on the day of the reversal."""
    q = (
        select(Outgoing, Material.name)
        .outerjoin(Material, Material.id == Outgoing.material_id)
        .where(Outgoing.review == "reversed", _in_range(Outgoing.reviewed_at, start, end), *extra)
        .order_by(Outgoing.reviewed_at, Outgoing.id)
    )
    return db.execute(q).all()


def outgoing(db: DbSession, start, end, area: int | None) -> Report:
    found = _approved(db, start, end)
    back = _reversed(db, start, end)
    label = {"sale": "Sale", "giveaway": "Recyclables given away", "compost": "Compost", "disposal": "Residual disposal"}
    by_kind: dict[str, float] = {}
    for o, _ in found:
        by_kind[o.type] = by_kind.get(o.type, 0) + o.kg
    for o, _ in back:
        by_kind[o.type] = by_kind.get(o.type, 0) - o.kg
    return Report(kind="outgoing", title=TITLES["outgoing"], subtitle="",
                  summary=[(label[k], f"{by_kind.get(k, 0):,.2f} kg") for k in label],
                  columns=["Date", "Code", "Kind", "Material", "Weight (kg)", "Recipient"],
                  rows=[[_local(o.decided_at)[:10], o.code, label[o.type],
                         m or ("Compost" if o.type == "compost" else "Residual"), round(o.kg, 2), o.recipient]
                        for o, m in found]
                  + [[_local(o.reviewed_at)[:10], f"{o.code} reversed", label[o.type],
                      m or ("Compost" if o.type == "compost" else "Residual"), -round(o.kg, 2), o.recipient]
                     for o, m in back])


def income(db: DbSession, start, end, area: int | None) -> Report:
    found = _approved(db, start, end, Outgoing.total.is_not(None))
    back = _reversed(db, start, end, Outgoing.total.is_not(None))
    total = sum(float(o.total) for o, _ in found) - sum(float(o.total) for o, _ in back)
    return Report(kind="income", title=TITLES["income"], subtitle="",
                  summary=[("Sales", str(len(found))), ("Total income", f"PHP {total:,.2f}")],
                  columns=["Date", "Code", "Material", "Weight (kg)", "Price per kg (PHP)", "Amount (PHP)"],
                  rows=[[_local(o.decided_at)[:10], o.code, m or "Compost", round(o.kg, 2),
                         float(o.price_per_kg or 0), float(o.total)] for o, m in found]
                  + [[_local(o.reviewed_at)[:10], f"{o.code} reversed", m or "Compost", -round(o.kg, 2),
                      float(o.price_per_kg or 0), -float(o.total)] for o, m in back])


BUILDERS = {"intake": intake, "segregation": segregation, "inventory": inventory,
            "composting": composting, "outgoing": outgoing, "income": income}
