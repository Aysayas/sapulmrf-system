"""SapulMRF simulator: stands in for Rhendel's devices and an MRF operator until the real ones exist.

    python -m app.simulator setup            # sim container: admin creates sim.operator + SIM- devices (keys saved in /state)
    python -m app.simulator run              # sim container: live loop through the HTTP API, like real devices and an operator
    python -m app.simulator backfill --days 40   # api container: past history through the same services, with past times
    python -m app.simulator remove           # api container: deletes everything simulated; real data is untouched

Everything simulated is tagged: the user sim.operator, devices SIM-…, and demo areas named "Demo …" (made only when
there are no real ones yet).
"""

import argparse
import json
import os
import random
import secrets
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

SIM_USER = "sim.operator"
DEVICES = [
    ("SIM-WS-01", "weighing_station", "Intake area"),
    ("SIM-CS-01", "compost_sensor", "Compost bay 1"),
    ("SIM-CS-02", "compost_sensor", "Compost bay 2"),
    ("SIM-CAM-01", "sorting_camera", "Sorting area"),
]
DEMO_PUROKS = [f"Demo Purok {i}" for i in range(1, 8)]
DEMO_AREAS = [
    ("Demo Area A · Plastics", 500),
    ("Demo Area B · Paper & cardboard", 500),
    ("Demo Area C · Metal", 300),
    ("Demo Area D · Residual", 500),
]
# Share of a delivery's dry waste per material; the rest is residual.
MIX = {"Plastic": 0.35, "Paper": 0.22, "Cardboard": 0.18, "Metal": 0.08}
PHOTOS = {  # same Unsplash stock photos as the mockup, until the real camera exists
    "Plastic": "https://images.unsplash.com/photo-1595278069441-2cf29f8005a4?w=900&q=60&auto=format&fit=crop",
    "Paper": "https://images.unsplash.com/photo-1654372066379-d8a1c70f7363?w=900&q=60&auto=format&fit=crop",
    "Cardboard": "https://images.unsplash.com/photo-1507560461415-997cd00bfd45?w=900&q=60&auto=format&fit=crop",
    "Metal": "https://images.unsplash.com/photo-1561503412-852800622772?w=900&q=60&auto=format&fit=crop",
}
STATE = Path(os.environ.get("SIM_STATE", "/state/sim.json"))
PRICES = {"Plastic": 12.0, "Paper": 4.0, "Cardboard": 3.5, "Metal": 25.0}  # placeholder ₱ per kg, not real junkshop rates
BUYERS = ["Buyer A Junkshop", "Buyer B Recycling"]
ADJUST_REASONS = ["Wet bags removed as residual", "Recount after pickup", "Torn bag, spilled"]
CORRECTIONS = ["Bag touched the edge", "Scale not zeroed"]
RECENT = timedelta(days=3)  # backfilled requests and corrections newer than this stay waiting for the admin


# ---------------------------------------------------------------- behaviour shared by backfill and live


def purok_profiles(names: list[str], seed: int = 7) -> dict[str, tuple[float, float]]:
    """(usual kg per delivery, chance of arriving segregated) per purok, stable across runs."""
    rnd = random.Random(seed)
    return {n: (round(rnd.uniform(6, 14), 1), round(rnd.uniform(0.35, 0.9), 2)) for n in sorted(names)}


def delivery_weight(rnd: random.Random, usual: float) -> float:
    if rnd.random() < 0.02:  # the occasional outlier, for Phase 6 to flag
        return round(usual * rnd.uniform(2.5, 3.5), 2)
    return round(max(1.0, rnd.gauss(usual, usual * 0.18)), 2)


def split_wet_dry(rnd: random.Random, kg: float, category: str) -> tuple[float, float]:
    if category == "Biodegradable":
        return kg, 0.0
    if category in ("Recyclable", "Residual", "Special waste"):
        return 0.0, kg
    wet = kg * rnd.uniform(0.35, 0.5)
    loss = kg * (rnd.uniform(0.06, 0.12) if rnd.random() < 0.03 else rnd.uniform(0, 0.02))  # rare received-vs-separated gap
    return round(wet, 2), round(max(0.0, kg - wet - loss), 2)


