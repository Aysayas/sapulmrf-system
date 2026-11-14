from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app import simulator
from app.approvals.models import AdjustmentRequest, Outgoing
from app.compost.models import CompostActivity, CompostBatch, CompostReading
from app.devices.models import Device
from app.intake.models import Delivery
from app.masterdata.models import SourceArea, StorageArea
from app.sorting.models import Classification, StockMovement
from app.users.models import User

NOW = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)  # 16:00 in Manila


def test_backfill_makes_days_of_history_and_remove_takes_it_all_back(db, world, make_user):
    admin = make_user("e2e.admin", role="admin")
    real_op = make_user("juan", role="operator")
    real = Delivery(source_area_id=world["purok1"], category_id=world["cat"]["Residual"], weight_kg=3, weighed_by="manual",
                    recorded_by=real_op.id, code="D-REAL")
    db.add_all([real, Outgoing(code="O-REAL", type="compost", kg=5, recipient="Purok 1", requested_by=real_op.id)])
    db.commit()

    counts = simulator.backfill(db, days=15, now=NOW)
    assert counts["deliveries"] >= 15 * 10 and counts["batches"] >= 1
    manila_day = func.date(func.timezone("Asia/Manila", Delivery.received_at))
    days = db.scalar(select(func.count(func.distinct(manila_day))).where(Delivery.code != "D-REAL"))
    assert days == 15
    # Saturday pickups became approved sales with income; recounts became adjustments
    assert counts["outgoing"] >= 1 and counts["adjustments"] == 2
    assert db.scalar(select(func.sum(Outgoing.total)).where(Outgoing.status == "approved")) > 0
    assert db.scalar(select(func.count()).where(StockMovement.kind == "outgoing")) >= 1
    # older corrections were reviewed, the last three days' wait for the admin
    unreviewed = db.scalars(select(Classification.confirmed_at).where(Classification.changed.is_(True),
                                                                      Classification.review.is_(None))).all()
    assert unreviewed and min(unreviewed) > NOW - simulator.RECENT
    assert db.scalar(select(func.count()).where(Classification.confirmed_at.is_(None))) == 0
    # one device (the kiosk); compost is logged by hand: no sensor, no readings, but watering and turning
    assert db.scalars(select(Device.code).where(Device.code.like("SIM-%"))).all() == ["SIM-WS-01"]
    assert db.scalar(select(func.count()).select_from(CompostReading)) == 0
    assert db.scalar(select(func.count()).where(CompostBatch.sensor_id.is_not(None))) == 0
    assert {"watering", "turning"} <= set(db.scalars(select(CompostActivity.type)))
    # the world's real areas were used, so no demo areas were made
    assert not db.scalar(select(SourceArea.id).where(SourceArea.name.like("Demo %")))
    # every area's stock stays at or above zero per material
    rows = db.execute(select(StockMovement.storage_area_id, StockMovement.material_id, func.sum(StockMovement.kg))
                      .group_by(StockMovement.storage_area_id, StockMovement.material_id)).all()
    assert all(kg >= -0.01 for _, _, kg in rows)

    # the admin reverses a recent simulated sale: its stock comes back with a movement of its own
    from app.approvals import service as approvals
    from app.approvals.schemas import OutgoingReviewIn
    sold = db.scalar(select(Outgoing).where(Outgoing.storage_area_id.is_not(None), Outgoing.code != "O-REAL").limit(1))
    sold.review = None  # as if it were still waiting for the admin
    approvals.review_outgoing(db, sold.id, OutgoingReviewIn(decision="reverse", comment="test"), admin)

    removed = simulator.remove(db)
    assert removed["deliveries"] == counts["deliveries"] and removed["users"] == 1
    assert db.scalar(select(func.count()).select_from(Delivery)) == 1  # the real one is untouched
    assert not db.scalar(select(Device.id).where(Device.code.like("SIM-%")))
    assert not db.scalar(select(User.id).where(User.username == simulator.SIM_USER))
    assert db.scalar(select(func.count()).select_from(StockMovement)) == 0  # including the rows the admin's approvals wrote
    assert db.scalars(select(Outgoing.code)).all() == ["O-REAL"]
    assert db.scalar(select(func.count()).select_from(AdjustmentRequest)) == 0


def test_backfill_needs_the_test_admin(db, world):
    with pytest.raises(RuntimeError, match="test admin"):
        simulator.backfill(db, days=1, now=NOW)


def test_backfill_makes_demo_areas_only_when_there_are_none(db, make_user):
    make_user("e2e.admin", role="admin")
    simulator.backfill(db, days=1, now=NOW)
    assert db.scalar(select(func.count()).where(SourceArea.name.like("Demo Purok %"))) == 7
    assert db.scalar(select(func.count()).where(StorageArea.name.like("Demo Area %"))) == 4
    simulator.remove(db)
    assert db.scalar(select(func.count()).where(SourceArea.name.like("Demo %"))) == 0


def test_behaviour_is_believable():
    import random

    rnd = random.Random(1)
    profiles = simulator.purok_profiles([f"P{i}" for i in range(7)])
    assert all(6 <= usual <= 14 and 0.35 <= rate <= 0.9 for usual, rate in profiles.values())
    guesses = [simulator.camera_guess(rnd, "Plastic") for _ in range(400)]
    unchanged = sum(1 for _, _, changed in guesses if not changed) / len(guesses)
    assert 0.78 < unchanged < 0.92
    wet, dry = simulator.split_wet_dry(rnd, 10.0, "Mixed household")
    assert 0 < wet < 10 and wet + dry <= 10
