from datetime import UTC, datetime

from sqlalchemy import select

from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.auth.models import Session
from app.intake.models import Delivery, SegregationCheck
from app.sorting.models import Classification, StockMovement
from app.sorting.service import material_bags, material_kg


def stock(db, world, kg=100, bags=10, area="area_a", material="Plastic"):
    db.add(StockMovement(material_id=world["mat"][material], storage_area_id=world[area], kg=kg, bags=bags, kind="sorted"))
    db.commit()


def move(client, world, **over):
    body = {"material_id": world["mat"]["Plastic"], "from_area_id": world["area_a"], "to_area_id": world["area_d"],
            "kg": 40, "bags": 4}
    return client.post("/inventory/transfers", json={**body, **over})


# ---- transfers ----


def test_a_transfer_moves_kg_and_bags_as_two_ledger_rows_and_is_logged(client, db, world, as_operator):
    stock(db, world)
    r = move(client, world)
    assert r.status_code == 201
    assert r.json() == {"material": "Plastic", "from_area": "Area A", "to_area": "Area D", "kg": 40.0, "bags": 4,
                        "from_area_kg": 60.0, "to_area_kg": 40.0}
    plastic = world["mat"]["Plastic"]
    assert material_kg(db, plastic, world["area_a"]) == 60 and material_bags(db, plastic, world["area_a"]) == 6
    assert material_kg(db, plastic, world["area_d"]) == 40 and material_bags(db, plastic, world["area_d"]) == 4
    rows = db.scalars(select(StockMovement).where(StockMovement.kind == "transfer")).all()
    assert sorted(m.kg for m in rows) == [-40, 40] and {m.by for m in rows} == {as_operator.id}
    row = db.scalar(select(ActivityLog).where(ActivityLog.action == "Transferred stock"))
    assert row.user_id == as_operator.id and "Plastic · Area A → Area D · 40.0 kg" in row.record


def test_a_transfer_cannot_take_more_than_the_source_holds(client, db, world, as_operator):
    stock(db, world, kg=30)
    r = move(client, world)
    assert r.status_code == 409 and "Only 30.0 kg" in r.json()["detail"]
    assert move(client, world, kg=10, bags=11).status_code == 409
    # Another material's stock in the same area doesn't count.
    stock(db, world, kg=200, material="Paper")
    assert move(client, world).status_code == 409


def test_a_transfer_cannot_pass_the_destination_capacity(client, db, world, as_operator):
    stock(db, world, kg=250, bags=0)
    stock(db, world, kg=280, bags=0, area="area_d", material="Paper")  # Area D holds 300 kg at most
    r = move(client, world, kg=21, bags=0)
    assert r.status_code == 409 and "Area D" in r.json()["detail"]
    assert move(client, world, kg=20, bags=0).status_code == 201


def test_emptying_a_material_takes_all_its_bags(client, db, world, as_operator):
    stock(db, world, kg=40)
    assert move(client, world, bags=0).json()["bags"] == 10
    assert material_bags(db, world["mat"]["Plastic"], world["area_a"]) == 0


def test_residual_can_move(client, db, world, as_operator):
    db.add(StockMovement(material_id=None, storage_area_id=world["area_a"], kg=50, bags=2, kind="sorted"))
    db.commit()
    r = move(client, world, material_id=None, kg=50, bags=2)
    assert r.status_code == 201 and r.json()["material"] == "Residual"


def test_transfer_input_is_checked(client, db, world, as_operator):
    stock(db, world)
    assert move(client, world, to_area_id=world["area_a"]).status_code == 422
    assert move(client, world, to_area_id=99999).status_code == 422
    assert move(client, world, material_id=99999).status_code == 422
    assert move(client, world, kg=0).status_code == 422
    assert move(client, world, bags=-1).status_code == 422


def test_only_operators_transfer(client, db, world, make_user, login):
    stock(db, world)
    make_user("maria", role="admin")
    make_user("rosa", role="staff")
    for who in ("maria", "rosa"):
        login(who)
        assert move(client, world).status_code == 403


# ---- my history ----


