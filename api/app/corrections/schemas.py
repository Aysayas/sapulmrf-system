from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class UndoIn(BaseModel):
    delivery_id: int
    to: Literal["sort", "segregation", "delivery"]  # undo from the newest step down to this one
    reason: Reason


class FixReviewIn(BaseModel):
    review: Literal["ok", "wrong"]


class CorrectionOut(BaseModel):
    id: int
    kind: str
    record_code: str
    summary: str
    reason: str
    by: str | None
    at: datetime
    redone_as: str | None
    review: str | None


class Fixable(BaseModel):
    id: int
    code: str
    source_area: str
    category: str
    weight_kg: float
    stage: Literal["recorded", "separated", "sorted"]