def camera_guess(rnd: random.Random, truth: str) -> tuple[str, float, bool]:
    """(label, confidence, operator changes it). About 85% of suggestions are accepted unchanged."""
    if rnd.random() < 0.85:
        return truth, round(rnd.uniform(0.78, 0.98), 2), False
    wrong = rnd.choice([m for m in MIX if m != truth])
    return wrong, round(rnd.uniform(0.38, 0.7), 2), True


def compost_reading(rnd: random.Random, day: float, prev_moist: float | None, hours: float = 0.5) -> tuple[float, float]:
    """A thermophilic curve: warms up over ~5 days, holds 55–65 °C with the odd spike, cools after ~3 weeks."""
    if day < 5:
        temp = 32 + day * 5.5
    elif day < 20:
        temp = 60 + rnd.gauss(0, 2.5) + (7 if rnd.random() < 0.03 else 0)
    else:
        temp = max(30.0, 60 - (day - 20) * 2.5)
    # dries ~3.5 points a day; noise scaled to the time since the last reading so 30 s and 30 min steps both look right
    drift = rnd.uniform(0.05, 0.25) * hours
    moist = (prev_moist if prev_moist is not None else 55) - drift + rnd.gauss(0, 0.15 * (hours / 0.5) ** 0.5)
    return round(temp + rnd.gauss(0, 0.6), 1), round(min(70, max(30, moist)), 1)


# ---------------------------------------------------------------- database side (api container)


def _db_entities(db):
    """Finds or makes sim.operator, the SIM devices and (only if none exist) demo puroks and areas."""
    from sqlalchemy import select

    from app.core.security import hash_password, token_hash
    from app.devices.models import Device
    from app.masterdata.models import SourceArea, StorageArea
    from app.users.models import User

    user = db.scalar(select(User).where(User.username == SIM_USER))
    if not user:
        user = User(
            name="Simulator (operator)",
            username=SIM_USER,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="operator",
        )
        db.add(user)
    devices = {}
    for code, type_, where in DEVICES:
        d = db.scalar(select(Device).where(Device.code == code))
        if not d:
            d = Device(code=code, type=type_, location=where, key_hash=token_hash(secrets.token_urlsafe(24)))
            db.add(d)
        devices[code] = d
    if not db.scalar(select(SourceArea.id).where(SourceArea.active)):
        db.add_all([SourceArea(name=n) for n in DEMO_PUROKS])
    if not db.scalar(select(StorageArea.id).where(StorageArea.active)):
        db.add_all([StorageArea(name=n, capacity_kg=cap, alert_pct=90) for n, cap in DEMO_AREAS])
    db.commit()
    return user, devices


def _approver(db):
    """Backfilled approvals and reviews are made as the test admin, never a real person."""
    from sqlalchemy import select

    from app.users.models import User

    name = os.environ.get("E2E_ADMIN_USERNAME", "e2e.admin")
    admin = db.scalar(select(User).where(User.username == name, User.role == "admin"))
    if not admin:
        raise RuntimeError(f"Create the test admin {name!r} first (docs/testing.md): the backfill decides old requests as it.")
    return admin


def area_for(areas: list, material: str | None):
    """The storage area whose name mentions the material (residual → 'Residual'), else the first one."""
    key = {"Cardboard": "Paper"}.get(material, material) if material else "Residual"
    return next((a for a in areas if key.lower() in a.name.lower()), areas[0])


