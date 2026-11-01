"""Unusual-record checks, run when a record is made. They only add a flag; the record itself never changes."""

from datetime import timedelta
from statistics import fmean, median, stdev

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.insights.models import Flag
from app.intake.models import Delivery, SegregationCheck
from app.settings import service as ranges
from app.sorting.models import StockMovement

MIN_HISTORY = 10  # earlier deliveries from a purok before its weights are judged
HISTORY = 100  # the most recent earlier deliveries used for "usual"
# After this an undecided flag counts as usual, so a lasting change isn't flagged forever.
UNDECIDED_KEPT_OUT = timedelta(days=14)
GAP_PCT, GAP_KG = 0.05, 0.3  # received vs separated + sorted must differ by both of these to flag


def _flag(db: DbSession, delivery: Delivery, kind: str, low: float, high: float) -> Flag:
    f = Flag(
        delivery_id=delivery.id, kind=kind, value_kg=delivery.weight_kg, expected_low=round(low, 2), expected_high=round(high, 2)
    )
    if delivery.received_at:
        f.found_at = delivery.received_at  # backfilled records keep their own time
    db.add(f)
    return f


def is_unusual(earlier: list[float], weight: float, limit: float) -> bool:
    """Modified z-score on one purok's earlier weights. A lower limit (the setting) flags more."""
    usual = median(earlier)
    distance = abs(weight - usual)
    if distance <= GAP_KG:  # scale noise, however tight the history
        return False
    mad = median(abs(w - usual) for w in earlier)
    return mad == 0 or 0.6745 * distance / mad > limit  # mad is 0 when most earlier weights are identical


def check_weight(db: DbSession, d: Delivery) -> Flag | None:
    """Judged against earlier weights, leaving out ones already flagged, or past outliers would hide later ones."""
    flagged = select(Flag.id).where(
        Flag.delivery_id == Delivery.id, Flag.kind == "weight",
        or_(Flag.status == "valid", (Flag.status == "open") & (Flag.found_at >= d.received_at - UNDECIDED_KEPT_OUT)),
    )
    earlier = db.scalars(
        select(Delivery.weight_kg)
        .where(Delivery.source_area_id == d.source_area_id, Delivery.id != d.id, Delivery.received_at <= d.received_at,
               ~flagged.exists())
        .order_by(Delivery.received_at.desc())
        .limit(HISTORY)
    ).all()
    if len(earlier) < MIN_HISTORY:
        return None
    if not is_unusual(earlier, d.weight_kg, ranges.get(db).anomaly_limit):
        return None
    mean, sd = fmean(earlier), stdev(earlier)  # the usual range only explains the flag
    return _flag(db, d, "weight", max(0.0, mean - sd), mean + sd)


def check_gap(db: DbSession, d: Delivery) -> Flag | None:
    """Received weight vs wet separated + dry sorted, once the delivery is sorted."""
    wet = db.scalar(select(SegregationCheck.wet_kg).where(SegregationCheck.delivery_id == d.id)) or 0.0
    sorted_kg = db.scalar(
        select(func.coalesce(func.sum(StockMovement.kg), 0.0)).where(
            StockMovement.delivery_id == d.id, StockMovement.kind == "sorted"
        )
    )
    accounted = wet + float(sorted_kg or 0)
    gap = abs(d.weight_kg - accounted)
    if gap <= GAP_PCT * d.weight_kg or gap <= GAP_KG:
        return None
    return _flag(db, d, "gap", accounted, accounted)
