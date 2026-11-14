from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.corrections.schemas import CorrectionOut
from app.intake.schemas import ClientKey

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Required = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class AdjustmentIn(BaseModel):
    material_id: int | None  # None means residual
    storage_area_id: int
    actual_kg: Annotated[float, Field(ge=0, le=50000)]
    reason: Required
    details: Text = ""


class OutgoingIn(BaseModel):
    type: Literal["sale", "compost", "disposal"]
    material_id: int | None = None
    storage_area_id: int | None = None
    kg: Annotated[float, Field(ge=0.01, le=50000)]
    recipient: Required
    price_per_kg: Annotated[float, Field(ge=0.01, le=100000)] | None = None
    client_key: ClientKey | None = None

    @model_validator(mode="after")
    def fits_the_type(self):
        if self.price_per_kg and round(self.kg, 2) * round(self.price_per_kg, 2) >= 100_000_000:
            raise ValueError("That total is too large. Check the kg and the price.")
        if self.type == "sale" and (self.material_id is None or self.storage_area_id is None or self.price_per_kg is None):
            raise ValueError("A sale needs the material, the storage area it leaves from, and the price per kg.")
        if self.type == "disposal" and (self.storage_area_id is None or self.material_id is not None or self.price_per_kg):
            raise ValueError("Residual for disposal needs its storage area, and has no material or price.")
        if self.type == "compost" and (self.material_id is not None or self.storage_area_id is not None):
            raise ValueError("Compost comes from finished batches, not from a storage area.")
        return self


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    comment: Text = ""

    @model_validator(mode="after")
    def reject_needs_a_reason(self):
        if self.decision == "reject" and not self.comment:
            raise ValueError("Say why you are rejecting it.")
        return self


class ReviewIn(BaseModel):
    review: Literal["ok", "recheck", "wrong"]  # weights take ok/recheck, classifications ok/wrong


class Decided(BaseModel):
    status: str
    requested_by: str | None
    decided_by: str | None
    decided_at: datetime | None
    comment: str


class AdjustmentOut(Decided):
    id: int
    requested_at: datetime
    material: str
    area: str
    system_kg: float
    actual_kg: float
    reason: str
    details: str
    current_kg: float  # the ledger now; approving sets it to actual_kg
    area_kg: float
    area_after_kg: float
    capacity_kg: int
    review: str | None = None


class OutgoingOut(Decided):
    id: int
    code: str
    requested_at: datetime
    type: str
    material: str
    area: str | None
    kg: float
    recipient: str
    price_per_kg: float | None
    total: float | None
    available_kg: float | None  # in that area (or compost on hand) right now; left out of lists of past records
    area_kg: float | None
    area_after_kg: float | None
    capacity_kg: int | None
    review: str | None = None  # ok / reversed, once the admin has looked


class ApprovalsOut(BaseModel):
    counts: dict[str, int]
    adjustments: list[AdjustmentOut]
    outgoing: list[OutgoingOut]  # old-flow rows still waiting for approve / reject
    outgoing_review: list[OutgoingOut] = []  # recorded at once by operators, waiting for the admin's ok / reverse
    adjustments_review: list[AdjustmentOut] = []  # recounts that already changed stock
    fixes: list[CorrectionOut] = []  # records operators undid


class OutgoingReviewIn(BaseModel):
    decision: Literal["ok", "reverse"]
    comment: Text = ""
