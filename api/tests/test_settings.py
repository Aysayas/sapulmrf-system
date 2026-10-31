from sqlalchemy import select

from app.activity.models import ActivityLog

DEFAULTS = {"compost_temp_min": 45.0, "compost_temp_max": 65.0, "moisture_min": 40.0, "moisture_max": 60.0,
            "prediction_min_days": 30, "anomaly_pct": 2.0}


def as_admin(make_user, login):
    make_user("msantos", role="admin")
    login("msantos")


def test_defaults_load(client, make_user, login):
    as_admin(make_user, login)
    assert client.get("/settings").json() == DEFAULTS


def test_admin_saves_ranges_and_area_limits_together(client, make_user, login):
    as_admin(make_user, login)
    area = client.post("/masterdata/storage-areas", json={"name": "Area A", "capacity_kg": 500}).json()
    limits = [{"id": area["id"], "capacity_kg": 600, "alert_pct": 85}]
    body = {**DEFAULTS, "compost_temp_max": 68, "storage_areas": limits}
    r = client.put("/settings", json=body)
    assert r.status_code == 200 and r.json()["compost_temp_max"] == 68
    saved = next(a for a in client.get("/masterdata/storage-areas").json() if a["id"] == area["id"])
    assert saved["capacity_kg"] == 600 and saved["alert_pct"] == 85


def test_each_minimum_must_be_below_its_maximum(client, make_user, login):
    as_admin(make_user, login)
    r = client.put("/settings", json={**DEFAULTS, "compost_temp_min": 70})
    assert r.status_code == 422
    assert "temperature" in str(r.json()["detail"]).lower()
    assert client.put("/settings", json={**DEFAULTS, "moisture_min": 60}).status_code == 422
    assert client.put("/settings", json={**DEFAULTS, "anomaly_pct": 0}).status_code == 422


def test_unknown_storage_area_is_404(client, make_user, login):
    as_admin(make_user, login)
    r = client.put("/settings", json={**DEFAULTS, "storage_areas": [{"id": 9999, "capacity_kg": 1, "alert_pct": 90}]})
    assert r.status_code == 404


def test_operators_can_read_but_not_change(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/settings").status_code == 200
    assert client.put("/settings", json=DEFAULTS).status_code == 403


def test_saving_is_logged_with_what_changed(client, make_user, login, db):
    as_admin(make_user, login)
    client.put("/settings", json={**DEFAULTS, "moisture_max": 62})
    row = db.scalar(select(ActivityLog).where(ActivityLog.action == "Changed ranges and limits"))
    assert row and "moisture_max 60.0 → 62.0" in row.record
