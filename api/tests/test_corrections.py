from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.corrections.models import Correction
from app.intake.models import Delivery, SegregationCheck
from app.sorting.models import Classification, StockMovement
from app.sorting.service import material_kg

YESTERDAY = datetime.now(UTC) - timedelta(days=1, hours=2)


def sorted_delivery(client, world, kg=5.0, wet=2.0, plastic=2.0, residual=1.0):
    d = client.post("/deliveries", json={"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"],
                                         "weight_kg": kg, "weighed_by": "manual"}).json()
    assert client.post(f"/deliveries/{d['id']}/segregation",
                       json={"condition": "mixed", "wet_kg": wet, "dry_kg": kg - wet}).status_code == 201
    r = client.post("/sorting", json={"delivery_id": d["id"], "rows": [
        {"material_id": world["mat"]["Plastic"], "bags": 2, "kg": plastic, "storage_area_id": world["area_a"]},
        {"material_id": None, "bags": 1, "kg": residual, "storage_area_id": world["area_d"]}]})
    assert r.status_code == 201, r.text
    return d


def undo(client, d, to, reason="Wrong weight"):
    return client.post("/corrections/undo", json={"delivery_id": d["id"], "to": to, "reason": reason})


def test_undo_sort_puts_the_delivery_back_to_be_sorted_and_logs_a_fix(client, db, world, as_operator):
    d = sorted_delivery(client, world)
    db.add(Classification(delivery_id=d["id"], suggested_material_id=world["mat"]["Plastic"], confidence=0.9,
                          final_material_id=world["mat"]["Paper"], changed=True, confirmed_at=datetime.now(UTC)))
    db.commit()
    r = undo(client, d, "sort", "Wrong sort")
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "sort" and r.json()["record_code"] == d["code"] and r.json()["reason"] == "Wrong sort"
    db.expire_all()
    assert db.get(Delivery, d["id"]).status == "separated"
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 0.0
    c = db.scalar(select(Classification).where(Classification.delivery_id == d["id"]))
    assert c.confirmed_at is None and c.final_material_id is None and c.changed is False


def test_undo_to_delivery_walks_the_whole_chain(client, db, world, as_operator):
    d = sorted_delivery(client, world)
    r = undo(client, d, "delivery", "Wrong purok")
    assert r.status_code == 201 and r.json()["kind"] == "delivery"
    s = r.json()["summary"]
    assert d["code"] in s and "Purok 1" in s and "5" in s and "wet 2" in s and "Plastic 2" in s, s
    db.expire_all()
    assert db.get(Delivery, d["id"]) is None
    assert db.scalar(select(func.count()).select_from(SegregationCheck)) == 0
    assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_undo_sort_is_refused_when_its_stock_was_sold(client, db, world, as_operator):
    d = sorted_delivery(client, world)
    sale = client.post("/outgoing", json={"type": "sale", "material_id": world["mat"]["Plastic"], "kg": 1.5,
                                          "storage_area_id": world["area_a"], "recipient": "Buyer", "price_per_kg": 5})
    assert sale.status_code == 201
    r = undo(client, d, "sort")
    assert r.status_code == 409 and "Area A" in r.json()["detail"] and "Plastic" in r.json()["detail"]
    db.expire_all()
    assert db.get(Delivery, d["id"]).status == "sorted"


def test_operators_fix_only_todays_steps_admins_any_day(client, db, world, make_user, login, as_operator):
    d = sorted_delivery(client, world)
    db.query(Delivery).filter_by(id=d["id"]).update({"received_at": YESTERDAY})  # received yesterday, sorted today
    db.commit()
    assert undo(client, d, "sort").status_code == 201
    r = undo(client, d, "delivery")
    assert r.status_code == 403 and "today" in r.json()["detail"]
    make_user("maria", role="admin")
    login("maria")
    r = undo(client, d, "delivery")
    assert r.status_code == 201 and r.json()["review"] == "ok"  # the admin's own fix isn't left for their review


def test_a_second_undo_of_the_same_step_is_409(client, db, world, as_operator):
    d = sorted_delivery(client, world)
    assert undo(client, d, "sort").status_code == 201
    assert undo(client, d, "sort").status_code == 409


def test_fixable_lists_todays_deliveries_with_their_stage(client, db, world, as_operator):
    d = sorted_delivery(client, world)
    old = Delivery(code="D-0OLD", source_area_id=world["purok1"], category_id=world["cat"]["Residual"], weight_kg=1,
                   weighed_by="manual", received_at=YESTERDAY)
    db.add(old)
    db.commit()
    rows = client.get("/corrections/fixable").json()
    assert [(x["code"], x["stage"]) for x in rows] == [(d["code"], "sorted")]


def test_a_kiosk_drop_off_that_replaces_one_links_the_fix(client, db, world, as_operator, make_user, login):
    from app.core.security import token_hash
    from app.devices.models import Device
    d = sorted_delivery(client, world)
    assert undo(client, d, "sort", "Wrong material").status_code == 201
    assert undo(client, d, "delivery", "Wrong purok").status_code == 201
    db.add(Device(code="KIOSK-T", type="weighing_station", key_hash=token_hash("kiosk-key")))
    db.commit()
    for _ in range(2):  # the second is a resend of the same drop-off (no photo): it links nothing more
        r = client.post("/devices/deliveries", headers={"X-Device-Key": "kiosk-key"}, json={
            "source_area": "Purok 2", "category": "Mixed household", "weight_kg": 5, "weighed_by": "manual",
            "client_key": "replace-1", "replaces": d["code"]})
        assert r.status_code == 201, r.text
    db.expire_all()
    linked = dict(db.execute(select(Correction.kind, Correction.redone_as).where(Correction.record_code == d["code"])).all())
    assert linked == {"delivery": r.json()["code"], "sort": None}  # only the removed delivery was recorded again


def test_admin_marks_a_fix_ok_or_wrong_once(client, db, world, as_operator, make_user, login):
    d = sorted_delivery(client, world)
    fix = undo(client, d, "sort").json()
    make_user("maria", role="admin")
    login("maria")
    assert client.get("/approvals").json()["counts"]["fixes"] == 1
    assert client.post(f"/corrections/{fix['id']}/review", json={"review": "wrong"}).json()["review"] == "wrong"
    assert client.post(f"/corrections/{fix['id']}/review", json={"review": "ok"}).status_code == 409
    assert client.get("/approvals").json()["counts"]["fixes"] == 0


def test_undo_sort_is_refused_when_its_bags_left_the_area(client, db, world, as_operator):
    d = sorted_delivery(client, world)  # put 2 bags of plastic in Area A
    db.add(StockMovement(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], kg=0, bags=-2,
                         kind="adjustment", note="bags taken"))
    db.commit()
    r = undo(client, d, "sort")
    assert r.status_code == 409 and "0 bags left" in r.json()["detail"]
