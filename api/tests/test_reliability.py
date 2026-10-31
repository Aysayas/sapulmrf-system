from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import WORKER_LATE_AFTER, app, worker_status
from app.simulator import Api


def test_worker_status_goes_late_when_the_worker_stops():
    now = datetime.now(UTC)
    assert worker_status(None, now) == "unknown"
    assert worker_status(now - timedelta(seconds=30), now) == "ok"
    assert worker_status(now - WORKER_LATE_AFTER - timedelta(seconds=1), now) == "late"


def test_health_reports_the_worker():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["worker"] in ("ok", "late", "unknown")


def test_an_unexpected_error_gets_a_plain_500():
    def broken():
        raise RuntimeError("secret detail")
        yield

    app.dependency_overrides[get_db] = broken
    try:
        body = {"username": "juan", "password": "password123"}
        r = TestClient(app, raise_server_exceptions=False).post("/auth/login", json=body)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500 and "secret" not in r.text and "Something went wrong" in r.json()["detail"]


def fake_api(handler) -> Api:
    api = Api("http://sim.test")
    api.http = httpx.Client(base_url="http://sim.test", transport=httpx.MockTransport(handler))
    return api


def test_the_simulator_logs_in_again_when_its_session_expires():
    logins, session = [], {"live": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            logins.append(request.content)
            session["live"] = True
            return httpx.Response(200, json={})
        if not session["live"]:
            return httpx.Response(401, json={"detail": "Log in first."})
        return httpx.Response(200, json={"ok": True})

    api = fake_api(handler)
    api.call("POST", "/auth/login", json={"username": "sim", "password": "x"})
    session["live"] = False
    assert api.call("GET", "/operations/compost") == {"ok": True}
    assert len(logins) == 2


def test_a_rejected_device_key_does_not_trigger_a_login():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path != "/auth/login"
        return httpx.Response(401, json={"detail": "Bad key"})

    api = fake_api(handler)
    api.login_body = {"username": "sim", "password": "x"}
    try:
        api.call("POST", "/devices/readings", "bad-key", json={})
    except RuntimeError as e:
        assert "401" in str(e)
    else:
        raise AssertionError("should have failed")
