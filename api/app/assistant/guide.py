"""Help with the website itself: what a word means, how to do something, where a page is.
Each entry in guide.json has example questions; a question is matched to the entry whose examples it is closest to
(TF-IDF over 3-5 letter chunks, so typos and Tagalog affixes still match)."""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

from app.assistant.dates import normalize
from app.assistant.schemas import Link

GUIDE = Path(__file__).with_name("guide.json")
MIN_SCORE = 0.35  # below this the closest entry isn't close enough: offer the nearest ones instead
# question words every guide question shares; matching on them made "how do i fly a kite" look like "how do i add a user"
FILLER = frozenset("""how do does did i we you can could to a an the is are was what whats where when which who why my me our
this that it of for in on at with please here there means mean meaning define explain tell show find get see
paano ano ang ng mga sa ba ko ako natin namin saan nasaan kung ito iyan yung yun po nga mag maka
ibig sabihin kahulugan""".split())


def _content(text: str) -> str:
    return " ".join(w for w in normalize(text).split() if w not in FILLER) or normalize(text)


@dataclass(frozen=True)
class Entry:
    id: str
    kind: str  # meaning | howto | where
    title: str
    text: str
    steps: tuple[str, ...]
    link: Link
    questions: tuple[str, ...]


@lru_cache(maxsize=1)
def entries() -> tuple[Entry, ...]:
    raw = json.loads(GUIDE.read_text(encoding="utf-8"))
    return tuple(Entry(id=e["id"], kind=e["kind"], title=e["title"], text=e["text"], steps=tuple(e.get("steps", [])),
                       link=Link(**e["link"]), questions=tuple(e["questions"])) for e in raw)


@lru_cache(maxsize=1)
def _index():
    owners, docs = [], []
    for e in entries():
        for q in (e.title, *e.questions):
            owners.append(e)
            docs.append(_content(q))
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit(docs)
    return vec, vec.transform(docs), owners


def _scores(text: str) -> dict[str, tuple[float, Entry]]:
    vec, matrix, owners = _index()
    sims = (matrix @ vec.transform([_content(text)]).T).toarray().ravel()  # rows are L2-normalised: cosine
    best: dict[str, tuple[float, Entry]] = {}
    for s, e in zip(sims, owners, strict=True):
        if s > best.get(e.id, (-1.0, e))[0]:
            best[e.id] = (float(s), e)
    return best


def find(text: str) -> tuple[Entry | None, float]:
    ranked = sorted(_scores(text).values(), key=lambda p: -p[0])
    score, entry = ranked[0]
    return (entry if score >= MIN_SCORE else None), score


def nearest(text: str, n: int = 3) -> list[Entry]:
    return [e for _, e in sorted(_scores(text).values(), key=lambda p: -p[0])[:n]]
