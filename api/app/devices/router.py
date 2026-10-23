from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session as DbSession

from app.compost import service as compost
from app.compost.schemas import ReadingIn, ReadingOut
from app.core.db import get_db
from app.core.deps import require_role
from app.devices import service
from app.devices.schemas import DeviceCreate, DeviceOut, DeviceUpdate, DeviceWithKey, Heartbeat
from app.sorting import service as sorting
from app.sorting.schemas import ClassificationOut, SuggestionIn
from app.users.models import User

router = APIRouter(prefix="/devices", tags=["devices"])
admin_only = require_role("admin")


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


@router.get("", response_model=list[DeviceOut])
def list_devices(db: DbSession = Depends(get_db), _: User = Depends(admin_only)):
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