def test_history_shows_only_my_own_work_without_logins(client, db, make_user, login):
    make_user("juan", role="operator")
    pedro = make_user("pedro", role="operator")
    db.add(ActivityLog(user_id=pedro.id, action="Recorded delivery", record="D-0001"))
    db.commit()
    login("juan")
    juan_id = client.get("/auth/me").json()["id"]
    db.add(ActivityLog(user_id=juan_id, action="Recorded delivery", record="D-0002"))
    db.commit()
    mine = client.get("/activity/mine").json()
    assert [a["record"] for a in mine] == ["D-0002"]
    assert client.get("/activity/mine?user_id=" + str(pedro.id)).json() == mine  # no way to ask for someone else's


def test_history_needs_a_session(client):
    assert client.get("/activity/mine").status_code == 401


# ---- profile and password ----


def test_i_can_change_my_name_and_contact_only(client, db, as_operator):
    r = client.patch("/auth/me", json={"name": " Juan D. Cruz ", "contact": "0917 123 4567", "role": "admin", "username": "x"})
    assert r.status_code == 200
    me = client.get("/auth/me").json()
    assert (me["name"], me["contact"], me["role"], me["username"]) == ("Juan D. Cruz", "0917 123 4567", "operator", "juan")
    assert db.scalar(select(ActivityLog).where(ActivityLog.action == "Updated own profile")).record == "name, contact"


def test_profile_input_is_checked(client, as_operator):
    assert client.patch("/auth/me", json={"name": "  "}).status_code == 422
    assert client.patch("/auth/me", json={"contact": "call me"}).status_code == 422
    assert client.patch("/auth/me", json={"contact": "1" * 31}).status_code == 422
    assert client.patch("/auth/me", json={"contact": ""}).status_code == 200  # clearing it is fine


def test_changing_my_password(client, db, as_operator, login):
    other = Session(token_hash="x" * 64, user_id=as_operator.id, expires_at=as_operator.created_at.replace(year=2099))
    db.add(other)
    db.commit()
    r = client.post("/auth/me/password", json={"current_password": "password123", "new_password": "new-password"})
    assert r.status_code == 204
    assert db.scalar(select(Session).where(Session.token_hash == "x" * 64)) is None  # other browsers are signed out
    assert client.get("/auth/me").status_code == 200  # this one stays in
    assert db.scalar(select(ActivityLog).where(ActivityLog.action == "Changed own password")).user_id == as_operator.id
    client.post("/auth/logout")
    assert client.post("/auth/login", json={"username": "juan", "password": "password123"}).status_code == 401
    login("juan", "new-password")


def test_a_password_change_needs_the_current_one_and_eight_characters(client, as_operator, login):
    wrong = client.post("/auth/me/password", json={"current_password": "nope", "new_password": "new-password"})
    assert wrong.status_code == 400
    short = client.post("/auth/me/password", json={"current_password": "password123", "new_password": "short"})
    assert short.status_code == 422
    same = client.post("/auth/me/password", json={"current_password": "password123", "new_password": "password123"})
    assert same.status_code == 422
    client.post("/auth/logout")
    login("juan", "password123")


# ---- my access ----


def test_staff_read_their_own_grants(client, db, make_user, login):
    rosa = make_user("rosa", role="staff")
    db.add(StaffAccess(user_id=rosa.id, screen="camera", granted=True))
    db.commit()
    login("rosa")
    body = client.get("/access/me").json()
    assert body["user_id"] == rosa.id
    assert body["grants"] == {"segregation": False, "predictions": False, "alerts": False, "camera": True, "reports": False}


def test_access_me_is_for_staff_only(client, make_user, login):
    assert client.get("/access/me").status_code == 401
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/access/me").status_code == 403


# ---- work lists ----


def delivery(db, world, status, dry=None):
    d = Delivery(source_area_id=world["purok1"], category_id=world["cat"]["Mixed household"], weight_kg=10, weighed_by="manual",
                 status=status)
    db.add(d)
    db.flush()
    d.code = f"D-{d.id:04d}"
    if dry is not None:
        db.add(SegregationCheck(delivery_id=d.id, condition="mixed", wet_kg=10 - dry, dry_kg=dry))
    db.commit()
    return d


