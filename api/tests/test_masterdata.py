from sqlalchemy import select

from app.activity.models import ActivityLog


def as_admin(make_user, login):
    make_user("msantos", role="admin")
    login("msantos")


def test_categories_and_materials_are_seeded(client, make_user, login):
    as_admin(make_user, login)
    cats = [c["name"] for c in client.get("/masterdata/categories").json()]
    assert {"Biodegradable", "Recyclable", "Residual", "Special waste", "Mixed household"} <= set(cats)
    mats = [m["name"] for m in client.get("/masterdata/materials").json()]
    assert {"Plastic", "Paper", "Cardboard", "Metal"} <= set(mats)
    assert client.get("/masterdata/puroks").json() == []


def test_admin_adds_a_purok_and_a_storage_area(client, make_user, login):
    as_admin(make_user, login)
    r = client.post("/masterdata/puroks", json={"name": "Purok 1"})
    assert r.status_code == 201 and r.json()["name"] == "Purok 1" and r.json()["active"] is True
    r = client.post("/masterdata/storage-areas", json={"name": "Area A · Plastics", "capacity_kg": 500})
    assert r.status_code == 201
    assert r.json()["capacity_kg"] == 500 and r.json()["alert_pct"] == 90


def test_storage_areas_need_a_capacity(client, make_user, login):
    as_admin(make_user, login)
    assert client.post("/masterdata/storage-areas", json={"name": "Area B"}).status_code == 422
    assert client.post("/masterdata/storage-areas", json={"name": "Area B", "capacity_kg": 0}).status_code == 422


def test_names_are_unique_ignoring_case(client, make_user, login):
    as_admin(make_user, login)
    client.post("/masterdata/puroks", json={"name": "Purok 1"})
    r = client.post("/masterdata/puroks", json={"name": "purok 1"})
    assert r.status_code == 409
    assert "already" in r.json()["detail"]


def test_deactivated_items_leave_the_pick_list_but_stay_listed(client, make_user, login):
    as_admin(make_user, login)
    pid = client.post("/masterdata/puroks", json={"name": "Purok 9"}).json()["id"]
    assert client.patch(f"/masterdata/puroks/{pid}", json={"active": False}).json()["active"] is False
    assert "Purok 9" not in [p["name"] for p in client.get("/masterdata/puroks?active=true").json()]
    assert "Purok 9" in [p["name"] for p in client.get("/masterdata/puroks").json()]


def test_rename_and_unknown_kinds(client, make_user, login):
    as_admin(make_user, login)
    pid = client.post("/masterdata/puroks", json={"name": "Purok 2"}).json()["id"]
    assert client.patch(f"/masterdata/puroks/{pid}", json={"name": "Purok 2 · Sampaguita"}).status_code == 200
    assert client.patch("/masterdata/puroks/9999", json={"name": "X"}).status_code == 404
    assert client.get("/masterdata/payroll").status_code == 422


def test_everyone_logged_in_can_read_but_only_admins_change(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/masterdata/categories").status_code == 200
    assert client.post("/masterdata/puroks", json={"name": "Purok 1"}).status_code == 403
    client.post("/auth/logout")
    assert client.get("/masterdata/categories").status_code == 401


def test_changes_are_logged(client, make_user, login, db):
    as_admin(make_user, login)
    pid = client.post("/masterdata/puroks", json={"name": "Purok 3"}).json()["id"]
    client.patch(f"/masterdata/puroks/{pid}", json={"active": False})
    client.patch(f"/masterdata/puroks/{pid}", json={"active": True})
    actions = db.scalars(select(ActivityLog.action).order_by(ActivityLog.id)).all()
    assert actions[-3:] == ["Added source area", "Deactivated source area", "Reactivated source area"]
