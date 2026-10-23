from datetime import UTC, datetime, timedelta

from app.alerts.models import ProblemReport
from app.approvals.models import AdjustmentRequest
from app.devices.models import Device
from app.sorting.models import StockMovement


def test_operators_see_only_their_own_requests_newest_first(client, db, world, make_user, login):
    juan, pedro = make_user("juan", role="operator"), make_user("pedro", role="operator")
    db.add(StockMovement(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], kg=100, kind="sorted"))
    db.commit()
    login("pedro")
    body = {"material_id": world["mat"]["Plastic"], "storage_area_id": world["area_a"], "actual_kg": 90, "reason": "Recount"}
    assert client.post("/inventory/adjustments", json=body).status_code == 201
    login("juan")
    first = client.post("/inventory/adjustments", json={**body, "actual_kg": 95}).json()
    second = client.post("/inventory/adjustments", json={**body, "actual_kg": 97}).json()
    old = AdjustmentRequest(material_id=None, storage_area_id=world["area_a"], system_kg=0, actual_kg=1, reason="Old",
                            requested_by=juan.id, requested_at=datetime.now(UTC) - timedelta(days=40))
    db.add(old)
    db.commit()

    mine = client.get("/inventory/adjustments/mine").json()
    assert [r["id"] for r in mine] == [second["id"], first["id"]]
    assert mine[0]["status"] == "pending" and mine[0]["actual_kg"] == 97
    assert len(client.get("/inventory/adjustments/mine?days=60").json()) == 3
    assert pedro.id != juan.id


def test_operators_see_only_their_own_problem_reports(client, db, make_user, login):
    juan, pedro = make_user("juan", role="operator"), make_user("pedro", role="operator")
    db.add(ProblemReport(code="R-T1", kind="record", record_ref="D-0001", details="old", reported_by=juan.id,
                         reported_at=datetime.now(UTC) - timedelta(days=40)))
    db.add(ProblemReport(code="R-T2", kind="record", record_ref="D-0002", details="pedro's", reported_by=pedro.id))
    db.commit()
    login("juan")
    sent = client.post("/problems", json={"kind": "record", "record_ref": "d-0139", "details": "Should be 4.10 kg"}).json()
    mine = client.get("/problems/mine").json()
    assert [(r["id"], r["record_ref"], r["status"]) for r in mine] == [(sent["id"], "D-0139", "open")]
    assert [r["details"] for r in client.get("/problems/mine?days=60").json()] == ["Should be 4.10 kg", "old"]


def test_mine_routes_are_for_operators_only(client, make_user, login):
    make_user("maria", role="admin")
    make_user("rosa", role="staff")
    for who in ("maria", "rosa"):
        login(who)
        assert client.get("/inventory/adjustments/mine").status_code == 403
        assert client.get("/problems/mine").status_code == 403


def test_operators_can_list_devices_without_keys_but_not_change_them(client, db, make_user, login):
    db.add(Device(code="WS-01", type="weighing_station", location="Intake", key_hash="secret-hash"))
    db.commit()
    make_user("juan", role="operator")
    make_user("rosa", role="staff")
    login("juan")
    r = client.get("/devices")
    assert r.status_code == 200 and [d["code"] for d in r.json()] == ["WS-01"]
    assert "secret-hash" not in r.text and "key" not in r.json()[0]
    assert client.post("/devices", json={"code": "X-1", "type": "weighing_station"}).status_code == 403
    login("rosa")
    assert client.get("/devices").status_code == 403
