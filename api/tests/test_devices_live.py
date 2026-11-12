import threading

import pytest
from starlette.websockets import WebSocketDisconnect

from app.devices import live

JPEG = b"\xff\xd8\xff\xe0 a test frame \xff\xd9"
SCALE = {"code": "KIOSK-01", "type": "weighing_station", "location": "Intake area"}


@pytest.fixture(autouse=True)
def no_feeds():
    live.feeds.clear()
    yield
    live.feeds.clear()


def kiosk_key(client, make_user, login):
    make_user("msantos", role="admin")
    login("msantos")
    dev = client.post("/devices", json=SCALE).json()
    return dev["id"], dev["key"]


def bridge(client, key):
    return client.websocket_connect("/devices/kiosk-live", headers={"X-Device-Key": key})


def test_a_bad_key_cannot_push_video(client, make_user, login):
    kiosk_key(client, make_user, login)
    with pytest.raises(WebSocketDisconnect), bridge(client, "mrfk_wrong") as ws:
        ws.receive_json()


def test_pushed_frames_show_as_live_with_their_detections(client, make_user, login):
    dev_id, key = kiosk_key(client, make_user, login)
    assert client.get("/devices/live").json() == []
    with bridge(client, key) as ws:
        assert ws.receive_json() == {"viewers": 0}
        ws.send_bytes(JPEG)
        ws.send_text('{"det": {"category": "Recyclable", "recyclable": 2}, "w": 1280, "h": 720}')
        ws.send_bytes(JPEG)  # the API has handled the text once this frame lands
        for _ in range(50):
            [feed] = client.get("/devices/live").json()
            if feed["det"]:
                break
        assert feed["device_id"] == dev_id and feed["code"] == "KIOSK-01" and feed["live"]
        assert (feed["w"], feed["h"], feed["det"]["category"]) == (1280, 720, "Recyclable")
    assert client.get("/devices/live").json()[0]["live"] is False  # the bridge left


def test_viewers_get_the_frames_and_the_bridge_hears_about_them(client, make_user, login):
    dev_id, key = kiosk_key(client, make_user, login)
    got = {}
    with bridge(client, key) as ws:
        assert ws.receive_json() == {"viewers": 0}
        # No frame yet: the laptop waits for a viewer, so the viewer must be able to start watching first.
        assert client.get("/devices/live").json()[0]["live"] is True
        watcher = threading.Thread(target=lambda: got.update(r=client.get(f"/devices/{dev_id}/live.mjpg")))
        watcher.start()
        assert ws.receive_json() == {"viewers": 1}
        ws.send_bytes(JPEG)
        for _ in range(50):
            if client.get("/devices/live").json()[0]["fps"] or client.get("/devices/live").json()[0]["last_frame_at"]:
                break
    watcher.join(timeout=10)  # the stream ends when the bridge leaves
    r = got["r"]
    assert r.status_code == 200 and r.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert b"--frame\r\nContent-Type: image/jpeg" in r.content and JPEG in r.content


def test_only_admins_and_operators_can_watch(client, make_user, login):
    dev_id, key = kiosk_key(client, make_user, login)
    assert client.get(f"/devices/{dev_id}/live.mjpg").status_code == 404  # not live yet
    make_user("staff1", role="staff")
    login("staff1")
    assert client.get(f"/devices/{dev_id}/live.mjpg").status_code == 403
    assert client.get("/devices/live").status_code == 403
    client.cookies.clear()
    assert client.get(f"/devices/{dev_id}/live.mjpg").status_code == 401


def test_an_oversized_or_non_jpeg_frame_closes_the_feed(client, make_user, login):
    _, key = kiosk_key(client, make_user, login)
    for bad in (b"\xff\xd8" + b"x" * live.MAX_FRAME, b"\x89PNG not a jpeg"):
        with bridge(client, key) as ws:
            ws.receive_json()
            ws.send_bytes(bad)
            assert ws.receive()["code"] == 1009


def test_a_deactivated_camera_drops_off_the_live_list(client, make_user, login):
    dev_id, key = kiosk_key(client, make_user, login)
    with bridge(client, key) as ws:
        ws.receive_json()
        ws.send_bytes(JPEG)
    assert len(client.get("/devices/live").json()) == 1
    client.patch(f"/devices/{dev_id}", json={"active": False})
    assert client.get("/devices/live").json() == []