def backfill(db, days: int, seed: int = 11, now: datetime | None = None) -> dict[str, int]:
    """Writes `days` days of history (ending now) through the same service functions the API uses."""
    from sqlalchemy import select

    from app.approvals import service as approvals
    from app.approvals.schemas import AdjustmentIn, DecisionIn, OutgoingIn
    from app.compost import service as compost
    from app.compost.schemas import ActivityIn, BatchIn, ReadingIn
    from app.core.config import settings
    from app.intake import service as intake
    from app.intake.models import Delivery
    from app.intake.schemas import DeliveryIn, SegregationIn
    from app.masterdata.models import Material, SourceArea, StorageArea, WasteCategory
    from app.sorting import service as sorting
    from app.sorting.models import Classification
    from app.sorting.schemas import ConfirmIn, SortIn, SuggestionIn

    rnd = random.Random(seed)
    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(UTC)
    admin = _approver(db)
    user, devices = _db_entities(db)
    puroks = list(db.scalars(select(SourceArea).where(SourceArea.active)))
    areas = list(db.scalars(select(StorageArea).where(StorageArea.active)))
    cats = {c.name: c.id for c in db.scalars(select(WasteCategory))}
    mats = {m.name: m.id for m in db.scalars(select(Material))}
    profiles = purok_profiles([p.name for p in puroks])
    names = {v: k for k, v in mats.items()}
    counts = {"deliveries": 0, "classifications": 0, "readings": 0, "batches": 0, "outgoing": 0, "adjustments": 0}
    sensors = [devices["SIM-CS-01"], devices["SIM-CS-02"]]
    batches: dict[str, object] = {}
    moist: dict[int, float] = {}
    wet_pool = 0.0

    def decide(decide_fn, row, t: datetime, reject: bool = False) -> None:
        if t > now - RECENT:
            return  # recent ones wait in the inbox
        data = DecisionIn(decision="reject", comment="Count again") if reject else DecisionIn(decision="approve")
        decide_fn(db, row.id, data, admin, at=t + timedelta(hours=2))

    def give_out(data: OutgoingIn, t: datetime) -> None:
        decide(approvals.decide_outgoing, approvals.request_outgoing(db, data, user, at=t), t)
        counts["outgoing"] += 1

    start_day = now.astimezone(tz).date() - timedelta(days=days - 1)
    for i in range(days):
        day = start_day + timedelta(days=i)
        opening = datetime(day.year, day.month, day.day, 7, 0, tzinfo=tz)
        for _ in range(rnd.randint(10, 16)):
            t = opening + timedelta(minutes=rnd.randint(0, 9 * 60))
            if t > now:
                continue
            p = rnd.choice(puroks)
            usual, seg_rate = profiles[p.name]
            category = rnd.choices(["Mixed household", "Biodegradable", "Recyclable", "Residual"], [75, 10, 10, 5])[0]
            kg = delivery_weight(rnd, usual)
            fix = (
                {"scale_kg": round(kg + rnd.uniform(0.1, 0.5), 2), "correction_reason": rnd.choice(CORRECTIONS)}
                if rnd.random() < 0.03
                else {}
            )
            d = intake.record_delivery(
                db,
                DeliveryIn(
                    source_area_id=p.id,
                    category_id=cats[category],
                    weight_kg=kg,
                    weighed_by="scale" if fix or rnd.random() > 0.05 else "manual",
                    device_id=devices["SIM-WS-01"].id,
                    **fix,
                ),
                user,
                at=t,
            )
            counts["deliveries"] += 1
            wet, dry = split_wet_dry(rnd, kg, category)
            condition = "segregated" if (category != "Mixed household" or rnd.random() < seg_rate) else "mixed"
            intake.record_segregation(
                db, d.id, SegregationIn(condition=condition, wet_kg=wet, dry_kg=dry), user, at=t + timedelta(minutes=10)
            )
            wet_pool += wet
            if dry <= 0:
                continue
            rows, sorted_at = [], t + timedelta(minutes=25)
            for material, share in MIX.items():
                label, conf, changed = camera_guess(rnd, material)
                c = sorting.create_suggestion(
                    db,
                    devices["SIM-CAM-01"],
                    SuggestionIn(label=label, confidence=conf, model_version="sim-1", image_url=PHOTOS[label]),
                    at=sorted_at,
                )
                sorting.confirm(
                    db,
                    c.id,
                    ConfirmIn(final_material_id=mats[material] if changed else None, reason="Looked again" if changed else ""),
                    user,
                    at=sorted_at,
                )
                counts["classifications"] += 1
                rows.append(
                    {
                        "material_id": mats[material],
                        "bags": max(1, round(dry * share / 3)),
                        "kg": round(dry * share, 2),
                        "storage_area_id": area_for(areas, material).id,
                    }
                )
            residual = round(dry * (1 - sum(MIX.values())), 2)
            if residual > 0:
                rows.append({"material_id": None, "bags": 1, "kg": residual, "storage_area_id": area_for(areas, None).id})
            sorting.sort_delivery(db, SortIn(delivery_id=d.id, rows=rows), user, at=sorted_at)

        # Saturday pickup: recyclables sold to a junkshop, residual to the city truck, from areas over 45% full
        pickup = opening + timedelta(hours=8)
        if day.weekday() == 5 and pickup <= now:
            for a in areas:
                if sorting.stock_kg(db, a.id) <= a.capacity_kg * 0.45:
                    continue
                for material_id, kg, _ in _stock_by_material(db, a.id):
                    if kg <= 1:
                        continue
                    share = round(kg * 0.6, 2)
                    give_out(
                        OutgoingIn(
                            type="sale",
                            material_id=material_id,
                            storage_area_id=a.id,
                            kg=share,
                            recipient=rnd.choice(BUYERS),
                            price_per_kg=PRICES[names[material_id]],
                        )
                        if material_id
                        else OutgoingIn(type="disposal", storage_area_id=a.id, kg=share, recipient="City ENRO truck"),
                        pickup,
                    )

        # every ~9 days the operator recounts one pile; the admin rejects about one in four
        recount = opening + timedelta(hours=6)
        if i % 9 == 4 and recount <= now:
            piles = [(a, m, kg) for a in areas for m, kg, _ in _stock_by_material(db, a.id) if kg > 5]
            if piles:
                a, m, kg = rnd.choice(piles)
                r = approvals.request_adjustment(
                    db,
                    AdjustmentIn(
                        material_id=m,
                        storage_area_id=a.id,
                        reason=rnd.choice(ADJUST_REASONS),
                        actual_kg=round(kg * rnd.uniform(0.94, 0.99), 2),
                    ),
                    user,
                    at=recount,
                )
                decide(approvals.decide_adjustment, r, recount, reject=rnd.random() < 0.25)
                counts["adjustments"] += 1

        # compost: start a batch on a free sensor every ~6 days from the wet waste collected, readings every 30 min
        for sensor in sensors:
            b = batches.get(sensor.code)
            if b and (datetime(day.year, day.month, day.day, tzinfo=tz) - b.started_at).days >= 21 and not b.finished_at:
                compost.log_activity(
                    db,
                    b.id,
                    ActivityIn(type="inspection", note="Mature", finished_kg=round(b.start_kg * 0.55, 1)),
                    user,
                    at=opening + timedelta(hours=1),
                )
                if opening + timedelta(hours=5) <= now:  # most of it goes to purok gardens, sometimes sold
                    give_out(
                        OutgoingIn(
                            type="compost",
                            kg=round(b.produced_kg * 0.7, 1),
                            recipient=f"{rnd.choice(puroks).name} gardens",
                            price_per_kg=5.0 if rnd.random() < 0.4 else None,
                        ),
                        opening + timedelta(hours=5),
                    )
                b = None
            if (not b or b.finished_at) and wet_pool > 40 and (i % 6 == sensors.index(sensor) * 3):
                b = compost.start_batch(
                    db, BatchIn(start_kg=round(wet_pool * 0.8, 1), sensor_id=sensor.id), user, at=opening + timedelta(hours=2)
                )
                batches[sensor.code], wet_pool = b, 0.0
                counts["batches"] += 1
        for sensor in sensors:
            b = batches.get(sensor.code)
            if not b or b.finished_at:
                continue
            for half_hour in range(48):
                t = datetime(day.year, day.month, day.day, tzinfo=tz) + timedelta(minutes=30 * half_hour)
                if t < b.started_at or t > now:
                    continue
                age = (t - b.started_at).total_seconds() / 86400
                temp, m = compost_reading(rnd, age, moist.get(b.id))
                if half_hour == 16 and m < 47:  # morning watering
                    compost.log_activity(db, b.id, ActivityIn(type="watering"), user, at=t)
                    m += 8
                moist[b.id] = m
                compost.record_reading(db, sensor, ReadingIn(temp_c=temp, moisture_pct=m), at=t)
                counts["readings"] += 1
            if i % 3 == 0:
                compost.log_activity(
                    db, b.id, ActivityIn(type="turning"), user, at=datetime(day.year, day.month, day.day, 9, tzinfo=tz)
                )

    # the admin has already reviewed older corrections; recent ones wait in the inbox
    rnd_review = random.Random(seed + 1)
    for d in db.scalars(
        select(Delivery).where(
            Delivery.recorded_by == user.id, Delivery.scale_kg.is_not(None), Delivery.received_at <= now - RECENT
        )
    ):
        d.review = "ok" if rnd_review.random() < 0.85 else "recheck"
        d.reviewed_by, d.reviewed_at = admin.id, d.received_at + timedelta(days=1)
    for c in db.scalars(
        select(Classification).where(
            Classification.confirmed_by == user.id, Classification.changed.is_(True), Classification.confirmed_at <= now - RECENT
        )
    ):
        c.review = "ok" if rnd_review.random() < 0.9 else "wrong"
        c.reviewed_by, c.reviewed_at = admin.id, c.confirmed_at + timedelta(days=1)
    from app.insights.models import Flag

    for f in db.scalars(select(Flag).join(Delivery).where(Delivery.recorded_by == user.id, Flag.found_at <= now - RECENT)):
        f.status = "incorrect" if rnd_review.random() < 0.6 else "valid"
        f.decided_by, f.decided_at = admin.id, f.found_at + timedelta(days=1)
    db.commit()

    # replay the worker's daily forecasts, so predicted vs actual has history (each uses only the days before it)
    from app.insights.forecast import make_forecasts

    counts["forecasts"] = sum(make_forecasts(db, start_day + timedelta(days=i)) for i in range(1, days))  # up to today
    return counts


