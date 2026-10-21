from __future__ import annotations

import csv
import io
import re

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from .. import services as svc
from .. import mapping_services as ms
from ..inference.simulation import MODEL_ID as SIMULATION_MODEL_ID
from ..db import utcnow
from ..deps import get_db
from . import errors

router = APIRouter(tags=["reports"])

DISCLAIMERS = [
    "Hitungan tanaman = penanda kind=plant berstatus accepted per foto. Kandidat model pending/rejected tidak dihitung.",
    "Hitungan antar foto yang bertumpang tindih tidak boleh dijumlahkan sebagai jumlah tanaman unik lahan.",
    "Posisi penanda foto adalah koordinat relatif dalam gambar (0–1), bukan lintang/bujur GPS. EXIF GPS foto = posisi "
    "kamera, bukan posisi tanaman.",
    "Foto biasa bukan orthomosaic; luas lahan tidak dihitung dari foto.",
    "Titik kosong dan titik periksa memerlukan pemeriksaan lapangan; ini bukan diagnosis penyakit.",
    "Confidence adalah keluaran model, bukan akurasi survei.",
]
DEMO_DISCLAIMER = "DATA CONTOH: gambar ilustrasi dan penanda contoh, bukan foto drone dan bukan hasil AI."
SIMULATION_DISCLAIMER = ("SIMULASI — BUKAN AI: survei ini memuat kandidat dari detector simulasi development "
                         f"(model_id {SIMULATION_MODEL_ID}). Kandidat itu tidak berasal dari model; hitungan yang "
                         "memakainya tidak boleh dipakai untuk keputusan lapangan.")


def _has_simulation(db: Session, photo_ids: list[str]) -> bool:
    if not photo_ids:
        return False
    return db.scalar(select(m.Annotation.id).join(m.AnalysisRun, m.Annotation.analysis_run_id == m.AnalysisRun.id)
                     .where(m.Annotation.photo_id.in_(photo_ids), m.AnalysisRun.model_id == SIMULATION_MODEL_ID)
                     .limit(1)) is not None


SOURCE_LABELS = {"manual_drawing": "digambar manual", "geojson_import": "impor GeoJSON",
                 "gnss_survey": "pengukuran GNSS/GPS lapangan", "digitized_from_raster": "digitasi di atas raster impor",
                 "other": "sumber lain"}


def build_mapping(db: Session, survey: m.Survey) -> s.SurveyMapping | None:
    field = db.get(m.Field, survey.field_id) if survey.field_id else None
    rasters = db.scalars(select(m.RasterAsset).where(m.RasterAsset.survey_id == survey.id)
                         .order_by(m.RasterAsset.created_at, m.RasterAsset.id)).all()
    if field is None and not rasters:
        return None
    containment = ms.FieldContainment(field) if field is not None else ms.FieldContainment(None)
    return s.SurveyMapping(
        field=s.FieldSummary(id=field.id, name=field.name, boundary_source=field.boundary_source,
                             measures=ms.measures_out(field)) if field else None,
        rasters=[s.RasterReportRow(raster_id=r.id, name=r.name, product_type=r.product_type,
                                   approx_gsd_m=r.approx_gsd_m, footprint_area_m2=r.footprint_area_m2,
                                   counts=ms.raster_counts(db, r, containment)) for r in rasters])


def mapping_disclaimers(mapping: s.SurveyMapping | None) -> list[str]:
    if mapping is None:
        return []
    out = []
    if mapping.field is not None:
        f = mapping.field
        out.append(f"Luas lahan {f.measures.area_ha:,.4f} ha dihitung geodesik (WGS84) dari batas "
                   f"{SOURCE_LABELS[f.boundary_source]}; akurasinya mengikuti sumber batas, bukan hasil ukur bersertifikat.")
    if mapping.rasters:
        out.append("Peta udara = GeoTIFF bergeoreferensi yang DIIMPOR pengguna. Georeferensi diambil apa adanya dari "
                   "berkas dan tidak diverifikasi WALLACEA; bukan orthomosaic yang dibuat aplikasi.")
        out.append("Hitungan kandidat peta berlaku per raster. Jangan menjumlahkan raster/penerbangan berbeda sebagai "
                   "tanaman unik lahan.")
    return out


def _raster_simulation(db: Session, survey_id: str) -> bool:
    return db.scalar(select(m.MapDetection.id).join(m.RasterAnalysisRun,
                                                    m.MapDetection.analysis_run_id == m.RasterAnalysisRun.id)
                     .join(m.RasterAsset, m.MapDetection.raster_id == m.RasterAsset.id)
                     .where(m.RasterAsset.survey_id == survey_id, m.RasterAnalysisRun.target == "simulation")
                     .limit(1)) is not None


