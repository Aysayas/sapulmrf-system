from sqlalchemy import select

from app.activity.models import ActivityLog
from app.sorting import service as sorting
from app.sorting.schemas import ConfirmIn, SuggestionIn


def deliveries(client, world):
    """One delivery straight from the scale, one the operator corrected."""
    base = {"source_area_id": world["purok1"], "category_id": world["cat"]["Recyclable"], "weighed_by": "manual"}
    plain = client.post("/deliveries", json={**base, "weight_kg": 8.0}).json()
    fixed = client.post("/deliveries", json={**base, "weight_kg": 9.85, "scale_kg": 10.05,
                                             "correction_reason": "Bag touched the edge"}).json()
    return plain, fixed


def classifications(db, world, operator):
    kept, changed = (sorting.create_suggestion(db, None, SuggestionIn(label="Paper", confidence=c)) for c in (0.9, 0.48))
    sorting.confirm(db, kept.id, ConfirmIn(), operator)
    sorting.confirm(db, changed.id, ConfirmIn(final_material_id=world["mat"]["Cardboard"], reason="Wet cardboard"), operator)
    return kept, changed


def test_only_corrected_weights_are_listed_and_a_mark_clears_them(client, db, world, as_operator, make_user, login):
    plain, fixed = deliveries(client, world)
    make_user("maria", role="admin", name="Maria Santos")
    login("maria")
    listed = client.get("/reviews/weights").json()
    assert [d["code"] for d in listed] == [fixed["code"]] and listed[0]["scale_kg"] == 10.05
    assert client.get("/approvals").json()["counts"]["weights"] == 1

    assert client.post(f"/reviews/weights/{fixed['id']}", json={"review": "wrong"}).status_code == 422
    assert client.post(f"/reviews/weights/{plain['id']}", json={"review": "ok"}).status_code == 404
    r = client.post(f"/reviews/weights/{fixed['id']}", json={"review": "recheck"})
    assert r.status_code == 200 and r.json()["weight_kg"] == 9.85  # a mark only
    assert client.get("/reviews/weights").json() == []
    assert client.post(f"/reviews/weights/{fixed['id']}", json={"review": "ok"}).status_code == 409
    assert db.scalar(select(ActivityLog.record).order_by(ActivityLog.id.desc())).endswith("recheck")


def test_only_changed_classifications_are_listed(client, db, world, as_operator, make_user, login):
    kept, changed = classifications(db, world, as_operator)
    make_user("maria", role="admin")
    login("maria")
    listed = client.get("/reviews/classifications").json()
    assert [c["id"] for c in listed] == [changed.id] and listed[0]["final"] == "Cardboard"
    assert client.post(f"/reviews/classifications/{kept.id}", json={"review": "ok"}).status_code == 404
    assert client.post(f"/reviews/classifications/{changed.id}", json={"review": "recheck"}).status_code == 422
    assert client.post(f"/reviews/classifications/{changed.id}", json={"review": "wrong"}).status_code == 200
    assert client.get("/approvals").json()["counts"]["classifications"] == 0


def test_reviews_are_for_admins(client, world, as_operator):
    assert client.get("/reviews/weights").status_code == 403
    assert client.post("/reviews/classifications/1", json={"review": "ok"}).status_code == 403