def _stock_by_material(db, area_id: int) -> list[tuple[int | None, float, int]]:
    from sqlalchemy import func, select

    from app.sorting.models import StockMovement

    return db.execute(
        select(StockMovement.material_id, func.sum(StockMovement.kg), func.sum(StockMovement.bags))
        .where(StockMovement.storage_area_id == area_id)
        .group_by(StockMovement.material_id)
    ).all()


def remove(db) -> dict[str, int]:
    """Deletes everything the simulator made. Demo areas still used by real records are kept and reported."""
    from sqlalchemy import and_, delete, false, or_, select
    from sqlalchemy.exc import IntegrityError

    from app.activity.models import ActivityLog
    from app.approvals.models import AdjustmentRequest, Outgoing
    from app.compost.models import CompostBatch
    from app.devices.models import Device
    from app.insights.models import Forecast
    from app.intake.models import Delivery
    from app.masterdata.models import SourceArea, StorageArea
    from app.sorting.models import Classification, StockMovement
    from app.users.models import User

    # -1 when there is no sim user, so "== user_id" never turns into "IS NULL" and catches real rows
    user_id = db.scalar(select(User.id).where(User.username == SIM_USER)) or -1
    device_ids = list(db.scalars(select(Device.id).where(Device.code.like("SIM-%"))))
    counts = {}
    counts["classifications"] = db.execute(
        delete(Classification).where(or_(Classification.device_id.in_(device_ids), Classification.confirmed_by == user_id))
    ).rowcount
    # approvals of the sim's requests were written by an admin, so find those ledger rows by their request
    codes = list(db.scalars(select(Outgoing.code).where(Outgoing.requested_by == user_id)))
    adjusted = [
        f"Adjustment #{i}:%" for i in db.scalars(select(AdjustmentRequest.id).where(AdjustmentRequest.requested_by == user_id))
    ]
    counts["stock movements"] = db.execute(
        delete(StockMovement).where(
            or_(
                StockMovement.by == user_id,
                and_(StockMovement.kind == "outgoing", StockMovement.note.in_(codes)),
                and_(StockMovement.kind == "adjustment", or_(false(), *[StockMovement.note.like(p) for p in adjusted])),
            )
        )
    ).rowcount
    counts["outgoing records"] = db.execute(delete(Outgoing).where(Outgoing.requested_by == user_id)).rowcount
    counts["adjustments"] = db.execute(delete(AdjustmentRequest).where(AdjustmentRequest.requested_by == user_id)).rowcount
    counts["deliveries"] = db.execute(delete(Delivery).where(Delivery.recorded_by == user_id)).rowcount
    counts["compost batches"] = db.execute(
        delete(CompostBatch).where(or_(CompostBatch.started_by == user_id, CompostBatch.sensor_id.in_(device_ids)))
    ).rowcount
    db.execute(delete(ActivityLog).where(ActivityLog.user_id == user_id))
    counts["devices"] = db.execute(delete(Device).where(Device.id.in_(device_ids))).rowcount
    counts["users"] = db.execute(delete(User).where(User.id == user_id)).rowcount
    # forecasts were built from the simulated history (flags went with their deliveries); the worker rebuilds from real data
    counts["forecasts"] = db.execute(delete(Forecast)).rowcount
    db.commit()
    kept = 0
    for model in (SourceArea, StorageArea):
        for item in db.scalars(select(model).where(model.name.like("Demo %"))).all():
            try:
                with db.begin_nested():
                    db.delete(item)
                    db.flush()
            except IntegrityError:
                kept += 1
    db.commit()
    counts["demo areas kept (used by real records)"] = kept
    return counts