def test_work_lists(client, db, world, as_operator):
    waiting = delivery(db, world, "awaiting")
    to_sort = delivery(db, world, "separated", dry=6)
    delivery(db, world, "separated", dry=0)  # all wet: nothing to sort
    delivery(db, world, "sorted", dry=6)
    def ids(q):
        return [d["id"] for d in client.get(f"/operations/intake?waiting={q}").json()]

    assert ids("segregation") == [waiting.id]
    assert ids("sorting") == [to_sort.id]
    assert client.get("/operations/intake?waiting=other").status_code == 422


def test_pending_classifications_are_for_operators(client, db, world, make_user, login):
    plastic = world["mat"]["Plastic"]
    todo = Classification(suggested_material_id=plastic, confidence=0.9)
    db.add_all([todo, Classification(suggested_material_id=plastic, confidence=0.8, final_material_id=plastic,
                                     confirmed_at=datetime.now(UTC))])
    db.commit()
    make_user("juan", role="operator")
    login("juan")
    assert [c["id"] for c in client.get("/classifications/pending").json()] == [todo.id]
    make_user("rosa", role="staff")
    login("rosa")
    assert client.get("/classifications/pending").status_code == 403


# ---- what staff can read ----


def grant(db, staff, screen):
    db.add(StaffAccess(user_id=staff.id, screen=screen, granted=True))
    db.commit()


def test_staff_cannot_write_anything_operators_write(client, db, world, make_user, login):
    make_user("rosa", role="staff")
    login("rosa")
    d = delivery(db, world, "awaiting")
    body = {"source_area_id": world["purok1"], "category_id": world["cat"]["Residual"], "weight_kg": 1, "weighed_by": "manual"}
    assert client.post("/deliveries", json=body).status_code == 403
    seg = {"condition": "mixed", "wet_kg": 1, "dry_kg": 1}
    assert client.post(f"/deliveries/{d.id}/segregation", json=seg).status_code == 403
    assert client.post("/sorting", json={"delivery_id": d.id, "rows": []}).status_code == 403
    assert client.post("/compost/batches", json={"start_kg": 1}).status_code == 403


def test_staff_read_the_shared_records_without_a_grant(client, make_user, login):
    make_user("rosa", role="staff")
    login("rosa")
    for path in ("/operations/intake", "/operations/inventory", "/operations/compost", "/operations/outgoing", "/overview"):
        assert client.get(path).status_code == 200, path


def test_staff_without_the_grant_do_not_see_segregation_on_intake(client, db, world, make_user, login):
    rosa = make_user("rosa", role="staff")
    delivery(db, world, "separated", dry=6)
    login("rosa")
    [row] = client.get("/operations/intake").json()
    assert row["segregation"] is None and row["status"] == "separated"
    grant(db, rosa, "segregation")
    [row] = client.get("/operations/intake").json()
    assert row["segregation"]["dry_kg"] == 6


def test_the_sorting_view_needs_the_camera_grant_for_staff(client, db, make_user, login):
    rosa = make_user("rosa", role="staff")
    login("rosa")
    assert client.get("/operations/sorting").status_code == 403
    grant(db, rosa, "camera")
    assert client.get("/operations/sorting").status_code == 200


def test_the_staff_overview_hides_what_is_not_granted(client, db, world, make_user, login):
    rosa = make_user("rosa", role="staff")
    db.add(Classification(suggested_material_id=world["mat"]["Plastic"], confidence=0.9))
    db.commit()
    login("rosa")
    o = client.get("/overview").json()
    assert o["compliance_week_pct"] is None and o["latest_classification"] is None
    assert o["open_alerts"] == {} and o["alert_batch_ids"] == []
    assert o["pending_approvals"] == 0 and o["income_month"] == 0 and o["devices"] == []
    grant(db, rosa, "segregation")
    grant(db, rosa, "camera")
    o = client.get("/overview").json()
    assert o["compliance_week_pct"] == 0 and o["latest_classification"]["suggested"] == "Plastic"
