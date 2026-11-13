from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.insights import forecast as fc
from app.insights import service
from app.insights.models import Flag
from app.operations.service import TZ
from app.sorting.models import StockMovement
from tests.test_flags import USUAL, deliver
from tests.test_forecast import history, weekly

ON = date(2026, 10, 23)


def sorted_in(db, area_id, kg_per_day, days=14, material_id=None, on=ON):
    """Stock sorted into an area, spread over the last `days` days."""
    db.add_all([StockMovement(material_id=material_id, storage_area_id=area_id, kg=kg_per_day, kind="sorted",
                              at=datetime(on.year, on.month, on.day, 9, tzinfo=TZ) - timedelta(days=i + 1))
                for i in range(days)])
    db.commit()


def test_storage_outlook_and_a_suggestion_before_the_alert_level(db, world):
    db.add(StockMovement(material_id=world["mat"]["Paper"], storage_area_id=world["area_a"], kg=120, kind="sorted",
                         at=datetime(2026, 9, 1, tzinfo=TZ)))  # an old base, outside the inflow window
    db.commit()
    sorted_in(db, world["area_a"], 20, material_id=world["mat"]["Paper"])  # now 400 of 500 kg, +20 kg a day
    rows = {o.area: o for o in service.outlook(db, ON)}
    a, d = rows["Area A"], rows["Area D"]
    assert a.kg == 400 and a.per_day_kg == 20 and a.days_to_full == 5 and a.days_to_alert == 3  # alert at 90% = 450 kg
    assert d.days_to_full is None and d.days_to_alert is None  # nothing coming in
    [plan] = service.schedule(db, list(rows.values()), ON)
    assert plan.what == "Sell paper" and plan.on == ON + timedelta(days=2) and plan.why == "Area A at 90% by Oct 26"


def test_residual_areas_get_a_pickup_not_a_sale(db, world):
    sorted_in(db, world["area_d"], 20)  # residual, 280 of 300 kg: past its 85% alert already
    [plan] = service.schedule(db, service.outlook(db, ON), ON)
    assert plan.what == "Residual pickup" and plan.on == ON and "already at" in plan.why


def test_predictions_wait_for_enough_days(client, db, world, as_operator):
    history(db, world, weekly, 10, start=ON - timedelta(days=10))
    body = client.get("/insights/predictions").json()
    assert body["ready"] is False and body["days_of_records"] == 10 and body["min_days"] == 30
    assert body["forecast"] == [] and body["categories"][0] == {"id": 0, "name": "All"}


def test_predictions_show_the_forecast_from_the_better_model(client, db, world, as_operator, monkeypatch):
    start = ON - timedelta(days=50)
    history(db, world, weekly, 50, start=start)
    for i in range(30, 51):
        fc.make_forecasts(db, start + timedelta(days=i))
    monkeypatch.setattr(service, "today", lambda: ON)
    body = client.get("/insights/predictions").json()
    assert body["ready"] is True and body["model_used"] == "ml"
    assert body["errors_14d"]["ml"] < body["errors_14d"]["baseline"]
    assert [f["day"] for f in body["forecast"]] == [str(ON + timedelta(days=h)) for h in range(7)]
    assert len(body["history"]) == 21 and len(body["compared"]) == 7
    assert body["compared"][0]["day"] == str(ON - timedelta(days=1)) and body["avg_error_pct"] is not None
    cat = world["cat"]["Mixed household"]
    assert client.get(f"/insights/predictions?category={cat}").json()["category"] == cat
    assert client.get("/insights/predictions?category=999").status_code == 404


def test_staff_need_the_predictions_grant(client, db, make_user, login):
    staff = make_user("rreyes", role="staff")
    login("rreyes")
    assert client.get("/insights/predictions").status_code == 403
    db.add(StaffAccess(user_id=staff.id, screen="predictions", granted=True))
    db.commit()
    assert client.get("/insights/predictions").status_code == 200
    assert client.get("/insights/flags").status_code == 403


def test_admins_mark_flags_valid_or_incorrect(client, db, world, make_user, login):
    op = make_user("juan", role="operator")
    for i, kg in enumerate(USUAL):
        deliver(db, world, op, kg, i)
    heavy = deliver(db, world, op, 14.1, 20)
    make_user("maria", role="admin")
    login("maria")
    assert client.get("/approvals").json()["counts"]["flagged"] == 1
    [f] = client.get("/insights/flags").json()
    assert f["code"] == heavy.code and f["why"] == "Unusual weight" and f["expected"].startswith("Usual for Purok 1: 7.")
    r = client.post(f"/insights/flags/{f['id']}", json={"decision": "incorrect"})
    assert r.status_code == 200 and r.json()["status"] == "incorrect"
    assert client.get("/insights/flags").json() == []
    assert client.post(f"/insights/flags/{f['id']}", json={"decision": "valid"}).status_code == 409
    assert client.post(f"/insights/flags/{f['id']}", json={"decision": "maybe"}).status_code == 422
    assert db.scalar(select(ActivityLog.action).order_by(ActivityLog.id.desc())) == "Marked flagged record a false alarm"
    assert db.get(Flag, f["id"]).delivery_id == heavy.id


def test_camera_accuracy_counts_the_last_30_days(db, world, make_user):
    from app.sorting import service as sorting
    from app.sorting.schemas import ConfirmIn, SuggestionIn

    op = make_user()
    for label, final in (("Plastic", None), ("Paper", None), ("Paper", world["mat"]["Cardboard"])):
        c = sorting.create_suggestion(db, None, SuggestionIn(label=label, confidence=0.9))
        sorting.confirm(db, c.id, ConfirmIn(final_material_id=final), op)
    c.review = "wrong"
    db.commit()
    acc = service.camera_accuracy(db)
    assert (acc.confirmed, acc.kept, acc.kept_pct, acc.changed, acc.reviewed_wrong) == (3, 2, 67, 1, 1)


def test_camera_accuracy_per_material_per_confidence_and_kiosk_category(db, world, make_user):
    from app.intake.models import Delivery
    from app.sorting import service as sorting
    from app.sorting.schemas import ConfirmIn, SuggestionIn

    op = make_user()
    for label, conf, final, not_rec in (("Plastic", 0.9, None, False), ("Plastic", 0.85, world["mat"]["Metal"], False),
                                        ("Paper", 0.5, None, True), ("Paper", 0.7, None, False)):
        c = sorting.create_suggestion(db, None, SuggestionIn(label=label, confidence=conf))
        sorting.confirm(db, c.id, ConfirmIn(final_material_id=final, not_recyclable=not_rec), op)
    rec = world["cat"]["Recyclable"]
    db.add_all([Delivery(code=f"K-{i}", source_area_id=world["purok1"], category_id=rec, weight_kg=1, weighed_by="manual",
                         cv_category=cv) for i, cv in enumerate(("Recyclable", "Recyclable", "Residual"))])
    db.commit()
    acc = service.camera_accuracy(db)
    plastic = next(m for m in acc.by_material if m.material == "Plastic")
    paper = next(m for m in acc.by_material if m.material == "Paper")
    assert (plastic.suggested, plastic.kept, plastic.changed_to) == (2, 1, "Metal")
    assert (paper.kept, paper.changed_to) == (1, "Not recyclable")
    bands = {b.band: (b.confirmed, b.kept_pct) for b in acc.by_confidence}
    assert bands == {"Below 60%": (1, 0), "60–80%": (1, 100), "80% and up": (2, 50)}
    assert (acc.kiosk.with_camera, acc.kiosk.matched, acc.kiosk.matched_pct) == (3, 2, 67)
