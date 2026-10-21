"""Analisis satu foto (sinkron, dengan batas waktu) dan impor hasil deteksi.

Semua kandidat model: source=model, review_status=pending, terhubung ke AnalysisRun dan sha256 foto.
Kandidat pending TIDAK masuk hitungan sampai manusia mengubahnya ke accepted.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..db import utcnow
from ..inference.simulation import NOTICE as SIMULATION_NOTICE
from ..deps import PageParams, get_db
from ..errors import ApiError
from ..imaging import oriented_from_bytes
from ..inference import InferenceFailed, ModelNotConfigured, ModelUnavailable, RawDetection
from .annotations import ensure_capacity
from . import errors

router = APIRouter(tags=["analysis"])
log = logging.getLogger("wallacea.inference")

NOTICE = ("Kandidat model berstatus pending dan belum masuk hitungan. Tinjau setiap kandidat: terima, koreksi, "
          "atau tolak. Confidence adalah keluaran model, bukan akurasi survei.")


def _guard_photo(db: Session, photo_id: str) -> m.Photo:
    photo = svc.get_photo(db, photo_id)
    if db.get(m.Survey, photo.survey_id).is_demo:
        raise ApiError(409, "DEMO_SURVEY_READONLY", "Analisis/impor model tidak dijalankan pada survei contoh (ilustrasi).")
    return photo


def _check_existing(db: Session, photo: m.Photo, model_id: str | None, model_version: str | None, on_existing: str):
    running = db.scalar(select(m.AnalysisRun.id).where(m.AnalysisRun.photo_id == photo.id,
                                                       m.AnalysisRun.status == "running"))
    if running:
        raise ApiError(409, "ANALYSIS_IN_PROGRESS", "Analisis foto ini sedang berjalan.", {"run_id": running})
    if on_existing != "reject":
        return
    q = select(m.AnalysisRun).where(
        m.AnalysisRun.photo_id == photo.id, m.AnalysisRun.status == "succeeded",
        m.AnalysisRun.input_sha256 == photo.sha256, m.AnalysisRun.model_id == model_id,
        m.AnalysisRun.model_version.is_(None) if model_version is None else m.AnalysisRun.model_version == model_version,
    ).order_by(m.AnalysisRun.started_at.desc())
    prev = db.scalars(q).first()
    if prev:
        raise ApiError(409, "ANALYSIS_EXISTS",
                       "Foto ini sudah dianalisis dengan model dan versi yang sama. Pilih on_existing="
                       "replace_pending (ganti kandidat pending) atau append (tambah) bila memang diinginkan.",
                       {"run_id": prev.id, "candidate_count": prev.candidate_count})


def _apply_candidates(db: Session, photo: m.Photo, run: m.AnalysisRun, detections: list[RawDetection],
                      on_existing: str, limit: int) -> tuple[list[m.Annotation], list[str]]:
    replaced: list[str] = []
    if on_existing == "replace_pending":
        replaced = list(db.scalars(select(m.Annotation.id).where(
            m.Annotation.photo_id == photo.id, m.Annotation.source == "model",
            m.Annotation.review_status == "pending",
            or_(m.Annotation.analysis_run_id.is_(None), m.Annotation.analysis_run_id != run.id))).all())
    ensure_capacity(db, photo.id, len(detections), limit, removing=len(replaced))
    if replaced:
        db.execute(delete(m.Annotation).where(m.Annotation.id.in_(replaced)))
    now = utcnow()
    created = []
    for d in detections:
        bbox = s.check_bbox(list(d.bbox))
        cx, cy = svc.bbox_center(bbox)
        a = m.Annotation(photo_id=photo.id, analysis_run_id=run.id, kind=d.label, geometry_type="bbox", x=cx, y=cy,
                         bbox_left=bbox[0], bbox_top=bbox[1], bbox_width=bbox[2], bbox_height=bbox[3],
                         source="model", review_status="pending", confidence=d.confidence,
                         model_label=(d.model_label or None) and str(d.model_label)[:120], note="",
                         created_at=now, updated_at=now)
        db.add(a)
        created.append(a)
    run.status, run.candidate_count, run.finished_at = "succeeded", len(created), utcnow()
    svc.bump_photo_revision(db, photo.id)
    return created, replaced


def _result(run: m.AnalysisRun, created: list[m.Annotation], replaced: list[str]) -> s.AnalysisResult:
    out = svc.run_out(run)
    return s.AnalysisResult(run=out, candidates=[svc.annotation_out(a) for a in created],
                            replaced_annotation_ids=replaced,
                            notice=SIMULATION_NOTICE if out.target == "simulation" else NOTICE)


@router.post(
    "/photos/{photo_id}/analyze", response_model=s.AnalysisResult, status_code=201,
    responses=errors(404, 409, 422, 500, 503, 504),
    summary="Jalankan detector pada SATU foto (sinkron). Tanpa model → 503 MODEL_NOT_CONFIGURED.",
    description="Sinkron: request menunggu sampai inferensi selesai atau melewati `limits.inference_timeout_s` "
                "(default 120 s) → 504 INFERENCE_TIMEOUT. Latensi bergantung CPU/GPU dan resolusi; tidak ada progres "
                "persentase. Tidak ada run yang dibuat bila model belum dikonfigurasi. Run yang terputus karena "
                "server restart ditandai failed (error_code=INTERRUPTED) saat startup. Revisi 4: 503 "
                "MODEL_NOT_CONFIGURED/MODEL_UNAVAILABLE membawa `details.diagnostic_code` (= health.model."
                "diagnostic_code, mis. MODEL_FILE_NOT_FOUND, DEPENDENCY_MISSING, LABEL_MAP_MISMATCH). Dengan "
                "WALLACEA_DETECTOR=simulation, run.target=simulation, model_id=simulation-not-ai dan `notice` "
                "menyatakan SIMULASI — BUKAN AI.",
)
async def analyze_photo(photo_id: str, request: Request, body: s.AnalyzeRequest | None = Body(None)):
    st = request.app.state
    detector, settings = st.detector, st.settings
    on_existing = body.on_existing if body else "reject"

    def start():
        with st.sessionmaker() as db:
            photo = _guard_photo(db, photo_id)
            info = detector.info()
            if info.state == "not_configured":
                raise ApiError(503, "MODEL_NOT_CONFIGURED", info.message,
                               {"model_state": info.state, "diagnostic_code": info.diagnostic_code})
            if not info.available:
                raise ApiError(503, "MODEL_UNAVAILABLE", info.message,
                               {"model_state": info.state, "diagnostic_code": info.diagnostic_code})
            _check_existing(db, photo, info.model_id, info.model_version, on_existing)
            run = m.AnalysisRun(photo_id=photo.id, run_type="inference", model_id=info.model_id,
                                model_version=info.model_version, input_sha256=photo.sha256, status="running",
                                started_at=utcnow(),
                                # adapter/target dicatat sejak awal agar run gagal pun membawa semantiknya
                                parameters_json=json.dumps({"on_existing": on_existing, "adapter": info.adapter,
                                                            "target": info.target}))
            db.add(run)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise ApiError(409, "ANALYSIS_IN_PROGRESS", "Analisis foto ini sedang berjalan.")
            return run.id, st.storage.read(photo.storage_key), photo.sha256

    def fail(run_id: str, code: str):
        with st.sessionmaker() as db:
            run = db.get(m.AnalysisRun, run_id)
            if run and run.status == "running":
                run.status, run.error_code, run.finished_at = "failed", code, utcnow()
                db.commit()

    run_id, data, sha = await run_in_threadpool(start)
    try:
        if hashlib.sha256(data).hexdigest() != sha:
            await run_in_threadpool(fail, run_id, "INPUT_HASH_MISMATCH")
            raise ApiError(500, "INTERNAL_ERROR", "Berkas foto di server tidak cocok dengan sha256 tersimpan.",
                           {"run_id": run_id})
        image = await run_in_threadpool(oriented_from_bytes, data)
        output = await asyncio.wait_for(run_in_threadpool(detector.detect, image), timeout=settings.inference_timeout_s)
    except ApiError:
        raise
    except asyncio.TimeoutError:
        await run_in_threadpool(fail, run_id, "INFERENCE_TIMEOUT")
        raise ApiError(504, "INFERENCE_TIMEOUT", f"Inferensi melewati {settings.inference_timeout_s:g} detik.",
                       {"run_id": run_id})
    except ModelNotConfigured as exc:
        await run_in_threadpool(fail, run_id, "MODEL_NOT_CONFIGURED")
        raise ApiError(503, "MODEL_NOT_CONFIGURED", str(exc), {"run_id": run_id, "diagnostic_code": "MODEL_PATH_NOT_SET"})
    except ModelUnavailable as exc:
        await run_in_threadpool(fail, run_id, "MODEL_UNAVAILABLE")
        raise ApiError(503, "MODEL_UNAVAILABLE", str(exc),
                       {"run_id": run_id, "diagnostic_code": exc.diagnostic_code, "model_state": "error"})
    except InferenceFailed as exc:
        await run_in_threadpool(fail, run_id, "INFERENCE_FAILED")
        raise ApiError(500, "INFERENCE_FAILED", str(exc), {"run_id": run_id})
    except Exception:
        log.exception("Unexpected inference error")
        await run_in_threadpool(fail, run_id, "INFERENCE_FAILED")
        raise ApiError(500, "INFERENCE_FAILED", "Inferensi gagal karena error tak terduga. Periksa log server.",
                       {"run_id": run_id})

    def finish():
        with st.sessionmaker() as db:
            run = db.get(m.AnalysisRun, run_id)
            photo = svc.get_photo(db, photo_id)
            run.model_id = output.model_id or run.model_id
            run.model_version = output.model_version or run.model_version
            # gabung (bukan timpa): adapter/target dari info tetap ada bila adapter tidak mengirimnya
            initial = {k: v for k, v in json.loads(run.parameters_json or "{}").items() if v is not None}
            run.parameters_json = json.dumps({**initial, **output.parameters, "on_existing": on_existing})
            try:
                created, replaced = _apply_candidates(db, photo, run, output.detections, on_existing,
                                                      settings.max_annotations_per_photo)
                db.commit()
            except ApiError as exc:
                db.rollback()
                fail(run_id, exc.code)
                exc.details["run_id"] = run_id
                raise
            except ValueError:
                db.rollback()
                fail(run_id, "INVALID_MODEL_OUTPUT")
                raise ApiError(500, "INFERENCE_FAILED", "Keluaran model tidak valid (bbox).", {"run_id": run_id})
            return _result(run, created, replaced)

    return await run_in_threadpool(finish)


@router.post(
    "/photos/{photo_id}/detections/import", response_model=s.AnalysisResult, status_code=201,
    responses=errors(404, 409, 413, 422),
    summary="Impor hasil deteksi JSON (format starter v0.1) sebagai kandidat pending",
    description="image_width/height wajib sama dengan Photo.width/height (terorientasi EXIF); image_sha256 opsional "
                "tetapi bila ada wajib sama dengan Photo.sha256. Maks 3000 deteksi, payload 5 MB.",
)
def import_detections(photo_id: str, body: s.DetectionImportRequest, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    photo = _guard_photo(db, photo_id)
    if (body.image_width, body.image_height) != (photo.width, photo.height):
        hint = (" Dimensi tertukar: model kemungkinan dijalankan pada gambar sebelum orientasi EXIF diterapkan."
                if (body.image_width, body.image_height) == (photo.height, photo.width) else "")
        raise ApiError(422, "DETECTION_MISMATCH", "Ukuran gambar pada hasil deteksi tidak sama dengan foto." + hint,
                       {"expected": {"width": photo.width, "height": photo.height},
                        "received": {"width": body.image_width, "height": body.image_height}})
    if body.image_sha256 and body.image_sha256 != photo.sha256:
        raise ApiError(422, "DETECTION_MISMATCH", "image_sha256 tidak sama dengan foto ini.",
                       {"expected_sha256": photo.sha256, "received_sha256": body.image_sha256})
    _check_existing(db, photo, body.model, body.model_version, body.on_existing)
    run = m.AnalysisRun(photo_id=photo.id, run_type="import", model_id=body.model, model_version=body.model_version,
                        input_sha256=photo.sha256, status="running", started_at=utcnow(),
                        parameters_json=json.dumps({"on_existing": body.on_existing,
                                                    "sha256_verified": body.image_sha256 is not None}))
    dets = [RawDetection(label=d.label, bbox=d.bbox, confidence=d.confidence) for d in body.detections]
    try:
        db.add(run)
        db.flush()
        created, replaced = _apply_candidates(db, photo, run, dets, body.on_existing, settings.max_annotations_per_photo)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "ANALYSIS_IN_PROGRESS", "Analisis foto ini sedang berjalan.")
    return _result(run, created, replaced)


@router.get("/photos/{photo_id}/analysis-runs", response_model=s.AnalysisRunPage, responses=errors(404),
            summary="Riwayat analysis run foto (terbaru dulu)")
def list_analysis_runs(photo_id: str, page: PageParams = Depends(), db: Session = Depends(get_db)):
    svc.get_photo(db, photo_id)
    total = db.scalar(select(func.count()).select_from(m.AnalysisRun).where(m.AnalysisRun.photo_id == photo_id))
    rows = db.scalars(select(m.AnalysisRun).where(m.AnalysisRun.photo_id == photo_id)
                      .order_by(m.AnalysisRun.started_at.desc(), m.AnalysisRun.id)
                      .limit(page.limit).offset(page.offset)).all()
    return s.AnalysisRunPage(items=[svc.run_out(r) for r in rows], total=total, limit=page.limit, offset=page.offset)
