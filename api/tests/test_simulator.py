from datetime import UTC, datetime

from sqlalchemy import func, select

from app import simulator
from app.compost.models import CompostReading
from app.devices.models import Device
from app.intake.models import Delivery
from app.masterdata.models import SourceArea, StorageArea
from app.sorting.models import Classification, StockMovement
from app.users.models import User

NOW = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)  # 16:00 in Manila


def test_backfill_makes_days_of_history_and_remove_takes_it_all_back(db, world, make_user):
    real_op = make_user("juan", role="operator")
    real = Delivery(source_area_id=world["purok1"], category_id=world["cat"]["Residual"], weight_kg=3, weighed_by="manual",
                    recorded_by=real_op.id, code="D-REAL")
    db.add(real)
    db.commit()

    counts = simulator.backfill(db, days=8, now=NOW)
    assert counts["deliveries"] >= 8 * 10 and counts["readings"] > 0 and counts["batches"] >= 1
    manila_day = func.date(func.timezone("Asia/Manila", Delivery.received_at))
    days = db.scalar(select(func.count(func.distinct(manila_day))).where(Delivery.code != "D-REAL"))
    assert days == 8
    assert db.scalar(select(func.count()).where(Classification.confirmed_at.is_(None))) == 0
    assert db.scalar(select(func.count()).select_from(CompostReading)) == counts["readings"]
    # the world's real areas were used, so no demo areas were made
    assert not db.scalar(select(SourceArea.id).where(SourceArea.name.like("Demo %")))
    # every area's stock stays at or above zero per material
    rows = db.execute(select(StockMovement.storage_area_id, StockMovement.material_id, func.sum(StockMovement.kg))
                      .group_by(StockMovement.storage_area_id, StockMovement.material_id)).all()
    assert all(kg >= -0.01 for _, _, kg in rows)

    removed = simulator.remove(db)
    assert removed["deliveries"] == counts["deliveries"] and removed["users"] == 1
    assert db.scalar(select(func.count()).select_from(Delivery)) == 1  # the real one is untouched
    assert not db.scalar(select(Device.id).where(Device.code.like("SIM-%")))
    assert not db.scalar(select(User.id).where(User.username == simulator.SIM_USER))
    assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_backfill_makes_demo_areas_only_when_there_are_none(db):
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
