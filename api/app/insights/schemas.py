from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class DayKg(BaseModel):
    day: date
    kg: float


class Compared(BaseModel):
    day: date
    predicted: float
    actual: float
    diff: float  # actual - predicted
    pct: float | None  # |diff| / actual, None when nothing was received


class Outlook(BaseModel):
    area: str
    pct: int
    kg: float
    capacity_kg: int
    alert_pct: int
    per_day_kg: float  # average sorted in per day, last 14 days
    days_to_full: int | None  # None: not filling (no inflow)
    days_to_alert: int | None


class Suggestion(BaseModel):
    on: date
    what: str
    why: str


class CameraAccuracy(BaseModel):
    confirmed: int
    kept: int
    kept_pct: int
    changed: int
    reviewed_wrong: int  # changes the admin marked wrong


class Category(BaseModel):
    id: int  # 0 = all waste
    name: str


class Predictions(BaseModel):
    ready: bool
    days_of_records: int
    min_days: int
    categories: list[Category]
    category: int
    model_used: Literal["baseline", "ml"]
    errors_7d: dict[str, float | None]  # MAPE % per model
    errors_14d: dict[str, float | None]
    history: list[DayKg]  # last 21 full days
    forecast: list[DayKg]  # next 7 days, from the model in use
    made_on: date | None
    compared: list[Compared]  # last 7 days, model in use
    avg_error_pct: float | None
    outlook: list[Outlook]
    schedule: list[Suggestion]
    camera: CameraAccuracy


class FlagOut(BaseModel):
    id: int
    kind: str
    delivery_id: int
    code: str
    received_at: datetime
    source_area: str
    category: str
    value_kg: float
    expected_low: float
    expected_high: float
    why: str
    expected: str
    status: str
    decided_by: str | None
    decided_at: datetime | None


class FlagDecision(BaseModel):
    decision: Literal["valid", "incorrect"]
