"""WALLACEA API v1. Jalankan: python -m app (bind 127.0.0.1:8000)."""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from . import API_VERSION, CONTRACT_REVISION
from . import models as m
from .config import API_ROOT, Settings, load_settings
from .db import make_engine, make_sessionmaker, utcnow
from .errors import REQUEST_ID_HEADER, RequestIdMiddleware, install_error_handlers
from .inference import Detector, build_detector
from .routers import analysis, annotations, health, imports, photos, reports, surveys
from .storage import Storage

log = logging.getLogger("wallacea")
PREFIX = "/api/v1"

DESCRIPTION = """
API lokal WALLACEA untuk survei pertanian dari foto drone **setelah mendarat** (unggah berkas).

* Tidak ada kontrol penerbangan, live video, georeferensi, atau orthomosaic.
* Koordinat penanda dinormalisasi 0–1 terhadap foto **setelah orientasi EXIF** (`display_url`), bukan GPS.
* Kandidat model selalu `pending` dan tidak dihitung sampai ditinjau manusia.
* Tanpa bobot model, `POST /photos/{id}/analyze` → 503 `MODEL_NOT_CONFIGURED`; mode manual tetap berfungsi.
* Error: `{"error": {"code", "message", "details", "request_id"}}`.
* Konkurensi penanda: `ETag`/`If-Match` berisi `revision` (wajib untuk PATCH/DELETE annotation).
"""


def run_migrations(engine, url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def _preload(detector: Detector) -> None:
    try:
        detector.preload()
        log.info("Model dimuat saat startup: %s", detector.info().model_id)
    except Exception:  # noqa: BLE001 — status error terlihat di /health; analyze tetap memberi 503
        log.exception("Preload model gagal")


def mark_interrupted_runs(sessionmaker) -> int:
    with sessionmaker() as db:
        res = db.execute(update(m.AnalysisRun).where(m.AnalysisRun.status == "running")
                         .values(status="failed", error_code="INTERRUPTED", finished_at=utcnow()))
        db.commit()
        return res.rowcount or 0


class BodyLimitMiddleware:
    """Tolak body terlalu besar sebelum di-parse/di-spool (Content-Length), plus hitung byte untuk chunked."""

    def __init__(self, app, settings: Settings):
        self.app = app
        mb = 1024 * 1024
        self.rules = [
            (re.compile(rf"^{PREFIX}/surveys/[^/]+/photos$"), settings.max_upload_bytes + mb),
            (re.compile(rf"^{PREFIX}/imports/starter-backup$"), settings.max_backup_bytes + mb),
            (re.compile(rf"^{PREFIX}/photos/[^/]+/detections/import$"), settings.max_detection_payload_bytes),
        ]
        self.default = mb

    def limit_for(self, path: str) -> int:
        return next((lim for rx, lim in self.rules if rx.match(path)), self.default)

    async def _reject(self, send, limit: int):
        rid = uuid.uuid4().hex
        body = json.dumps({"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Ukuran permintaan melebihi batas.",
                                     "details": {"max_bytes": limit}, "request_id": rid}}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                                (REQUEST_ID_HEADER.lower().encode(), rid.encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        limit = self.limit_for(scope["path"])
        for k, v in scope["headers"]:
            if k == b"content-length" and v.isdigit() and int(v) > limit:
                return await self._reject(send, limit)
        state = {"received": 0, "exceeded": False, "replaced": False}

        async def limited_receive():
            msg = await receive()
            if msg["type"] == "http.request":
                state["received"] += len(msg.get("body", b""))
                if state["received"] > limit:
                    state["exceeded"] = True
                    return {"type": "http.disconnect"}
            return msg

        async def guarded_send(msg):
            if state["exceeded"]:
                if not state["replaced"] and msg["type"] == "http.response.start":
                    state["replaced"] = True
                    await self._reject(send, limit)
                return
            await send(msg)

        await self.app(scope, limited_receive, guarded_send)


def create_app(settings: Settings | None = None, detector: Detector | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        if settings.auto_migrate:
            run_migrations(app.state.engine, settings.database_url)
        n = mark_interrupted_runs(app.state.sessionmaker)
        if n:
            log.warning("%d analysis run terputus ditandai failed (INTERRUPTED)", n)
        if settings.model_preload and app.state.detector.info().available:
            # Thread latar: server tetap menerima request; /health menunjukkan state=loaded setelah selesai.
            threading.Thread(target=_preload, args=(app.state.detector,), name="model-preload", daemon=True).start()
        yield
        app.state.engine.dispose()

    app = FastAPI(title="WALLACEA API", version=f"{API_VERSION}.{CONTRACT_REVISION}.0", description=DESCRIPTION,
                  lifespan=lifespan, openapi_url=f"{PREFIX}/openapi.json", docs_url=f"{PREFIX}/docs", redoc_url=None,
                  generate_unique_id_function=lambda route: route.name)  # operationId = nama fungsi
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)
    app.state.storage = Storage(settings.uploads_dir)
    app.state.detector = detector or build_detector(settings)

    install_error_handlers(app)
    # add_middleware: yang terakhir ditambahkan = paling luar. CORS paling luar agar 413 pun membawa header CORS.
    app.add_middleware(BodyLimitMiddleware, settings=settings)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "If-Match", REQUEST_ID_HEADER],
        expose_headers=["ETag", REQUEST_ID_HEADER, "Content-Disposition"],
    )
    for r in (health, surveys, photos, annotations, analysis, reports, imports):
        app.include_router(r.router, prefix=PREFIX)
    return app
