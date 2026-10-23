from sqlalchemy import select

from app.activity.models import ActivityLog


def delivery(world, **over):
    body = {"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"], "weight_kg": 12.4,
            "weighed_by": "scale"}
    return {**body, **over}


def test_operator_records_a_delivery(client, world, as_operator, db):
    r = client.post("/deliveries", json=delivery(world))
    assert r.status_code == 201
    d = r.json()
    assert d["code"] == f"D-{d['id']:04d}" and d["status"] == "awaiting"
    assert d["source_area"] == "Purok 1" and d["category"] == "Mixed household" and d["weight_kg"] == 12.4
    assert db.scalar(select(ActivityLog.action).order_by(ActivityLog.id.desc())) == "Recorded delivery"


def test_a_corrected_scale_reading_needs_a_reason(client, world, as_operator):
    assert client.post("/deliveries", json=delivery(world, weight_kg=12.1, scale_kg=12.4)).status_code == 422
    r = client.post("/deliveries", json=delivery(world, weight_kg=12.1, scale_kg=12.4, correction_reason="Bag on edge"))
    assert r.status_code == 201 and r.json()["corrected"] is True and r.json()["scale_kg"] == 12.4


def test_weights_and_picks_are_checked(client, world, as_operator, db):
    assert client.post("/deliveries", json=delivery(world, weight_kg=0)).status_code == 422
    assert client.post("/deliveries", json=delivery(world, weight_kg=-3)).status_code == 422
    assert client.post("/deliveries", json=delivery(world, source_area_id=9999)).status_code == 422
    client.post("/auth/logout")


def test_only_operators_record(client, world, make_user, login):
    make_user("msantos", role="admin")
    login("msantos")
    assert client.post("/deliveries", json=delivery(world)).status_code == 403


def test_segregation_check_moves_the_delivery_on(client, world, as_operator):
    d = client.post("/deliveries", json=delivery(world)).json()
    r = client.post(f"/deliveries/{d['id']}/segregation", json={"condition": "mixed", "wet_kg": 4.85, "dry_kg": 7.4})
    assert r.status_code == 201
    assert r.json()["status"] == "separated" and r.json()["segregation"]["condition"] == "mixed"


def test_a_delivery_is_checked_only_once(client, world, as_operator):
    d = client.post("/deliveries", json=delivery(world)).json()
    body = {"condition": "segregated", "wet_kg": 4, "dry_kg": 8}
    assert client.post(f"/deliveries/{d['id']}/segregation", json=body).status_code == 201
    assert client.post(f"/deliveries/{d['id']}/segregation", json=body).status_code == 409


def test_wet_plus_dry_cannot_be_far_above_what_was_received(client, world, as_operator):
    d = client.post("/deliveries", json=delivery(world, weight_kg=10)).json()
    r = client.post(f"/deliveries/{d['id']}/segregation", json={"condition": "mixed", "wet_kg": 8, "dry_kg": 8})
    assert r.status_code == 422
    assert "more than" in r.json()["detail"]
    missing = client.post("/deliveries/9999/segregation", json={"condition": "mixed", "wet_kg": 1, "dry_kg": 1})
    assert missing.status_code == 404
