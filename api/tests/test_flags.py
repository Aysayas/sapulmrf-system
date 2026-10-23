from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.insights.models import Flag
from app.intake import service as intake
from app.intake.schemas import DeliveryIn, SegregationIn
from app.settings import service as ranges
from app.sorting import service as sorting
from app.sorting.schemas import SortIn

T0 = datetime(2026, 10, 1, 1, 0, tzinfo=UTC)
USUAL = [7.5, 8.0, 8.5, 7.8, 8.2, 7.9, 8.1, 8.4, 7.6, 8.0]  # mean 8.0, SD about 0.3


def deliver(db, world, op, kg, i, purok="purok1"):
    return intake.record_delivery(db, DeliveryIn(source_area_id=world[purok], category_id=world["cat"]["Mixed household"],
                                                 weight_kg=kg, weighed_by="scale"), op, at=T0 + timedelta(hours=i))


def flags(db, kind):
    return db.scalars(select(Flag).where(Flag.kind == kind)).all()


def test_an_unusual_weight_is_flagged_with_the_usual_range(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    assert flags(db, "weight") == []
    normal = deliver(db, world, op, 8.3, 20)
    heavy = deliver(db, world, op, 14.1, 21)
    [f] = flags(db, "weight")
    assert f.delivery_id == heavy.id != normal.id and f.value_kg == 14.1
    assert 7.5 < f.expected_low < 8.0 < f.expected_high < 8.5 and f.status == "open"


def test_no_judgement_before_ten_earlier_deliveries(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL[:9]):
        deliver(db, world, op, kg, i)
    deliver(db, world, op, 40.0, 20)
    assert flags(db, "weight") == []


def test_each_purok_has_its_own_usual(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg * 3, i, purok="purok2")  # purok 2 delivers about 24 kg
    deliver(db, world, op, 24.0, 30, purok="purok2")
    assert flags(db, "weight") == []


def test_the_sensitivity_setting_changes_what_is_flagged(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    ranges.get(db).anomaly_sd = 3.0
    deliver(db, world, op, 8.9, 20)  # about 2.8 SD above: fine at 3.0
    assert flags(db, "weight") == []
    ranges.get(db).anomaly_sd = 2.0
    deliver(db, world, op, 9.0, 21)  # about 2.3 SD above the (now 11) earlier ones: flagged at 2.0
    assert len(flags(db, "weight")) == 1


def sort(db, world, op, kg, wet, dry, sorted_kg):
    d = deliver(db, world, op, kg, 0)
    intake.record_segregation(db, d.id, SegregationIn(condition="mixed", wet_kg=wet, dry_kg=dry), op)
    sorting.sort_delivery(db, SortIn(delivery_id=d.id, rows=[{"material_id": world["mat"]["Plastic"], "bags": 1,
                                                                "kg": sorted_kg, "storage_area_id": world["area_a"]}]), op)
    return d


def test_a_received_vs_sorted_gap_is_flagged(db, world, make_user):
    op = make_user()
    d = sort(db, world, op, 11.3, wet=2.0, dry=7.1, sorted_kg=7.1)  # 9.1 kg accounted for: 2.2 kg missing
    [f] = flags(db, "gap")
    assert f.delivery_id == d.id and f.value_kg == 11.3 and f.expected_low == f.expected_high == 9.1


def test_a_small_difference_is_not_a_gap(db, world, make_user):
    op = make_user()
    sort(db, world, op, 10.0, wet=4.0, dry=5.9, sorted_kg=5.9)  # 0.1 kg (1%)
    assert flags(db, "gap") == []
