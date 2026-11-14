from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.activity.models import ActivityLog
from app.approvals.models import Outgoing
from app.compost.models import CompostBatch
from app.intake.models import Delivery
from app.sorting.models import StockMovement
from app.sorting.schemas import SortRow
from app.sorting.service import material_bags, material_kg
from app.users.models import User
from tests.test_approvals import as_admin, stock

KEY = "a" * 32


def adjustment(client, world, kg):
    body = {"material_id": world["mat"]["Plastic"], "storage_area_id": world["area_a"], "actual_kg": kg, "reason": "Recount"}
    return client.post("/inventory/adjustments", json=body).json()


def test_a_stale_adjustment_cant_be_approved(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100)
    r = adjustment(client, world, 90)
    stock(db, world, kg=-50, bags=0)  # sold before the admin decides
    as_admin(make_user, login)
    d = client.post(f"/approvals/adjustments/{r['id']}", json={"decision": "approve"})
    assert d.status_code == 409 and "changed" in d.json()["detail"]
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 50.0
    reject = {"decision": "reject", "comment": "Count again"}
    assert client.post(f"/approvals/adjustments/{r['id']}", json=reject).status_code == 200


@pytest.mark.parametrize("actual,bags_left", [(0, 0), (50, 5), (120, 10)])
def test_adjustments_keep_bags_in_step(client, db, world, as_operator, make_user, login, actual, bags_left):
    stock(db, world, kg=100, bags=10)
    r = adjustment(client, world, actual)
    as_admin(make_user, login)
    assert client.post(f"/approvals/adjustments/{r['id']}", json={"decision": "approve"}).status_code == 200
    assert material_bags(db, world["mat"]["Plastic"], world["area_a"]) == bags_left


def test_a_resent_delivery_records_once(client, db, world, as_operator):
    body = {"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"], "weight_kg": 8,
            "weighed_by": "manual", "client_key": KEY}
    a, b = client.post("/deliveries", json=body), client.post("/deliveries", json=body)
    assert a.status_code == b.status_code == 201 and a.json()["code"] == b.json()["code"]
    assert db.scalar(select(func.count(Delivery.id))) == 1
    assert db.scalar(select(func.count(ActivityLog.id)).where(ActivityLog.action == "Recorded delivery")) == 1
    other = client.post("/deliveries", json={**body, "client_key": "b" * 32})
    assert other.json()["code"] != a.json()["code"]


def test_deliveries_without_a_key_still_record_each_time(client, db, world, as_operator):
    body = {"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"], "weight_kg": 8,
            "weighed_by": "manual"}
    client.post("/deliveries", json=body), client.post("/deliveries", json=body)
    assert db.scalar(select(func.count(Delivery.id))) == 2


def test_a_resent_outgoing_records_once(client, db, world, as_operator):
    stock(db, world)
    body = {"type": "sale", "material_id": world["mat"]["Plastic"], "kg": 10, "storage_area_id": world["area_a"],
            "recipient": "Buyer A", "price_per_kg": 12.5, "client_key": KEY}
    a, b = client.post("/outgoing", json=body), client.post("/outgoing", json=body)
    assert a.status_code == b.status_code == 201 and a.json()["code"] == b.json()["code"]
    assert db.scalar(select(func.count(Outgoing.id))) == 1


def test_a_resent_transfer_moves_stock_once(client, db, world, as_operator):
    stock(db, world, kg=100)
    body = {"material_id": world["mat"]["Plastic"], "from_area_id": world["area_a"], "to_area_id": world["area_d"],
            "kg": 20, "client_key": KEY}
    a, b = client.post("/inventory/transfers", json=body), client.post("/inventory/transfers", json=body)
    assert a.status_code == b.status_code == 200 or a.status_code == b.status_code == 201
    assert a.json()["kg"] == b.json()["kg"] == 20 and b.json()["bags"] == a.json()["bags"]
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 80.0
    assert db.scalar(select(func.count(StockMovement.id)).where(StockMovement.kind == "transfer")) == 2


