from datetime import UTC, datetime

from sqlalchemy import select

from app.activity.models import ActivityLog
from app.compost.models import CompostBatch
from app.sorting.models import StockMovement
from app.sorting.service import material_kg


def stock(db, world, kg=100.0, bags=10, material="Plastic", area="area_a"):
    db.add(StockMovement(material_id=world["mat"][material] if material else None, storage_area_id=world[area],
                         kg=kg, bags=bags, kind="sorted"))
    db.commit()


def sale(client, world, kg=40.0, price=12.5, area="area_a"):
    return client.post("/outgoing", json={"type": "sale", "material_id": world["mat"]["Plastic"], "kg": kg,
                                          "storage_area_id": world[area], "recipient": "Buyer A", "price_per_kg": price})


def as_admin(make_user, login):
    make_user("maria", role="admin", name="Maria Santos")
    login("maria")


def pending(db, world, kg=40.0, material="Plastic", area="area_a", type_="sale", price=12.5):
    """An outgoing record from before operators' outgoing counted at once: it still waits for approve / reject."""
    from decimal import Decimal

    from app.approvals.models import Outgoing
    o = Outgoing(type=type_, material_id=world["mat"][material] if material else None,
                 storage_area_id=world[area] if area else None, kg=kg, recipient="Buyer A",
                 price_per_kg=Decimal(str(price)) if price else None,
                 total=Decimal(str(round(kg * price, 2))) if price else None)
    db.add(o)
    db.flush()
    o.code = f"O-{o.id:04d}"
    db.commit()
    return o


def test_operators_record_outgoing_and_it_counts_at_once(client, db, world, as_operator, make_user, login):
    stock(db, world)
    r = sale(client, world)
    assert r.status_code == 201
    o = r.json()
    assert o["code"].startswith("O-") and o["status"] == "approved" and o["total"] == 500.0
    assert o["available_kg"] == 60.0 and o["area_after_kg"] == 60.0 and o["requested_by"] == "Juan Dela Cruz"
    second = sale(client, world).json()
    assert int(second["code"][2:]) == int(o["code"][2:]) + 1
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 20.0  # both left at once
    rows = db.scalars(select(StockMovement).where(StockMovement.kind == "outgoing")).all()
    assert len(rows) == 2 and rows[0].bags == -4 and rows[0].note == o["code"]
    assert client.get("/approvals").status_code == 403

    as_admin(make_user, login)
    body = client.get("/approvals").json()
    assert body["counts"]["outgoing"] == 0 and body["counts"]["outgoing_review"] == 2
    assert [x["code"] for x in body["outgoing_review"]] == [o["code"], second["code"]]


def test_each_type_needs_its_own_fields(client, db, world, as_operator):
    db.add(CompostBatch(code="B-90", start_kg=100, finished_at=datetime.now(UTC), produced_kg=30))
    db.commit()
    base = {"kg": 5, "recipient": "Someone"}
    assert client.post("/outgoing", json={**base, "type": "sale", "material_id": world["mat"]["Paper"],
                                          "storage_area_id": world["area_a"]}).status_code == 422  # no price
    assert client.post("/outgoing", json={**base, "type": "disposal"}).status_code == 422  # no area
    assert client.post("/outgoing", json={**base, "type": "compost", "storage_area_id": world["area_a"]}).status_code == 422
    r = client.post("/outgoing", json={**base, "type": "compost", "price_per_kg": 5})
    assert r.status_code == 201 and r.json()["material"] == "Compost" and r.json()["total"] == 25.0


