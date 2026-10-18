"""Error envelope konsisten: {"error": {code, message, details, request_id}}."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("wallacea")

REQUEST_ID_HEADER = "X-Request-ID"

ERROR_CODES = (
    "BAD_REQUEST", "VALIDATION_ERROR", "NOT_FOUND", "METHOD_NOT_ALLOWED", "HTTP_ERROR",
    "PRECONDITION_REQUIRED", "REVISION_CONFLICT",
    "PAYLOAD_TOO_LARGE", "UNSUPPORTED_MEDIA_TYPE", "INVALID_IMAGE", "IMAGE_TOO_LARGE",
    "ANNOTATION_LIMIT_EXCEEDED", "DEMO_SURVEY_READONLY",
    "DETECTION_MISMATCH", "ANALYSIS_EXISTS", "ANALYSIS_IN_PROGRESS",
    "MODEL_NOT_CONFIGURED", "MODEL_UNAVAILABLE", "INFERENCE_FAILED", "INFERENCE_TIMEOUT",
    "INVALID_BACKUP", "INTERNAL_ERROR",
)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None):
        assert code in ERROR_CODES, code
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = details or {}
        self.headers = headers or {}


def not_found(entity: str, entity_id: str) -> ApiError:
    labels = {"survey": "Survei", "photo": "Foto", "annotation": "Penanda", "analysis_run": "Analysis run"}
    return ApiError(404, "NOT_FOUND", f"{labels.get(entity, entity)} tidak ditemukan.",
                    {"entity": entity, "id": entity_id})


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or uuid.uuid4().hex


def error_response(request: Request, status: int, code: str, message: str,
                   details: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    rid = request_id(request)
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}, "request_id": rid}},
        headers={**(headers or {}), REQUEST_ID_HEADER: rid},
    )


_HTTP_CODES = {
    400: "BAD_REQUEST", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE", 422: "VALIDATION_ERROR", 500: "INTERNAL_ERROR",
}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        rid = incoming if incoming.isascii() and 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.setdefault(REQUEST_ID_HEADER, rid)
        return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        issues = []
        for err in exc.errors():
            issues.append({
                "loc": [str(p) for p in err.get("loc", ())],
                "type": err.get("type"),
                "msg": err.get("msg"),
            })
        return error_response(request, 422, "VALIDATION_ERROR", "Data permintaan tidak valid.", {"issues": issues})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Permintaan gagal."
        if exc.status_code == 404:
            message = "Endpoint tidak ditemukan."
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error (request_id=%s)", request_id(request))
        return error_response(request, 500, "INTERNAL_ERROR", "Terjadi kesalahan pada server. Lihat log dengan request_id ini.")
