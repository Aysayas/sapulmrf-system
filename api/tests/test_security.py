from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.access.models import StaffAccess
from app.auth.service import MAX_FAILURES_PER_IP
from app.core.csvsafe import safe_cell
from app.devices.models import Device
from app.intake.models import Delivery
from app.sorting.schemas import SuggestionIn
from app.users.models import User


@pytest.mark.parametrize("cell", ["=HYPERLINK(1)", "+1+1", "-1+1", "@SUM(A1)", "\tx", "\rx"])
def test_formula_cells_are_escaped(cell):
    assert safe_cell(cell) == "'" + cell


@pytest.mark.parametrize("cell", ["-5.2", "-1,000", "Buyer A", "", 3, -3.5, None])
def test_other_cells_are_left_alone(cell):
    assert safe_cell(cell) == cell


def test_a_typed_name_cant_run_in_the_activity_export(client, make_user, login):
    make_user("maria", role="admin", name="=HYPERLINK(1)")
    login("maria")
    client.post("/masterdata/puroks", json={"name": "=1+1 Purok"})
    text = client.get("/activity/export").content.decode()
    assert ",=" not in text and "'=HYPERLINK(1)" in text


def test_many_failed_logins_from_one_address_are_refused_even_for_unknown_names(client, make_user):
    make_user("juan", password="password123")
    for i in range(MAX_FAILURES_PER_IP):
        assert client.post("/auth/login", json={"username": f"nobody{i}", "password": "nope-nope"}).status_code == 401
    assert client.post("/auth/login", json={"username": "juan", "password": "password123"}).status_code == 429


def test_wrong_passwords_are_still_counted_after_the_connection_is_released(client, db, make_user):
    u = make_user("juan")
    client.post("/auth/login", json={"username": "juan", "password": "wrong-pass"})
    db.expire_all()
    assert db.scalar(select(User.failed_attempts).where(User.id == u.id)) == 1
    assert client.post("/auth/login", json={"username": "juan", "password": "password123"}).status_code == 200


def station(db, kg=12.4, age=timedelta(0)):
    d = Device(code="SCALE-1", type="weighing_station", key_hash="x" * 64,
               last_reading={"kg": kg, "stable": True, "at": (datetime.now(UTC) - age).isoformat()})
    db.add(d)
    db.commit()
    return d


def body(world, **over):
    return {"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"], "weight_kg": 12.4,
            "weighed_by": "scale", **over}


def test_a_scale_weight_needs_a_station_with_a_recent_reading(client, db, world, as_operator):
    assert client.post("/deliveries", json=body(world)).status_code == 422
    old = station(db, age=timedelta(hours=1))
    assert client.post("/deliveries", json=body(world, device_id=old.id)).status_code == 422


def test_a_scale_weight_matching_the_reading_is_not_a_correction(client, db, world, as_operator):
    r = client.post("/deliveries", json=body(world, device_id=station(db).id))
    assert r.status_code == 201 and r.json()["corrected"] is False


def test_a_weight_differing_from_the_reading_counts_as_a_correction(client, db, world, as_operator):
    d = station(db, kg=20.0)
    assert client.post("/deliveries", json=body(world, device_id=d.id)).status_code == 422
    r = client.post("/deliveries", json=body(world, device_id=d.id, correction_reason="Bag on edge"))
    assert r.status_code == 201 and r.json()["corrected"] is True
    assert db.get(Delivery, r.json()["id"]).scale_kg == 20.0


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "http://a b"])
def test_camera_image_urls_must_be_web_addresses(url):
    with pytest.raises(ValidationError):
        SuggestionIn(label="Plastic", confidence=0.9, image_url=url)


def test_camera_accuracy_follows_the_camera_grant(client, db, make_user, login):
    u = make_user("ana", role="staff")
    db.add(StaffAccess(user_id=u.id, screen="predictions", granted=True))
    db.commit()
    login("ana")
    assert client.get("/insights/predictions").json()["camera"] is None
    db.add(StaffAccess(user_id=u.id, screen="camera", granted=True))
    db.commit()
    assert client.get("/insights/predictions").json()["camera"] is not None
