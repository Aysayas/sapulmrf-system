from datetime import UTC, datetime

import pytest

from app.intake.models import Delivery


@pytest.fixture
def admin(make_user, login):
    u = make_user("maria", role="admin", name="Maria Santos")
    login("maria")
    return u


def ask(client, text, conversation_id=None, intent=None):
    body = {"text": text}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if intent:
        body["intent"] = intent
    return client.post("/assistant/ask", json=body)


@pytest.mark.parametrize("role", ["operator", "staff"])
def test_only_admins_can_ask(client, make_user, login, role):
    make_user("pedro", role=role)
    login("pedro")
    assert ask(client, "income this month").status_code == 403
    assert client.get("/assistant/conversations").status_code == 403


def test_blank_question_is_422(client, admin):
    assert ask(client, "   ").status_code == 422


def test_long_question_is_422(client, admin):
    assert ask(client, "x" * 501).status_code == 422


def test_ask_creates_a_conversation_titled_by_the_question(client, world, admin):
    r = ask(client, "How much did we earn this month? " + "x" * 80)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assistant"]["answer"]["intent"] == "income" and body["user"]["role"] == "user"
    convs = client.get("/assistant/conversations").json()
    assert len(convs) == 1 and convs[0]["id"] == body["conversation_id"] and len(convs[0]["title"]) <= 60


def test_follow_up_keeps_topic_and_dates(client, db, world, admin):
    first = ask(client, "how many kg from purok 1 last month").json()
    assert first["assistant"]["answer"]["intent"] == "intake"
    second = ask(client, "and purok 2?", first["conversation_id"]).json()
    a = second["assistant"]["answer"]
    assert a["intent"] == "intake" and "last month" in a["title"]
    assert a["export"]["area"] == world["purok2"] and "Purok 2" in a["title"]
    assert not any(x.startswith("Not what you meant?") for x in a["suggestions"])  # a follow-up's topic isn't in doubt


def test_intent_override_skips_the_classifier(client, world, admin):
    a = ask(client, "asdf", intent="compost").json()["assistant"]["answer"]
    assert a["intent"] == "compost"


def test_gibberish_asks_did_you_mean(client, world, admin):
    a = ask(client, "asdf qwer").json()["assistant"]["answer"]
    assert a["intent"] == "unsure" and len(a["suggestions"]) == 3


def test_history_is_private(client, world, make_user, login, admin):
    body = ask(client, "income this month").json()
    cid, mid = body["conversation_id"], body["assistant"]["id"]
    make_user("ana", role="admin")
    login("ana")
    assert client.get("/assistant/conversations").json() == []
    assert client.get(f"/assistant/conversations/{cid}").status_code == 404
    assert client.patch(f"/assistant/conversations/{cid}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/assistant/conversations/{cid}").status_code == 404
    assert client.post(f"/assistant/messages/{mid}/feedback", json={"helpful": True}).status_code == 404
    assert ask(client, "and today?", cid).status_code == 404


def test_rename_delete_and_feedback(client, world, admin):
    body = ask(client, "income this month").json()
    cid, mid = body["conversation_id"], body["assistant"]["id"]
    assert client.patch(f"/assistant/conversations/{cid}", json={"title": "Money"}).json()["title"] == "Money"
    r = client.post(f"/assistant/messages/{mid}/feedback", json={"helpful": False, "corrected_intent": "outgoing"})
    assert r.status_code == 204
    detail = client.get(f"/assistant/conversations/{cid}").json()
    assert detail["messages"][1]["helpful"] is False
    assert client.delete(f"/assistant/conversations/{cid}").status_code == 204
    assert client.get("/assistant/conversations").json() == []


def test_feedback_rejects_an_unknown_topic(client, world, admin):
    mid = ask(client, "income this month").json()["assistant"]["id"]
    r = client.post(f"/assistant/messages/{mid}/feedback", json={"helpful": False, "corrected_intent": "weather"})
    assert r.status_code == 422


def test_reopened_conversation_returns_saved_answers_in_order(client, db, world, admin):
    cid = ask(client, "how many kg today").json()["conversation_id"]
    ask(client, "income this month", cid)
    db.add(Delivery(code="D-LATE", source_area_id=world["purok1"], category_id=world["cat"]["Recyclable"],
                    weight_kg=9, weighed_by="manual", received_at=datetime.now(UTC)))
    db.commit()  # new data after the answer: the saved answer stays as it was
    msgs = client.get(f"/assistant/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[1]["answer"]["cards"][0]["value"] == "0"


def test_a_shaky_answer_offers_its_runner_up():
    from app.assistant.nlp import Guess, examples
    from app.assistant.schemas import Answer
    from app.assistant.service import with_hint
    a = Answer(intent="intake", title="t", summary="s")
    shaky = with_hint(a, Guess(intent="intake", score=0.35, runner_up="income"))
    assert shaky.suggestions[0] == f"Not what you meant? {examples('income', 1)[0]}"
    assert with_hint(a, Guess(intent="intake", score=0.9, runner_up="income")).suggestions == []


def test_suggestions(client, admin):
    s = client.get("/assistant/suggestions").json()
    assert len(s) >= 4 and all(isinstance(x, str) for x in s)


def test_impossible_date_asks_which_dates_instead_of_crashing(client, world, admin):
    r = ask(client, "intake feb 30-31")
    assert r.status_code == 200 and r.json()["assistant"]["answer"]["title"] == "Which dates?"


def test_follow_up_drops_a_stale_unknown_purok_note(client, world, admin):
    cid = ask(client, "intake purok 99 last month").json()["conversation_id"]
    a = ask(client, "and purok 2?", cid).json()["assistant"]["answer"]
    assert "Purok 2" in a["title"] and "Purok 99" not in (a["note"] or "")


def test_a_clear_new_topic_wins_over_a_follow_up_word(client, world, admin):
    cid = ask(client, "how many kg came in last month").json()["conversation_id"]
    a = ask(client, "and how much did we earn?", cid).json()["assistant"]["answer"]
    assert a["intent"] == "income"
