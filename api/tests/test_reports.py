import csv
import io
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.access.models import StaffAccess
from app.activity.models import ActivityLog
from app.approvals import service as approvals
from app.approvals.models import Outgoing
from app.approvals.schemas import OutgoingIn, OutgoingReviewIn
from app.compost.models import CompostBatch, CompostReading
from app.intake.models import Delivery, SegregationCheck
from app.operations.service import TZ
from app.reports.models import ReportExport
from app.sorting.models import StockMovement

TODAY = datetime.now(TZ).date()


def delivery(db, world, purok, kg, cond=None, at=None, cat="Recyclable"):
    d = Delivery(code=f"D-{db.query(Delivery).count() + 1}", source_area_id=world[purok], category_id=world["cat"][cat],
                 weight_kg=kg, weighed_by="scale", received_at=at or datetime.now(UTC))
    db.add(d)
    db.flush()
    if cond:
        db.add(SegregationCheck(delivery_id=d.id, condition=cond, wet_kg=0, dry_kg=kg))
    db.commit()
    return d


def get(client, kind, frm=None, to=None, **extra):
    q = {"from": str(frm or TODAY), "to": str(to or TODAY), **extra}
    return client.get(f"/reports/{kind}", params=q)


@pytest.fixture
def admin(make_user, login):
    u = make_user("maria", role="admin", name="Maria Santos")
    login("maria")
    return u


def test_intake_and_segregation_match_hand_numbers(client, db, world, admin):
    delivery(db, world, "purok1", 10.0, "segregated")
    delivery(db, world, "purok1", 5.5, "mixed")
    delivery(db, world, "purok2", 4.0, "segregated")
    delivery(db, world, "purok2", 99.0, "segregated", at=datetime.now(UTC) - timedelta(days=5))  # outside the range

    r = get(client, "intake").json()
    assert r["summary"] == [["Deliveries", "3"], ["Total weight", "19.50 kg"]]
    assert r["rows"] == [["Purok 1", "Recyclable", 2, 15.5], ["Purok 2", "Recyclable", 1, 4.0]]

    r = get(client, "segregation").json()
    assert r["rows"] == [["Purok 1", 2, 1, 50], ["Purok 2", 1, 1, 100]]
    assert r["summary"][-1] == ["Compliance", "67%"]

    only2 = get(client, "intake", area=world["purok2"]).json()
    assert only2["rows"] == [["Purok 2", "Recyclable", 1, 4.0]] and "Purok 2" in only2["subtitle"]
    assert get(client, "segregation", area=world["purok2"]).json()["rows"] == [["Purok 2", 1, 1, 100]]


def test_range_edges_are_inclusive_manila_days(client, db, world, admin):
    midnight = datetime(TODAY.year, TODAY.month, TODAY.day, tzinfo=TZ)
    delivery(db, world, "purok1", 1.0, at=midnight)                                   # first moment of the day: in
    delivery(db, world, "purok1", 2.0, at=midnight - timedelta(minutes=1))            # last minute of yesterday: out
    delivery(db, world, "purok1", 4.0, at=midnight + timedelta(hours=23, minutes=59))  # last minute of the day: in
    assert get(client, "intake").json()["rows"][0][3] == 5.0
    assert get(client, "intake", frm=TODAY - timedelta(days=1)).json()["rows"][0][3] == 7.0


def test_empty_range_and_bad_ranges(client, world, admin):
    r = get(client, "intake")
    assert r.status_code == 200 and r.json()["rows"] == [] and r.json()["total_rows"] == 0
    assert get(client, "intake", frm=TODAY, to=TODAY - timedelta(days=1)).status_code == 422
    assert get(client, "intake", frm=TODAY - timedelta(days=366)).status_code == 422
    assert get(client, "intake", frm=TODAY - timedelta(days=365)).status_code == 200
    assert get(client, "nonsense").status_code == 422
    assert get(client, "intake", area=9999).status_code == 404


