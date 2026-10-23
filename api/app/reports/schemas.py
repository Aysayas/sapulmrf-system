from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Kind = Literal["intake", "segregation", "inventory", "composting", "outgoing", "income"]
Format = Literal["csv", "pdf"]
Cell = str | int | float


class Report(BaseModel):
    """One report, the single structure the page, the CSV and the PDF are all drawn from."""

    kind: Kind
    title: str
    subtitle: str
    summary: list[tuple[str, str]]
    columns: list[str]
    rows: list[list[Cell]]
    total_rows: int = 0


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
