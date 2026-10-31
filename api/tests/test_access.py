from sqlalchemy import select

from app.activity.models import ActivityLog


def setup(make_user, login):
    make_user("msantos", role="admin")
    staff = make_user("rreyes", role="staff", name="Rosa Reyes")
    make_user("juan", role="operator")
    login("msantos")
    return staff


def test_staff_start_with_every_screen_off(client, make_user, login):
    setup(make_user, login)
    body = client.get("/access").json()
    assert [s["key"] for s in body["screens"]] == ["segregation", "predictions", "alerts", "camera", "reports"]
    assert [p["username"] for p in body["staff"]] == ["rreyes"]  # only staff are listed
    assert body["staff"][0]["grants"] == {"segregation": False, "predictions": False, "alerts": False, "camera": False,
                                         "reports": False}


def test_admin_grants_and_removes_screens(client, make_user, login):
    staff = setup(make_user, login)
    r = client.put(f"/access/{staff.id}", json={"grants": {"camera": True, "alerts": True}})
    assert r.status_code == 200
    assert r.json()["grants"] == {"segregation": False, "predictions": False, "alerts": True, "camera": True, "reports": False}
    client.put(f"/access/{staff.id}", json={"grants": {"camera": False}})
    assert client.get("/access").json()["staff"][0]["grants"]["camera"] is False


def test_only_staff_accounts_get_per_person_screens(client, make_user, login, db):
    setup(make_user, login)
    operator_id = next(u["id"] for u in client.get("/users").json() if u["username"] == "juan")
    assert client.put(f"/access/{operator_id}", json={"grants": {"camera": True}}).status_code == 400
    assert client.put("/access/9999", json={"grants": {"camera": True}}).status_code == 404


def test_unknown_screens_are_rejected(client, make_user, login):
    staff = setup(make_user, login)
    assert client.put(f"/access/{staff.id}", json={"grants": {"payroll": True}}).status_code == 422


def test_non_admins_cannot_read_or_change_access(client, make_user, login):
    make_user("rreyes", role="staff")
    login("rreyes")
    assert client.get("/access").status_code == 403


def test_access_changes_are_logged(client, make_user, login, db):
    staff = setup(make_user, login)
    client.put(f"/access/{staff.id}", json={"grants": {"camera": True}})
    row = db.scalar(select(ActivityLog).where(ActivityLog.action == "Changed staff access"))
    assert row and "Rosa Reyes" in row.record and "camera on" in row.record