def test_approving_an_old_pending_sale_moves_stock_once(client, db, world, make_user, login):
    stock(db, world)
    o = pending(db, world)
    as_admin(make_user, login)
    r = client.post(f"/approvals/outgoing/{o.id}", json={"decision": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"] == "Maria Santos"
    assert r.json()["review"] == "ok"  # the admin decided it: nothing left to review
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 60.0
    rows = db.scalars(select(StockMovement).where(StockMovement.kind == "outgoing")).all()
    assert len(rows) == 1 and rows[0].bags == -4 and rows[0].note == o.code
    assert client.post(f"/approvals/outgoing/{o.id}", json={"decision": "approve"}).status_code == 409
    assert db.scalar(select(ActivityLog.action).order_by(ActivityLog.id.desc())) == "Approved outgoing sale"


def test_rejecting_needs_a_reason_and_moves_nothing(client, db, world, make_user, login):
    stock(db, world)
    o = pending(db, world)
    as_admin(make_user, login)
    assert client.post(f"/approvals/outgoing/{o.id}", json={"decision": "reject"}).status_code == 422
    r = client.post(f"/approvals/outgoing/{o.id}", json={"decision": "reject", "comment": "Wrong buyer"})
    assert r.json()["status"] == "rejected" and r.json()["comment"] == "Wrong buyer"
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 100.0
    assert client.get("/approvals").json()["counts"]["outgoing"] == 0


def test_two_sales_cannot_overdraw(client, db, world, as_operator):
    stock(db, world, kg=50)
    assert sale(client, world, kg=40).status_code == 201
    r = sale(client, world, kg=40)
    assert r.status_code == 409 and "Only 10.0 kg of Plastic" in r.json()["detail"]
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 10.0


def test_compost_comes_from_finished_batches(client, db, world, as_operator):
    db.add_all([CompostBatch(code="B-90", start_kg=100, finished_at=datetime.now(UTC), produced_kg=30),
                CompostBatch(code="B-91", start_kg=100)])  # still composting: not on hand
    db.commit()
    give = {"type": "compost", "kg": 20, "recipient": "Purok 2 gardens"}
    assert client.post("/outgoing", json=give).status_code == 201
    r = client.post("/outgoing", json=give)
    assert r.status_code == 409 and "finished compost" in r.json()["detail"]


def test_disposal_takes_residual_from_its_area(client, db, world, as_operator):
    stock(db, world, kg=80, material=None, area="area_d")
    o = client.post("/outgoing", json={"type": "disposal", "storage_area_id": world["area_d"], "kg": 80,
                                       "recipient": "City ENRO truck"}).json()
    assert o["material"] == "Residual" and o["total"] is None
    assert material_kg(db, None, world["area_d"]) == 0.0


def test_an_approved_adjustment_sets_stock_to_the_count(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100)
    body = {"material_id": world["mat"]["Plastic"], "storage_area_id": world["area_a"], "actual_kg": 92.5,
            "reason": "Wet bags removed as residual"}
    r = client.post("/inventory/adjustments", json=body)
    assert r.status_code == 201 and r.json()["system_kg"] == 100.0 and r.json()["area_after_kg"] == 92.5
    as_admin(make_user, login)
    assert client.post("/inventory/adjustments", json=body).status_code == 403
    d = client.post(f"/approvals/adjustments/{r.json()['id']}", json={"decision": "approve"})
    assert d.status_code == 200
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 92.5
    rows = db.scalars(select(StockMovement.kg).where(StockMovement.kind == "adjustment")).all()
    assert rows == [-7.5]
    assert client.post(f"/approvals/adjustments/{r.json()['id']}", json={"decision": "reject", "comment": "x"}).status_code == 409


def test_a_rejected_adjustment_changes_nothing(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100)
    r = client.post("/inventory/adjustments", json={"material_id": world["mat"]["Plastic"], "storage_area_id": world["area_a"],
                                                    "actual_kg": 50, "reason": "Recount"}).json()
    as_admin(make_user, login)
    client.post(f"/approvals/adjustments/{r['id']}", json={"decision": "reject", "comment": "Count again"})
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 100.0
    assert db.scalar(select(ActivityLog.action).order_by(ActivityLog.id.desc())) == "Rejected inventory adjustment"
