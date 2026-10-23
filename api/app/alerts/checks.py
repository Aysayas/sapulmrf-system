"""The scheduled checks behind alerts. run_checks is safe to run any number of times: it only opens what isn't
open yet and resolves what has cleared."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.alerts.models import Alert
from app.compost.models import CompostBatch, CompostReading
from app.core.config import settings
from app.devices import service as devices
from app.devices.models import Device
from app.masterdata.models import StorageArea
from app.settings import service as ranges
from app.sorting.models import StockMovement

COMPOST_WAIT = timedelta(minutes=10)  # out of range this long opens an alert; back in range this long resolves it
WINDOW = timedelta(hours=6)  # readings looked at per batch
TZ = ZoneInfo(settings.timezone)
DEVICE_LABEL = {"weighing_station": "Weighing station", "compost_sensor": "Compost sensor", "sorting_camera": "Sorting camera"}


def _streak(readings: list[tuple[datetime, bool]]) -> tuple[bool, datetime]:
    """(is the latest reading in range, when the current run of same-state readings began). Oldest first."""
    ok, since = readings[-1][1], readings[-1][0]
    for at, state in reversed(readings):
        if state != ok:
            break
        since = at
    return ok, since


def _compost(db: DbSession, now: datetime) -> dict[int, tuple[str, str] | None]:
    """Per open batch: (title, details) if it has been out of range long enough, None if it is fine, absent if unsure."""
    r = ranges.get(db)
    found: dict[int, tuple[str, str] | None] = {}
    for b in db.scalars(select(CompostBatch).where(CompostBatch.finished_at.is_(None))):
        rows = db.execute(
            select(CompostReading.read_at, CompostReading.temp_c, CompostReading.moisture_pct)
            .where(CompostReading.batch_id == b.id, CompostReading.read_at > now - WINDOW, CompostReading.read_at <= now)
            .order_by(CompostReading.read_at)
        ).all()
        if not rows:
            continue
        ok, since = _streak(
            [(at, r.compost_temp_min <= t <= r.compost_temp_max and r.moisture_min <= m <= r.moisture_max) for at, t, m in rows]
        )
        if now - since < COMPOST_WAIT:
            continue  # too soon to change anything either way
        if ok:
            found[b.id] = None
            continue
        _, t, m = rows[-1]
        if not r.compost_temp_min <= t <= r.compost_temp_max:
            side = "above" if t > r.compost_temp_max else "below"
            found[b.id] = (f"Compost {b.code} {side} range", f"{t} °C (range {r.compost_temp_min:g}–{r.compost_temp_max:g} °C)")
        else:
            side = "above" if m > r.moisture_max else "below"
            found[b.id] = (
                f"Compost {b.code} moisture {side} range",
                f"{m}% moisture (range {r.moisture_min:g}–{r.moisture_max:g}%)",
            )
    return found


def _devices(db: DbSession, now: datetime) -> dict[int, tuple[str, str] | None]:
    found: dict[int, tuple[str, str] | None] = {}
    for d in db.scalars(select(Device)):
        if d.active and devices.status(d, now) == "offline":
            seen = d.last_seen_at.astimezone(TZ)
            found[d.id] = (f"{DEVICE_LABEL[d.type]} {d.code} disconnected", f"Last heard from {seen:%b %d, %I:%M %p}")
        else:
            found[d.id] = None
    return found


def _storage(db: DbSession) -> dict[int, tuple[str, str] | None]:
    kg = dict(
        db.execute(
            select(StockMovement.storage_area_id, func.sum(StockMovement.kg)).group_by(StockMovement.storage_area_id)
        ).all()
    )
    found: dict[int, tuple[str, str] | None] = {}
    for a in db.scalars(select(StorageArea)):
        pct = round(float(kg.get(a.id, 0)) / a.capacity_kg * 100) if a.capacity_kg else 0
        found[a.id] = (
            (f"{a.name} almost full", f"{pct}% of {a.capacity_kg:,} kg (alert at {a.alert_pct}%)")
            if a.active and pct >= a.alert_pct
            else None
        )
    return found


def run_checks(db: DbSession, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    open_alerts = {(a.kind, a.subject_id): a for a in db.scalars(select(Alert).where(Alert.resolved_at.is_(None)))}
    counts = {"opened": 0, "resolved": 0}
    for kind, found in (("compost", _compost(db, now)), ("device", _devices(db, now)), ("storage", _storage(db))):
        for subject_id, hit in found.items():
            alert = open_alerts.pop((kind, subject_id), None)
            if hit and alert:
                alert.details = hit[1]  # keep the latest value on the open alert
            elif hit:
                try:
                    with db.begin_nested():
                        db.add(Alert(kind=kind, subject_id=subject_id, title=hit[0], details=hit[1], opened_at=now))
                    counts["opened"] += 1
                except IntegrityError:
                    pass  # another worker opened it first
            elif alert:
                alert.resolved_at = now
                counts["resolved"] += 1
    # open alerts whose subject is gone (a finished batch, a deleted device or area) resolve too
    for (kind, subject_id), alert in open_alerts.items():
        batch = db.get(CompostBatch, subject_id) if kind == "compost" else None
        if kind != "compost" or batch is None or batch.finished_at:
            alert.resolved_at = now
            counts["resolved"] += 1
    db.commit()
    return counts