def test_outgoing_and_income_count_what_left_and_take_off_reversals(client, db, world, make_user, admin):
    op = make_user("juan", role="operator")
    db.add(StockMovement(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], kg=500, kind="sorted"))
    db.add(StockMovement(material_id=None, storage_area_id=world["area_d"], kg=100, kind="sorted"))
    db.commit()

    def sale(kg, price):
        return approvals.request_outgoing(db, OutgoingIn(type="sale", material_id=world["mat"]["Plastic"], kg=kg,
                                                         price_per_kg=price, storage_area_id=world["area_a"],
                                                         recipient="Buyer A"), op)

    sale(10, 12.0)
    sale(20, 10.0)
    back = sale(40, 10.0)
    approvals.review_outgoing(db, back.id, OutgoingReviewIn(decision="reverse", comment="returned"), admin)
    db.add(Outgoing(code="O-9999", type="sale", material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"],
                    kg=50, recipient="Buyer A", price_per_kg=10, total=500))   # old flow, still pending: not counted
    db.commit()
    approvals.request_outgoing(db, OutgoingIn(type="disposal", storage_area_id=world["area_d"], kg=60, recipient="ENRO"), op)

    inc = get(client, "income").json()
    assert inc["summary"] == [["Sales", "2"], ["Total income", "PHP 320.00"]]  # the reversed sale counts in neither
    assert [row[-1] for row in inc["rows"]] == [120.0, 200.0, 400.0, -400.0]  # the reversal is its own negative row
    out = get(client, "outgoing").json()
    assert out["summary"] == [["Sale", "30.00 kg"], ["Recyclables given away", "0.00 kg"], ["Compost", "0.00 kg"],
                              ["Residual disposal", "60.00 kg"]]
    assert len(out["rows"]) == 5 and out["rows"][-1][1].endswith("reversed")


def test_inventory_ignores_range_and_matches_page(client, db, world, admin):
    db.add(StockMovement(material_id=world["mat"]["Plastic"], storage_area_id=world["area_a"], kg=250, bags=5, kind="sorted"))
    db.commit()
    old = TODAY - timedelta(days=200)
    r = get(client, "inventory", frm=old, to=old).json()
    assert r["rows"] == [["Area A", "Plastic", 250.0, 5, 50]]
    page = client.get("/operations/inventory").json()
    assert r["summary"][0][1] == f"{sum(s['kg'] for s in page['stock']):,.2f} kg"


def test_composting_lists_batches_in_range(client, db, admin):
    now = datetime.now(UTC)
    b = CompostBatch(code="B-7", start_kg=80, started_at=now - timedelta(days=3))
    old = CompostBatch(code="B-1", start_kg=50, started_at=now - timedelta(days=90),
                       finished_at=now - timedelta(days=60), produced_kg=20)
    db.add_all([b, old])
    db.commit()
    r = get(client, "composting").json()
    assert [row[0] for row in r["rows"]] == ["B-7"]
    assert r["rows"][0][2:] == ["Active", 80.0, ""]
    wide = get(client, "composting", frm=TODAY - timedelta(days=100)).json()
    assert [row[0] for row in wide["rows"]] == ["B-1", "B-7"] and wide["summary"][1] == ["Compost produced", "20.00 kg"]


