from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.intake.schemas import ClientKey

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class SuggestionIn(BaseModel):
    """What the camera sends (the CV-result contract in docs/roadmap.md)."""

    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    confidence: Annotated[float, Field(ge=0, le=1)]
    model_version: Annotated[str, StringConstraints(max_length=40)] = ""
    image_url: Annotated[str, StringConstraints(max_length=500, pattern=r"^(https?://\S+)?$")] = ""  # it reaches <img src>


class ConfirmIn(BaseModel):
    final_material_id: int | None = None  # leave out to accept the suggestion as it is
    not_recyclable: bool = False
    reason: Text = ""


class ClassificationOut(BaseModel):
    id: int
    suggested_at: datetime
    suggested: str
    confidence: float
    model_version: str
    image_url: str
    final: str | None
    changed: bool | None
    reason: str
    confirmed_by: str | None
    confirmed_at: datetime | None


class TransferIn(BaseModel):
    material_id: int | None  # None means residual
    from_area_id: int
    to_area_id: int
    kg: Annotated[float, Field(ge=0.01, le=50000)]
    bags: Annotated[int, Field(ge=0, le=1000)] | None = None  # None: in proportion to the kg
    client_key: ClientKey | None = None


class TransferOut(BaseModel):
    material: str
    from_area: str
    to_area: str
    kg: float
    bags: int
    from_area_kg: float
    to_area_kg: float


class SortRow(BaseModel):
    material_id: int | None  # None means residual
    bags: Annotated[int, Field(ge=0, le=1000)]
    kg: Annotated[float, Field(ge=0.01, le=5000)]
    storage_area_id: int


class SortIn(BaseModel):
    delivery_id: int
    rows: Annotated[list[SortRow], Field(min_length=1, max_length=20)]
