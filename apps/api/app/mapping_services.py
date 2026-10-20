"""Logika bersama mapping (revisi 5): serialisasi lahan/raster/deteksi, hitungan per raster, uji di-dalam-lahan."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import geo
from . import models as m
from . import schemas as s
from .errors import ApiError, not_found
from .geo import raster as georaster

API_PREFIX = "/api/v1"


def require_boundaries():
    if not geo.boundaries_available():
        raise ApiError(503, "MAPPING_UNAVAILABLE", "Paket geospasial (shapely, pyproj) belum terpasang di venv API: "
                                                   "pip install -r requirements.lock.txt")


def require_rasters():
    if not geo.rasters_available():
        raise ApiError(503, "MAPPING_UNAVAILABLE", "Paket raster (rasterio, pyproj, shapely, numpy) belum terpasang "
                                                   "di venv API: pip install -r requirements.lock.txt")


# ---------------------------------------------------------------- lookups
def get_field(db: Session, field_id: str) -> m.Field:
    obj = db.get(m.Field, field_id)
    if obj is None:
        raise not_found("field", field_id)
    return obj


def get_raster(db: Session, raster_id: str) -> m.RasterAsset:
    obj = db.get(m.RasterAsset, raster_id)
    if obj is None:
        raise not_found("raster", raster_id)
    return obj


def get_detection(db: Session, detection_id: str) -> m.MapDetection:
    obj = db.get(m.MapDetection, detection_id)
    if obj is None:
        raise not_found("map_detection", detection_id)
    return obj


def check_field_ref(db: Session, field_id: str | None) -> None:
    if field_id is not None and db.get(m.Field, field_id) is None:
        raise ApiError(422, "VALIDATION_ERROR", "field_id tidak ditemukan.",
                       {"issues": [{"loc": ["body", "field_id"], "msg": "Lahan tidak ditemukan", "type": "not_found"}]})


# ---------------------------------------------------------------- fields
def measures_out(f: m.Field) -> s.FieldMeasures:
    return s.FieldMeasures(area_m2=f.area_m2, area_ha=f.area_m2 / 10_000, perimeter_m=f.perimeter_m,
                           exterior_perimeter_m=f.exterior_perimeter_m)


def field_out(db: Session, f: m.Field) -> s.FarmField:
    survey_ids = list(db.scalars(select(m.Survey.id).where(m.Survey.field_id == f.id).order_by(m.Survey.created_at)))
    return s.FarmField(
        id=f.id, name=f.name, notes=f.notes, boundary_source=f.boundary_source, source_note=f.source_note,
        geometry=json.loads(f.geometry_json), measures=measures_out(f),
        bbox=[f.min_lon, f.min_lat, f.max_lon, f.max_lat], label_point=[f.label_lon, f.label_lat],
        vertex_count=f.vertex_count, polygon_count=f.polygon_count, hole_count=f.hole_count, survey_ids=survey_ids,
        revision=f.revision, created_at=f.created_at, updated_at=f.updated_at,
    )


def field_feature(db: Session, f: m.Field) -> dict[str, Any]:
    out = field_out(db, f)
    return {"type": "Feature", "id": f.id, "geometry": json.loads(f.geometry_json),
            "properties": {"name": f.name, "notes": f.notes, "boundary_source": f.boundary_source,
                           "source_note": f.source_note, "area_m2": out.measures.area_m2,
                           "area_ha": out.measures.area_ha, "perimeter_m": out.measures.perimeter_m,
                           "measure_method": "geodesic_wgs84", "revision": f.revision,
                           "updated_at": f.updated_at.isoformat()}}


def apply_geometry(f: m.Field, geometry: dict[str, Any], max_vertices: int) -> None:
    from .geo.boundary import GeometryError, measure, normalize_geometry

    try:
        clean = normalize_geometry(geometry, max_vertices)
        mm = measure(clean)
    except GeometryError as exc:
        raise ApiError(422, "INVALID_GEOMETRY", str(exc), exc.details) from exc
    f.geometry_type, f.geometry_json = clean["type"], georaster.dumps(clean)
    f.area_m2, f.perimeter_m, f.exterior_perimeter_m = mm.area_m2, mm.perimeter_m, mm.exterior_perimeter_m
    f.min_lon, f.min_lat, f.max_lon, f.max_lat = mm.bbox
    f.label_lon, f.label_lat = mm.label_point
    f.vertex_count, f.hole_count, f.polygon_count = mm.vertex_count, mm.hole_count, mm.polygon_count


# ---------------------------------------------------------------- rasters & detections
class FieldContainment:
    """Uji pusat deteksi di dalam batas lahan survei (planar pada lon/lat — memadai untuk lahan kecil)."""

    def __init__(self, field: m.Field | None):
        self.field = field
        self._geom = None
        if field is not None:
            from shapely.geometry import shape
            from shapely.prepared import prep
            self._geom = prep(shape(json.loads(field.geometry_json)))

    def contains(self, lon: float, lat: float) -> bool | None:
        if self._geom is None:
            return None
        from shapely.geometry import Point
        return bool(self._geom.covers(Point(lon, lat)))


def survey_field(db: Session, survey_id: str) -> m.Field | None:
    survey = db.get(m.Survey, survey_id)
    return db.get(m.Field, survey.field_id) if survey and survey.field_id else None


def raster_counts(db: Session, raster: m.RasterAsset, containment: FieldContainment | None = None
                  ) -> s.RasterDetectionCounts:
    rows = db.execute(select(m.MapDetection.kind, m.MapDetection.review_status, func.count())
                      .where(m.MapDetection.raster_id == raster.id)
                      .group_by(m.MapDetection.kind, m.MapDetection.review_status)).all()
    c = dict(plant_accepted=0, pending_review=0, rejected=0, total=0)
    for kind, status, n in rows:
        c["total"] += n
        if status == "pending":
            c["pending_review"] += n
        elif status == "rejected":
            c["rejected"] += n
        elif kind == "plant":
            c["plant_accepted"] += n
    containment = containment or FieldContainment(survey_field(db, raster.survey_id))
    inside = None
    if containment.field is not None:
        pts = db.execute(select(m.MapDetection.lon, m.MapDetection.lat).where(
            m.MapDetection.raster_id == raster.id, m.MapDetection.kind == "plant",
            m.MapDetection.review_status == "accepted")).all()
        inside = sum(1 for lon, lat in pts if containment.contains(lon, lat))
    return s.RasterDetectionCounts(**c, plant_accepted_inside_field=inside)


def raster_out(db: Session, r: m.RasterAsset) -> s.RasterAsset:
    base = f"{API_PREFIX}/rasters/{r.id}"
    meta = json.loads(r.metadata_json or "{}")
    processing = json.loads(r.processing_json or "{}")
    lat = (r.min_lat + r.max_lat) / 2
    minz, maxz = georaster.zoom_range(r.approx_gsd_m, lat, len(processing.get("display", {}).get("overviews", [])))
    return s.RasterAsset(
        id=r.id, survey_id=r.survey_id, name=r.name, original_name=r.original_name, product_type=r.product_type,
        source_description=r.source_description, size_bytes=r.size_bytes, sha256=r.sha256, width=r.width,
        height=r.height, band_count=r.band_count,
        crs=s.RasterCrs(epsg=r.crs_epsg, name=r.crs_name, wkt=r.crs_wkt, is_geographic=bool(meta.get("crs_is_geographic"))),
        transform=json.loads(r.transform_json), bounds_native=json.loads(r.bounds_native_json),
        bounds_wgs84=[r.min_lon, r.min_lat, r.max_lon, r.max_lat], footprint=json.loads(r.footprint_json),
        footprint_area_m2=r.footprint_area_m2, approx_gsd_m=r.approx_gsd_m, nodata=r.nodata, has_alpha=r.has_alpha,
        metadata=meta, processing=processing, warnings=meta.get("warnings", []),
        content_url=f"{base}/content", preview_url=f"{base}/preview.png", tilejson_url=f"{base}/tilejson.json",
        tile_url_template=f"{base}/tiles/{{z}}/{{x}}/{{y}}.png", minzoom=minz, maxzoom=maxz,
        detection_counts=raster_counts(db, r), revision=r.revision, created_at=r.created_at, updated_at=r.updated_at,
    )


def rrun_out(run: m.RasterAnalysisRun) -> s.RasterAnalysisRun:
    params = json.loads(run.parameters_json or "{}")
    return s.RasterAnalysisRun(
        id=run.id, raster_id=run.raster_id, model_id=run.model_id, model_version=run.model_version,
        adapter=run.adapter, target=run.target if run.target in ("plant", "tree_crown", "simulation") else None,
        input_sha256=run.input_sha256, status=run.status, candidate_count=run.candidate_count, parameters=params,
        started_at=run.started_at, finished_at=run.finished_at, error_code=run.error_code,
    )


def detection_out(d: m.MapDetection, containment: FieldContainment) -> s.MapDetection:
    return s.MapDetection(
        id=d.id, raster_id=d.raster_id, analysis_run_id=d.analysis_run_id, kind=d.kind, source=d.source,
        review_status=d.review_status, confidence=d.confidence, model_label=d.model_label, note=d.note,
        pixel_bbox=[d.px_left, d.px_top, d.px_width, d.px_height], center=[d.lon, d.lat],
        center_native=[d.center_x, d.center_y], geometry=json.loads(d.geometry_json),
        inside_field=containment.contains(d.lon, d.lat), revision=d.revision, created_at=d.created_at,
        updated_at=d.updated_at,
    )


def detection_feature(d: m.MapDetection, containment: FieldContainment) -> dict[str, Any]:
    out = detection_out(d, containment)
    return {"type": "Feature", "id": d.id, "geometry": json.loads(d.geometry_json),
            "properties": {"raster_id": d.raster_id, "analysis_run_id": d.analysis_run_id, "kind": d.kind,
                           "source": d.source, "review_status": d.review_status, "confidence": d.confidence,
                           "model_label": d.model_label, "note": d.note, "pixel_bbox": out.pixel_bbox,
                           "center": out.center, "inside_field": out.inside_field, "revision": d.revision}}
