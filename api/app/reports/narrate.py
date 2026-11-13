"""Optional AI summary: a local LLM rewords a report's findings as one paragraph.

The model only rewords. Its paragraph is dropped if it holds any number the findings don't, so a wrong figure
never reaches the page; the findings themselves are always shown.
"""

import re

import httpx

from app.core.config import settings
from app.reports.schemas import Report

TIMEOUT = 60  # seconds; a 7B model partly on the CPU of a 6 GB laptop GPU needs this on the first call
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
PROMPT = """You write for the administrator of a barangay waste facility.
Rewrite the findings below from the {title} as one short paragraph of at most 80 words.
Use only these facts. Copy every number exactly as written. Do not add numbers, dates, causes or advice that are not listed.
Keep each number with the same thing and the same period it belongs to. Give no advice.

Findings:
{findings}

Paragraph:"""

# shortcut: in-process cache, fine for one API process; move to a table if it runs several workers.
_cache: dict[tuple, str | None] = {}


WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
         "million", "dozen", "half", "double", "twice", "triple", "quarter"}


def _numbers(text: str) -> set[float | str]:
    words = set(re.findall(r"[a-z]+", text.lower())) & WORDS
    return {float(n.replace(",", "")) for n in NUMBER.findall(text)} | words


def numbers_ok(paragraph: str, findings: list[str]) -> bool:
    """True when every number in the paragraph, in digits or words, appears in the findings."""
    allowed = set().union(*(_numbers(f) for f in findings)) if findings else set()
    return _numbers(paragraph) <= allowed


def narrate(r: Report) -> str | None:
    """The checked paragraph, or None when the AI is off, unreachable, slow, or got a number wrong."""
    texts = [f.text for f in r.findings if f.topic != "next"]  # advice stays in the bullets, the model reworded it as done
    if not settings.ollama_url or not texts:
        return None
    key = (settings.ollama_model, r.title, tuple(texts))
    if key not in _cache:
        prompt = PROMPT.format(title=r.title, findings="\n".join(f"- {t}" for t in texts))
        try:
            res = httpx.post(f"{settings.ollama_url}/api/generate", timeout=TIMEOUT, json={
                "model": settings.ollama_model, "prompt": prompt, "stream": False,
                "options": {"temperature": 0, "num_predict": 200}})
            res.raise_for_status()
            text = res.json().get("response", "").strip()
        except (httpx.HTTPError, ValueError):
            return None  # not cached, so the next try can succeed
        _cache[key] = text if text and numbers_ok(text, texts) else None
    return _cache[key]
