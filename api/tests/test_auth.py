from sqlalchemy import select

from app.activity.models import ActivityLog
from app.auth.models import Session
from app.core.deps import COOKIE


def test_login_sets_a_session_cookie_and_returns_the_user(client, make_user):
    make_user("msantos", role="admin")
    r = client.post("/auth/login", json={"username": "msantos", "password": "password123"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "msantos" and body["role"] == "admin"
    assert "password" not in str(body) and "hash" not in str(body)
    assert COOKIE in r.cookies
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/auth/me").json()["username"] == "msantos"


def test_usernames_ignore_case_at_login(client, make_user):
    make_user("aysaya", role="admin")
    assert client.post("/auth/login", json={"username": " Aysaya ", "password": "password123"}).status_code == 200


def test_wrong_password_and_unknown_user_get_the_same_answer(client, make_user):
    make_user("msantos")
    wrong = client.post("/auth/login", json={"username": "msantos", "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"username": "ghost", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Wrong username or password."}


def test_disabled_account_is_refused(client, make_user):
    make_user("pgarcia", role="staff", active=False)
    r = client.post("/auth/login", json={"username": "pgarcia", "password": "password123"})
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"]


def test_five_wrong_passwords_lock_the_account(client, make_user):
    make_user("juan")
    for _ in range(5):
        assert client.post("/auth/login", json={"username": "juan", "password": "wrong-pass"}).status_code == 401
    r = client.post("/auth/login", json={"username": "juan", "password": "password123"})
    assert r.status_code == 423
    assert "Try again" in r.json()["detail"]


def test_logout_ends_the_session(client, make_user, login, db):
    make_user("msantos", role="admin")
    login("msantos")
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert db.scalar(select(Session)) is None


def test_requests_without_a_session_get_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Log in first."}


def test_login_and_logout_are_logged(client, make_user, login, db):
    make_user("msantos", role="admin")
    login("msantos")
    client.post("/auth/logout")
    actions = db.scalars(select(ActivityLog.action).order_by(ActivityLog.id)).all()
    assert actions == ["Logged in", "Logged out"]
