"""Unusual-record checks, run when a record is made. They only add a flag; the record itself never changes."""

from statistics import fmean, stdev

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.insights.models import Flag
from app.intake.models import Delivery, SegregationCheck
from app.settings import service as ranges
from app.sorting.models import StockMovement

MIN_HISTORY = 10  # earlier deliveries from a purok before its weights are judged
HISTORY = 100  # the most recent earlier deliveries used for "usual"
GAP_PCT, GAP_KG = 0.05, 0.3  # received vs separated + sorted must differ by both of these to flag


def _flag(db: DbSession, delivery: Delivery, kind: str, low: float, high: float) -> Flag:
    f = Flag(
        delivery_id=delivery.id, kind=kind, value_kg=delivery.weight_kg, expected_low=round(low, 2), expected_high=round(high, 2)
    )
    if delivery.received_at:
        f.found_at = delivery.received_at  # backfilled records keep their own time
    db.add(f)
    return f


def check_weight(db: DbSession, d: Delivery) -> Flag | None:
    """z-score against the same purok's earlier deliveries: |weight - mean| > anomaly_sd × SD."""
    earlier = db.scalars(
        select(Delivery.weight_kg)
        .where(Delivery.source_area_id == d.source_area_id, Delivery.id != d.id, Delivery.received_at <= d.received_at)
        .order_by(Delivery.received_at.desc())
        .limit(HISTORY)
    ).all()
    if len(earlier) < MIN_HISTORY:
        return None
    mean, sd = fmean(earlier), stdev(earlier)
    if sd == 0 or abs(d.weight_kg - mean) <= ranges.get(db).anomaly_sd * sd:
        return None
    return _flag(db, d, "weight", max(0.0, mean - sd), mean + sd)


def check_gap(db: DbSession, d: Delivery) -> Flag | None:
    """Received weight vs wet separated + dry sorted, once the delivery is sorted."""
    wet = db.scalar(select(SegregationCheck.wet_kg).where(SegregationCheck.delivery_id == d.id)) or 0.0
    sorted_kg = db.scalar(
        select(func.coalesce(func.sum(StockMovement.kg), 0.0)).where(
            StockMovement.delivery_id == d.id, StockMovement.kind == "sorted"
        )
    )
    accounted = wet + float(sorted_kg)
    gap = abs(d.weight_kg - accounted)
    if gap <= GAP_PCT * d.weight_kg or gap <= GAP_KG:
        return None
    return _flag(db, d, "gap", accounted, accounted)
