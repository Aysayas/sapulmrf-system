import json

import pytest

from app.assistant.nlp import EXAMPLES, INTENTS, THRESHOLD, classify, examples


def _test_pairs():
    test = json.loads(EXAMPLES.read_text(encoding="utf-8"))["test"]
    return [(q, i) for i, qs in test.items() for q in qs]


def test_held_out_accuracy_is_at_least_90_percent():
    pairs = _test_pairs()
    wrong = [(q, i, classify(q).intent) for q, i in pairs if classify(q).intent != i]
    assert (len(pairs) - len(wrong)) / len(pairs) >= 0.90, wrong


def test_every_intent_has_train_and_test_examples():
    from app.assistant.nlp import _train
    data = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    assert set(INTENTS) <= set(_train()) and set(INTENTS) == set(data["test"])
    assert all(len(_train()[i]) >= 20 for i in INTENTS)


def test_test_questions_are_not_in_train():
    from app.assistant.nlp import _train
    train = {q.lower() for qs in _train().values() for q in qs}
    assert not [q for q, _ in _test_pairs() if q.lower() in train]


def test_cross_validated_on_unseen_wording():
    """The honest measure: each question is judged by a model, and an MRF-word list, that never saw it (5 folds)."""
    import numpy as np
    from sklearn.base import clone
    from sklearn.model_selection import StratifiedKFold

    from app.assistant import nlp
    from app.assistant.dates import normalize
    train = nlp._train()
    x = np.array([normalize(q) for qs in train.values() for q in qs])
    y = np.array([i for i, qs in train.items() for _ in qs])
    right = wrong = topic = slipped = off = 0
    for fit, held in StratifiedKFold(5, shuffle=True, random_state=0).split(x, y):
        model = clone(nlp._model()).fit(x[fit], y[fit])
        words = nlp.vocab(x[fit][y[fit] != nlp.OTHER])
        other = list(model.classes_).index(nlp.OTHER)
        p = model.predict_proba(x[held])
        topics = p.copy()
        topics[:, other] = -1
        guess = model.classes_[topics.argmax(1)]
        score = np.where((p.argmax(1) == other) | ~np.array([nlp.on_topic(t, words) for t in x[held]]), 0, topics.max(1))
        answered, on, truth = score >= THRESHOLD, y[held] != nlp.OTHER, y[held]
        right += (answered & (guess == truth) & on).sum()
        wrong += (answered & (guess != truth) & on).sum()
        topic += on.sum()
        slipped += (answered & ~on).sum()
        off += (~on).sum()
    assert right / topic >= 0.80     # answered, and right
    assert wrong / topic <= 0.10     # answered, but the wrong topic
    assert slipped / off <= 0.20     # off-topic that still gets an answer


@pytest.mark.parametrize("text", ["asdf qwer", "what's the weather tomorrow", "sino ang presidente ng pilipinas"])
def test_off_topic_scores_below_threshold(text):
    assert classify(text).score < THRESHOLD


def test_overlapping_topics():
    assert classify("magkano ang kinita ngayong buwan").intent == "income"
    assert classify("kailan mapupuno ang area b").intent == "storage"


def test_guess_has_a_runner_up_that_is_a_real_topic():
    g = classify("how many kg came in last week")
    assert g.intent in INTENTS and g.runner_up in INTENTS and g.runner_up != g.intent


def test_examples_for_a_topic():
    assert len(examples("compost", 3)) == 3


@pytest.mark.parametrize("intent", INTENTS)
def test_example_buttons_are_real_questions(intent):
    assert all(len(q.split()) >= 3 for q in examples(intent, 3))
