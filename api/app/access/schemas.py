from typing import Literal

from pydantic import BaseModel

Screen = Literal["segregation", "predictions", "alerts", "camera", "reports"]
LABELS: dict[str, str] = {
    "segregation": "View segregation compliance",
    "predictions": "View intake predictions",
    "alerts": "View alerts and notifications",
    "camera": "View live camera",
    "reports": "View and download exported reports",
}


class ScreenOut(BaseModel):
    key: Screen
    label: str


class StaffAccessOut(BaseModel):
    user_id: int
    name: str
    username: str
    active: bool
    grants: dict[Screen, bool]


class AccessOverview(BaseModel):
    screens: list[ScreenOut]
    staff: list[StaffAccessOut]


class AccessUpdate(BaseModel):
    grants: dict[Screen, bool]
