from app.sorting import service
from app.sorting.schemas import SuggestionIn


def suggest(db, world, label="Plastic", confidence=0.92):
    return service.create_suggestion(db, None, SuggestionIn(label=label, confidence=confidence, model_version="sim-1",
                                                            image_url="https://example.invalid/plastic.jpg"))


def separated_delivery(client, world, weight=12.0, dry=7.0):
    d = client.post("/deliveries", json={"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"],
                                         "weight_kg": weight, "weighed_by": "manual"}).json()
    client.post(f"/deliveries/{d['id']}/segregation", json={"condition": "mixed", "wet_kg": weight - dry, "dry_kg": dry})
    return d


def test_confirming_unchanged_keeps_the_suggestion(client, world, as_operator, db):
    c = suggest(db, world)
    r = client.post(f"/classifications/{c.id}/confirm", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["final"] == "Plastic" and body["changed"] is False and body["confirmed_by"] == "Juan Dela Cruz"


def test_changing_the_material_is_recorded(client, world, as_operator, db):
    c = suggest(db, world, label="Paper", confidence=0.48)
    r = client.post(f"/classifications/{c.id}/confirm",
                    json={"final_material_id": world["mat"]["Cardboard"], "reason": "Wet cardboard"})
    assert r.json()["final"] == "Cardboard" and r.json()["changed"] is True and r.json()["suggested"] == "Paper"
    assert client.post(f"/classifications/{c.id}/confirm", json={}).status_code == 409


def test_not_recyclable_is_a_change(client, world, as_operator, db):
    c = suggest(db, world)
    r = client.post(f"/classifications/{c.id}/confirm", json={"not_recyclable": True})
    assert r.json()["final"] == "Not recyclable" and r.json()["changed"] is True


def test_unknown_labels_from_the_camera_are_refused(db, world):
    import pytest

    from app.core.errors import AppError

    with pytest.raises(AppError):
        suggest(db, world, label="Glass")


def test_sorting_adds_to_stock_and_finishes_the_delivery(client, world, as_operator, db):
    d = separated_delivery(client, world)
    rows = [{"material_id": world["mat"]["Plastic"], "bags": 2, "kg": 5.0, "storage_area_id": world["area_a"]},
            {"material_id": None, "bags": 1, "kg": 1.5, "storage_area_id": world["area_d"]}]
    r = client.post("/sorting", json={"delivery_id": d["id"], "rows": rows})
    assert r.status_code == 201 and r.json()["status"] == "sorted"
    assert service.stock_kg(db, world["area_a"]) == 5.0
    assert service.stock_kg(db, world["area_d"]) == 1.5
    assert client.post("/sorting", json={"delivery_id": d["id"], "rows": rows}).status_code == 409


def test_sorting_waits_for_the_segregation_check(client, world, as_operator):
    d = client.post("/deliveries", json={"source_area_id": world["purok1"], "category_id": world["cat"]["Recyclable"],
                                         "weight_kg": 3, "weighed_by": "manual"}).json()
    rows = [{"material_id": world["mat"]["Metal"], "bags": 1, "kg": 2, "storage_area_id": world["area_a"]}]
    r = client.post("/sorting", json={"delivery_id": d["id"], "rows": rows})
    assert r.status_code == 409 and "segregation" in r.json()["detail"]


def test_sorted_kg_cannot_exceed_the_dry_waste(client, world, as_operator):
    d = separated_delivery(client, world, weight=12, dry=5)
    rows = [{"material_id": world["mat"]["Paper"], "bags": 3, "kg": 9, "storage_area_id": world["area_a"]}]
    r = client.post("/sorting", json={"delivery_id": d["id"], "rows": rows})
    assert r.status_code == 422 and "dry" in r.json()["detail"]


def test_admins_cannot_sort_or_confirm(client, world, make_user, login, db):
    c = suggest(db, world)
    make_user("msantos", role="admin")
    login("msantos")
    assert client.post(f"/classifications/{c.id}/confirm", json={}).status_code == 403
    assert client.post("/sorting", json={"delivery_id": 1, "rows": []}).status_code == 403
