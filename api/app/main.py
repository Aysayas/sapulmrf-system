from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.access.router import router as access_router
from app.activity.router import router as activity_router
from app.alerts.router import router as alerts_router
from app.approvals.router import router as approvals_router
from app.auth.router import router as auth_router
from app.compost.router import router as compost_router
from app.core import errors
from app.core.db import engine
from app.corrections.router import router as corrections_router
from app.devices.router import router as devices_router
from app.insights.router import router as insights_router
from app.intake.router import router as intake_router
from app.masterdata.router import router as masterdata_router
from app.operations.router import router as operations_router
from app.reports.router import router as reports_router
from app.settings.models import Settings
from app.settings.router import router as settings_router
from app.sorting.router import router as sorting_router
from app.users.router import router as users_router

app = FastAPI(title="SapulMRF API", version="0.1.0")
errors.install(app)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(access_router)
app.include_router(activity_router)
app.include_router(masterdata_router)
app.include_router(devices_router)
app.include_router(settings_router)
app.include_router(intake_router)
app.include_router(sorting_router)
app.include_router(compost_router)
app.include_router(operations_router)
app.include_router(approvals_router)
app.include_router(corrections_router)
app.include_router(alerts_router)
app.include_router(insights_router)
app.include_router(reports_router)


WORKER_LATE_AFTER = timedelta(minutes=5)


def worker_status(seen: datetime | None, now: datetime) -> str:
    if seen is None:
        return "unknown"
    return "ok" if now - seen <= WORKER_LATE_AFTER else "late"


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            seen = conn.scalar(select(Settings.worker_seen_at))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "down"})
    # A late worker doesn't fail the check: the API still works, and restarting it wouldn't help.
    return {"status": "ok", "db": "ok", "worker": worker_status(seen, datetime.now(UTC))}
