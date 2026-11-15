from datetime import date

import pytest

from app.assistant.dates import parse_range
from app.assistant.slots import Names, extract, load_names

TODAY = date(2026, 11, 14)  # a Saturday; weeks start on Monday


@pytest.fixture
def names():
    return Names(puroks=[(i, f"Purok {i}") for i in range(1, 8)],
                 storage_areas=[(351, "Demo Area A · Plastics"), (352, "Demo Area B · Paper & cardboard")],
                 materials=[(1, "Plastic"), (2, "Paper"), (3, "Metal")],
                 categories=[(10, "Recyclable"), (11, "Biodegradable")])


@pytest.mark.parametrize("text,frm,to", [
    ("today", "2026-11-14", "2026-11-14"), ("ngayon", "2026-11-14", "2026-11-14"),
    ("yesterday", "2026-11-13", "2026-11-13"), ("kahapon", "2026-11-13", "2026-11-13"),
    ("this week", "2026-11-09", "2026-11-14"), ("ngayong linggo", "2026-11-09", "2026-11-14"),
    ("last week", "2026-11-02", "2026-11-08"), ("noong isang linggo", "2026-11-02", "2026-11-08"),
    ("this month", "2026-11-01", "2026-11-14"), ("ngayong buwan", "2026-11-01", "2026-11-14"),
    ("last month", "2026-10-01", "2026-10-31"), ("nakaraang buwan", "2026-10-01", "2026-10-31"),
    ("last 7 days", "2026-11-08", "2026-11-14"), ("this year", "2026-01-01", "2026-11-14"),
    ("in october", "2026-10-01", "2026-10-31"), ("noong oktubre", "2026-10-01", "2026-10-31"),
    ("nov 1-5", "2026-11-01", "2026-11-05"), ("from 2026-10-03 to 2026-10-09", "2026-10-03", "2026-10-09"),
    ("december", "2025-12-01", "2025-12-31"),  # a month later than now means last year's
])
def test_parse_range(text, frm, to):
    p = parse_range(text, TODAY)
    assert p is not None, text
    assert (p.from_day.isoformat(), p.to_day.isoformat()) == (frm, to)
    assert p.label


def test_no_date_gives_none():
    assert parse_range("how much compost", TODAY) is None


def test_purok_material_area_and_unknown(names):
    s = extract("plastic from p3 and purok 99 in area a", names, TODAY)
    assert s.purok == (3, "Purok 3") and s.material[1] == "Plastic"
    assert s.storage_area[1].startswith("Demo Area A") and s.unknown == ["Purok 99"]


def test_typo_material_matches(names):
    assert extract("platic", names, TODAY).material[1] == "Plastic"


def test_last_n_days_also_sets_days(names):
    s = extract("camera accuracy last 14 days", names, TODAY)
    assert s.days == 14 and s.period.from_day == date(2026, 11, 1)


def test_category(names):
    assert extract("forecast for biodegradable", names, TODAY).category == (11, "Biodegradable")


def test_load_names_reads_active_master_data(db, world):
    n = load_names(db)
    assert n.puroks and n.storage_areas and n.materials and n.categories
    assert all(isinstance(i, int) and isinstance(name, str) for i, name in n.materials)


@pytest.mark.parametrize("text", ["intake feb 30-31", "intake nov 1-40", "intake 2026-02-30"])
def test_impossible_dates_are_flagged_not_raised(names, text):
    s = extract(text, names, TODAY)
    assert s.bad_dates and s.period is None


@pytest.mark.parametrize("text,wants", [
    ("show a chart of intake last week", ["chart"]), ("graph ng benta", ["chart"]),
    ("income this month as a table", ["table"]), ("listahan ng mga ibinigay", ["table"]),
    ("i-download ang csv ng intake", ["export"]), ("intake last month", []),
    ("table and chart of income", ["chart", "table"]),
])
def test_asking_for_a_visual(names, text, wants):
    assert extract(text, names, TODAY).wants == wants


@pytest.mark.parametrize("text,chat", [("salamat po", "thanks"), ("thank you!", "thanks"), ("hi", "hello"),
                                       ("magandang umaga", "hello"), ("who are you", "who"), ("ano ka", "who")])
def test_small_talk_kind(names, text, chat):
    assert extract(text, names, TODAY).chat == chat
