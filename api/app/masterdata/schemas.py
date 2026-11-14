from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Kind = Literal["categories", "puroks", "materials", "storage-areas", "buyers"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Capacity = Annotated[int, Field(ge=1, le=1_000_000)]
AlertPct = Annotated[int, Field(ge=1, le=100)]


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    active: bool
    capacity_kg: int | None = None
    alert_pct: int | None = None


class ItemCreate(BaseModel):
    name: Name
    capacity_kg: Capacity | None = None
    alert_pct: AlertPct | None = None


class ItemUpdate(BaseModel):
    name: Name | None = None
    active: bool | None = None
    capacity_kg: Capacity | None = None
    alert_pct: AlertPct | None = None
