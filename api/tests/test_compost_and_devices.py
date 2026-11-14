from sqlalchemy import select

from app.compost.models import CompostReading
from app.sorting.models import Classification


def register(client, code, type_):
    """Registers a device (an admin must be logged in) and returns (id, key)."""
    r = client.post("/devices", json={"code": code, "type": type_, "location": "test"})
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["key"]


def setup_devices(client, make_user, login, db=None, world=None):
    """Registers a compost sensor, a scale and a camera, then logs in as the operator. With db and world, 100 kg of
    wet waste is waiting for compost, so batches can start."""
    if db is not None:
        from test_compost_balance import check
        check(db, world, 100.0)
    make_user("msantos", role="admin")
    login("msantos")
    sensor = register(client, "CS-01", "compost_sensor")
    scale = register(client, "WS-01", "weighing_station")
    camera = register(client, "CAM-01", "sorting_camera")
    client.post("/auth/logout")
    make_user("juan", role="operator", name="Juan Dela Cruz")
    login("juan")
    return sensor, scale, camera


def test_operator_starts_a_batch_with_a_sensor_and_logs_activities(client, make_user, login, world, db):
    (sensor_id, _), _, _ = setup_devices(client, make_user, login, db, world)
    r = client.post("/compost/batches", json={"start_kg": 18.4, "sensor_id": sensor_id})
    assert r.status_code == 201
    b = r.json()
    assert b["code"] == f"B-{b['id']:02d}" and b["sensor"] == "CS-01" and b["finished_at"] is None
    r = client.post(f"/compost/batches/{b['id']}/activities", json={"type": "turning", "note": "Turned fully"})
    assert r.status_code == 201 and r.json()["activities"][0]["type"] == "turning"


def test_one_sensor_per_unfinished_batch(client, make_user, login, world, db):
    (sensor_id, _), (scale_id, _), _ = setup_devices(client, make_user, login, db, world)
    client.post("/compost/batches", json={"start_kg": 10, "sensor_id": sensor_id})
    assert client.post("/compost/batches", json={"start_kg": 10, "sensor_id": sensor_id}).status_code == 409
    assert client.post("/compost/batches", json={"start_kg": 10, "sensor_id": scale_id}).status_code == 422


def test_finishing_a_batch_records_the_compost_and_closes_it(client, make_user, login, world, db):
    (sensor_id, _), _, _ = setup_devices(client, make_user, login, db, world)
    b = client.post("/compost/batches", json={"start_kg": 20, "sensor_id": sensor_id}).json()
    r = client.post(f"/compost/batches/{b['id']}/activities", json={"type": "inspection", "finished_kg": 12.5})
    assert r.json()["finished_at"] is not None and r.json()["produced_kg"] == 12.5
    assert client.post(f"/compost/batches/{b['id']}/activities", json={"type": "watering"}).status_code == 409


def test_sensor_readings_land_on_the_linked_batch(client, make_user, login, world, db):
    (sensor_id, sensor_key), _, _ = setup_devices(client, make_user, login, db, world)
    b = client.post("/compost/batches", json={"start_kg": 20, "sensor_id": sensor_id}).json()
    r = client.post("/devices/readings", headers={"X-Device-Key": sensor_key}, json={"temp_c": 58.2, "moisture_pct": 52})
    assert r.status_code == 200 and r.json()["stored_on"] == b["code"]
    row = db.scalar(select(CompostReading))
    assert row.batch_id == b["id"] and row.temp_c == 58.2


def test_scale_readings_update_the_live_readout(client, make_user, login, world):
    _, (_, scale_key), _ = setup_devices(client, make_user, login)
    r = client.post("/devices/readings", headers={"X-Device-Key": scale_key}, json={"kg": 12.36, "stable": False})
    assert r.status_code == 200 and r.json()["stored_on"] is None
    assert client.post("/devices/readings", headers={"X-Device-Key": scale_key}, json={"temp_c": 50}).status_code == 422
    assert client.post("/devices/readings", headers={"X-Device-Key": "mrfk_nope"}, json={"kg": 1}).status_code == 401


def test_camera_suggestions_become_pending_classifications(client, make_user, login, world, db):
    _, _, (_, cam_key) = setup_devices(client, make_user, login)
    body = {"label": "plastic", "confidence": 0.92, "model_version": "yolo-s-1", "image_url": "https://example.invalid/a.jpg"}
    r = client.post("/devices/cv-suggestions", headers={"X-Device-Key": cam_key}, json=body)
    assert r.status_code == 201 and r.json()["suggested"] == "Plastic" and r.json()["final"] is None
    c = db.scalar(select(Classification))
    assert c.confirmed_at is None and c.device_id is not None


def test_the_kiosk_sends_camera_suggestions_but_a_compost_sensor_cannot(client, make_user, login, world):
    (_, sensor_key), (_, kiosk_key), _ = setup_devices(client, make_user, login)
    body = {"label": "plastic", "confidence": 0.9}
    assert client.post("/devices/cv-suggestions", headers={"X-Device-Key": kiosk_key}, json=body).status_code == 201
    r = client.post("/devices/cv-suggestions", headers={"X-Device-Key": sensor_key}, json=body)
    assert r.status_code == 403 and "weighing station or sorting camera" in r.json()["detail"]
