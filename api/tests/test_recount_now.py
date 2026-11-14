from sqlalchemy import select
from test_approvals import as_admin, stock

from app.approvals.models import AdjustmentRequest
from app.sorting.models import StockMovement
from app.sorting.service import material_bags, material_kg


def recount(client, world, kg, reason="Miscounted"):
    return client.post("/inventory/adjustments", json={"material_id": world["mat"]["Plastic"],
                                                       "storage_area_id": world["area_a"], "actual_kg": kg, "reason": reason})


def test_a_recount_applies_at_once_and_waits_for_review(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100)
    r = recount(client, world, 92.5)
    assert r.status_code == 201 and r.json()["status"] == "approved" and r.json()["review"] is None
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 92.5
    as_admin(make_user, login)
    body = client.get("/approvals").json()
    assert body["counts"]["adjustments_review"] == 1 and body["adjustments_review"][0]["id"] == r.json()["id"]


def test_reverse_puts_the_old_count_back_once(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100)
    r = recount(client, world, 92.5).json()
    as_admin(make_user, login)
    back = client.post(f"/approvals/adjustments/{r['id']}/review", json={"decision": "reverse", "comment": "Recounted"})
    assert back.status_code == 200 and back.json()["review"] == "reversed"
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 100.0
    again = client.post(f"/approvals/adjustments/{r['id']}/review", json={"decision": "reverse", "comment": "x"})
    assert again.status_code == 409


def test_recount_to_zero_then_reverse_restores_bags(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=40, bags=8)
    r = recount(client, world, 0, "Spilled").json()
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 0.0
    assert material_bags(db, world["mat"]["Plastic"], world["area_a"]) == 0
    as_admin(make_user, login)
    client.post(f"/approvals/adjustments/{r['id']}/review", json={"decision": "reverse", "comment": "Found them"})
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 40.0
    assert material_bags(db, world["mat"]["Plastic"], world["area_a"]) == 8


def test_old_pending_adjustment_still_approves(client, db, world, make_user, login):
    stock(db, world, kg=100)
    r = AdjustmentRequest(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], system_kg=100,
                          actual_kg=90, reason="old flow")
    db.add(r)
    db.commit()
    as_admin(make_user, login)
    d = client.post(f"/approvals/adjustments/{r.id}", json={"decision": "approve"})
    assert d.status_code == 200 and d.json()["review"] == "ok"
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 90.0
    assert len(db.scalars(select(StockMovement).where(StockMovement.kind == "adjustment")).all()) == 1


def test_a_recount_cannot_be_reversed_once_stock_changed_after_it(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100)
    a = recount(client, world, 80).json()
    recount(client, world, 50)  # a later count of the same pile: reversing the first would make it 70
    as_admin(make_user, login)
    r = client.post(f"/approvals/adjustments/{a['id']}/review", json={"decision": "reverse", "comment": "x"})
    assert r.status_code == 409 and "changed" in r.json()["detail"]
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 50.0
