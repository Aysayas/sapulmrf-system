from datetime import UTC, datetime, timedelta

from test_approvals import as_admin, sale, stock

from app.approvals.models import Outgoing
from app.compost.models import CompostBatch
from app.operations.service import income_since, month_start
from app.sorting.service import material_kg


def test_a_sale_leaves_stock_at_once_and_waits_for_review(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=10)
    r = sale(client, world, kg=4, price=12)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "approved" and r.json()["review"] is None and r.json()["total"] == 48.0
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 6.0
    as_admin(make_user, login)
    body = client.get("/approvals").json()
    assert body["counts"]["outgoing_review"] == 1 and [o["code"] for o in body["outgoing_review"]] == [r.json()["code"]]


def test_selling_more_than_the_area_holds_is_refused(client, db, world, as_operator):
    stock(db, world, kg=10)
    r = sale(client, world, kg=11)
    assert r.status_code == 409 and "Only 10.0 kg" in r.json()["detail"]
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 10.0


def test_reverse_puts_stock_back_and_income_drops_on_the_reversal_day(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=10)
    o = sale(client, world, kg=4, price=12).json()
    earlier = month_start(1)  # the sale happened last month; the reversal is today
    db.query(Outgoing).filter_by(id=o["id"]).update({"decided_at": earlier, "requested_at": earlier})
    db.commit()
    as_admin(make_user, login)
    r = client.post(f"/approvals/outgoing/{o['id']}/review", json={"decision": "reverse", "comment": "Buyer returned it"})
    assert r.status_code == 200 and r.json()["review"] == "reversed"
    db.expire_all()
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 10.0
    assert income_since(db, earlier) == 0.0          # last month +48, this month -48
    assert income_since(db, month_start()) == -48.0  # the reversal lands on its own day
    assert client.get("/approvals").json()["counts"]["outgoing_review"] == 0


def test_a_reviewed_or_pending_row_cannot_be_reviewed(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=10)
    o = sale(client, world, kg=2).json()
    old = Outgoing(code="O-9999", type="disposal", storage_area_id=world["area_a"], kg=1, recipient="x")  # old flow
    db.add(old)
    db.commit()
    as_admin(make_user, login)
    assert client.post(f"/approvals/outgoing/{o['id']}/review", json={"decision": "ok"}).status_code == 200
    again = client.post(f"/approvals/outgoing/{o['id']}/review", json={"decision": "reverse"})
    assert again.status_code == 409 and "already reviewed" in again.json()["detail"]
    assert client.post(f"/approvals/outgoing/{old.id}/review", json={"decision": "ok"}).status_code == 409


def test_compost_given_out_then_reversed_is_on_hand_again(client, db, world, as_operator, make_user, login):
    db.add(CompostBatch(code="B-1", start_kg=20, finished_at=datetime.now(UTC) - timedelta(days=1), produced_kg=10))
    db.commit()
    r = client.post("/outgoing", json={"type": "compost", "kg": 6, "recipient": "Purok 1 gardens"})
    assert r.status_code == 201
    assert client.post("/outgoing", json={"type": "compost", "kg": 5, "recipient": "x"}).status_code == 409
    as_admin(make_user, login)
    client.post(f"/approvals/outgoing/{r.json()['id']}/review", json={"decision": "reverse", "comment": "not taken"})
    assert client.get("/operations/outgoing").json()["compost_on_hand_kg"] == 10.0


def test_recipients_are_the_recent_distinct_names_for_that_type(client, db, world, as_operator):
    stock(db, world, kg=100)
    for name in ["A", "B", "A", "C", "D", "E", "F", "G", "H", "I"]:
        client.post("/outgoing", json={"type": "sale", "material_id": world["mat"]["Plastic"], "kg": 1,
                                       "storage_area_id": world["area_a"], "recipient": name, "price_per_kg": 1})
    assert client.get("/outgoing/recipients?type=sale").json() == ["I", "H", "G", "F", "E", "D", "C", "A"]
    assert client.get("/outgoing/recipients?type=compost").json() == []


def test_admins_can_record_outgoing_too(client, db, world, make_user, login):
    stock(db, world, kg=10)
    as_admin(make_user, login)
    assert sale(client, world, kg=1).status_code == 201
