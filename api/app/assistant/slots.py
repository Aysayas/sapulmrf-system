"""What a question is about besides its topic: dates, purok, storage area, material, category."""
import re
from dataclasses import dataclass, field
from datetime import date
from difflib import get_close_matches

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.assistant.dates import Period, normalize, parse_range
from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory

__all__ = ["Names", "Slots", "extract", "load_names", "normalize"]

Named = tuple[int, str]
WANTS = (  # what a question can ask to see, in English or Tagalog
    ("chart", r"\b(?:chart|charts|graph|graphs|graf|tsart|plot|visual|visualize)\b"),
    ("table", r"\b(?:table|tables|list|listahan|talaan|lista|breakdown|rows)\b"),
    ("export", r"\b(?:download|i-download|idownload|export|csv|pdf|file)\b"),
)
CHAT = (  # small talk, first match wins
    ("thanks", r"\b(?:salamat|thanks|thank you|thank u|ty|tnx|appreciate)\b"),
    ("who", r"\b(?:who are you|what are you|sino ka|ano ka|who made you|your name|pangalan mo)\b"),
    ("hello", r"\b(?:hi|hello|hey|good (?:morning|afternoon|evening)|magandang (?:umaga|hapon|gabi|araw)|kumusta ka)\b"),
)


@dataclass
class Names:
    puroks: list[Named] = field(default_factory=list)
    storage_areas: list[Named] = field(default_factory=list)
    materials: list[Named] = field(default_factory=list)
    categories: list[Named] = field(default_factory=list)


class Slots(BaseModel):
    period: Period | None = None
    purok: Named | None = None
    storage_area: Named | None = None
    material: Named | None = None
    category: Named | None = None
    unknown: list[str] = []
    days: int | None = None
    bad_dates: bool = False  # a date that doesn't exist ("feb 30"): the answer asks which dates
    wants: list[str] = []  # visuals the question asks for ("chart", "table", "export"): shown at once
    chat: str | None = None  # small talk: "thanks", "hello" or "who"
    text: str = ""  # the question itself, for the guide's search


def load_names(db: DbSession) -> Names:
    def rows(model) -> list[Named]:
        return [(i, n) for i, n in db.execute(select(model.id, model.name).where(model.active.is_(True)).order_by(model.id))]
    return Names(rows(SourceArea), rows(StorageArea), rows(Material), rows(WasteCategory))


def _fuzzy(words: list[str], options: list[Named]) -> Named | None:
    """A word (or two) close to a name, so 'platic' finds Plastic. Longest phrase first."""
    by_name = {normalize(n): (i, n) for i, n in options}
    phrases = [" ".join(words[i:i + 2]) for i in range(len(words) - 1)] + words
    for p in phrases:
        if len(p) < 4:
            continue
        hit = get_close_matches(p, by_name, n=1, cutoff=0.85)
        if hit:
            return by_name[hit[0]]
    return None


def extract(text: str, names: Names, today: date) -> Slots:
    t = normalize(text)
    try:
        s = Slots(period=parse_range(text, today))
    except ValueError:
        s = Slots(bad_dates=True)
    if m := re.search(r"\b(?:last|past|huling|nakaraang)\s+(\d{1,3})\s+(?:days|day|araw)\b", t):
        s.days = int(m[1])
    s.wants = [w for w, pattern in WANTS if re.search(pattern, t)]
    s.text = text.strip()
    s.chat = next((kind for kind, pattern in CHAT if re.search(pattern, t)), None)
    for m in re.finditer(r"\b(?:purok|p)\s*(\d{1,2})\b", t):  # the first known purok counts; unknown ones are noted
        n = int(m[1])
        hit = next(((i, name) for i, name in names.puroks if re.search(rf"\b{n}\b", name)), None)
        if hit is None:
            s.unknown.append(f"Purok {n}")
        elif s.purok is None:
            s.purok = hit
    if m := re.search(r"\barea\s+([a-z])\b", t):  # "area a" -> "Demo Area A · Plastics"
        s.storage_area = next(((i, n) for i, n in names.storage_areas
                               if re.search(rf"\barea {m[1]}\b", normalize(n))), None)
        if s.storage_area is None:
            s.unknown.append(f"Area {m[1].upper()}")
    words = [w for w in re.sub(r"\b(?:purok|p|area)\s*\w\b", " ", t).split() if not w.isdigit()]
    s.material = _fuzzy(words, names.materials)
    s.category = _fuzzy(words, names.categories)
    return s
