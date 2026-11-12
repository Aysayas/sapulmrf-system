from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.intake.schemas import ClientKey, Kg

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


Count = Annotated[int, Field(ge=0, le=999)]


class CvCounts(BaseModel):
    recyclable: Count = 0
    residual: Count = 0
    bio: Count = 0


class CvResult(BaseModel):
    """What the kiosk camera decided, before the resident confirmed or changed it."""

    category: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]
    counts: CvCounts
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None


class KioskDeliveryIn(BaseModel):
    """A drop-off recorded at the resident kiosk. Purok and category by name, as the kiosk shows them."""

    source_area: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    weight_kg: Kg
    weighed_by: Literal["scale", "manual"]
    client_key: ClientKey  # required: the kiosk resends unsent drop-offs, and this stops duplicates
    cv: CvResult | None = None
    photo: Annotated[str, StringConstraints(max_length=140_000)] | None = None  # base64 JPEG, about 100 KB at most


class KioskActions(BaseModel):
    buzz: int = 0  # beeps


class KioskReceipt(BaseModel):
    code: str
    actions: KioskActions = KioskActions()


Light = Literal["green", "amber", "red"]


class KioskToday(BaseModel):
    kg: float
    drops: int


class KioskAlert(BaseModel):
    kind: str
    title: str
    details: str


class KioskActuators(BaseModel):
    light: Light
    buzz: int = 0


class KioskState(BaseModel):
    """Everything the kiosk shows or drives, polled by its laptop every few seconds."""

    today: KioskToday
    alerts: list[KioskAlert]
    actuators: KioskActuators


class KioskRow(BaseModel):
    """One line of the kiosk's operator screen, already formatted for its small table."""

    code: str
    time: str
    purok: str
    cat: str
    kg: str

