import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.insights.flags import check_weight, is_unusual
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


def test_the_limit_setting_changes_what_is_flagged(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    deliver(db, world, op, 9.0, 20)  # median 8.0, MAD 0.2: M is about 3.4, under the default 3.5
    assert flags(db, "weight") == []
    ranges.get(db).anomaly_limit = 3
    deliver(db, world, op, 9.0, 21)
    assert len(flags(db, "weight")) == 1


def test_the_same_history_gives_the_same_answer(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    d = deliver(db, world, op, 14.1, 20)
    first = flags(db, "weight")
    assert [f.delivery_id for f in first] == [d.id]
    db.delete(first[0])
    db.flush()
    check_weight(db, d)
    assert [f.delivery_id for f in flags(db, "weight")] == [d.id]


def test_identical_history_flags_nothing(db, world, make_user):
    op = make_user()
    for i in range(10):
        deliver(db, world, op, 8.0, i)
    deliver(db, world, op, 8.0, 20)
    assert flags(db, "weight") == []
    far = deliver(db, world, op, 40.0, 21)
    assert [f.delivery_id for f in flags(db, "weight")] == [far.id]


def test_a_tiny_difference_from_identical_history_is_not_flagged(db, world, make_user):
    op = make_user()
    for i in range(10):
        deliver(db, world, op, 8.0, i)
    deliver(db, world, op, 8.01, 20)
    deliver(db, world, op, 8.1, 21)
    assert flags(db, "weight") == []


def test_an_old_outlier_in_the_history_does_not_hide_a_new_one():
    earlier = [7, 7.5, 8, 8, 8.5, 9, 21]  # raises the mean and SD enough that a z-score of 20 kg is only about 2
    assert is_unusual(earlier, 20, 3.5)
    assert not is_unusual(earlier, 8.5, 3.5)


def test_a_past_outlier_does_not_hide_the_next_one(db, world, make_user):
    op = make_user()
    rnd = random.Random(1)
    for i in range(30):
        deliver(db, world, op, round(rnd.gauss(8, 1.4), 2), i)
    hours = iter(range(40, 50))
    first, second = [deliver(db, world, op, kg, next(hours)) for kg in (24.0, 26.0)]
    third = deliver(db, world, op, 25.0, next(hours))
    assert {f.delivery_id for f in flags(db, "weight")} >= {first.id, second.id, third.id}


def test_a_flag_marked_incorrect_goes_back_into_the_usual_weights(db, world, make_user):
    op = make_user()
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    for i in range(20, 35):  # the median moves only once enough of them count as usual
        deliver(db, world, op, 14.1, i)
        for f in flags(db, "weight"):
            f.status = "incorrect"
        db.flush()
    before = len(flags(db, "weight"))
    deliver(db, world, op, 14.1, 40)
    assert 0 < before == len(flags(db, "weight"))


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
