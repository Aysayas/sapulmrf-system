"""Which topic a question is about: a small TF-IDF + logistic regression model trained on examples.json.
Character n-grams carry typos and Tagalog affixes ("nagse-segregate"); word n-grams carry phrases.
An "other" class holds off-topic questions: when it wins, the score is 0, so the chat asks instead of guessing."""
import json
import random
from dataclasses import dataclass
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.assistant import guide
from app.assistant.dates import normalize

EXAMPLES = Path(__file__).with_name("examples.json")
INTENTS = ("today", "intake", "segregation", "storage", "compost", "outgoing", "income", "forecast", "unusual",
           "attention", "camera", "help", "smalltalk", "guide")
THRESHOLD = 0.30  # see test_cross_validated_on_unseen_wording for the measured trade-off
SURE = 0.45  # below this an answer also offers "Not what you meant?"
OTHER = "other"
# always MRF words, even if no example happens to use them
ALWAYS = frozenset(
    "kg kilo kilos kilogram purok area plastic paper cardboard metal glass compost residual recyclable biodegradable".split()
)


@dataclass(frozen=True)
class Guess:
    intent: str
    score: float
    runner_up: str


@lru_cache(maxsize=1)
def _train() -> dict[str, list[str]]:
    train = json.loads(EXAMPLES.read_text(encoding="utf-8"))["train"]
    # the guide's own example questions teach the "guide" topic, so a new guide entry trains it too
    train["guide"] = [q for e in guide.entries() for q in e.questions]
    return train


@lru_cache(maxsize=1)
def _model() -> Pipeline:
    texts, labels = zip(*[(normalize(q), intent) for intent, qs in _train().items() for q in qs], strict=True)
    model = Pipeline([
        ("f", FeatureUnion([("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
                            ("w", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True))])),
        ("m", LogisticRegression(max_iter=2000, C=10, class_weight="balanced")),  # the big guide topic mustn't swallow the rest
    ])
    return model.fit(texts, labels)


def vocab(texts) -> frozenset[str]:
    """The MRF's words: every content word of the on-topic examples."""
    words = set(ALWAYS)
    for t in texts:
        words |= {w for w in normalize(t).split() if w not in guide.FILLER and not w.isdigit() and len(w) > 1}
    return frozenset(words)


@lru_cache(maxsize=1)
def _vocab() -> frozenset[str]:
    return vocab(q for intent, qs in _train().items() if intent != OTHER for q in qs)


def on_topic(text: str, words: frozenset[str] | None = None) -> bool:
    """A question with no MRF word at all ("how do i cook rice") is off-topic, whatever the model thinks. Typos allowed."""
    words = words if words is not None else _vocab()
    content = [w for w in normalize(text).split() if w not in guide.FILLER and not w.isdigit()]
    return any(w in words or (len(w) >= 4 and get_close_matches(w, words, 1, 0.85)) for w in content)


def classify(text: str) -> Guess:
    model = _model()
    probs = model.predict_proba([normalize(text)])[0]
    ranked = sorted(zip(model.classes_, probs, strict=True), key=lambda p: -p[1])
    topics = [(label, p) for label, p in ranked if label != OTHER]
    off_topic = ranked[0][0] == OTHER or not on_topic(text)
    return Guess(intent=topics[0][0], score=0.0 if off_topic else float(topics[0][1]), runner_up=topics[1][0])


def examples(intent: str, n: int = 3) -> list[str]:
    """Example questions for a topic, to show as buttons. The same ones each time (stable for the page)."""
    qs = [q for q in _train().get(intent, []) if len(q.split()) >= 3]  # "menu" and "hi" train well but make poor buttons
    random.Random(intent).shuffle(qs)
    return qs[:n]
