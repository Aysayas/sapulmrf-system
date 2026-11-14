from datetime import timedelta

from app.approvals import service as approvals
from app.approvals.models import Outgoing
from app.approvals.schemas import OutgoingIn, OutgoingReviewIn
from app.operations.service import month_start
from app.sorting.models import StockMovement


def test_income_counts_approved_sales_only_by_manila_month(client, db, world, make_user, login):
    op, admin = make_user("juan", role="operator"), make_user("maria", role="admin")
    db.add(StockMovement(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], kg=500, kind="sorted"))
    db.add(StockMovement(material_id=None, storage_area_id=world["area_d"], kg=100, kind="sorted"))
    db.commit()

    def sale(kg, price, at=None):
        return approvals.request_outgoing(db, OutgoingIn(type="sale", material_id=world["mat"]["Plastic"], kg=kg,
                                                         price_per_kg=price, storage_area_id=world["area_a"],
                                                         recipient="Buyer A"), op, at=at)

    sale(10, 12.0)                                                     # ₱120 this month
    sale(20, 10.0, at=month_start() + timedelta(minutes=5))            # ₱200, just after Manila midnight on the 1st
    sale(30, 10.0, at=month_start() - timedelta(minutes=5))            # ₱300, last month
    back = sale(40, 10.0)                                              # reversed the same month: no income
    approvals.review_outgoing(db, back.id, OutgoingReviewIn(decision="reverse", comment="no"), admin)
    db.add(Outgoing(code="O-9999", type="sale", material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"],
                    kg=50, recipient="Buyer A", price_per_kg=10, total=500))   # old flow, still pending: no income
    db.commit()
    approvals.request_outgoing(db, OutgoingIn(type="disposal", storage_area_id=world["area_d"], kg=60,
                                              recipient="City ENRO truck"), op)

    login("maria")
    v = client.get("/operations/outgoing").json()
    assert v["income_month"] == 320.0 and v["sold_kg_month"] == 30.0 and v["disposed_kg_month"] == 60.0
    assert v["pending"] == 1 and len(v["records"]) == 6
    assert [m["income"] for m in v["income_6m"]][-2:] == [300.0, 320.0]
    assert client.get("/overview").json()["income_month"] == 320.0
    assert client.get("/overview").json()["pending_approvals"] == 5  # 1 old-flow pending + 4 recorded to review
