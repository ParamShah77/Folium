"""Unified error type + global exception handlers (§3D).

Every error response has the shape:
    {
      "error":   "MACHINE_CODE",
      "message": "human readable",
      "detail":  { ... optional ... },
      "request_id": "abc123"
    }

``AppError`` is the app's own exception carrying an explicit machine code +
optional detail. FastAPI's ``HTTPException`` and any unhandled ``Exception`` are
also normalised to this shape by the handlers registered in ``register_error_handlers``.
"""
from __future__ import annotations

from typing import Any, Optional

import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Application error with a machine code, HTTP status, and optional detail."""

    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        detail: Optional[dict[str, Any]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message
        self.detail = detail
        self.extra = extra or {}
        super().__init__(message)


class ServiceUnavailableError(Exception):
    """External dependency (market data, Claude, email, etc.) is unavailable (§3D)."""

    def __init__(self, service: str, detail: str = "") -> None:
        self.service = service
        self.detail = detail
        super().__init__(f"{service} unavailable")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _body(error: str, message: str, request_id: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"error": error, "message": message, "request_id": request_id}
    body.update({k: v for k, v in extra.items() if v is not None})
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(
                exc.error,
                exc.message,
                _request_id(request),
                detail=exc.detail,
                **exc.extra,
            ),
        )

    @app.exception_handler(ServiceUnavailableError)
    async def _service_unavailable_handler(
        request: Request, exc: ServiceUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_body(
                "SERVICE_UNAVAILABLE",
                f"{exc.service} is currently unavailable. Please try again.",
                _request_id(request),
                service=exc.service,
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        error = exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR"
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(error, str(message), _request_id(request)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_body(
                "VALIDATION_ERROR",
                "Request validation failed.",
                _request_id(request),
                detail={"errors": _safe_errors(exc)},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        sentry_sdk.capture_exception(exc)
        logger.error(
            "unhandled_exception",
            request_id=_request_id(request),
            path=request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content=_body(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Our team has been notified.",
                _request_id(request),
            ),
        )


def _safe_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """Strip non-JSON-serialisable bits (e.g. exception ctx) from pydantic errors."""
    cleaned: list[dict[str, Any]] = []
    for err in exc.errors():
        cleaned.append(
            {
                "loc": [str(p) for p in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return cleaned