# ---------------------------------------------------------------- HTTP side (sim container)


class Api:
    def __init__(self, base: str):
        import httpx

        self.http = httpx.Client(base_url=base, timeout=15)
        self.login_body = None

    def call(self, method: str, path: str, key: str | None = None, **kw):
        r = self.http.request(method, path, headers={"X-Device-Key": key} if key else None, **kw)
        if path == "/auth/login" and r.status_code == 200:
            self.login_body = kw["json"]
        elif r.status_code == 401 and not key and self.login_body:  # sessions expire, and this runs for days
            self.http.post("/auth/login", json=self.login_body).raise_for_status()
            r = self.http.request(method, path, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{method} {path} → {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else None


def setup(base: str) -> None:
    """As the admin from .env: (re)creates sim.operator and the SIM devices, saving a fresh password and keys to /state."""
    api = Api(base)
    api.call(
        "POST", "/auth/login", json={"username": os.environ["E2E_ADMIN_USERNAME"], "password": os.environ["E2E_ADMIN_PASSWORD"]}
    )
    password = secrets.token_urlsafe(18)
    users = {u["username"]: u for u in api.call("GET", "/users")}
    if SIM_USER in users:
        api.call("PATCH", f"/users/{users[SIM_USER]['id']}", json={"password": password, "active": True})
    else:
        api.call(
            "POST",
            "/users",
            json={"name": "Simulator (operator)", "username": SIM_USER, "role": "operator", "password": password},
        )
    existing = {d["code"]: d for d in api.call("GET", "/devices")}
    keys = {}
    for code, type_, where in DEVICES:
        if code in existing:
            d = api.call("POST", f"/devices/{existing[code]['id']}/new-key")
        else:
            d = api.call("POST", "/devices", json={"code": code, "type": type_, "location": where})
        keys[code] = {"id": d["id"], "key": d["key"]}
    for name in DEMO_PUROKS if not api.call("GET", "/masterdata/puroks?active=true") else []:
        api.call("POST", "/masterdata/puroks", json={"name": name})
    for name, cap in DEMO_AREAS if not api.call("GET", "/masterdata/storage-areas?active=true") else []:
        api.call("POST", "/masterdata/storage-areas", json={"name": name, "capacity_kg": cap})
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"password": password, "devices": keys}))
    print(f"Simulator ready: {SIM_USER} and {len(keys)} devices. Start it with: docker compose --profile sim up -d sim")


