from datetime import UTC, datetime

from sqlalchemy import select

from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.alerts.models import Alert
from app.devices.models import Device


def alert(db, title="Area A almost full", kind="storage", subject_id=1, resolved=False):
    a = Alert(kind=kind, subject_id=subject_id, title=title, details="92% of 500 kg", opened_at=datetime.now(UTC),
              resolved_at=datetime.now(UTC) if resolved else None)
    db.add(a)
    db.commit()
    return a


def test_acknowledging_moves_an_alert_but_keeps_it_open(client, db, make_user, login):
    a = alert(db)
    make_user("maria", role="admin", name="Maria Santos")
    login("maria")
    assert [x["title"] for x in client.get("/alerts").json()] == ["Area A almost full"]
    r = client.post(f"/alerts/{a.id}/acknowledge")
    assert r.status_code == 200 and r.json()["acknowledged_by"] == "Maria Santos" and r.json()["resolved_at"] is None
    assert client.get("/alerts").json() == []
    assert [x["id"] for x in client.get("/alerts?state=acknowledged").json()] == [a.id]
    assert client.post(f"/alerts/{a.id}/acknowledge").status_code == 409
    assert client.get("/alerts/summary").json()["open_alerts"] == 1  # still open until the condition clears
    assert db.scalar(select(ActivityLog.action).order_by(ActivityLog.id.desc())) == "Acknowledged alert"


def test_resolved_alerts_are_listed_separately_and_cannot_be_acknowledged(client, db, make_user, login):
    done = alert(db, resolved=True)
    make_user("juan", role="operator")
    login("juan")
    assert [x["id"] for x in client.get("/alerts?state=resolved").json()] == [done.id]
    assert client.post(f"/alerts/{done.id}/acknowledge").status_code == 409


def test_staff_see_alerts_only_with_the_grant_and_never_acknowledge(client, db, make_user, login):
    a = alert(db)
    staff = make_user("rreyes", role="staff")
    login("rreyes")
    assert client.get("/alerts").status_code == 403
    db.add(StaffAccess(user_id=staff.id, screen="alerts", granted=True))
    db.commit()
    assert client.get("/alerts").status_code == 200
    assert client.get("/alerts/summary").json()["open_reports"] == 0
    assert client.post(f"/alerts/{a.id}/acknowledge").status_code == 403


def test_summary_counts_by_kind_and_lists_the_latest(client, db, make_user, login):
    alert(db, "Compost B-04 above range", kind="compost", subject_id=4)
    alert(db, "Area B almost full", subject_id=2)
    alert(db, "Old", subject_id=3, resolved=True)
    make_user("maria", role="admin")
    login("maria")
    s = client.get("/alerts/summary").json()
    assert s["open_alerts"] == 2 and s["by_kind"] == {"compost": 1, "storage": 1} and s["unacknowledged"] == 2
    assert [i["title"] for i in s["latest"]] == ["Area B almost full", "Compost B-04 above range"]
    o = client.get("/overview").json()
    assert o["open_alerts"] == {"compost": 1, "storage": 1} and o["alert_batch_ids"] == [4]


def test_operators_report_problems_and_admins_resolve_them(client, db, make_user, login):
    ws = Device(code="WS-01", type="weighing_station", key_hash="a" * 64)
    db.add(ws)
    db.commit()
    make_user("juan", role="operator", name="Juan Dela Cruz")
    make_user("maria", role="admin", name="Maria Santos")
    login("juan")
    assert client.post("/problems", json={"kind": "device", "details": "Screen blank"}).status_code == 422  # which device?
    assert client.post("/problems", json={"kind": "record", "details": "Typo"}).status_code == 422  # which record?
    r = client.post("/problems", json={"kind": "device", "device_id": ws.id, "details": "Screen blank"})
    assert r.status_code == 201 and r.json()["code"].startswith("R-") and r.json()["device"] == "WS-01"
    rec = client.post("/problems", json={"kind": "record", "record_ref": "d-0139", "details": "Should be 4.10 kg"}).json()
    assert rec["record_ref"] == "D-0139"
    assert client.get("/problems").status_code == 403

    login("maria")
    assert client.post("/problems", json={"kind": "record", "record_ref": "D-1", "details": "x"}).status_code == 403
    assert [p["code"] for p in client.get("/problems").json()] == [rec["code"], r.json()["code"]]
    assert client.get("/alerts/summary").json()["open_reports"] == 2
    pid = r.json()["id"]
    assert client.post(f"/problems/{pid}/resolve", json={"note": " "}).status_code == 422
    done = client.post(f"/problems/{pid}/resolve", json={"note": "Restarted the station"})
    assert done.json()["status"] == "resolved" and done.json()["resolved_by"] == "Maria Santos"
    assert client.post(f"/problems/{pid}/resolve", json={"note": "again"}).status_code == 409
    assert [p["code"] for p in client.get("/problems?status=resolved").json()] == [r.json()["code"]]
