from sqlalchemy import select

from app.activity.models import ActivityLog
from app.auth.models import Session

NEW = {"name": "Rosa Reyes", "username": "rreyes", "role": "staff", "password": "temporary123"}


def as_admin(make_user, login):
    admin = make_user("msantos", role="admin", name="Maria Santos")
    login("msantos")
    return admin


def test_admin_creates_a_user_and_never_sees_the_password(client, make_user, login):
    as_admin(make_user, login)
    r = client.post("/users", json=NEW)
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "rreyes" and body["role"] == "staff" and body["active"] is True
    assert "password" not in body and "password_hash" not in body
    assert [u["username"] for u in client.get("/users").json()] == ["msantos", "rreyes"]


def test_usernames_are_unique(client, make_user, login):
    as_admin(make_user, login)
    client.post("/users", json=NEW)
    r = client.post("/users", json={**NEW, "name": "Someone Else"})
    assert r.status_code == 409
    assert r.json() == {"detail": "That username is taken."}


def test_bad_input_is_rejected(client, make_user, login):
    as_admin(make_user, login)
    assert client.post("/users", json={**NEW, "password": "short"}).status_code == 422
    assert client.post("/users", json={**NEW, "role": "superuser"}).status_code == 422
    assert client.post("/users", json={**NEW, "username": "Has Spaces"}).status_code == 422


def test_only_admins_manage_users(client, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/users").status_code == 403
    assert client.post("/users", json=NEW).status_code == 403


def test_disabling_a_user_ends_their_sessions(client, make_user, login, db):
    as_admin(make_user, login)
    staff = make_user("rreyes", role="staff")
    db.add(Session(token_hash="x" * 64, user_id=staff.id, expires_at=staff.created_at.replace(year=2099)))
    db.commit()
    r = client.patch(f"/users/{staff.id}", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False
    assert db.scalar(select(Session).where(Session.user_id == staff.id)) is None


def test_admins_cannot_disable_or_demote_themselves(client, make_user, login):
    admin = as_admin(make_user, login)
    assert client.patch(f"/users/{admin.id}", json={"active": False}).status_code == 400
    assert client.patch(f"/users/{admin.id}", json={"role": "staff"}).status_code == 400
    assert client.patch(f"/users/{admin.id}", json={"name": "Maria C. Santos"}).status_code == 200


def test_editing_a_missing_user_is_404(client, make_user, login):
    as_admin(make_user, login)
    assert client.patch("/users/9999", json={"name": "X"}).status_code == 404


def test_user_changes_are_logged(client, make_user, login, db):
    as_admin(make_user, login)
    uid = client.post("/users", json=NEW).json()["id"]
    client.patch(f"/users/{uid}", json={"password": "another-temp-1"})
    client.patch(f"/users/{uid}", json={"active": False})
    actions = db.scalars(select(ActivityLog.action).order_by(ActivityLog.id)).all()
    assert actions[-3:] == ["Created user", "Reset password", "Disabled user"]
