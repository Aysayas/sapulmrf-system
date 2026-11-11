from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.activity.models import ActivityLog
from app.devices.models import Device

SCALE = {"code": "WS-01", "type": "weighing_station", "location": "Intake area"}


def as_admin(make_user, login):
    make_user("msantos", role="admin")
    login("msantos")


def test_registering_returns_the_key_once(client, make_user, login, db):
    as_admin(make_user, login)
    r = client.post("/devices", json=SCALE)
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "WS-01" and body["status"] == "never" and body["key"].startswith("mrfk_")
    listed = client.get("/devices").json()
    assert "key" not in listed[0] and "key_hash" not in listed[0]
    assert db.scalar(select(Device.key_hash)) != body["key"]


def test_heartbeat_with_the_key_puts_the_device_online(client, make_user, login):
    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    r = client.post("/devices/heartbeat", headers={"X-Device-Key": key})
    assert r.status_code == 200 and r.json() == {"device": "WS-01", "status": "online"}
    d = client.get("/devices").json()[0]
    assert d["status"] == "online" and d["last_seen_at"] is not None


def test_devices_go_offline_after_two_minutes_of_silence(client, make_user, login, db):
    as_admin(make_user, login)
    client.post("/devices", json=SCALE)
    db.scalar(select(Device)).last_seen_at = datetime.now(UTC) - timedelta(minutes=3)
    db.commit()
    assert client.get("/devices").json()[0]["status"] == "offline"


def test_bad_keys_and_inactive_devices_are_refused(client, make_user, login):
    as_admin(make_user, login)
    dev = client.post("/devices", json=SCALE).json()
    assert client.post("/devices/heartbeat").status_code == 401
    assert client.post("/devices/heartbeat", headers={"X-Device-Key": "mrfk_wrong"}).status_code == 401
    client.patch(f"/devices/{dev['id']}", json={"active": False})
    assert client.post("/devices/heartbeat", headers={"X-Device-Key": dev["key"]}).status_code == 403


def test_a_new_key_replaces_the_old_one(client, make_user, login):
    as_admin(make_user, login)
    dev = client.post("/devices", json=SCALE).json()
    new = client.post(f"/devices/{dev['id']}/new-key").json()["key"]
    assert new != dev["key"]
    assert client.post("/devices/heartbeat", headers={"X-Device-Key": dev["key"]}).status_code == 401
    assert client.post("/devices/heartbeat", headers={"X-Device-Key": new}).status_code == 200


def test_codes_are_unique_and_types_are_checked(client, make_user, login):
    as_admin(make_user, login)
    client.post("/devices", json=SCALE)
    assert client.post("/devices", json={**SCALE, "code": "ws-01"}).status_code == 409
    assert client.post("/devices", json={**SCALE, "code": "CS-03", "type": "toaster"}).status_code == 422


def test_only_admins_manage_devices(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/devices").status_code == 200  # listing is open to operators (problem reports)
    assert client.post("/devices", json=SCALE).status_code == 403


def test_device_changes_are_logged_but_heartbeats_are_not(client, make_user, login, db):
    as_admin(make_user, login)
    dev = client.post("/devices", json=SCALE).json()
    client.post("/devices/heartbeat", headers={"X-Device-Key": dev["key"]})
    client.post(f"/devices/{dev['id']}/new-key")
    actions = db.scalars(select(ActivityLog.action).order_by(ActivityLog.id)).all()
    assert actions[-2:] == ["Registered device", "Generated new device key"]


def kiosk_drop(client, key, **over):
    body = {"source_area": "purok 1", "category": "Recyclable", "weight_kg": 3.5, "weighed_by": "manual",
            "client_key": "kiosk-0001-aaaa"} | over
    return client.post("/devices/deliveries", json=body, headers={"X-Device-Key": key} if key else {})


def test_the_kiosk_records_a_drop_off_with_its_own_key(client, make_user, login, db, world):
    from app.intake.models import Delivery

    as_admin(make_user, login)
    dev = client.post("/devices", json=SCALE).json()
    assert kiosk_drop(client, None).status_code == 401
    assert kiosk_drop(client, "mrfk_wrong").status_code == 401
    r = kiosk_drop(client, dev["key"])
    assert r.status_code == 201
    d = db.scalar(select(Delivery))
    assert r.json() == {"code": d.code} and d.device_id == dev["id"] and d.recorded_by is None
    assert d.source_area_id == world["purok1"] and d.category_id == world["cat"]["Recyclable"]
    assert "by WS-01" in db.scalar(select(ActivityLog.record).where(ActivityLog.action == "Recorded delivery"))


def test_a_resent_kiosk_drop_off_is_recorded_once(client, make_user, login, db, world):
    from app.intake.models import Delivery

    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    first, again = kiosk_drop(client, key).json(), kiosk_drop(client, key).json()
    assert first == again and len(db.scalars(select(Delivery)).all()) == 1


def test_the_kiosk_gets_a_clear_error_for_an_unknown_purok_or_a_camera_key(client, make_user, login, world):
    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    r = kiosk_drop(client, key, source_area="Purok 99")
    assert r.status_code == 422 and "Purok 99" in r.json()["detail"]
    cam = client.post("/devices", json={"code": "CAM-01", "type": "sorting_camera"}).json()["key"]
    assert kiosk_drop(client, cam).status_code == 403
