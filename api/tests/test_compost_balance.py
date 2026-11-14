from app.compost.models import CompostBatch
from app.compost.service import wet_waiting
from app.intake.models import Delivery, SegregationCheck


def check(db, world, wet: float) -> Delivery:
    """A delivery with a segregation check: `wet` kg of wet waste now waits for compost."""
    d = Delivery(code=f"D-{wet:g}-{db.query(Delivery).count()}", source_area_id=world["purok1"],
                 category_id=world["cat"]["Mixed household"], weight_kg=wet + 1, weighed_by="manual")
    db.add(d)
    db.flush()
    db.add(SegregationCheck(delivery_id=d.id, condition="mixed", wet_kg=wet, dry_kg=1))
    db.commit()
    return d


def test_wet_waiting_is_wet_minus_batches_and_never_negative(db, world):
    check(db, world, 12.0)
    check(db, world, 8.0)
    assert wet_waiting(db) == 20.0
    db.add(CompostBatch(code="B-1", start_kg=15))
    db.commit()
    assert wet_waiting(db) == 5.0
    db.add(CompostBatch(code="B-2", start_kg=50))  # older batches from before the rule
    db.commit()
    assert wet_waiting(db) == 0.0


def test_a_batch_cannot_use_more_than_is_waiting(client, db, world, make_user, login):
    check(db, world, 10.0)
    make_user("op", role="operator")
    login("op")
    assert client.post("/compost/batches", json={"start_kg": 10.4}).status_code == 201  # 0.5 kg slack
    r = client.post("/compost/batches", json={"start_kg": 1})
    assert r.status_code == 422 and r.json()["detail"] == "Only 0 kg of wet waste is waiting for compost."
    # the slack is for one batch's rounding, not to be used again and again
    assert client.post("/compost/batches", json={"start_kg": 0.5}).status_code == 422


def test_undoing_a_check_lowers_the_balance(client, db, world, make_user, login):
    check(db, world, 4.0)
    d = Delivery(code="D-UNDO", source_area_id=world["purok1"], category_id=world["cat"]["Mixed household"],
                 weight_kg=7, weighed_by="manual")
    db.add(d)
    db.commit()
    make_user("op", role="operator")
    login("op")  # only the operator who made a check can undo it
    r = client.post(f"/deliveries/{d.id}/segregation", json={"condition": "mixed", "wet_kg": 6, "dry_kg": 1})
    assert r.status_code == 201, r.text
    assert wet_waiting(db) == 10.0
    assert client.delete(f"/deliveries/{d.id}/segregation").status_code == 200
    db.expire_all()
    assert wet_waiting(db) == 4.0


def test_admins_can_start_batches_and_see_the_balance(client, db, world, make_user, login):
    check(db, world, 6.0)
    make_user("boss", role="admin")
    login("boss")
    assert client.get("/operations/compost").json()["wet_waiting_kg"] == 6.0
    assert client.get("/overview").json()["wet_waiting_kg"] == 6.0
    assert client.post("/compost/batches", json={"start_kg": 6}).status_code == 201
    assert client.get("/operations/compost").json()["wet_waiting_kg"] == 0.0