def test_csv_export_matches_preview_and_is_recorded(client, db, world, admin):
    delivery(db, world, "purok1", 10.0, "segregated")
    r = client.get("/reports/segregation/export", params={"from": str(TODAY), "to": str(TODAY), "format": "csv"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert f'segregation-report_{TODAY}_{TODAY}.csv' in r.headers["content-disposition"]
    lines = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    header = lines.index(["Source area", "Deliveries", "Segregated", "Compliance (%)"])
    preview = get(client, "segregation").json()
    assert lines[header + 1:] == [[str(c) for c in row] for row in preview["rows"]]
    assert db.query(ReportExport).count() == 1
    assert db.query(ActivityLog).filter_by(action="Exported segregation report as CSV").count() == 1


def test_pdf_export(client, db, world, admin):
    delivery(db, world, "purok1", 10.0, "segregated")
    for kind in ("intake", "segregation", "inventory", "composting", "outgoing", "income"):
        r = client.get(f"/reports/{kind}/export", params={"from": str(TODAY), "to": str(TODAY), "format": "pdf"})
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf", kind
        assert r.content.startswith(b"%PDF") and len(r.content) > 1000, kind


def test_preview_is_logged_and_recent_is_newest_first(client, db, world, admin):
    get(client, "intake")
    assert db.query(ActivityLog).filter_by(action="Viewed intake report").count() == 1
    assert db.query(ReportExport).count() == 0
    for kind in ("intake", "income"):
        client.get(f"/reports/{kind}/export", params={"from": str(TODAY), "to": str(TODAY), "format": "csv"})
    recent = client.get("/reports/recent").json()
    assert [r["kind"] for r in recent] == ["income", "intake"]
    assert recent[0]["by"] == "Maria Santos" and recent[0]["area"] == "All puroks" and recent[0]["title"] == "Income Report"


def test_preview_is_capped_at_500_rows(client, db, world, admin):
    from app.reports import service
    from app.reports.builders import TITLES
    from app.reports.schemas import Report

    big = Report(kind="income", title=TITLES["income"], subtitle="", summary=[], columns=["n"], rows=[[i] for i in range(600)])
    service.BUILDERS["income"], real = (lambda *a: big.model_copy()), service.BUILDERS["income"]
    try:
        r = get(client, "income").json()
    finally:
        service.BUILDERS["income"] = real
    assert len(r["rows"]) == 500 and r["total_rows"] == 600


def export_one(client, make_user, login, fmt="csv"):
    make_user("maria", role="admin")
    login("maria")
    client.get("/reports/intake/export", params={"from": str(TODAY), "to": str(TODAY), "format": fmt})
    return client.get("/reports/recent").json()[0]["id"]


def test_staff_with_the_grant_view_and_download_exports_without_new_export_rows(client, db, make_user, login):
    export_id = export_one(client, make_user, login)
    rosa = make_user("rosa", role="staff")
    login("rosa")
    assert client.get("/reports/recent").status_code == 403
    assert client.get(f"/reports/exports/{export_id}/download").status_code == 403
    db.add(StaffAccess(user_id=rosa.id, screen="reports", granted=True))
    db.commit()

    exports = db.scalar(select(func.count(ReportExport.id)))
    assert [e["id"] for e in client.get("/reports/recent").json()] == [export_id]
    assert client.get(f"/reports/exports/{export_id}").json()["kind"] == "intake"
    r = client.get(f"/reports/exports/{export_id}/download")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "intake-report" in r.headers["content-disposition"]
    assert client.get("/reports/exports/99999/download").status_code == 404
    assert db.scalar(select(func.count(ReportExport.id))) == exports

    # The grant covers exports already made, not building or previewing new ones.
    assert get(client, "intake").status_code == 403
    assert client.get("/reports/intake/export", params={"from": str(TODAY), "to": str(TODAY), "format": "csv"}).status_code == 403


def test_operators_get_no_exports(client, make_user, login):
    export_id = export_one(client, make_user, login)
    make_user("juan", role="operator")
    login("juan")
    assert client.get("/reports/recent").status_code == 403
    assert client.get(f"/reports/exports/{export_id}").status_code == 403
    assert client.get(f"/reports/exports/{export_id}/download").status_code == 403


def test_only_admins(client, make_user, login):
    assert get(client, "intake").status_code == 401
    make_user("juan", role="operator")
    make_user("rosa", role="staff")
    for who in ("juan", "rosa"):
        login(who)
        assert get(client, "intake").status_code == 403
        assert client.get("/reports/recent").status_code == 403
        export = client.get("/reports/intake/export", params={"from": str(TODAY), "to": str(TODAY), "format": "csv"})
        assert export.status_code == 403


# ---- findings


def texts(r, topic=None):
    return [f["text"] for f in r["findings"] if topic in (None, f["topic"])]


def test_intake_findings_compare_with_the_previous_period(client, db, world, admin):
    delivery(db, world, "purok1", 10.0)
    delivery(db, world, "purok2", 5.0)
    delivery(db, world, "purok1", 10.0, at=datetime.now(UTC) - timedelta(days=1))
    r = get(client, "intake").json()
    assert "Intake was 15.00 kg, up 50% from 10.00 kg in the day before." in texts(r, "compare")

    delivery(db, world, "purok1", 4990.0, at=datetime.now(UTC) - timedelta(days=1))
    later = get(client, "intake").json()
    assert "Intake was 15.00 kg, down 99% from 5,000.00 kg in the day before." in texts(later)  # not "down 100%"
    assert "Purok 1 brought the most: 10.00 kg (67% of the total)." in texts(r, "compare")


def test_segregation_findings_name_the_lowest_purok(client, db, world, admin):
    delivery(db, world, "purok1", 10.0, "segregated")
    delivery(db, world, "purok1", 5.5, "mixed")
    delivery(db, world, "purok2", 4.0, "segregated")
    r = get(client, "segregation").json()
    assert "Purok 1 had the lowest compliance: 50% (1 of 2 deliveries segregated)." in texts(r, "attention")
    assert "Plan a segregation reminder or visit for Purok 1." in texts(r, "next")


def test_composting_is_logged_by_hand_so_no_temperature_or_moisture(client, db, admin):
    b = CompostBatch(code="B-9", start_kg=80, started_at=datetime.now(UTC) - timedelta(days=2))
    db.add(b)
    db.flush()
    db.add(CompostReading(batch_id=b.id, temp_c=70.0, moisture_pct=30.0))  # an old sensor reading is ignored
    db.commit()
    r = get(client, "composting").json()
    assert r["columns"] == ["Batch", "Started", "Status", "Raw waste (kg)", "Compost (kg)"]
    assert texts(r, "attention") == []


def test_no_data_means_no_findings(client, world, admin):
    assert get(client, "intake").json()["findings"] == []


def test_findings_go_in_the_csv_above_the_table(client, db, world, admin):
    delivery(db, world, "purok1", 10.0, "segregated")
    delivery(db, world, "purok2", 4.0, "mixed")
    r = client.get("/reports/segregation/export", params={"from": str(TODAY), "to": str(TODAY), "format": "csv"})
    lines = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    header = lines.index(["Source area", "Deliveries", "Segregated", "Compliance (%)"])
    assert ["Finding", "Purok 2 had the lowest compliance: 0% (0 of 1 delivery segregated)."] in lines[:header]


# ---- AI summary


def test_numbers_check_rejects_made_up_numbers():
    from app.reports.narrate import numbers_ok

    facts = ["Intake was 1,215.50 kg, up 18% from 1,030.00 kg in the previous 30 days."]
    assert numbers_ok("Intake rose 18% to 1,215.50 kg compared with the previous 30 days.", facts)
    assert numbers_ok("Intake rose to 1215.5 kg.", facts)  # same number, other formatting
    assert not numbers_ok("Intake rose 20% to 1,215.50 kg.", facts)
    assert not numbers_ok("Intake rose by about fifty percent.", facts)
    assert numbers_ok("", facts)


@pytest.fixture
def ai(monkeypatch):
    """Turns the AI on with a fake Ollama that answers with whatever `ai.reply` holds."""
    from app.core.config import settings
    from app.reports import narrate

    class Fake:
        reply, calls = "", 0

    def post(url, json, timeout):
        Fake.calls += 1
        return httpx.Response(200, json={"response": Fake.reply}, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "ollama_url", "http://ollama:11434")
    monkeypatch.setattr(narrate.httpx, "post", post)
    monkeypatch.setattr(narrate, "_cache", {})
    return Fake


def narrative(client, kind="intake"):
    return client.get(f"/reports/{kind}/narrative", params={"from": str(TODAY), "to": str(TODAY)})


def test_summary_is_off_without_an_ollama_url(client, db, world, admin):
    delivery(db, world, "purok1", 10.0)
    assert narrative(client).json() == {"text": None}


def test_summary_is_shown_only_when_its_numbers_match(client, db, world, admin, ai):
    delivery(db, world, "purok1", 10.0)
    ai.reply = "Intake was 10.00 kg today, with none the day before."
    assert narrative(client).json()["text"] == ai.reply
    narrative(client)
    assert ai.calls == 1  # the same findings are not sent twice

    delivery(db, world, "purok1", 2.0)
    ai.reply = "Intake was 15.00 kg today."
    assert narrative(client).json() == {"text": None}


def test_summary_falls_back_when_ollama_is_down(client, db, world, admin, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")  # nothing listens here
    delivery(db, world, "purok1", 10.0)
    assert narrative(client).json() == {"text": None}


def test_staff_summary_follows_the_report_grants(client, db, make_user, login, ai):
    make_user("maria", role="admin")
    login("maria")
    client.get("/reports/income/export", params={"from": str(TODAY), "to": str(TODAY), "format": "csv"})
    income_id = client.get("/reports/recent").json()[0]["id"]
    rosa = make_user("rosa", role="staff")
    db.add(StaffAccess(user_id=rosa.id, screen="reports", granted=True))
    db.commit()
    login("rosa")
    assert client.get(f"/reports/exports/{income_id}/narrative").status_code == 403
    assert narrative(client).status_code == 403  # building new summaries is admin only
