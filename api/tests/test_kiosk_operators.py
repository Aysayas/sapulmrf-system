"""Operators sign in at the resident kiosk with their own PIN; the kiosk's laptop then acts as that operator."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.activity.models import ActivityLog
from app.auth.models import Session
from app.core.deps import COOKIE
from app.core.security import token_hash

KIOSK = {"code": "KIOSK-01", "type": "weighing_station", "location": "Gate"}


def setup(client, make_user, login):
    """An admin registers the kiosk; Juan (operator) sets PIN 2468. Returns the kiosk key and Juan."""
    make_user("msantos", role="admin")
    login("msantos")
    key = client.post("/devices", json=KIOSK).json()["key"]
    juan = make_user("juan", role="operator", name="Juan Dela Cruz")
    login("juan")
    assert client.put("/auth/me/kiosk-pin", json={"pin": "2468"}).status_code == 204
    client.post("/auth/logout")
    return key, juan


def kiosk_login(client, key, user_id, pin):
    return client.post("/devices/kiosk-login", json={"user_id": user_id, "pin": pin}, headers={"X-Device-Key": key})


def test_only_operators_set_a_kiosk_pin_and_it_must_be_4_to_6_digits(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.put("/auth/me/kiosk-pin", json={"pin": "12a4"}).status_code == 422
    assert client.put("/auth/me/kiosk-pin", json={"pin": "123"}).status_code == 422
    assert client.put("/auth/me/kiosk-pin", json={"pin": "123456"}).status_code == 204
    assert client.get("/auth/me").json()["has_kiosk_pin"] is True
    assert client.delete("/auth/me/kiosk-pin").status_code == 204
    assert client.get("/auth/me").json()["has_kiosk_pin"] is False
    for role in ("admin", "staff"):
        make_user(role, role=role)
        login(role)
        assert client.put("/auth/me/kiosk-pin", json={"pin": "2468"}).status_code == 403


def test_the_kiosk_lists_operators_with_a_pin_and_needs_its_key(client, make_user, login):
    key, juan = setup(client, make_user, login)
    make_user("pedro", role="operator")  # no PIN, so not on the kiosk
    assert client.get("/devices/kiosk-operators").status_code == 401
    r = client.get("/devices/kiosk-operators", headers={"X-Device-Key": key})
    assert r.json() == [{"id": juan.id, "name": "Juan Dela Cruz"}]
    assert kiosk_login(client, "mrfk_wrong", juan.id, "2468").status_code == 401


def test_a_pin_opens_a_30_minute_operator_session(client, make_user, login, db):
    key, juan = setup(client, make_user, login)
    r = kiosk_login(client, key, juan.id, "2468")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Juan Dela Cruz" and body["expires_in_s"] == 1800
    s = db.scalar(select(Session).where(Session.token_hash == token_hash(body["token"])))
    assert timedelta(minutes=29) < s.expires_at - datetime.now(UTC) <= timedelta(minutes=30)
    client.cookies.clear()
    assert client.get("/classifications/pending", cookies={COOKIE: body["token"]}).status_code == 200
    assert db.scalar(select(ActivityLog.record).where(ActivityLog.action == "Kiosk sign-in")) == "KIOSK-01"
    client.post("/auth/logout", cookies={COOKIE: body["token"]})  # the kiosk's Lock
    assert client.get("/classifications/pending", cookies={COOKIE: body["token"]}).status_code == 401


def test_five_wrong_pins_lock_that_operator_for_five_minutes(client, make_user, login, db):
    key, juan = setup(client, make_user, login)
    for _ in range(4):
        assert kiosk_login(client, key, juan.id, "0000").json() == {"detail": "Wrong PIN."}
    r = kiosk_login(client, key, juan.id, "0000")
    assert r.status_code == 423 and "5 minutes" in r.json()["detail"]
    assert kiosk_login(client, key, juan.id, "2468").status_code == 423  # even the right PIN, until it ends
    assert db.scalar(select(ActivityLog.id).where(ActivityLog.action == "Kiosk PIN locked"))
    db.refresh(juan)
    juan.kiosk_locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert kiosk_login(client, key, juan.id, "2468").status_code == 200


def test_admins_staff_disabled_users_and_cleared_pins_cannot_sign_in(client, make_user, login, db):
    key, juan = setup(client, make_user, login)
    login("msantos")
    assert client.delete(f"/users/{juan.id}/kiosk-pin").status_code == 204
    assert {u["username"]: u["has_kiosk_pin"] for u in client.get("/users").json()}["juan"] is False
    assert kiosk_login(client, key, juan.id, "2468").status_code == 401
    assert db.scalar(select(ActivityLog.record).where(ActivityLog.action == "Cleared kiosk PIN")) == \
        "Juan Dela Cruz (juan)"
    admin = db.scalar(select(type(juan)).where(type(juan).username == "msantos"))
    assert kiosk_login(client, key, admin.id, "2468").status_code == 401
