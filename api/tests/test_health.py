from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import main

client = TestClient(main.app)


def test_health_ok_when_db_answers():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["db"] == "ok" and "worker" in r.json()


def test_health_reports_db_down(monkeypatch):
    def broken_connect():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(main.engine, "connect", broken_connect)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "db": "down"}
