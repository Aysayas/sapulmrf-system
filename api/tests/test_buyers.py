from datetime import UTC, datetime, timedelta

from test_approvals import as_admin, sale, stock

from app.approvals.models import Outgoing
from app.masterdata.models import Buyer


def test_admins_keep_the_buyers_list_and_operators_read_it(client, db, world, make_user, login):
    make_user("juan", role="operator")
    login("juan")
    assert client.post("/masterdata/buyers", json={"name": "Junkshop Reyes"}).status_code == 403
    as_admin(make_user, login)
    r = client.post("/masterdata/buyers", json={"name": "Junkshop Reyes"})
    assert r.status_code == 201
    assert client.post("/masterdata/buyers", json={"name": "junkshop reyes"}).status_code == 409
    client.post("/masterdata/buyers", json={"name": "ENRO truck"})
    client.patch(f"/masterdata/buyers/{r.json()['id']}", json={"active": False})
    login("juan")
    assert [b["name"] for b in client.get("/masterdata/buyers?active=true").json()] == ["ENRO truck"]


def test_stock_rows_carry_the_last_price_of_that_material_ignoring_reversed_sales(client, db, world, as_operator,
                                                                                  make_user, login):
    stock(db, world, kg=100)
    assert sale(client, world, kg=1, price=10).status_code == 201
    later = sale(client, world, kg=1, price=14).json()
    db.query(Outgoing).filter_by(id=later["id"]).update({"decided_at": datetime.now(UTC) + timedelta(minutes=1)})
    db.commit()
    row = next(s for s in client.get("/operations/inventory").json()["stock"] if s["material"] == "Plastic")
    assert row["last_price_per_kg"] == 14.0
    as_admin(make_user, login)
    client.post(f"/approvals/outgoing/{later['id']}/review", json={"decision": "reverse", "comment": "returned"})
    row = next(s for s in client.get("/operations/inventory").json()["stock"] if s["material"] == "Plastic")
    assert row["last_price_per_kg"] == 10.0


def test_the_buyers_table_exists(db):
    db.add(Buyer(name="Purok 2 gardens"))
    db.commit()
    assert db.query(Buyer).count() == 1
