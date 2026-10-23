from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth.router import router as auth_router
from app.core import errors
from app.core.db import engine

app = FastAPI(title="SapulMRF API", version="0.1.0")
errors.install(app)
app.include_router(auth_router)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "down"})
    return {"status": "ok", "db": "ok"}
