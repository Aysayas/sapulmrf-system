from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.access.router import router as access_router
from app.activity.router import router as activity_router
from app.auth.router import router as auth_router
from app.core import errors
from app.core.db import engine
from app.masterdata.router import router as masterdata_router
from app.users.router import router as users_router

app = FastAPI(title="SapulMRF API", version="0.1.0")
errors.install(app)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(access_router)
app.include_router(activity_router)
app.include_router(masterdata_router)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "down"})
    return {"status": "ok", "db": "ok"}
