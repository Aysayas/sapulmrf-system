"""Dates in a question, in English or Tagalog: "last week", "kahapon", "noong oktubre", "nov 1-5", ISO ranges."""
import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    from_day: date
    to_day: date  # inclusive
    label: str


def normalize(text: str) -> str:
    """Lowercase, no accents, only letters, digits, '-' and single spaces."""
    t = unicodedata.normalize("NFKD", text.replace("–", "-").replace("—", "-")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", t.lower()).split())


MONTHS = {}
for _n, (_en, _abbr, _tl) in enumerate([
    ("january", "jan", "enero"), ("february", "feb", "pebrero"), ("march", "mar", "marso"), ("april", "apr", "abril"),
    ("may", "may", "mayo"), ("june", "jun", "hunyo"), ("july", "jul", "hulyo"), ("august", "aug", "agosto"),
    ("september", "sep", "setyembre"), ("october", "oct", "oktubre"), ("november", "nov", "nobyembre"),
    ("december", "dec", "disyembre"),
], start=1):
    MONTHS.update({_en: _n, _abbr: _n, _tl: _n})
MONTHS["sept"] = 9
MONTHS["septyembre"] = 9
_MONTH = "|".join(sorted((m for m in MONTHS if m != "may"), key=len, reverse=True))  # bare "may" is too common


def _fmt(d: date) -> str:
    return f"{d:%b} {d.day}"


def _month(year: int, month: int, today: date) -> Period:
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return Period(first, min(last, today), f"{first:%B %Y}")


def _month_named(m: int, today: date) -> Period:
    year = today.year if m <= today.month else today.year - 1  # a month still to come means last year's
    return _month(year, m, today)


def parse_range(text: str, today: date) -> Period | None:
    t = normalize(text)
    if m := re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|-|hanggang|until)\s*(\d{4}-\d{2}-\d{2})", t):
        a, b = date.fromisoformat(m[1]), date.fromisoformat(m[2])
        return Period(a, b, f"{_fmt(a)} to {_fmt(b)}")
    if m := re.search(rf"\b({_MONTH}|may)\s+(\d{{1,2}})\s*(?:-|to|hanggang)\s*(\d{{1,2}})\b", t):
        mon = MONTHS[m[1]]
        year = today.year if mon <= today.month else today.year - 1
        a, b = date(year, mon, int(m[2])), date(year, mon, int(m[3]))
        return Period(a, b, f"{_fmt(a)} to {_fmt(b)}")
    if m := re.search(r"\b\d{4}-\d{2}-\d{2}\b", t):
        d = date.fromisoformat(m[0])
        return Period(d, d, _fmt(d))
    if m := re.search(r"\b(?:last|past|huling|nakaraang)\s+(\d{1,3})\s+(?:days|day|araw)\b", t):
        n = max(1, int(m[1]))
        return Period(today - timedelta(days=n - 1), today, f"the last {n} days")
    if re.search(r"\b(?:ngayong linggo|this week|linggong ito)\b", t):
        start = today - timedelta(days=today.weekday())
        return Period(start, today, "this week")
    if re.search(r"\b(?:last week|noong isang linggo|nakaraang linggo)\b", t):
        end = today - timedelta(days=today.weekday() + 1)
        return Period(end - timedelta(days=6), end, "last week")
    if re.search(r"\b(?:ngayong buwan|this month|buwang ito)\b", t):
        return Period(today.replace(day=1), today, "this month")
    if re.search(r"\b(?:last month|noong isang buwan|nakaraang buwan)\b", t):
        prev = today.replace(day=1) - timedelta(days=1)
        p = _month(prev.year, prev.month, today)
        return Period(p.from_day, p.to_day, "last month")
    if re.search(r"\b(?:this year|ngayong taon)\b", t):
        return Period(date(today.year, 1, 1), today, "this year")
    if re.search(r"\b(?:yesterday|kahapon)\b", t):
        d = today - timedelta(days=1)
        return Period(d, d, "yesterday")
    if re.search(r"\b(?:today|ngayon|ngayong araw)\b", t):
        return Period(today, today, "today")
    if m := re.search(rf"\b(?:in|noong|nung|ng|sa|for)\s+(may)\b|\b({_MONTH})\b", t):
        return _month_named(MONTHS[m[1] or m[2]], today)
    return None