def build_report(db: Session, survey_id: str) -> s.SurveyReport:
    survey = svc.get_survey(db, survey_id)
    photos = db.scalars(select(m.Photo).where(m.Photo.survey_id == survey_id).order_by(m.Photo.created_at, m.Photo.id)).all()
    counts = svc.counts_for(db, [p.id for p in photos])
    dups = svc.duplicates_for(db, survey_id)
    names = {p.id: p.original_name for p in photos}
    findings = db.scalars(select(m.Annotation).where(
        m.Annotation.photo_id.in_(list(names)), m.Annotation.kind.in_(("check", "gap")),
        m.Annotation.review_status != "rejected",
    ).order_by(m.Annotation.photo_id, m.Annotation.created_at)).all() if names else []
    rows = [s.PhotoReportRow(photo_id=p.id, original_name=p.original_name, width=p.width, height=p.height,
                             captured_at=p.captured_at, duplicate_photo_ids=dups.get(p.id, []),
                             counts=s.AnnotationCounts(**counts[p.id])) for p in photos]
    mapping = build_mapping(db, survey)
    totals = s.ReportTotals(
        photo_count=len(photos),
        plant_accepted_sum_across_photos=sum(c["plant_accepted"] for c in counts.values()),
        pending_review=sum(c["pending_review"] for c in counts.values()),
        check_accepted=sum(c["check_accepted"] for c in counts.values()),
        gap_accepted=sum(c["gap_accepted"] for c in counts.values()),
    )
    return s.SurveyReport(
        survey=svc.survey_out(survey, len(photos)), generated_at=utcnow(), photos=rows, totals=totals,
        findings=[s.Finding(annotation_id=a.id, photo_id=a.photo_id, photo_name=names[a.photo_id], kind=a.kind,
                            review_status=a.review_status, source=a.source, x=a.x, y=a.y, note=a.note) for a in findings],
        disclaimers=([DEMO_DISCLAIMER] if survey.is_demo else [])
        + ([SIMULATION_DISCLAIMER] if _has_simulation(db, list(names)) or _raster_simulation(db, survey_id) else [])
        + DISCLAIMERS + mapping_disclaimers(mapping),
        mapping=mapping,
    )


@router.get("/surveys/{survey_id}/report", response_model=s.SurveyReport, responses=errors(404),
            summary="Laporan: hitungan per foto, temuan periksa/titik kosong, dan disclaimer")
def survey_report(survey_id: str, db: Session = Depends(get_db)):
    return build_report(db, survey_id)


_FORMULA = ("=", "+", "-", "@", "\t", "\r", "\n")


def csv_cell(value) -> str:
    """Cegah formula injection: teks yang diawali = + - @ tab/CR diberi prefiks apostrof."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "ya" if value else "tidak"
    if isinstance(value, (int, float)):
        return repr(round(value, 6)) if isinstance(value, float) else str(value)
    text = str(value)
    return "'" + text if text.startswith(_FORMULA) else text


def _iso(ts) -> str:
    return ts.isoformat().replace("+00:00", "Z")


CSV_COLUMNS = [
    "survey_id", "survey_name", "survey_date", "crop_type", "location_label", "is_demo",
    "photo_id", "photo_name", "photo_sha256", "photo_width", "photo_height",
    "annotation_id", "kind", "geometry_type", "x", "y", "bbox_left", "bbox_top", "bbox_width", "bbox_height",
    "source", "review_status", "counted_as_plant", "confidence", "model_id", "model_version", "analysis_run_id",
    "note", "created_at", "updated_at",
]


@router.get("/surveys/{survey_id}/export.csv", responses={
    200: {"content": {"text/csv": {}}, "description": "CSV UTF-8 (dengan BOM), satu baris per penanda"}, **errors(404)},
    response_class=Response, summary="Ekspor semua penanda survei sebagai CSV")
def export_csv(survey_id: str, db: Session = Depends(get_db)):
    survey = svc.get_survey(db, survey_id)
    rows = db.execute(
        select(m.Photo, m.Annotation, m.AnalysisRun)
        .join(m.Annotation, m.Annotation.photo_id == m.Photo.id)
        .outerjoin(m.AnalysisRun, m.AnalysisRun.id == m.Annotation.analysis_run_id)
        .where(m.Photo.survey_id == survey_id)
        .order_by(m.Photo.created_at, m.Photo.id, m.Annotation.created_at, m.Annotation.id)
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(CSV_COLUMNS)
    for p, a, run in rows:
        bbox = a.bbox or [None] * 4
        w.writerow([csv_cell(v) for v in (
            survey.id, survey.name, survey.survey_date.isoformat(), survey.crop_type, survey.location_label,
            survey.is_demo, p.id, p.original_name, p.sha256, p.width, p.height,
            a.id, a.kind, a.geometry_type, a.x, a.y, *bbox, a.source, a.review_status,
            a.kind == "plant" and a.review_status == "accepted", a.confidence,
            run.model_id if run else None, run.model_version if run else None, a.analysis_run_id,
            a.note, _iso(a.created_at), _iso(a.updated_at),
        )])
    slug = re.sub(r"[^a-z0-9]+", "-", survey.name.lower()).strip("-")[:40] or "survei"
    filename = f"wallacea-{slug}-{survey.survey_date.isoformat()}.csv"
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "X-Content-Type-Options": "nosniff"})
