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


def test_date_range_is_inclusive_manila_days(client, make_user, login, db):
    from app.operations.service import TZ

    make_user("msantos", role="admin")
    day = datetime(2026, 3, 10, tzinfo=TZ)
    for label, at in [("before", day - timedelta(minutes=1)), ("start", day), ("end", day + timedelta(hours=23, minutes=59)),
                      ("after", day + timedelta(days=1))]:
        db.add(ActivityLog(user_id=None, action=label, at=at))
    db.commit()
    login("msantos")
    got = client.get("/activity?from=2026-03-10&to=2026-03-10").json()
    assert sorted(i["action"] for i in got) == ["end", "start"]
    open_ended = client.get("/activity?from=2026-03-10").json()
    assert sorted(i["action"] for i in open_ended if i["action"] in ("before", "after", "end")) == ["after", "end"]


def test_category_filter_and_csv_match(client, make_user, login, db):
    make_user("msantos", role="admin")
    for action in ["Logged in", "Created user", "Approved outgoing sale", "Rejected inventory adjustment",
                   "Exported income report as PDF", "Viewed intake report", "Recorded delivery", "Reported a problem"]:
        db.add(ActivityLog(user_id=None, action=action))
    db.commit()
    login("msantos")

    def actions(cat):
        return {i["action"] for i in client.get(f"/activity?category={cat}&limit=500").json()
                if i["action"] != "Logged in" or cat == "logins"}

    assert actions("logins") == {"Logged in"}
    assert actions("users") == {"Created user"}
    assert actions("approvals") == {"Approved outgoing sale", "Rejected inventory adjustment"}
    assert actions("reports") == {"Exported income report as PDF", "Viewed intake report"}
    assert {"Recorded delivery", "Reported a problem"} <= actions("records")
    assert not actions("records") & {"Created user", "Viewed intake report", "Approved outgoing sale"}
    assert client.get("/activity?category=nonsense").status_code == 422

    r = client.get("/activity/export?category=approvals")
    assert r.headers["content-type"].startswith("text/csv") and "activity-log.csv" in r.headers["content-disposition"]
    import csv
    import io
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0] == ["When", "Who", "Action", "Record"]
    assert {row[2] for row in rows[1:]} == {"Approved outgoing sale", "Rejected inventory adjustment"}


def test_export_is_admin_only(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/activity/export").status_code == 403
