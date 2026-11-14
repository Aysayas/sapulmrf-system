from test_approvals import as_admin, stock

from app.sorting.service import material_kg


def give(client, world, kg=3.0, **extra):
    return client.post("/outgoing", json={"type": "giveaway", "material_id": world["mat"]["Plastic"],
                                          "storage_area_id": world["area_a"], "kg": kg, "recipient": "Sapul Elementary",
                                          **extra})


def test_a_giveaway_leaves_stock_at_once_and_waits_for_review(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=10)
    r = give(client, world)
    assert r.status_code == 201, r.text
    assert r.json()["type"] == "giveaway" and r.json()["total"] is None and r.json()["status"] == "approved"
    assert material_kg(db, world["mat"]["Plastic"], world["area_a"]) == 7.0
    as_admin(make_user, login)
    assert client.get("/approvals").json()["counts"]["outgoing_review"] == 1


def test_a_giveaway_has_no_price_and_needs_its_material_and_area(client, db, world, as_operator):
    stock(db, world, kg=10)
    r = give(client, world, price_per_kg=5)
    assert r.status_code == 422 and "no price" in r.text
    r = client.post("/outgoing", json={"type": "giveaway", "kg": 1, "recipient": "x", "storage_area_id": world["area_a"]})
    assert r.status_code == 422


def test_a_giveaway_cannot_take_more_than_the_area_holds(client, db, world, as_operator):
    stock(db, world, kg=2)
    assert give(client, world, kg=3).status_code == 409


def test_reports_show_giveaways_apart_and_income_ignores_them(client, db, world, as_operator, make_user, login):
    stock(db, world, kg=10)
    give(client, world, kg=4)
    as_admin(make_user, login)
    v = client.get("/operations/outgoing").json()
    assert v["given_kg_month"] == 4.0 and v["sold_kg_month"] == 0.0 and v["income_month"] == 0.0
    from test_reports import get
    out = get(client, "outgoing").json()
    assert ["Recyclables given away", "4.00 kg"] in out["summary"]
