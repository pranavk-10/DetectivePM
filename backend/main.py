"""DetectivePM API: python -m uvicorn backend.main:app --port 8000"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import jobs, operations
from backend.config import settings
from backend.db import get_db
from backend.logging_setup import configure_logging
from backend.schemas import Health

log = logging.getLogger("detectivepm.api")

_ERROR_CODES = {
    400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
    409: "conflict", 422: "validation_error", 429: "rate_limited", 503: "service_unavailable",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """No scraping happens here. Boot stays fast, and discovery belongs to the worker."""
    configure_logging()
    settings.validate()
    scheduler = None
    if settings.run_scheduler_in_api:
        from backend.scheduler import start_background

        scheduler = start_background()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="DetectivePM API",
    description="India-only Product Management job intelligence.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)


def _error(status_code: int, message: str, details: list | None = None) -> JSONResponse:
    body = {"code": _ERROR_CODES.get(status_code, "error"), "message": message, "details": details}
    return JSONResponse(status_code=status_code, content={"error": jsonable_encoder(body)})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in item["loc"]), "problem": item["msg"]} for item in exc.errors()
    ]
    return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Request validation failed", details)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")


@app.get("/api/health", response_model=Health, tags=["health"])
def health(db: Session = Depends(get_db)) -> Health:
    try:
        db.execute(text("SELECT 1"))
        connected = True
    except Exception:  # noqa: BLE001 - reported in the response
        connected = False
    return Health(
        status="healthy" if connected else "degraded",
        service="DetectivePM API",
        database="connected" if connected else "unavailable",
        environment=settings.environment,
    )


app.include_router(jobs.router)
app.include_router(operations.router)
