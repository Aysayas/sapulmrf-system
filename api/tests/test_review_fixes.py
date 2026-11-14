"""Rules added after the operator and staff review: what staff can't see, stock locks, password guessing, bags, undo."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select

from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.approvals import service as approvals
from app.approvals.models import Outgoing
from app.approvals.schemas import AdjustmentIn, DecisionIn, OutgoingIn
from app.compost.models import CompostBatch, CompostReading
from app.core.config import settings
from app.intake.models import Delivery, SegregationCheck
from app.reports.models import ReportExport
from app.sorting import service as sorting
from app.sorting.models import StockMovement
from app.sorting.schemas import SortIn
from app.sorting.service import material_bags

TODAY = datetime.now(UTC).date()


def stock(db, world, kg=100, bags=10):
    db.add(StockMovement(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], kg=kg, bags=bags, kind="sorted"))
    db.commit()


def grant(db, staff, *screens):
    db.add_all(StaffAccess(user_id=staff.id, screen=s, granted=True) for s in screens)
    db.commit()


# ---- staff never see money ----


def test_staff_get_outgoing_records_without_any_money(client, db, world, make_user, login):
    admin = make_user("maria", role="admin")
    stock(db, world)
    o = approvals.request_outgoing(db, OutgoingIn(type="sale", material_id=world["mat"]["Plastic"],
                                                  storage_area_id=world["area_a"], kg=10, recipient="Junk shop",
                                                  price_per_kg=12), admin)
    assert o.status == "approved"  # recorded by the admin: it counts at once
    make_user("rosa", role="staff")
    login("rosa")
    v = client.get("/operations/outgoing").json()
    assert v["income_month"] == 0 and v["income_6m"] == []
    [row] = v["records"]
    assert row["kg"] == 10 and row["price_per_kg"] is None and row["total"] is None
    login("maria")
    v = client.get("/operations/outgoing").json()
    assert v["income_month"] == 120 and v["records"][0]["total"] == 120


def test_staff_exports_leave_out_income_and_ungranted_segregation_and_are_logged(client, db, make_user, login):
    admin = make_user("maria", role="admin")
    ids = {}
    for kind in ("income", "segregation", "intake"):
        e = ReportExport(kind=kind, from_day=TODAY, to_day=TODAY, format="csv", user_id=admin.id)
        db.add(e)
        db.flush()
        ids[kind] = e.id
    rosa = make_user("rosa", role="staff")
    grant(db, rosa, "reports")
    login("rosa")
    assert [e["kind"] for e in client.get("/reports/recent").json()] == ["intake"]
    for kind in ("income", "segregation"):
        assert client.get(f"/reports/exports/{ids[kind]}").status_code == 403
        assert client.get(f"/reports/exports/{ids[kind]}/download").status_code == 403

    assert client.get(f"/reports/exports/{ids['intake']}").status_code == 200
    assert client.get(f"/reports/exports/{ids['intake']}/download").status_code == 200
    logged = db.scalars(select(ActivityLog.action)
                        .where(ActivityLog.user_id == rosa.id, ActivityLog.action.like("%report%"))).all()
    assert sorted(logged) == ["Downloaded intake report as CSV", "Viewed intake report"]

    grant(db, rosa, "segregation")
    assert {e["kind"] for e in client.get("/reports/recent").json()} == {"intake", "segregation"}
    assert client.get(f"/reports/exports/{ids['segregation']}").status_code == 200
    assert client.get(f"/reports/exports/{ids['income']}").status_code == 403


# ---- whoever changes stock holds the lock ----


@pytest.fixture
def locks(db):
    """The tables locked by each statement: two real sessions can't meet inside the rolled-back test transaction."""
    seen = []

    def watch(conn, cursor, statement, params, context, executemany):
        if "FOR UPDATE" in statement:
            seen.append(re.search(r"FROM\s+(\w+)", statement).group(1))

    event.listen(db.get_bind(), "before_cursor_execute", watch)
    yield seen
    event.remove(db.get_bind(), "before_cursor_execute", watch)


def test_approving_an_outgoing_locks_the_record_and_the_area(db, world, make_user, locks):
    admin = make_user("maria", role="admin")
    stock(db, world)
    o = Outgoing(code="O-9999", type="sale", material_id=world["mat"]["Plastic"], price_per_kg=1, total=10,
                 storage_area_id=world["area_a"], kg=10, recipient="Hauler")  # an old-flow pending record
    db.add(o)
    db.commit()
    locks.clear()
    approvals.decide_outgoing(db, o.id, DecisionIn(decision="approve"), admin)
    assert locks == ["outgoing", "storage_areas"]


def test_recording_an_outgoing_locks_the_area(db, world, make_user, locks):
    admin = make_user("maria", role="admin")
    stock(db, world)
    locks.clear()
    approvals.request_outgoing(db, OutgoingIn(type="sale", material_id=world["mat"]["Plastic"], price_per_kg=1,
                                              storage_area_id=world["area_a"], kg=10, recipient="Hauler"), admin)
    assert locks == ["storage_areas"]


def test_approving_an_adjustment_locks_the_record_and_the_area(db, world, make_user, locks):
    admin = make_user("maria", role="admin")
    from app.approvals.models import AdjustmentRequest
    r = AdjustmentRequest(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], system_kg=0,
                          actual_kg=5, reason="Recount")  # an old-flow pending count
    db.add(r)
    db.commit()
    locks.clear()
    approvals.decide_adjustment(db, r.id, DecisionIn(decision="approve"), admin)
    assert locks == ["adjustment_requests", "storage_areas"]


