from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.access.models import StaffAccess
from app.core.db import get_db
from app.core.deps import current_user
from app.core.errors import AppError
from app.intake.schemas import DeliveryOut
from app.operations import schemas as s
from app.operations import service
from app.users.models import User

router = APIRouter(tags=["operations (read)"])


def viewer(screen: str | None = None):
    """Admins and operators see everything; staff need the per-person grant for granted screens."""

    def check(user: User = Depends(current_user), db: DbSession = Depends(get_db)) -> User:
        if user.role == "staff" and screen:
            row = db.get(StaffAccess, (user.id, screen))
            if not row or not row.granted:
                raise AppError(403, "This screen isn't shared with you. Ask the Barangay Administrator.")
        return user

    return check


anyone = viewer()
segregation_viewer = viewer("segregation")
camera_viewer = viewer("camera")


@router.get("/operations/intake", response_model=list[DeliveryOut])
def intake(days: int | None = Query(None, ge=1, le=366), q: str | None = None, limit: int = Query(50, ge=1, le=200),
           db: DbSession = Depends(get_db), _: User = Depends(anyone)):
    return service.intake_list(db, days, q, limit)


@router.get("/operations/segregation", response_model=s.Compliance)
def segregation(days: int = Query(30, ge=1, le=366), db: DbSession = Depends(get_db), _: User = Depends(segregation_viewer)):
    return service.compliance(db, days)


@router.get("/operations/sorting", response_model=s.SortingView)
def sorting(days: int = Query(1, ge=1, le=366), db: DbSession = Depends(get_db), _: User = Depends(anyone)):
    return service.sorting_view(db, days)


@router.get("/operations/inventory", response_model=s.InventoryView)
def inventory(db: DbSession = Depends(get_db), _: User = Depends(anyone)):
    return service.inventory(db)


@router.get("/operations/compost", response_model=s.CompostView)
def compost(batch: str | None = None, db: DbSession = Depends(get_db), _: User = Depends(anyone)):
    return service.compost_view(db, batch)


@router.get("/operations/camera", response_model=s.CameraView)
def camera(db: DbSession = Depends(get_db), _: User = Depends(camera_viewer)):
    return service.camera(db)


@router.get("/overview", response_model=s.Overview)
def overview(db: DbSession = Depends(get_db), _: User = Depends(anyone)):
    return service.overview(db)
