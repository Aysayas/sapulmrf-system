from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

DeviceType = Literal["weighing_station", "compost_sensor", "sorting_camera"]
Status = Literal["online", "offline", "never"]
Code = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9-]{2,20}$")]
Location = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]


class DeviceOut(BaseModel):
    id: int
    code: str
    type: DeviceType
    location: str
    active: bool
    last_seen_at: datetime | None
    status: Status


class DeviceWithKey(DeviceOut):
    key: str  # shown once; only its hash is stored


class DeviceCreate(BaseModel):
    code: Code
    type: DeviceType
    location: Location = ""


class DeviceUpdate(BaseModel):
    code: Code | None = None
    type: DeviceType | None = None
    location: Location | None = None
    active: bool | None = None


class Heartbeat(BaseModel):
    device: str
    status: Status
