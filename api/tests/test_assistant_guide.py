import json

import pytest

from app.assistant.answers import answer
from app.assistant.guide import GUIDE, entries, find
from app.assistant.slots import Slots
from app.insights.service import today as local_today

ADMIN_ROUTES = ("/admin", "/admin/approvals", "/admin/alerts", "/admin/operations/intake", "/admin/operations/segregation",
                "/admin/operations/sorting", "/admin/operations/inventory", "/admin/operations/compost",
                "/admin/operations/outgoing", "/admin/operations/camera", "/admin/insights", "/admin/reports",
                "/admin/assistant", "/admin/settings", "/admin/settings/users", "/admin/settings/roles",
                "/admin/settings/masterdata", "/admin/settings/devices", "/admin/settings/ranges", "/admin/settings/activity")


def test_every_entry_is_complete_and_links_to_a_real_page():
    ids = set()
    for e in entries():
        assert e.id not in ids and e.kind in ("meaning", "howto", "where") and e.title and e.text
        assert len(e.questions) >= 3, e.id
        assert e.link.to.split("?")[0] in ADMIN_ROUTES, (e.id, e.link.to)
        ids.add(e.id)
    assert len(ids) >= 30


@pytest.mark.parametrize("question,entry", [
    ("what does compliance mean", "compliance"),
    ("ano ang ibig sabihin ng residual", "residual"),
    ("how do I export a report", "export-report"),
    ("paano mag download ng report", "export-report"),
    ("where do I review sales", "review-outgoing"),
    ("how to add a buyer", "add-buyer"),
    ("saan ko makikita ang live camera", "live-camera"),
    ("what is a give-away", "giveaway"),
    ("ano ang ibig sabihin ng compliance?", "compliance"),
    ("ano ang kahulugan ng recount", "recount"),
])
def test_find_picks_the_right_entry(question, entry):
    hit, score = find(question)
    assert hit is not None and hit.id == entry, (question, hit and hit.id, score)


def test_no_entry_for_nonsense():
    hit, _ = find("purple elephants dancing")
    assert hit is None


def test_guide_answer_has_text_steps_and_a_link(db, world):
    a = answer(db, "guide", Slots(text="how do I export a report"), local_today())
    assert a.intent == "guide" and a.summary and a.steps and a.links[0].to.startswith("/admin/reports")


def test_guide_answer_without_a_match_offers_close_entries(db, world):
    a = answer(db, "guide", Slots(text="how do I fly a kite"), local_today())
    assert a.title.startswith("I don't have a guide") and len(a.suggestions) == 3


def test_guide_questions_train_the_classifier():
    data = json.loads((GUIDE.parent / "examples.json").read_text(encoding="utf-8"))
    assert "guide" in data["test"]
