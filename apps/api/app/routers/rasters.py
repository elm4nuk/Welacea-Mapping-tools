"""Raster GeoTIFF impor + tile + analisis model per jendela → kandidat berkoordinat (revisi 5).

Raster diakses hanya lewat ID aset terdaftar; tidak ada endpoint yang membuka path/URL dari pengguna.
Impor GeoTIFF BUKAN fotogrametri: georeferensi diambil apa adanya dari berkas (product_type
imported_georeferenced_raster, is_verified_orthomosaic=false).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

from fastapi import APIRouter, Body, Depends, File, Form, Path, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import mapping_services as ms
from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..db import utcnow
from ..deps import PageParams, get_db, get_storage
from ..errors import ApiError
from ..inference import InferenceFailed, ModelNotConfigured, ModelUnavailable
from ..inference.simulation import NOTICE as SIMULATION_NOTICE
from ..storage import Storage
from .photos import clean_filename
from . import errors

router = APIRouter(tags=["rasters"])
log = logging.getLogger("wallacea.mapping")
PNG = {200: {"content": {"image/png": {}}, "description": "PNG"}}
GEOJSON = "application/geo+json"
CACHE = {"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"}
NOTICE = ("Kandidat peta berstatus pending dan belum masuk hitungan. Posisi geografis berasal dari georeferensi "
          "berkas GeoTIFF impor (tidak diverifikasi WALLACEA). Hitungan per raster tidak boleh dijumlahkan antar "
          "raster/penerbangan sebagai tanaman unik.")


def _raster_error(exc):
    from ..geo.raster import RasterError
    if isinstance(exc, RasterError):
        return ApiError(exc.status, exc.code, exc.message, exc.details)
    return exc


# ---------------------------------------------------------------- upload & CRUD
@router.post(
    "/surveys/{survey_id}/rasters", response_model=s.RasterUploadResult, status_code=201,
    responses=errors(400, 404, 409, 413, 415, 422, 503),
    summary="Impor SATU GeoTIFF RGB bergeoreferensi (multipart `file`). Bukan pembuatan orthomosaic.",
    description="Diterima: GTiff, 3 band RGB uint8 atau 4 band RGBA (band 4 alpha), CRS geografis/proyeksi valid, "
                "geotransform bukan identitas. Ditolak tanpa ditempel ke peta: tanpa CRS / hanya GCP / transform "
                "identitas (422 RASTER_NOT_GEOREFERENCED). Batas ukuran: `limits.max_raster_bytes`, "
                "`limits.max_raster_pixels`, cakupan ≤ `limits.max_raster_footprint_km2`. Berkas asli disimpan utuh "
                "(sha256), plus turunan tampilan RGBA ber-overview untuk tile. Proses sinkron: raster ratusan MB "
                "dapat memakan beberapa menit.",
)
async def upload_raster(survey_id: str, request: Request, file: UploadFile = File(...),
                        name: str = Form("", max_length=150), source_description: str = Form("", max_length=500)):
    settings = request.app.state.settings
    storage: Storage = request.app.state.storage
    ms.require_rasters()

    def precheck():
        with request.app.state.sessionmaker() as db:
            if svc.get_survey(db, survey_id).is_demo:
                raise ApiError(409, "DEMO_SURVEY_READONLY", "Survei contoh tidak menerima raster. Buat survei nyata dahulu.")

    await run_in_threadpool(precheck)
    tmp = storage.temp_path()
    h, total = hashlib.sha256(), 0
    try:
        with open(tmp, "wb") as out:
            while chunk := await file.read(4 * 1024 * 1024):
                total += len(chunk)
                if total > settings.max_raster_bytes:
                    raise ApiError(413, "RASTER_TOO_LARGE", f"Berkas melebihi {settings.max_raster_bytes // 2**20} MB.",
                                   {"max_raster_bytes": settings.max_raster_bytes})
                h.update(chunk)
                out.write(chunk)
        await file.close()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    original = clean_filename(file.filename)

    def process():
        from ..geo import raster as gr
        written: list[str] = []
        try:
            try:
                info = gr.inspect(tmp, settings.max_raster_pixels, settings.max_raster_footprint_km2)
            except Exception as exc:  # noqa: BLE001
                raise _raster_error(exc)
            base = Storage.new_base()
            key, dkey = f"{base}_raster.tif", f"{base}_rdisplay.tif"
            storage.adopt(key, tmp)
            written.append(key)
            dtmp = storage.temp_path().with_suffix(".tif")
            try:
                processing = gr.build_display(storage.path(key), dtmp)
                storage.adopt(dkey, dtmp)
            finally:
                dtmp.unlink(missing_ok=True)
            written.append(dkey)
            with request.app.state.sessionmaker() as db:
                survey = svc.get_survey(db, survey_id)
                dups = db.scalars(select(m.RasterAsset.id).where(m.RasterAsset.survey_id == survey.id,
                                                                 m.RasterAsset.sha256 == h.hexdigest())).all()
                now = utcnow()
                meta = {"driver": info.driver, "dtype": info.dtype, "colorinterp": info.colorinterp,
                        "mask_flags": info.mask_flags, "compression": info.compression, "is_rotated": info.is_rotated,
                        "pixel_size_native": info.pixel_size_native, "crs_is_geographic": info.crs_is_geographic,
                        "warnings": info.warnings}
                r = m.RasterAsset(
                    survey_id=survey.id, name=(name.strip() or original)[:150], original_name=original,
                    source_description=source_description.strip(), storage_key=key, display_key=dkey,
                    size_bytes=total, sha256=h.hexdigest(), width=info.width, height=info.height,
                    band_count=info.band_count, crs_wkt=info.crs_wkt, crs_epsg=info.crs_epsg, crs_name=info.crs_name,
                    transform_json=json.dumps(info.transform), bounds_native_json=json.dumps(info.bounds_native),
                    min_lon=info.bounds_wgs84[0], min_lat=info.bounds_wgs84[1], max_lon=info.bounds_wgs84[2],
                    max_lat=info.bounds_wgs84[3], footprint_json=gr.dumps(info.footprint_wgs84),
                    footprint_area_m2=info.footprint_area_m2, approx_gsd_m=info.approx_gsd_m, nodata=info.nodata,
                    has_alpha=info.has_alpha, metadata_json=json.dumps(meta), processing_json=json.dumps(processing),
                    created_at=now, updated_at=now)
                db.add(r)
                db.commit()
                warnings = [s.Warning(code="DUPLICATE_IN_SURVEY", message="Raster identik (sha256 sama) sudah ada di "
                                      "survei ini; hitungannya jangan dijumlahkan.", details={"raster_ids": list(dups)})
                            ] if dups else []
                return s.RasterUploadResult(raster=ms.raster_out(db, r), warnings=warnings)
        except BaseException:
            storage.delete(*written)
            tmp.unlink(missing_ok=True)
            raise

    return await run_in_threadpool(process)


@router.get("/surveys/{survey_id}/rasters", response_model=s.RasterPage, responses=errors(404),
            summary="Daftar raster impor survei")
def list_rasters(survey_id: str, page: PageParams = Depends(), db: Session = Depends(get_db)):
    svc.get_survey(db, survey_id)
    q = select(m.RasterAsset).where(m.RasterAsset.survey_id == survey_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(m.RasterAsset.created_at, m.RasterAsset.id).limit(page.limit).offset(page.offset))
    return s.RasterPage(items=[ms.raster_out(db, r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@router.get("/rasters/{raster_id}", response_model=s.RasterAsset, responses=errors(404))
def get_raster(raster_id: str, response: Response, db: Session = Depends(get_db)):
    r = ms.get_raster(db, raster_id)
    response.headers.update(svc.etag(r.revision))
    return ms.raster_out(db, r)


@router.patch("/rasters/{raster_id}", response_model=s.RasterAsset, responses=errors(400, 404, 409, 422),
              summary="Ubah nama/keterangan sumber. If-Match opsional. Georeferensi tidak dapat diubah lewat API.")
def update_raster(raster_id: str, body: s.RasterUpdate, request: Request, response: Response,
                  db: Session = Depends(get_db)):
    expected = svc.parse_if_match(request, required=False)
    r = ms.get_raster(db, raster_id)
    if expected is not None and expected != r.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Raster sudah diubah di tempat lain.",
                       {"current": ms.raster_out(db, r).model_dump(mode="json")})
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v.strip())
    r.revision += 1
    r.updated_at = utcnow()
    db.commit()
    response.headers.update(svc.etag(r.revision))
    return ms.raster_out(db, r)


@router.delete("/rasters/{raster_id}", status_code=204, responses=errors(400, 404, 409),
               summary="Hapus raster, berkasnya, run, dan semua deteksi petanya")
def delete_raster(raster_id: str, request: Request, db: Session = Depends(get_db),
                  storage: Storage = Depends(get_storage)):
    expected = svc.parse_if_match(request, required=False)
    r = ms.get_raster(db, raster_id)
    if expected is not None and expected != r.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Raster sudah diubah di tempat lain.", {"current_revision": r.revision})
    keys = (r.storage_key, r.display_key)
    db.delete(r)
    db.commit()
    storage.delete(*keys)
    return Response(status_code=204)


# ---------------------------------------------------------------- berkas, preview, tile
def _path(storage: Storage, key: str):
    p = storage.path(key)
    if not p.is_file():
        raise ApiError(404, "NOT_FOUND", "Berkas raster tidak ditemukan di penyimpanan server.", {"entity": "raster_file"})
    return p


@router.get("/rasters/{raster_id}/content", response_class=FileResponse,
            responses={200: {"content": {"image/tiff": {}}, "description": "GeoTIFF asli"}, **errors(404)},
            summary="GeoTIFF asli apa adanya (sha256 = raster.sha256)")
def raster_content(raster_id: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)):
    r = ms.get_raster(db, raster_id)
    return FileResponse(_path(storage, r.storage_key), media_type="image/tiff", filename=r.original_name,
                        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/rasters/{raster_id}/preview.png", response_class=Response, responses={**PNG, **errors(404, 503)},
            summary="Preview PNG di ruang piksel raster (TIDAK diproyeksi ulang; untuk peta gunakan tile)")
def raster_preview(raster_id: str, max_size: int = Query(1024, ge=64, le=2048), db: Session = Depends(get_db),
                   storage: Storage = Depends(get_storage)):
    from ..geo.raster import render_preview
    ms.require_rasters()
    r = ms.get_raster(db, raster_id)
    return Response(render_preview(_path(storage, r.display_key), max_size), media_type="image/png", headers=CACHE)


@router.get("/rasters/{raster_id}/tilejson.json", response_model=s.TileJson, responses=errors(404),
            summary="TileJSON 3.0.0 (URL tile relatif terhadap origin API)")
def raster_tilejson(raster_id: str, db: Session = Depends(get_db)):
    r = ms.get_raster(db, raster_id)
    out = ms.raster_out(db, r)
    attribution = f"Raster impor: {r.name}" + (f" — {r.source_description}" if r.source_description else "") + \
        " (georeferensi dari berkas, tidak diverifikasi)"
    return s.TileJson(name=r.name, tiles=[out.tile_url_template], minzoom=out.minzoom, maxzoom=out.maxzoom,
                      bounds=out.bounds_wgs84, center=[(r.min_lon + r.max_lon) / 2, (r.min_lat + r.max_lat) / 2,
                                                       max(out.minzoom, out.maxzoom - 2)], attribution=attribution)


@router.get("/rasters/{raster_id}/tiles/{z}/{x}/{y}.png", response_class=Response,
            responses={**PNG, **errors(404, 422, 503)},
            summary="Tile XYZ Web Mercator (EPSG:3857), PNG RGBA 256 px. Di luar raster: transparan.")
def raster_tile(raster_id: str, z: int = Path(ge=0, le=24), x: int = Path(ge=0), y: int = Path(ge=0),
                db: Session = Depends(get_db), storage: Storage = Depends(get_storage)):
    from ..geo.raster import render_tile
    ms.require_rasters()
    if x >= 2 ** z or y >= 2 ** z:
        raise ApiError(422, "VALIDATION_ERROR", "Koordinat tile di luar rentang zoom.", {"z": z, "x": x, "y": y})
    r = ms.get_raster(db, raster_id)
    path = _path(storage, r.display_key)
    db.close()   # tidak menahan koneksi DB selama render
    return Response(render_tile(path, z, x, y), media_type="image/png", headers=CACHE)


# ---------------------------------------------------------------- analisis model pada raster
def _check_existing(db: Session, r: m.RasterAsset, model_id, model_version, on_existing: str):
    running = db.scalar(select(m.RasterAnalysisRun.id).where(m.RasterAnalysisRun.raster_id == r.id,
                                                             m.RasterAnalysisRun.status == "running"))
    if running:
        raise ApiError(409, "ANALYSIS_IN_PROGRESS", "Analisis raster ini sedang berjalan.", {"run_id": running})
    if on_existing != "reject":
        return
    q = select(m.RasterAnalysisRun).where(
        m.RasterAnalysisRun.raster_id == r.id, m.RasterAnalysisRun.status == "succeeded",
        m.RasterAnalysisRun.input_sha256 == r.sha256, m.RasterAnalysisRun.model_id == model_id,
        m.RasterAnalysisRun.model_version.is_(None) if model_version is None
        else m.RasterAnalysisRun.model_version == model_version,
    ).order_by(m.RasterAnalysisRun.started_at.desc())
    prev = db.scalars(q).first()
    if prev:
        raise ApiError(409, "ANALYSIS_EXISTS", "Raster ini sudah dianalisis dengan model dan versi yang sama. Pilih "
                                               "on_existing=replace_pending atau append bila memang diinginkan.",
                       {"run_id": prev.id, "candidate_count": prev.candidate_count})


def detect_on_raster(detector, display_path, width: int, height: int, req: s.RasterAnalyzeRequest,
                     deadline: float, max_detections: int):
    """Jalankan detector per jendela → kotak piksel raster asal (setelah buang tepi/mask & dedup) + statistik."""
    import numpy as np
    import rasterio
    from PIL import Image
    from rasterio.enums import Resampling
    from rasterio.windows import Window as RWindow

    from ..geo import detection as gd

    last = None
    boxes, stats = [], dict(window_count=0, windows_skipped_masked=0, raw_detections=0, dropped_edge=0,
                            dropped_masked=0)
    with rasterio.open(display_path) as src:
        for win in gd.windows(width, height, req.tile_size, req.overlap_px):
            if time.monotonic() > deadline:
                raise TimeoutError
            rw = RWindow(win.col_off, win.row_off, win.width, win.height)
            mask = src.read(4, window=rw)
            if not mask.any():
                stats["windows_skipped_masked"] += 1
                continue
            stats["window_count"] += 1
            if req.scale != 1.0:
                shape = (3, max(1, round(win.height * req.scale)), max(1, round(win.width * req.scale)))
                rgb = src.read([1, 2, 3], window=rw, out_shape=shape, resampling=Resampling.bilinear)
            else:
                rgb = src.read([1, 2, 3], window=rw)
            out = detector.detect(Image.fromarray(np.ascontiguousarray(rgb.transpose(1, 2, 0))))
            for d in out.detections:
                stats["raw_detections"] += 1
                left, top, w, h = gd.to_raster_pixels(win, list(d.bbox))
                pb = gd.PixelBox(d.label, left, top, w, h, d.confidence, d.model_label)
                if req.overlap_px > 0 and gd.touches_inner_edge(pb, win, width, height):
                    stats["dropped_edge"] += 1
                    continue
                cc = min(win.width - 1, max(0, int(left + w / 2) - win.col_off))
                cr = min(win.height - 1, max(0, int(top + h / 2) - win.row_off))
                if mask[cr, cc] == 0:
                    stats["dropped_masked"] += 1
                    continue
                boxes.append(pb)
            last = out
    kept = gd.deduplicate(boxes, req.iou_threshold, req.ios_threshold)
    stats.update(after_edge_and_mask=len(boxes), after_dedup=len(kept),
                 dedup={"method": "greedy_nms_per_kind", "iou_threshold": req.iou_threshold,
                        "ios_threshold": req.ios_threshold, "edge_rule": "drop_boxes_touching_inner_window_edges"
                        if req.overlap_px > 0 else "none"})
    if len(kept) > max_detections:
        raise ApiError(422, "ANNOTATION_LIMIT_EXCEEDED", f"Lebih dari {max_detections} kandidat pada satu raster; "
                                                         "naikkan confidence model atau potong raster.",
                       {"count": len(kept), "max": max_detections})
    return kept, stats, (last if stats["window_count"] else None)


@router.post(
    "/rasters/{raster_id}/analyze", response_model=s.RasterAnalysisResult, status_code=201,
    responses=errors(404, 409, 422, 500, 503, 504),
    summary="Jalankan model aktif pada raster per jendela (sinkron) → kandidat peta pending berkoordinat WGS84",
    description="Jendela `tile_size` px ber-overlap `overlap_px`, opsional resize `scale`. Posisi dikembalikan ke "
                "piksel raster asal, lalu transform raster + CRS → WGS84 (pyproj always_xy, [lon, lat]). Duplikat "
                "antarjendela dihapus (NMS per kind, IoU/IoS; lihat parameters.dedup). Kandidat selalu pending. "
                "Batas waktu total `limits.raster_analysis_timeout_s` → 504 INFERENCE_TIMEOUT.",
)
async def analyze_raster(raster_id: str, request: Request, body: s.RasterAnalyzeRequest | None = Body(None)):
    st = request.app.state
    detector, settings = st.detector, st.settings
    req = body or s.RasterAnalyzeRequest()
    ms.require_rasters()

    def start():
        with st.sessionmaker() as db:
            r = ms.get_raster(db, raster_id)
            info = detector.info()
            if info.state == "not_configured":
                raise ApiError(503, "MODEL_NOT_CONFIGURED", info.message,
                               {"model_state": info.state, "diagnostic_code": info.diagnostic_code})
            if not info.available:
                raise ApiError(503, "MODEL_UNAVAILABLE", info.message,
                               {"model_state": info.state, "diagnostic_code": info.diagnostic_code})
            _check_existing(db, r, info.model_id, info.model_version, req.on_existing)
            run = m.RasterAnalysisRun(raster_id=r.id, model_id=info.model_id, model_version=info.model_version,
                                      adapter=info.adapter, target=info.target, input_sha256=r.sha256,
                                      status="running", started_at=utcnow(),
                                      parameters_json=json.dumps(req.model_dump()))
            db.add(run)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise ApiError(409, "ANALYSIS_IN_PROGRESS", "Analisis raster ini sedang berjalan.")
            return run.id, st.storage.path(r.display_key), r.width, r.height, json.loads(r.transform_json), r.crs_wkt

    def fail(run_id: str, code: str):
        with st.sessionmaker() as db:
            run = db.get(m.RasterAnalysisRun, run_id)
            if run and run.status == "running":
                run.status, run.error_code, run.finished_at = "failed", code, utcnow()
                db.commit()

    run_id, display, width, height, transform, crs_wkt = await run_in_threadpool(start)
    deadline = time.monotonic() + settings.raster_analysis_timeout_s
    try:
        kept, stats, last = await run_in_threadpool(detect_on_raster, detector, display, width, height, req, deadline,
                                                    settings.max_map_detections)
    except ApiError as exc:
        await run_in_threadpool(fail, run_id, exc.code)
        exc.details["run_id"] = run_id
        raise
    except TimeoutError:
        await run_in_threadpool(fail, run_id, "INFERENCE_TIMEOUT")
        raise ApiError(504, "INFERENCE_TIMEOUT", f"Analisis raster melewati {settings.raster_analysis_timeout_s:g} detik.",
                       {"run_id": run_id})
    except ModelNotConfigured as exc:
        await run_in_threadpool(fail, run_id, "MODEL_NOT_CONFIGURED")
        raise ApiError(503, "MODEL_NOT_CONFIGURED", str(exc), {"run_id": run_id})
    except ModelUnavailable as exc:
        await run_in_threadpool(fail, run_id, "MODEL_UNAVAILABLE")
        raise ApiError(503, "MODEL_UNAVAILABLE", str(exc), {"run_id": run_id, "diagnostic_code": exc.diagnostic_code})
    except InferenceFailed as exc:
        await run_in_threadpool(fail, run_id, "INFERENCE_FAILED")
        raise ApiError(500, "INFERENCE_FAILED", str(exc), {"run_id": run_id})
    except Exception:
        log.exception("Raster analysis failed")
        await run_in_threadpool(fail, run_id, "INFERENCE_FAILED")
        raise ApiError(500, "INFERENCE_FAILED", "Analisis raster gagal karena error tak terduga. Periksa log server.",
                       {"run_id": run_id})

    def finish():
        from ..geo.raster import PixelGeo, dumps
        geo = PixelGeo(transform, crs_wkt)
        with st.sessionmaker() as db:
            run = db.get(m.RasterAnalysisRun, run_id)
            replaced = 0
            if req.on_existing == "replace_pending":
                replaced = db.execute(delete(m.MapDetection).where(
                    m.MapDetection.raster_id == raster_id, m.MapDetection.review_status == "pending",
                    m.MapDetection.analysis_run_id != run_id)).rowcount or 0
            now = utcnow()
            for b in kept:
                cx, cy = b.left + b.width / 2, b.top + b.height / 2
                nx, ny = geo.native(cx, cy)
                lon, lat = geo.to_wgs.transform(nx, ny)
                db.add(m.MapDetection(
                    raster_id=raster_id, analysis_run_id=run_id, kind=b.kind, px_left=b.left, px_top=b.top,
                    px_width=b.width, px_height=b.height, center_x=nx, center_y=ny, lon=lon, lat=lat,
                    geometry_json=dumps(geo.box_polygon(b.left, b.top, b.width, b.height)), source="model",
                    review_status="pending", confidence=b.confidence,
                    model_label=(b.model_label or None) and str(b.model_label)[:120], created_at=now, updated_at=now))
            params = {**json.loads(run.parameters_json or "{}"), **stats}
            if last is not None:
                params["model_parameters"] = last.parameters
                run.model_id = last.model_id or run.model_id
                run.model_version = last.model_version or run.model_version
            run.parameters_json = json.dumps(params)
            run.status, run.candidate_count, run.finished_at = "succeeded", len(kept), utcnow()
            db.commit()
            base = f"/api/v1/rasters/{raster_id}"
            return s.RasterAnalysisResult(
                run=ms.rrun_out(run), candidate_count=len(kept), replaced_detection_count=replaced,
                detections_url=f"{base}/detections", detections_geojson_url=f"{base}/detections.geojson",
                notice=(SIMULATION_NOTICE + " " if run.target == "simulation" else "") + NOTICE)

    return await run_in_threadpool(finish)


@router.get("/rasters/{raster_id}/analysis-runs", response_model=s.RasterAnalysisRunPage, responses=errors(404),
            summary="Riwayat analisis raster (terbaru dulu)")
def list_raster_runs(raster_id: str, page: PageParams = Depends(), db: Session = Depends(get_db)):
    ms.get_raster(db, raster_id)
    q = select(m.RasterAnalysisRun).where(m.RasterAnalysisRun.raster_id == raster_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(m.RasterAnalysisRun.started_at.desc(), m.RasterAnalysisRun.id)
                      .limit(page.limit).offset(page.offset))
    return s.RasterAnalysisRunPage(items=[ms.rrun_out(r) for r in rows], total=total, limit=page.limit,
                                   offset=page.offset)


def _detections_query(raster_id: str, review_status: str | None):
    q = select(m.MapDetection).where(m.MapDetection.raster_id == raster_id)
    if review_status:
        q = q.where(m.MapDetection.review_status == review_status)
    return q


@router.get("/rasters/{raster_id}/detections", response_model=s.MapDetectionPage, responses=errors(404),
            summary="Kandidat/temuan peta raster (urutan dibuat). Hitungan hanya untuk raster ini.")
def list_detections(raster_id: str, review_status: s.ReviewStatus | None = None,
                    limit: int = Query(1000, ge=1, le=5000), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db)):
    r = ms.get_raster(db, raster_id)
    containment = ms.FieldContainment(ms.survey_field(db, r.survey_id))
    q = _detections_query(raster_id, review_status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(m.MapDetection.created_at, m.MapDetection.id).limit(limit).offset(offset))
    return s.MapDetectionPage(items=[ms.detection_out(d, containment) for d in rows], total=total, limit=limit,
                              offset=offset, counts=ms.raster_counts(db, r, containment))


@router.get("/rasters/{raster_id}/detections.geojson", response_class=JSONResponse,
            responses={200: {"content": {GEOJSON: {}}, "description": "FeatureCollection WGS84"}, **errors(404)},
            summary="Ekspor kandidat/temuan peta raster sebagai GeoJSON (poligon kotak WGS84)")
def detections_geojson(raster_id: str, review_status: s.ReviewStatus | None = None, db: Session = Depends(get_db)):
    r = ms.get_raster(db, raster_id)
    containment = ms.FieldContainment(ms.survey_field(db, r.survey_id))
    rows = db.scalars(_detections_query(raster_id, review_status).order_by(m.MapDetection.created_at,
                                                                            m.MapDetection.id))
    fc = {"type": "FeatureCollection", "features": [ms.detection_feature(d, containment) for d in rows],
          "properties": {"raster_id": r.id, "raster_name": r.name, "product_type": r.product_type,
                         "counts_are_unique_plants": False, "crs": "EPSG:4326 (lon, lat)"}}
    return JSONResponse(fc, media_type=GEOJSON,
                        headers={"Content-Disposition": f'attachment; filename="deteksi-{r.id}.geojson"'})


@router.patch("/map-detections/{detection_id}", response_model=s.MapDetection,
              responses=errors(400, 404, 409, 422, 428),
              summary="Review kandidat peta (terima/tolak/koreksi kind/catatan). If-Match WAJIB.")
def update_detection(detection_id: str, body: s.MapDetectionUpdate, request: Request, response: Response,
                     db: Session = Depends(get_db)):
    expected = svc.parse_if_match(request, required=True)
    d = ms.get_detection(db, detection_id)
    raster = ms.get_raster(db, d.raster_id)
    containment = ms.FieldContainment(ms.survey_field(db, raster.survey_id))
    if expected != d.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Kandidat sudah diubah di tempat lain.",
                       {"current": ms.detection_out(d, containment).model_dump(mode="json")})
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    d.revision += 1
    d.updated_at = utcnow()
    db.commit()
    response.headers.update(svc.etag(d.revision))
    return ms.detection_out(d, containment)
