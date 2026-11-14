from datetime import date, datetime

from pydantic import BaseModel

from app.approvals.schemas import OutgoingOut
from app.compost.schemas import BatchOut
from app.sorting.schemas import ClassificationOut


class ComplianceRow(BaseModel):
    source_area: str
    deliveries: int
    segregated: int
    pct: int


class Compliance(BaseModel):
    days: int
    deliveries: int
    segregated: int
    pct: int
    wet_kg_separated: float
    rows: list[ComplianceRow]


class SortedRow(BaseModel):
    at: datetime
    delivery: str | None
    material: str
    bags: int
    kg: float
    area: str


class SortingView(BaseModel):
    classified: int
    unchanged: int
    changed: int
    accepted_pct: int
    pending: int
    sorted_kg: float
    classifications: list[ClassificationOut]
    sorted: list[SortedRow]


class AreaFill(BaseModel):
    id: int
    name: str
    capacity_kg: int
    alert_pct: int
    kg: float
    pct: int


class StockRow(BaseModel):
    material: str
    area: str
    bags: int
    kg: float
    last_change: datetime


class InventoryView(BaseModel):
    areas: list[AreaFill]
    stock: list[StockRow]


class Point(BaseModel):
    at: datetime
    temp_c: float
    moisture_pct: float


class BatchLive(BatchOut):
    temp_c: float | None
    moisture_pct: float | None
    read_at: datetime | None
    in_range: bool | None
    day: int


class CompostView(BaseModel):
    ranges: dict[str, float]
    batches: list[BatchLive]
    selected: str | None
    wet_waiting_kg: float  # wet waste from segregation checks not yet in a batch
    series: list[Point]


class MaterialBin(BaseModel):
    material: str
    kg: float
    bags: int


class CameraView(BaseModel):
    latest: ClassificationOut | None
    pending: int
    today: int
    accepted_pct: int
    bins: list[MaterialBin]


class DayKg(BaseModel):
    day: date
    kg: float


class DeviceLive(BaseModel):
    code: str
    type: str
    status: str
    last_reading: dict | None


class Overview(BaseModel):
    today_deliveries: int
    today_kg: float
    awaiting_segregation: int
    compliance_week_pct: int | None  # None for staff without the segregation grant
    in_storage_kg: float
    active_batches: int
    wet_waiting_kg: float
    intake_14d: list[DayKg]
    areas: list[AreaFill]
    compost: list[BatchLive]
    devices: list[DeviceLive]
    latest_classification: ClassificationOut | None
    pending_approvals: int
    income_month: float
    open_alerts: dict[str, int]  # per kind, open (not yet cleared)
    alert_batch_ids: list[int]  # compost batches with an open alert


class MonthIncome(BaseModel):
    month: date  # the first day of the month
    income: float


class OutgoingView(BaseModel):
    """This month counts what was approved this month (barangay time); income is approved sales only."""

    income_month: float
    sold_kg_month: float
    compost_kg_month: float
    disposed_kg_month: float
    pending: int
    compost_on_hand_kg: float
    income_6m: list[MonthIncome]
    records: list[OutgoingOut]
