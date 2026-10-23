from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class AlertOut(BaseModel):
    id: int
    kind: str
    title: str
    details: str
    opened_at: datetime
    resolved_at: datetime | None
    acknowledged_by: str | None
    acknowledged_at: datetime | None


class BellItem(BaseModel):
    """One line in the bell menu: an open alert or an open problem report."""

    type: Literal["alert", "report"]
    id: int
    title: str
    details: str
    at: datetime


class AlertSummary(BaseModel):
    open_alerts: int  # not resolved, acknowledged or not
    by_kind: dict[str, int]
    unacknowledged: int
    open_reports: int  # admins only; 0 for others
    latest: list[BellItem]


class ProblemIn(BaseModel):
    kind: Literal["device", "record"]
    device_id: int | None = None
    record_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ""
    details: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]

    @model_validator(mode="after")
    def says_what(self):
        if self.kind == "device" and self.device_id is None:
            raise ValueError("Pick the device that has a problem.")
        if self.kind == "record" and not self.record_ref:
            raise ValueError("Say which record is wrong, for example D-0139.")
        return self


class ResolveIn(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProblemOut(BaseModel):
    id: int
    code: str
    kind: str
    device: str | None
    record_ref: str
    details: str
    reported_by: str | None
    reported_at: datetime
    status: str
    resolved_by: str | None
    resolved_at: datetime | None
    note: str
