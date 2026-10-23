from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Kg = Annotated[float, Field(gt=0, le=5000)]
KgOrZero = Annotated[float, Field(ge=0, le=5000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class DeliveryIn(BaseModel):
    source_area_id: int
    category_id: int
    weight_kg: Kg
    weighed_by: Literal["scale", "manual"]
    scale_kg: Kg | None = None  # the scale's reading, when the operator corrected it
    correction_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    device_id: int | None = None


class SegregationIn(BaseModel):
    condition: Literal["segregated", "mixed"]
    wet_kg: KgOrZero
    dry_kg: KgOrZero
    note: Note = ""


class SegregationOut(BaseModel):
    condition: str
    wet_kg: float
    dry_kg: float
    note: str
    checked_at: datetime


class DeliveryOut(BaseModel):
    id: int
    code: str
    received_at: datetime
    source_area: str
    category: str
    weight_kg: float
    weighed_by: str
    scale_kg: float | None
    corrected: bool
    correction_reason: str | None
    status: str
    recorded_by: str | None
    segregation: SegregationOut | None = None
