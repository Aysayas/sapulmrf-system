from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Kind = Literal["intake", "segregation", "inventory", "composting", "outgoing", "income"]
Format = Literal["csv", "pdf"]
Cell = str | int | float


Topic = Literal["compare", "attention", "next"]


class Finding(BaseModel):
    """One sentence computed from the data, so its numbers are always right. Topic matches a suggested question."""

    topic: Topic
    text: str


class Report(BaseModel):
    """One report, the single structure the page, the CSV and the PDF are all drawn from."""

    kind: Kind
    title: str
    subtitle: str
    summary: list[tuple[str, str]]
    columns: list[str]
    rows: list[list[Cell]]
    total_rows: int = 0
    findings: list[Finding] = []


class Narrative(BaseModel):
    text: str | None  # None: the AI is off or its paragraph failed the number check


class RecentExport(BaseModel):
    id: int
    kind: Kind
    title: str
    from_day: date
    to_day: date
    area_id: int | None
    area: str
    format: Format
    by: str
    created_at: datetime
