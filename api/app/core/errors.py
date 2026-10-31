import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Raised by services for an expected refusal; turned into {"detail": ...} with the given status code."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def _app_error(_: Request, e: AppError):
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    @app.exception_handler(Exception)
    def _unexpected(request: Request, e: Exception):
        logging.getLogger("uvicorn.error").error("%s %s failed", request.method, request.url.path, exc_info=e)
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Try again."})