def run(base: str, pace: float) -> None:
    """The live loop. `pace` multiplies every wait (0.5 = twice as fast)."""
    state = json.loads(STATE.read_text())
    keys = {code: v["key"] for code, v in state["devices"].items()}
    ids = {code: v["id"] for code, v in state["devices"].items()}
    op = Api(base)
    op.call("POST", "/auth/login", json={"username": SIM_USER, "password": state["password"]})
    rnd = random.Random()
    puroks = op.call("GET", "/masterdata/puroks?active=true")
    areas = [SimpleNamespace(**a) for a in op.call("GET", "/masterdata/storage-areas?active=true")]
    cats = {c["name"]: c["id"] for c in op.call("GET", "/masterdata/categories")}
    mats = {m["name"]: m["id"] for m in op.call("GET", "/masterdata/materials")}
    profiles = purok_profiles([p["name"] for p in puroks])
    moist: dict[str, float] = {}
    quiet: dict[str, float] = {}  # sensor → monotonic time its readings resume
    hot: dict[str, float] = {}  # sensor → monotonic time its batch cools back down
    next_delivery = time.monotonic()
    next_readings = time.monotonic()
    print(f"Simulator running against {base} (pace ×{pace}). Ctrl+C or `docker compose stop sim` to stop.", flush=True)
    while True:
        now = time.monotonic()
        try:
            if now >= next_readings:
                op.call("POST", "/devices/readings", keys["SIM-WS-01"], json={"kg": 0.0, "stable": True})
                op.call("POST", "/devices/heartbeat", keys["SIM-CAM-01"])
                view = op.call("GET", "/operations/compost")
                open_by_sensor = {b["sensor"]: b for b in view["batches"] if not b["finished_at"] and b["sensor"]}
                for sensor in ("SIM-CS-01", "SIM-CS-02"):
                    b = open_by_sensor.get(sensor)
                    if not b:
                        op.call(
                            "POST", "/compost/batches", json={"start_kg": round(rnd.uniform(15, 25), 1), "sensor_id": ids[sensor]}
                        )
                        continue
                    # now and then a sensor drops out for ~5 minutes, or a batch overheats for ~15, so alerts open and clear
                    if now >= quiet.get(sensor, 0) and now >= hot.get(sensor, 0):
                        if rnd.random() < 1 / 100:
                            quiet[sensor] = now + 300 * pace
                            print(f"{datetime.now():%H:%M:%S} disturbance: {sensor} silent for ~5 min", flush=True)
                        elif rnd.random() < 1 / 100:
                            hot[sensor] = now + 900 * pace
                            print(f"{datetime.now():%H:%M:%S} disturbance: {b['code']} overheating for ~15 min", flush=True)
                    if now < quiet.get(sensor, 0):
                        continue
                    age = b["day"] - 1 + datetime.now().hour / 24
                    temp, m = compost_reading(rnd, age, moist.get(sensor, b["moisture_pct"]), hours=30 * pace / 3600)
                    if now < hot.get(sensor, 0):
                        temp = round(max(temp, 66) + rnd.uniform(3, 6), 1)
                    if m < 45:  # the operator waters a drying batch
                        op.call("POST", f"/compost/batches/{b['id']}/activities", json={"type": "watering"})
                        m += 8
                    moist[sensor] = m
                    op.call("POST", "/devices/readings", keys[sensor], json={"temp_c": temp, "moisture_pct": m})
                    if rnd.random() < 0.01:
                        op.call(
                            "POST", f"/compost/batches/{b['id']}/activities", json={"type": rnd.choice(["turning", "inspection"])}
                        )
                next_readings = now + 30 * pace
            if now >= next_delivery:
                next_delivery = now + rnd.uniform(60, 120) * pace  # first, so a failure partway doesn't start another at once
                _one_delivery(op, rnd, keys, ids, puroks, profiles, cats, mats, areas)
                if rnd.random() < 0.08:  # about every 20 minutes, something for the admin's inbox
                    _one_request(op, rnd, mats, areas)
        except Exception as e:  # keep going; the API may be restarting
            print(f"{datetime.now():%H:%M:%S} {e!r}", file=sys.stderr, flush=True)
        time.sleep(1)


