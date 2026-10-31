"""Tests run against <DB_NAME>_test (created on first run). Each test runs in a transaction that is rolled back."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.service import FAILED_LOGINS
from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_password
from app.main import app
from app.masterdata.seed import seed
from app.models import Base
from app.users.models import User

DEV_URL = make_url(settings.database_url)
TEST_URL = DEV_URL.set(database=f"{DEV_URL.database}_test")


@pytest.fixture(scope="session")
def engine():
    server = create_engine(DEV_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as c:
        if not c.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_URL.database}):
            c.execute(text(f'CREATE DATABASE "{TEST_URL.database}"'))
    server.dispose()
    eng = create_engine(TEST_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with eng.begin() as conn:
        seed(conn)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def fresh_login_counts():
    FAILED_LOGINS.clear()


@pytest.fixture
def db(engine):
    conn = engine.connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    outer.rollback()
    conn.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db):
    def make(username="juan", role="operator", password="password123", active=True, name=None):
        u = User(name=name or username.title(), username=username, password_hash=hash_password(password),
                 role=role, active=active)
        db.add(u)
        db.commit()
        return u

    return make


@pytest.fixture
def login(client):
    def do(username, password="password123"):
        r = client.post("/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return r

    return do


@pytest.fixture
def world(db):
    """A small MRF: two puroks, the seeded categories and materials, two storage areas."""
    from sqlalchemy import select

    from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory

    p1, p2 = SourceArea(name="Purok 1"), SourceArea(name="Purok 2")
    a_plastic = StorageArea(name="Area A", capacity_kg=500, alert_pct=90)
    a_residual = StorageArea(name="Area D", capacity_kg=300, alert_pct=85)
    db.add_all([p1, p2, a_plastic, a_residual])
    db.commit()
    cat = {c.name: c.id for c in db.scalars(select(WasteCategory))}
    mat = {m.name: m.id for m in db.scalars(select(Material))}
    return {"purok1": p1.id, "purok2": p2.id, "area_a": a_plastic.id, "area_d": a_residual.id, "cat": cat, "mat": mat}


@pytest.fixture
def as_operator(make_user, login):
    u = make_user("juan", role="operator", name="Juan Dela Cruz")
    login("juan")
    return u
