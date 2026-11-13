from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Request, WebSocket
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from app.compost import service as compost
from app.compost.schemas import ReadingIn, ReadingOut
from app.core.db import get_db
from app.core.deps import current_user, require_role
from app.core.errors import AppError
from app.devices import kiosk, live, service
from app.devices.models import Device
from app.devices.schemas import (
    DeviceCreate,
    DeviceOut,
    DeviceUpdate,
    DeviceWithKey,
    Heartbeat,
    KioskActions,
    KioskDeliveryIn,
    KioskLoginIn,
    KioskLoginOut,
    KioskOperator,
    KioskReceipt,
    KioskRow,
    KioskState,
    LiveStatus,
)
from app.intake import service as intake
from app.intake.schemas import DeliveryIn
from app.masterdata.models import SourceArea, WasteCategory
from app.sorting import service as sorting
from app.sorting.schemas import ClassificationOut, SuggestionIn
from app.users.models import User

router = APIRouter(prefix="/devices", tags=["devices"])
admin_only = require_role("admin")
can_list = require_role("admin", "operator")  # operators pick a device when reporting a problem


@router.post("/heartbeat", response_model=Heartbeat)
def heartbeat(x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """Devices call this with their own key in the X-Device-Key header, not a user session."""
    d = service.heartbeat(db, x_device_key)
    return Heartbeat(device=d.code, status="online")


@router.post("/readings", response_model=ReadingOut)
def reading(body: ReadingIn, x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """A weighing station or compost sensor sends a reading. It also counts as a heartbeat."""
    d = service.authenticate(db, x_device_key)
    return ReadingOut(device=d.code, stored_on=compost.record_reading(db, d, body))


@router.post("/cv-suggestions", response_model=ClassificationOut, status_code=201)
def cv_suggestion(body: SuggestionIn, x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """The sorting camera sends what it thinks an item is; the operator confirms it."""
    d = service.authenticate(db, x_device_key, expected_type="sorting_camera")
    c = sorting.create_suggestion(db, d, body)
    d.last_seen_at = c.suggested_at
    db.commit()
    return sorting.out(db, c)


@router.post("/deliveries", response_model=KioskReceipt, status_code=201)
def kiosk_delivery(body: KioskDeliveryIn, x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """The resident kiosk records a drop-off itself. Same rules as an operator's delivery; the receipt code is ours."""
    d = service.authenticate(db, x_device_key, expected_type="weighing_station")
    d.last_seen_at = datetime.now(UTC)
    rec = intake.record_delivery(db, DeliveryIn(
        source_area_id=intake.by_name(db, SourceArea, body.source_area, "purok"),
        category_id=intake.by_name(db, WasteCategory, body.category, "category"),
        weight_kg=body.weight_kg, weighed_by=body.weighed_by, device_id=d.id, client_key=body.client_key,
    ), actor=None)
    if kiosk.attach_cv(db, rec, body):  # first time this drop-off arrives, not a resend
        kiosk.attach_materials(db, rec, d, body)
    db.commit()
    return KioskReceipt(code=rec.code, actions=KioskActions(buzz=1))


def _kiosk(db: DbSession, key: str | None):
    """The kiosk's laptop polls every few seconds; that also keeps the kiosk online."""
    d = service.authenticate(db, key, expected_type="weighing_station")
    d.last_seen_at = datetime.now(UTC)
    db.commit()
    return d


@router.get("/kiosk-state", response_model=KioskState)
def kiosk_state(x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """Today's totals, open alerts and what the kiosk's light and buzzer should do."""
    _kiosk(db, x_device_key)
    return kiosk.kiosk_state(db)


@router.get("/kiosk-recent", response_model=list[KioskRow])
def kiosk_recent(x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """This kiosk's latest drop-offs, for its operator screen."""
    return kiosk.kiosk_recent(db, _kiosk(db, x_device_key))


@router.get("/kiosk-operators", response_model=list[KioskOperator])
def kiosk_operators(x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """Operators who set a kiosk PIN, for the kiosk's sign-in buttons."""
    _kiosk(db, x_device_key)
    return kiosk.kiosk_operators(db)


@router.post("/kiosk-login", response_model=KioskLoginOut)
def kiosk_login(body: KioskLoginIn, x_device_key: str | None = Header(None), db: DbSession = Depends(get_db)):
    """An operator's PIN at the kiosk opens a 30-minute session; the laptop then uses the operator routes with it."""
    user, token = kiosk.kiosk_login(db, _kiosk(db, x_device_key), body.user_id, body.pin)
    return KioskLoginOut(token=token, name=user.name, expires_in_s=kiosk.SESSION_MIN * 60)


@router.get("", response_model=list[DeviceOut])
def list_devices(db: DbSession = Depends(get_db), _: User = Depends(can_list)):
    return service.list_devices(db)


@router.post("", response_model=DeviceWithKey, status_code=201)
def register(body: DeviceCreate, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.register(db, body, actor)


@router.patch("/{device_id}", response_model=DeviceOut)
def update(device_id: int, body: DeviceUpdate, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.update(db, device_id, body, actor)


@router.post("/{device_id}/new-key", response_model=DeviceWithKey)
def new_key(device_id: int, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.new_key(db, device_id, actor)


@router.websocket("/kiosk-live")
async def kiosk_live(ws: WebSocket):
    """The kiosk's laptop pushes full-quality camera frames (binary JPEG) and their detections (JSON text)."""
    with live.short_db(ws.app) as db:
        try:
            d = service.authenticate(db, ws.headers.get("x-device-key"), expected_type="weighing_station")
        except AppError:
            await ws.close(code=1008)
            return
        device_id, code = d.id, d.code
    feed = live.feeds.setdefault(device_id, live.LiveFeed(device_id, code))
    await ws.accept()
    old, feed.bridge = feed.bridge, ws
    if old is not None:  # a restarted bridge replaces the old connection
        try:
            await old.close()
        except Exception:
            pass
    await feed.tell_bridge()
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                jpeg = msg["bytes"]
                if len(jpeg) > live.MAX_FRAME or not jpeg.startswith(b"\xff\xd8"):
                    await ws.close(code=1009)
                    break
                await feed.put_frame(jpeg)
            elif msg.get("text"):
                meta = live.parse_meta(msg["text"])
                feed.det = meta.get("det") if isinstance(meta.get("det"), dict) else feed.det
                feed.w, feed.h = int(meta.get("w") or feed.w), int(meta.get("h") or feed.h)
    finally:
        if feed.bridge is ws:
            feed.bridge = None
        await feed.wake_viewers()


@router.get("/live", response_model=list[LiveStatus])
def live_status(db: DbSession = Depends(get_db), _: User = Depends(can_list)):
    """Which kiosk cameras are live right now, for the Live camera page. Removed or deactivated devices drop out."""
    return [
        LiveStatus(device_id=f.device_id, code=d.code, live=f.live, fps=round(f.fps_now, 1), w=f.w, h=f.h,
                   det=f.det, viewers=f.viewers, last_frame_at=f.last_frame_at)
        for f in list(live.feeds.values())
        if (d := db.get(Device, f.device_id)) is not None and d.active
    ]


@router.get("/{device_id}/live.mjpg")
async def live_mjpg(device_id: int, request: Request):
    """The camera as an MJPEG stream (an <img> plays it). Auth is checked once, then no DB is held."""
    with live.short_db(request.app) as db:
        if current_user(request, db).role not in ("admin", "operator"):
            raise AppError(403, "Your role can't do this.")
    feed = live.feeds.get(device_id)
    if not feed or not feed.live:
        raise AppError(404, "This camera isn't live.")
    return StreamingResponse(live.mjpeg(feed), media_type=f"multipart/x-mixed-replace; boundary={live.BOUNDARY}",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
