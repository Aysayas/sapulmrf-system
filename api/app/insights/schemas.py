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


class MaterialAccuracy(BaseModel):
    material: str          # what the camera suggested
    suggested: int
    kept: int
    changed: int
    changed_to: str | None  # what operators most often chose instead ("Not recyclable" included)


class ConfidenceBand(BaseModel):
    band: str              # "Below 60%", "60–80%", "80% and up"
    confirmed: int
    kept_pct: int


class KioskAccuracy(BaseModel):
    with_camera: int       # kiosk drop-offs with a camera result
    matched: int           # the camera's category was the one recorded
    matched_pct: int


class CameraAccuracy(BaseModel):
    confirmed: int
    kept: int
    kept_pct: int
    changed: int
    reviewed_wrong: int  # changes the admin marked wrong
    by_material: list[MaterialAccuracy] = []
    by_confidence: list[ConfidenceBand] = []
    kiosk: KioskAccuracy | None = None


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
    errors_7d: dict[str, float | None]  # total kg error (WAPE) % per model
    errors_14d: dict[str, float | None]
    history: list[DayKg]  # last 21 full days
    forecast: list[DayKg]  # next 7 days, from the model in use
    made_on: date | None
    compared: list[Compared]  # last 7 days, model in use
    missing_days: int  # of those 7, days with no forecast (the system was off)
    avg_error_pct: float | None  # total kg error over the compared days
    outlook: list[Outlook]
    schedule: list[Suggestion]
    camera: CameraAccuracy | None  # None for staff without the camera grant


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
