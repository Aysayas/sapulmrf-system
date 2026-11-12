import base64
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
    assert r.json() == {"code": d.code, "actions": {"buzz": 1}} and d.device_id == dev["id"] and d.recorded_by is None
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


JPEG = base64.b64encode(b"\xff\xd8\xff\xe0 tiny test jpeg \xff\xd9").decode()
CV = {"category": "Recyclable", "counts": {"recyclable": 3, "residual": 1, "bio": 0}, "confidence": 0.82}


def test_the_kiosk_keeps_what_its_camera_saw_and_a_photo(client, make_user, login, db, world):
    from app.intake.models import Delivery

    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    r = kiosk_drop(client, key, category="Residual", cv=CV, photo=JPEG)  # the resident changed the category
    assert r.status_code == 201 and r.json()["actions"] == {"buzz": 1}
    d = db.scalar(select(Delivery))
    assert (d.cv_category, d.cv_counts, d.cv_confidence) == ("Recyclable", CV["counts"], 0.82)
    assert d.category_id == world["cat"]["Residual"]
    photo = client.get(f"/deliveries/{d.id}/photo")
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert photo.content == base64.b64decode(JPEG)


def test_a_resend_keeps_the_first_photo_and_bad_photos_are_refused(client, make_user, login, db, world):
    from app.intake.models import DeliveryPhoto

    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    kiosk_drop(client, key, cv=CV, photo=JPEG)
    again = base64.b64encode(b"\xff\xd8 a different shot").decode()
    assert kiosk_drop(client, key, cv=CV, photo=again).status_code == 201
    assert db.scalar(select(DeliveryPhoto.jpeg)) == base64.b64decode(JPEG)
    assert kiosk_drop(client, key, client_key="kiosk-0002-bbbb", photo="not base64!").status_code == 422
    png = base64.b64encode(b"\x89PNG not a jpeg").decode()
    assert kiosk_drop(client, key, client_key="kiosk-0003-cccc", photo=png).status_code == 422
    assert kiosk_drop(client, key, client_key="kiosk-0004-dddd", photo="A" * 2_800_004).status_code == 422


def test_kiosk_state_drives_the_light(client, make_user, login, db, world):
    from app.alerts.models import Alert
    from app.sorting.models import StockMovement

    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    state = lambda: client.get("/devices/kiosk-state", headers={"X-Device-Key": key})  # noqa: E731
    assert client.get("/devices/kiosk-state").status_code == 401
    kiosk_drop(client, key)
    s = state().json()
    assert s["actuators"]["light"] == "green" and s["today"] == {"kg": 3.5, "drops": 1} and s["alerts"] == []
    db.add(Alert(kind="device", subject_id=1, title="Compost sensor CS-01 disconnected", details="", opened_at=datetime.now(UTC)))
    db.commit()
    s = state().json()
    assert s["actuators"]["light"] == "amber" and s["alerts"][0]["title"] == "Compost sensor CS-01 disconnected"
    db.add(StockMovement(material_id=None, storage_area_id=world["area_a"], kg=510, kind="sorted"))  # 102% of 500
    db.commit()
    assert state().json()["actuators"]["light"] == "red"
    assert db.scalar(select(Device.last_seen_at)) is not None  # polling keeps the kiosk online


def test_kiosk_recent_lists_only_this_kiosks_drop_offs(client, make_user, login, world):
    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    other = client.post("/devices", json={**SCALE, "code": "WS-02"}).json()["key"]
    kiosk_drop(client, key)
    kiosk_drop(client, other, client_key="kiosk-0009-zzzz")
    [row] = client.get("/devices/kiosk-recent", headers={"X-Device-Key": key}).json()
    assert row["purok"] == "Purok 1" and row["cat"] == "Recyclable" and row["kg"] == "3.5 kg" and row["code"].startswith("D-")


def test_the_kiosk_camera_also_suggests_materials_for_sorting(client, make_user, login, db, world):
    from app.intake.models import Delivery
    from app.sorting.models import Classification

    as_admin(make_user, login)
    dev = client.post("/devices", json=SCALE).json()
    materials = [{"label": "plastic", "confidence": 0.86}, {"label": "Metal", "confidence": 0.7},
                 {"label": "Glass", "confidence": 0.9}]  # SapulMRF has no Glass: skipped, the drop-off still saves
    assert kiosk_drop(client, dev["key"], cv=CV, photo=JPEG, materials=materials).status_code == 201
    d = db.scalar(select(Delivery))
    rows = db.scalars(select(Classification).order_by(Classification.id)).all()
    mat = world["mat"]
    assert [(c.suggested_material_id, c.confidence) for c in rows] == [(mat["Plastic"], 0.86), (mat["Metal"], 0.7)]
    assert all(c.delivery_id == d.id and c.device_id == dev["id"] and c.confirmed_at is None for c in rows)
    assert rows[0].image_url == f"/api/deliveries/{d.id}/photo"
    kiosk_drop(client, dev["key"], cv=CV, photo=JPEG, materials=materials)  # a resend adds no suggestions
    assert len(db.scalars(select(Classification)).all()) == 2


def test_material_suggestions_without_a_photo_have_no_image(client, make_user, login, db, world):
    from app.sorting.models import Classification

    as_admin(make_user, login)
    key = client.post("/devices", json=SCALE).json()["key"]
    kiosk_drop(client, key, materials=[{"label": "Paper", "confidence": 0.5}])
    assert db.scalar(select(Classification.image_url)) == ""
    assert kiosk_drop(client, key, client_key="kiosk-0005-eeee", materials=[{"label": "x", "confidence": 2}]).status_code == 422