def _one_delivery(op, rnd, keys, ids, puroks, profiles, cats, mats, areas):
    p = rnd.choice(puroks)
    usual, seg_rate = profiles[p["name"]]
    category = rnd.choices(["Mixed household", "Biodegradable", "Recyclable", "Residual"], [75, 10, 10, 5])[0]
    kg = delivery_weight(rnd, usual)
    fix = (
        {"scale_kg": round(kg + rnd.uniform(0.1, 0.5), 2), "correction_reason": rnd.choice(CORRECTIONS)}
        if rnd.random() < 0.03
        else {}
    )
    op.call("POST", "/devices/readings", keys["SIM-WS-01"], json={"kg": fix.get("scale_kg", kg), "stable": True})
    d = op.call(
        "POST",
        "/deliveries",
        json={
            "source_area_id": p["id"],
            "category_id": cats[category],
            "weight_kg": kg,
            "weighed_by": "scale",
            "device_id": ids["SIM-WS-01"],
            **fix,
        },
    )
    wet, dry = split_wet_dry(rnd, kg, category)
    condition = "segregated" if (category != "Mixed household" or rnd.random() < seg_rate) else "mixed"
    op.call("POST", f"/deliveries/{d['id']}/segregation", json={"condition": condition, "wet_kg": wet, "dry_kg": dry})
    if dry <= 0:
        return
    rows = []
    for material, share in MIX.items():
        label, conf, changed = camera_guess(rnd, material)
        c = op.call(
            "POST",
            "/devices/cv-suggestions",
            keys["SIM-CAM-01"],
            json={"label": label, "confidence": conf, "model_version": "sim-1", "image_url": PHOTOS[label]},
        )
        body = {"final_material_id": mats[material], "reason": "Looked again"} if changed else {}
        op.call("POST", f"/classifications/{c['id']}/confirm", json=body)
        rows.append(
            {
                "material_id": mats[material],
                "bags": max(1, round(dry * share / 3)),
                "kg": round(dry * share, 2),
                "storage_area_id": area_for(areas, material).id,
            }
        )
    residual = round(dry * (1 - sum(MIX.values())), 2)
    if residual > 0:
        rows.append({"material_id": None, "bags": 1, "kg": residual, "storage_area_id": area_for(areas, None).id})
    op.call("POST", "/sorting", json={"delivery_id": d["id"], "rows": rows})
    print(f"{datetime.now():%H:%M:%S} {d['code']} {p['name']} {kg} kg {condition}", flush=True)