def test_a_recount_locks_the_area(db, world, make_user, locks):
    admin = make_user("maria", role="admin")
    locks.clear()
    approvals.request_adjustment(db, AdjustmentIn(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"],
                                                  actual_kg=5, reason="Recount"), admin)
    assert locks == ["storage_areas"]


def separated(db, world, dry=6):
    d = Delivery(source_area_id=world["purok1"], category_id=world["cat"]["Mixed household"], weight_kg=10, weighed_by="manual",
                 status="separated")
    db.add(d)
    db.flush()
    d.code = f"D-{d.id:04d}"
    db.add(SegregationCheck(delivery_id=d.id, condition="mixed", wet_kg=10 - dry, dry_kg=dry))
    db.commit()
    return d


def test_sorting_locks_the_delivery_then_the_areas_and_refuses_a_second_submit(db, world, make_user, locks):
    op = make_user()
    d = separated(db, world)
    body = SortIn(delivery_id=d.id, rows=[{"material_id": None, "bags": 1, "kg": 6, "storage_area_id": world["area_a"]}])
    sorting.sort_delivery(db, body, op)
    assert locks == ["deliveries", "storage_areas"]
    with pytest.raises(Exception, match="already sorted"):
        sorting.sort_delivery(db, body, op)
    assert len(db.scalars(select(StockMovement).where(StockMovement.delivery_id == d.id)).all()) == 1


# ---- guessing a password from a session ----


def test_wrong_current_passwords_lock_the_account_like_login(client, db, as_operator):
    wrong = {"current_password": "nope-nope", "new_password": "new-password"}
    for _ in range(settings.lockout_attempts):
        assert client.post("/auth/me/password", json=wrong).status_code == 400
    assert db.get(type(as_operator), as_operator.id).locked_until is not None
    assert db.scalar(select(ActivityLog).where(ActivityLog.action == "Account locked")) is not None
    right = {"current_password": "password123", "new_password": "new-password"}
    assert client.post("/auth/me/password", json=right).status_code == 423  # even the right one, while locked


# ---- bags follow the kg ----


def move(client, world, **over):
    return client.post("/inventory/transfers", json={"material_id": world["mat"]["Plastic"], "from_area_id": world["area_a"],
                                                     "to_area_id": world["area_d"], "kg": 50, **over})


def test_without_a_bag_count_bags_move_in_proportion(client, db, world, as_operator):
    stock(db, world)
    assert move(client, world).json()["bags"] == 5
    assert material_bags(db, world["mat"]["Plastic"], world["area_a"]) == 5


def test_a_partial_transfer_cannot_take_every_bag(client, db, world, as_operator):
    stock(db, world)
    r = move(client, world, kg=1, bags=10)
    assert r.status_code == 409 and "at least one bag" in r.json()["detail"]
    assert move(client, world, kg=99.9).json()["bags"] == 9  # rounding leaves the last bag too


# ---- taking back a segregation check ----


def waiting(client, world):
    return client.post("/deliveries", json={"source_area_id": world["purok1"], "category_id": world["cat"]["Mixed household"],
                                            "weight_kg": 10, "weighed_by": "manual"}).json()["id"]


SEG = {"condition": "mixed", "wet_kg": 4, "dry_kg": 6}


def test_i_can_undo_my_own_recent_check_and_record_it_again(client, db, world, as_operator):
    d = waiting(client, world)
    assert client.post(f"/deliveries/{d}/segregation", json=SEG).status_code == 201
    r = client.delete(f"/deliveries/{d}/segregation")
    assert r.status_code == 200 and r.json()["status"] == "awaiting" and r.json()["segregation"] is None
    assert db.scalar(select(ActivityLog).where(ActivityLog.action == "Undid segregation check")) is not None
    assert client.post(f"/deliveries/{d}/segregation", json=SEG).status_code == 201


def test_undo_is_refused_for_old_sorted_or_other_peoples_checks(client, db, world, make_user, login, as_operator):
    d = waiting(client, world)
    assert client.delete(f"/deliveries/{d}/segregation").status_code == 404
    client.post(f"/deliveries/{d}/segregation", json=SEG)
    check = db.scalar(select(SegregationCheck).where(SegregationCheck.delivery_id == d))
    check.checked_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()
    assert client.delete(f"/deliveries/{d}/segregation").status_code == 409  # too late
    check.checked_at = datetime.now(UTC)
    db.commit()
    row = {"material_id": None, "bags": 1, "kg": 6, "storage_area_id": world["area_a"]}
    client.post("/sorting", json={"delivery_id": d, "rows": [row]})
    assert client.delete(f"/deliveries/{d}/segregation").status_code == 409  # already sorted

    other = waiting(client, world)
    client.post(f"/deliveries/{other}/segregation", json=SEG)
    make_user("pedro", role="operator")
    login("pedro")
    assert client.delete(f"/deliveries/{other}/segregation").status_code == 409


# ---- a week of readings ----


def test_compost_can_ask_for_a_week_of_readings(client, db, as_operator):
    b = CompostBatch(code="B-99", start_kg=10)
    db.add(b)
    db.flush()
    db.add(CompostReading(batch_id=b.id, temp_c=50, moisture_pct=50, read_at=datetime.now(UTC) - timedelta(days=3)))
    db.commit()
    assert client.get("/operations/compost?batch=B-99").json()["series"] == []
    assert len(client.get("/operations/compost?batch=B-99&days=7").json()["series"]) == 1
    assert client.get("/operations/compost?days=8").status_code == 422
