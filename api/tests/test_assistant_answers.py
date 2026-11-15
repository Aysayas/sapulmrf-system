from datetime import UTC, date, datetime

import pytest

from app.assistant.answers import answer, unsure
from app.assistant.dates import Period
from app.assistant.nlp import INTENTS, Guess
from app.assistant.schemas import Answer
from app.assistant.slots import Slots
from app.insights.service import today as local_today
from app.intake.models import Delivery
from app.reports.service import build


def _deliveries(db, world, n=2, kg=4.0, area="purok1"):
    for i in range(n):
        db.add(Delivery(code=f"D-T{area[-1]}{i}", source_area_id=world[area], category_id=world["cat"]["Recyclable"],
                        weight_kg=kg, weighed_by="manual", received_at=datetime.now(UTC)))
    db.commit()


def _month(today):
    return Period(today.replace(day=1), today, "this month")


def test_intake_answer_matches_the_report(db, world):
    _deliveries(db, world)
    t = local_today()
    a = answer(db, "intake", Slots(period=_month(t)), t)
    r = build(db, "intake", t.replace(day=1), t, None)
    assert a.cards[0].value == r.summary[0][1] and a.cards[1].value == r.summary[1][1]
    assert a.export is not None and a.export.kind == "intake" and a.export.from_day == t.replace(day=1)
    assert a.chart is not None and a.chart.series[0].values  # kg per purok


def test_purok_filters_intake(db, world):
    _deliveries(db, world, n=2, area="purok1")
    _deliveries(db, world, n=1, area="purok2")
    t = local_today()
    a = answer(db, "intake", Slots(period=_month(t), purok=(world["purok2"], "Purok 2")), t)
    assert a.cards[0].value == "1" and a.export.area == world["purok2"]
    assert "Purok 2" in a.title
    assert a.chart is not None and a.chart.x == ["Recyclable"]  # one purok: charted by category instead


def test_chart_skips_a_column_with_one_value():
    from app.assistant.answers import _chart
    from app.reports.schemas import Report
    cols = ["Source area", "Waste category", "Deliveries", "Weight (kg)"]
    r = Report(kind="intake", title="t", subtitle="s", summary=[], columns=cols,
               rows=[["Purok 1", "Recyclable", 1, 2.0], ["Purok 1", "Residual", 1, 3.0]])
    assert _chart(r).x == ["Recyclable", "Residual"] and _chart(r).series[0].values == [2.0, 3.0]


def test_purok_on_income_covers_all_puroks_and_says_so(db, world):
    t = local_today()
    a = answer(db, "income", Slots(period=_month(t), purok=(world["purok1"], "Purok 1")), t)
    assert "all puroks" in a.note and a.export.area is None


def test_unknown_purok_is_noted(db, world):
    t = local_today()
    a = answer(db, "intake", Slots(period=_month(t), unknown=["Purok 99"]), t)
    assert "No Purok 99 in SapulMRF" in a.note


@pytest.mark.parametrize("period", [
    Period(date(2026, 11, 5), date(2026, 11, 1), "x"),   # reversed
    Period(date(2024, 1, 1), date(2026, 11, 1), "x"),    # over a year
])
def test_bad_range_asks_which_dates(db, world, period):
    a = answer(db, "intake", Slots(period=period), date(2026, 11, 14))
    assert a.title == "Which dates?" and a.export is None


def test_future_range_asks_which_dates(db, world):
    t = local_today()
    a = answer(db, "intake", Slots(period=Period(date(t.year + 1, 1, 1), date(t.year + 1, 1, 31), "x")), t)
    assert a.title == "Which dates?"


def test_default_period_is_noted(db, world):
    a = answer(db, "outgoing", Slots(), local_today())
    assert a.note and "Assumed this month" in a.note


def test_forecast_not_ready_on_empty_db(db, world):
    a = answer(db, "forecast", Slots(), local_today())
    assert a.summary.startswith("Not enough data yet")


@pytest.mark.parametrize("intent", INTENTS)
def test_every_handler_answers_on_an_empty_db(db, world, intent):
    a = answer(db, intent, Slots(), local_today())
    assert isinstance(a, Answer) and a.title and a.intent == intent


def test_unsure_offers_two_topics_and_help():
    a = unsure(Guess(intent="income", score=0.1, runner_up="outgoing"))
    assert a.intent == "unsure" and a.title == "Did you mean…" and len(a.suggestions) == 3
    assert a.suggestions[-1] == "What can you answer?"


def test_impossible_dates_ask_which_dates(db, world):
    a = answer(db, "intake", Slots(bad_dates=True), local_today())
    assert a.title == "Which dates?" and a.export is None


def test_a_requested_visual_is_shown_and_others_wait(db, world):
    _deliveries(db, world, n=2, area="purok1")
    _deliveries(db, world, n=1, area="purok2")
    t = local_today()
    asked = answer(db, "intake", Slots(period=_month(t), wants=["chart", "table"]), t)
    assert asked.show == ["chart", "table"]
    plain = answer(db, "intake", Slots(period=_month(t)), t)
    assert plain.show == [] and plain.chart is not None  # there to offer, not shown


def test_a_request_for_a_visual_the_answer_lacks_is_dropped(db, world):
    a = answer(db, "attention", Slots(wants=["chart", "export"]), local_today())
    assert "export" not in a.show


def test_stock_of_one_material_per_area(db, world):
    from test_approvals import stock
    stock(db, world, kg=40, material="Plastic", area="area_a")
    stock(db, world, kg=7, material="Paper", area="area_a")
    a = answer(db, "storage", Slots(material=(world["mat"]["Plastic"], "Plastic")), local_today())
    assert "Plastic" in a.title and "40" in a.summary
    assert [r[0] for r in a.table.rows] and all("Paper" not in str(r) for r in a.table.rows)


@pytest.mark.parametrize("chat,word", [("thanks", "welcome"), ("hello", "Ask"), ("who", "SapulMRF")])
def test_small_talk_replies_in_words(db, world, chat, word):
    a = answer(db, "smalltalk", Slots(chat=chat), local_today())
    assert word in a.summary and not a.cards and a.chart is None