def test_giving_out_compost_holds_a_lock_other_connections_see(client, db, engine, world, as_operator):
    db.add(CompostBatch(code="B-90", start_kg=100, finished_at=datetime.now(UTC), produced_kg=30))
    db.commit()
    assert client.post("/outgoing", json={"type": "compost", "kg": 20, "recipient": "Gardens"}).status_code == 201
    with engine.connect() as other:  # the test's transaction is still open, so its lock is still held
        assert other.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext('compost'))")) is False
        other.rollback()


def test_a_storage_area_holding_stock_cant_be_deactivated(client, db, world, make_user, login):
    stock(db, world, kg=20)
    as_admin(make_user, login)
    r = client.patch(f"/masterdata/storage-areas/{world['area_a']}", json={"active": False})
    assert r.status_code == 409 and "20" in r.json()["detail"]
    assert client.patch(f"/masterdata/storage-areas/{world['area_a']}", json={"name": "Area A2"}).status_code == 200
    assert client.patch(f"/masterdata/storage-areas/{world['area_d']}", json={"active": False}).status_code == 200


def test_null_user_fields_change_nothing(client, db, make_user, login):
    make_user("maria", role="admin")
    login("maria")
    u = make_user("pedro", name="Pedro")
    r = client.patch(f"/users/{u.id}", json={"name": None, "username": None, "role": None, "active": None})
    assert r.status_code == 200
    assert db.get(User, u.id).name == "Pedro"


def test_amounts_that_cant_be_stored_are_refused(client, db, world, as_operator):
    d = {"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"], "weight_kg": 0.001,
         "weighed_by": "manual"}
    assert client.post("/deliveries", json=d).status_code == 422
    sale = {"type": "sale", "material_id": world["mat"]["Plastic"], "storage_area_id": world["area_a"], "recipient": "A"}
    assert client.post("/outgoing", json={**sale, "kg": 0.001, "price_per_kg": 5}).status_code == 422
    assert client.post("/outgoing", json={**sale, "kg": 1, "price_per_kg": 0.001}).status_code == 422
    assert client.post("/outgoing", json={**sale, "kg": 50000, "price_per_kg": 100000}).status_code == 422
    with pytest.raises(ValidationError):
        SortRow(material_id=None, bags=0, kg=0.001, storage_area_id=1)


def test_a_partial_count_leaves_at_least_one_bag(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=100, bags=3)
    r = adjustment(client, world, 10)
    as_admin(make_user, login)
    assert client.post(f"/approvals/adjustments/{r['id']}", json={"decision": "approve"}).status_code == 200
    assert material_bags(db, world["mat"]["Plastic"], world["area_a"]) == 1


def test_a_count_cant_add_stock_to_an_inactive_area(client, db, world, as_operator, make_user, login):
    r = adjustment(client, world, 10)
    as_admin(make_user, login)
    assert client.patch(f"/masterdata/storage-areas/{world['area_a']}", json={"active": False}).status_code == 200
    d = client.post(f"/approvals/adjustments/{r['id']}", json={"decision": "approve"})
    assert d.status_code == 409 and "no longer active" in d.json()["detail"]


def test_a_resent_transfer_still_answers_after_the_area_closes(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=20)
    body = {"material_id": world["mat"]["Plastic"], "from_area_id": world["area_a"], "to_area_id": world["area_d"],
            "kg": 20, "client_key": KEY}
    assert client.post("/inventory/transfers", json=body).json()["kg"] == 20
    as_admin(make_user, login)
    assert client.patch(f"/masterdata/storage-areas/{world['area_a']}", json={"active": False}).status_code == 200
    login("juan")
    assert client.post("/inventory/transfers", json=body).json()["kg"] == 20


def test_a_total_that_only_overflows_after_rounding_is_refused(client, db, world, as_operator):
    sale = {"type": "sale", "material_id": world["mat"]["Plastic"], "storage_area_id": world["area_a"], "recipient": "A"}
    assert client.post("/outgoing", json={**sale, "kg": 50000, "price_per_kg": 1999.999}).status_code == 422