def _one_request(op, rnd, mats, areas):
    """A recount, a sale or a disposal from a random pile, waiting for the admin."""
    piles = [r for r in op.call("GET", "/operations/inventory")["stock"] if r["kg"] > 5]
    if not piles:
        return
    pile = rnd.choice(piles)
    area = next(a for a in areas if a.name == pile["area"])
    material_id = mats.get(pile["material"])  # "Residual" is not a material: None
    if rnd.random() < 0.25:
        body = {
            "material_id": material_id,
            "storage_area_id": area.id,
            "reason": rnd.choice(ADJUST_REASONS),
            "actual_kg": round(pile["kg"] * rnd.uniform(0.95, 0.99), 2),
        }
        op.call("POST", "/inventory/adjustments", json=body)
    elif material_id:
        op.call(
            "POST",
            "/outgoing",
            json={
                "type": "sale",
                "material_id": material_id,
                "storage_area_id": area.id,
                "kg": round(pile["kg"] * 0.5, 2),
                "recipient": rnd.choice(BUYERS),
                "price_per_kg": PRICES[pile["material"]],
            },
        )
    else:
        op.call(
            "POST",
            "/outgoing",
            json={
                "type": "disposal",
                "storage_area_id": area.id,
                "kg": round(pile["kg"] * 0.5, 2),
                "recipient": "City ENRO truck",
            },
        )
    print(f"{datetime.now():%H:%M:%S} request: {pile['material']} in {pile['area']}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.simulator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    r = sub.add_parser("run")
    r.add_argument("--pace", type=float, default=float(os.environ.get("SIM_PACE", "1")))
    b = sub.add_parser("backfill")
    b.add_argument("--days", type=int, default=40)
    sub.add_parser("remove")
    args = parser.parse_args(argv)
    base = os.environ.get("API_BASE", "http://api:8000")
    if args.command == "setup":
        setup(base)
    elif args.command == "run":
        run(base, args.pace)
    else:
        from app.core.db import SessionLocal

        with SessionLocal() as db:
            result = backfill(db, args.days) if args.command == "backfill" else remove(db)
        print(", ".join(f"{v} {k}" for k, v in result.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
