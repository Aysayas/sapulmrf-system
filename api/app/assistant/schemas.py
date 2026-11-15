from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.reports.schemas import Kind

Cell = str | float | int | None


class Card(BaseModel):
    label: str
    value: str
    delta: str | None = None


class Table(BaseModel):
    columns: list[str]
    rows: list[list[Cell]]


class Series(BaseModel):
    name: str
    values: list[float]


class Chart(BaseModel):
    kind: Literal["bar", "line"]
    x: list[str]
    series: list[Series]


class ExportRef(BaseModel):
    kind: Kind
    from_day: date
    to_day: date
    area: int | None = None


class Link(BaseModel):
    label: str
    to: str  # a page on this website, e.g. /admin/reports


class Answer(BaseModel):
    """What the chat shows for one question. Every number in it comes from an existing SapulMRF function."""

    intent: str
    title: str
    summary: str
    cards: list[Card] = []
    table: Table | None = None
    chart: Chart | None = None
    export: ExportRef | None = None
    note: str | None = None
    suggestions: list[str] = []
    steps: list[str] = []  # how-to answers: what to click, in order
    links: list[Link] = []  # pages the answer points to
    show: list[str] = []  # visuals opened at once because the question asked for them; the rest are offered
