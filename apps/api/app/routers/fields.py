"""Lahan & batasnya (revisi 5). Koordinat WGS84 [lon, lat]; luas/keliling selalu dihitung backend (geodesik)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import mapping_services as ms
from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..db import utcnow
from ..deps import PageParams, get_db, get_settings
from ..errors import ApiError
from . import errors

router = APIRouter(tags=["fields"])
GEOJSON = "application/geo+json"
_GEOJSON_RESPONSE = {200: {"content": {GEOJSON: {}}, "description": "GeoJSON (RFC 7946), WGS84 [lon, lat]"}}


def _conflict(db: Session, obj: m.Field, expected: int | None):
    if expected is not None and expected != obj.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Lahan sudah diubah di tempat lain. Muat ulang lalu ulangi.",
                       {"current": ms.field_out(db, obj).model_dump(mode="json")})


@router.get("/fields", response_model=s.FieldPage, summary="Daftar lahan (terbaru dulu)")
def list_fields(page: PageParams = Depends(), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(m.Field))
    rows = db.scalars(select(m.Field).order_by(m.Field.created_at.desc(), m.Field.id)
                      .limit(page.limit).offset(page.offset)).all()
    return s.FieldPage(items=[ms.field_out(db, f) for f in rows], total=total, limit=page.limit, offset=page.offset)


@router.post("/fields", response_model=s.FarmField, status_code=201, responses=errors(413, 422, 503),
             summary="Buat lahan dari GeoJSON Polygon/MultiPolygon WGS84. Luas & keliling dihitung server.")
def create_field(body: s.FieldCreate, response: Response, db: Session = Depends(get_db),
                 settings=Depends(get_settings)):
    ms.require_boundaries()
    now = utcnow()
    obj = m.Field(name=body.name, notes=body.notes, boundary_source=body.boundary_source, source_note=body.source_note,
                  created_at=now, updated_at=now)
    ms.apply_geometry(obj, body.geometry, settings.max_field_vertices)
    db.add(obj)
    db.commit()
    response.headers.update(svc.etag(obj.revision))
    return ms.field_out(db, obj)


@router.get("/fields/{field_id}", response_model=s.FarmField, responses=errors(404))
def get_field(field_id: str, response: Response, db: Session = Depends(get_db)):
    obj = ms.get_field(db, field_id)
    response.headers.update(svc.etag(obj.revision))
    return ms.field_out(db, obj)


@router.patch("/fields/{field_id}", response_model=s.FarmField, responses=errors(400, 404, 409, 422, 503),
              summary="Ubah lahan. If-Match opsional; bila dikirim harus = revision. Geometri baru diukur ulang.")
def update_field(field_id: str, body: s.FieldUpdate, request: Request, response: Response,
                 db: Session = Depends(get_db), settings=Depends(get_settings)):
    expected = svc.parse_if_match(request, required=False)
    obj = ms.get_field(db, field_id)
    _conflict(db, obj, expected)
    changes = body.model_dump(exclude_unset=True)
    if "geometry" in changes:
        ms.require_boundaries()
        ms.apply_geometry(obj, changes.pop("geometry"), settings.max_field_vertices)
    for k, v in changes.items():
        setattr(obj, k, v)
    obj.revision += 1
    obj.updated_at = utcnow()
    db.commit()
    response.headers.update(svc.etag(obj.revision))
    return ms.field_out(db, obj)


@router.delete("/fields/{field_id}", status_code=204, responses=errors(400, 404, 409),
               summary="Hapus lahan. Survei yang tertaut tetap ada (field_id menjadi null).")
def delete_field(field_id: str, request: Request, db: Session = Depends(get_db)):
    expected = svc.parse_if_match(request, required=False)
    obj = ms.get_field(db, field_id)
    if expected is not None and expected != obj.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Lahan sudah diubah di tempat lain.", {"current_revision": obj.revision})
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


@router.get("/fields/{field_id}/geojson", response_class=JSONResponse, responses={**_GEOJSON_RESPONSE, **errors(404)},
            summary="Ekspor satu lahan sebagai GeoJSON Feature (geometri persis seperti tersimpan)")
def export_field(field_id: str, db: Session = Depends(get_db)):
    obj = ms.get_field(db, field_id)
    return JSONResponse(ms.field_feature(db, obj), media_type=GEOJSON,
                        headers={"Content-Disposition": f'attachment; filename="lahan-{obj.id}.geojson"'})


@router.get("/fields-export.geojson", response_class=JSONResponse, responses=_GEOJSON_RESPONSE,
            summary="Ekspor semua lahan sebagai GeoJSON FeatureCollection")
def export_fields(db: Session = Depends(get_db)):
    rows = db.scalars(select(m.Field).order_by(m.Field.created_at, m.Field.id)).all()
    return JSONResponse({"type": "FeatureCollection", "features": [ms.field_feature(db, f) for f in rows]},
                        media_type=GEOJSON, headers={"Content-Disposition": 'attachment; filename="lahan.geojson"'})


@router.post("/fields/import", response_model=s.FieldImportResult, status_code=201,
             responses=errors(400, 413, 422, 503),
             summary="Impor lahan dari berkas GeoJSON (FeatureCollection/Feature/Polygon/MultiPolygon). Semua-atau-tidak.",
             description="Setiap Feature menjadi satu lahan. Nama dari properties.name (atau `name_prefix` + nomor). "
                         "Bila satu geometri tidak valid, tidak ada yang disimpan dan error menyebut feature-nya. "
                         "CRS harus WGS84 lon/lat: GeoJSON dengan member `crs` non-WGS84 ditolak.")
async def import_fields(request: Request, file: UploadFile = File(...), name_prefix: str = Form("Lahan impor"),
                        boundary_source: s.BoundarySource = Form("geojson_import")):
    from ..geo.boundary import GeometryError, features_from_geojson

    settings = request.app.state.settings
    ms.require_boundaries()
    raw, total = [], 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > settings.max_field_import_bytes:
            raise ApiError(413, "PAYLOAD_TOO_LARGE", "Berkas GeoJSON terlalu besar.",
                           {"max_bytes": settings.max_field_import_bytes})
        raw.append(chunk)
    try:
        obj = json.loads(b"".join(raw).decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ApiError(400, "BAD_REQUEST", "Berkas bukan JSON UTF-8 yang valid.") from exc
    crs = obj.get("crs") if isinstance(obj, dict) else None
    if crs is not None:
        name = json.dumps(crs)
        if not any(k in name for k in ("CRS84", "EPSG::4326", "EPSG:4326")):
            raise ApiError(422, "INVALID_GEOMETRY", "GeoJSON memakai CRS selain WGS84 lon/lat. Ekspor ulang dalam "
                                                    "EPSG:4326 (RFC 7946); API tidak memproyeksi ulang.",
                           {"crs": crs})
    try:
        feats = features_from_geojson(obj)
    except GeometryError as exc:
        raise ApiError(422, "INVALID_GEOMETRY", str(exc), exc.details) from exc
    filename = (file.filename or "geojson")[:200]

    def save():
        with request.app.state.sessionmaker() as db:
            now = utcnow()
            created = []
            for i, (geom, props) in enumerate(feats, start=1):
                name = str(props.get("name") or props.get("nama") or f"{name_prefix} {i}")[:100].strip() or f"Lahan {i}"
                f = m.Field(name=name, notes=str(props.get("notes") or "")[:2000], boundary_source=boundary_source,
                            source_note=f"Impor {filename}, feature {i}", created_at=now, updated_at=now)
                try:
                    ms.apply_geometry(f, geom, settings.max_field_vertices)
                except ApiError as exc:
                    exc.message = f"Feature {i} ({name}): {exc.message}"
                    exc.details = {**exc.details, "feature_index": i - 1}
                    raise
                db.add(f)
                created.append(f)
            db.commit()
            return s.FieldImportResult(fields=[ms.field_out(db, f) for f in created])

    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(save)
