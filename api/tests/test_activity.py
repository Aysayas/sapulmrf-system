from datetime import UTC, datetime, timedelta

from app.activity.models import ActivityLog


def test_newest_first_with_who_did_it(client, make_user, login, db):
    admin = make_user("msantos", role="admin", name="Maria Santos")
    login("msantos")
    rosa = {"name": "Rosa Reyes", "username": "rreyes", "role": "staff", "password": "temporary123"}
    client.post("/users", json=rosa)
    items = client.get("/activity").json()
    assert [i["action"] for i in items[:2]] == ["Created user", "Logged in"]
    assert items[0]["who"] == "Maria Santos" and items[0]["user_id"] == admin.id
    assert "Rosa Reyes" in items[0]["record"]


def test_filters_by_user_and_days(client, make_user, login, db):
    admin = make_user("msantos", role="admin")
    other = make_user("juan", role="operator")
    db.add(ActivityLog(user_id=other.id, action="Old thing", at=datetime.now(UTC) - timedelta(days=10)))
    db.add(ActivityLog(user_id=None, action="System thing"))
    db.commit()
    login("msantos")
    assert [i["action"] for i in client.get(f"/activity?user_id={other.id}").json()] == ["Old thing"]
    recent = [i["action"] for i in client.get("/activity?days=7").json()]
    assert "Old thing" not in recent and "System thing" in recent
    system = next(i for i in client.get("/activity").json() if i["action"] == "System thing")
    assert system["who"] == "System"
    assert all(i["user_id"] == admin.id for i in client.get(f"/activity?user_id={admin.id}").json())


def test_only_admins_read_the_log(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/activity").status_code == 403
