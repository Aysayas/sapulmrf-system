from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints


class BatchIn(BaseModel):
    start_kg: Annotated[float, Field(gt=0, le=5000)]
    sensor_id: int | None = None


class ActivityIn(BaseModel):
    type: Literal["turning", "watering", "inspection"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    finished_kg: Annotated[float, Field(gt=0, le=5000)] | None = None  # set to mark the batch finished


class ActivityOut(BaseModel):
    type: str
    note: str
    by: str | None
    at: datetime


class BatchOut(BaseModel):
    id: int
    code: str
    started_at: datetime
    start_kg: float
    sensor: str | None
    finished_at: datetime | None
    produced_kg: float | None
    activities: list[ActivityOut] = []


class ReadingIn(BaseModel):
    """What a device sends. A weighing station sends kg; a compost sensor sends temp_c and moisture_pct."""

    kg: Annotated[float, Field(ge=0, le=5000)] | None = None
    stable: bool | None = None
    temp_c: Annotated[float, Field(ge=-20, le=120)] | None = None
    moisture_pct: Annotated[float, Field(ge=0, le=100)] | None = None
    read_at: AwareDatetime | None = None  # when it was measured, for readings buffered while offline


class ReadingOut(BaseModel):
    device: str
    stored_on: str | None  # the batch code a compost reading was stored on
