"""Logika bersama: serialisasi ORM → skema, hitungan, duplikat, revisi."""
from __future__ import annotations

import json
import re
from collections import defaultdict

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .errors import ApiError, not_found

API_PREFIX = "/api/v1"
_IF_MATCH = re.compile(r'^\s*(?:W/)?"?(\d{1,9})"?\s*$')


# ---------------------------------------------------------------- revisions
def parse_if_match(request: Request, required: bool) -> int | None:
    raw = request.headers.get("If-Match")
    if raw is None:
        if required:
            raise ApiError(428, "PRECONDITION_REQUIRED",
                           'Header If-Match wajib berisi revision saat ini, contoh: If-Match: "3".')
        return None
    mt = _IF_MATCH.match(raw)
    if not mt:
        raise ApiError(400, "BAD_REQUEST", 'If-Match harus berupa revision integer, contoh: "3".')
    return int(mt.group(1))


def etag(revision: int) -> dict[str, str]:
    return {"ETag": f'"{revision}"'}


def bump_photo_revision(db: Session, photo_id: str) -> None:
    db.execute(update(m.Photo).where(m.Photo.id == photo_id).values(revision=m.Photo.revision + 1))


# ---------------------------------------------------------------- lookups
def get_survey(db: Session, survey_id: str) -> m.Survey:
    obj = db.get(m.Survey, survey_id)
    if obj is None:
        raise not_found("survey", survey_id)
    return obj


def get_photo(db: Session, photo_id: str) -> m.Photo:
    obj = db.get(m.Photo, photo_id)
    if obj is None:
        raise not_found("photo", photo_id)
    return obj


def get_annotation(db: Session, annotation_id: str) -> m.Annotation:
    obj = db.get(m.Annotation, annotation_id)
    if obj is None:
        raise not_found("annotation", annotation_id)
    return obj


# ---------------------------------------------------------------- counts
def empty_counts() -> dict[str, int]:
    return dict(plant_accepted=0, plant_pending=0, check_accepted=0, gap_accepted=0, pending_review=0, rejected=0, total=0)


def counts_for(db: Session, photo_ids: list[str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {pid: empty_counts() for pid in photo_ids}
    if not photo_ids:
        return out
    rows = db.execute(
        select(m.Annotation.photo_id, m.Annotation.kind, m.Annotation.review_status, func.count())
        .where(m.Annotation.photo_id.in_(photo_ids))
        .group_by(m.Annotation.photo_id, m.Annotation.kind, m.Annotation.review_status)
    ).all()
    for pid, kind, status, n in rows:
        c = out[pid]
        c["total"] += n
        if status == "pending":
            c["pending_review"] += n
            if kind == "plant":
                c["plant_pending"] += n
        elif status == "rejected":
            c["rejected"] += n
        elif status == "accepted":
            if kind == "plant":
                c["plant_accepted"] += n
            elif kind == "check":
                c["check_accepted"] += n
            elif kind == "gap":
                c["gap_accepted"] += n
    return out


def duplicates_for(db: Session, survey_id: str) -> dict[str, list[str]]:
    rows = db.execute(select(m.Photo.id, m.Photo.sha256).where(m.Photo.survey_id == survey_id)
                      .order_by(m.Photo.created_at)).all()
    by_sha: dict[str, list[str]] = defaultdict(list)
    for pid, sha in rows:
        by_sha[sha].append(pid)
    return {pid: [o for o in ids if o != pid] for ids in by_sha.values() for pid in ids}


def photo_counts_for_surveys(db: Session, survey_ids: list[str]) -> dict[str, int]:
    if not survey_ids:
        return {}
    rows = db.execute(select(m.Photo.survey_id, func.count()).where(m.Photo.survey_id.in_(survey_ids))
                      .group_by(m.Photo.survey_id)).all()
    return {sid: n for sid, n in rows}


# ---------------------------------------------------------------- serializers
def survey_out(obj: m.Survey, photo_count: int) -> s.Survey:
    return s.Survey(
        id=obj.id, name=obj.name, crop_type=obj.crop_type, location_label=obj.location_label,
        survey_date=obj.survey_date, notes=obj.notes, is_demo=obj.is_demo, revision=obj.revision,
        photo_count=photo_count, created_at=obj.created_at, updated_at=obj.updated_at,
    )


def survey_out_single(db: Session, obj: m.Survey) -> s.Survey:
    return survey_out(obj, photo_counts_for_surveys(db, [obj.id]).get(obj.id, 0))


def photo_out(obj: m.Photo, counts: dict[str, int], duplicates: list[str]) -> s.Photo:
    base = f"{API_PREFIX}/photos/{obj.id}"
    return s.Photo(
        id=obj.id, survey_id=obj.survey_id, original_name=obj.original_name, width=obj.width, height=obj.height,
        mime_type=obj.mime_type, size_bytes=obj.size_bytes, sha256=obj.sha256, exif_orientation=obj.exif_orientation,
        has_exif_gps=obj.has_exif_gps, captured_at=obj.captured_at, georef_status=obj.georef_status,
        revision=obj.revision, created_at=obj.created_at,
        content_url=f"{base}/content", display_url=f"{base}/display", thumbnail_url=f"{base}/thumbnail",
        duplicate_photo_ids=duplicates, counts=s.AnnotationCounts(**counts),
    )


def photo_out_single(db: Session, obj: m.Photo) -> s.Photo:
    return photo_out(obj, counts_for(db, [obj.id])[obj.id], duplicates_for(db, obj.survey_id).get(obj.id, []))


def annotation_out(obj: m.Annotation) -> s.Annotation:
    return s.Annotation(
        id=obj.id, photo_id=obj.photo_id, analysis_run_id=obj.analysis_run_id, kind=obj.kind,
        geometry_type=obj.geometry_type, x=obj.x, y=obj.y, bbox=obj.bbox, source=obj.source,
        review_status=obj.review_status, confidence=obj.confidence, model_label=obj.model_label, note=obj.note,
        revision=obj.revision, created_at=obj.created_at, updated_at=obj.updated_at,
    )


def run_out(obj: m.AnalysisRun) -> s.AnalysisRun:
    try:
        params = json.loads(obj.parameters_json or "{}")
    except ValueError:
        params = {}
    return s.AnalysisRun(
        id=obj.id, photo_id=obj.photo_id, run_type=obj.run_type, model_id=obj.model_id,
        model_version=obj.model_version, input_sha256=obj.input_sha256, status=obj.status,
        candidate_count=obj.candidate_count, parameters=params, started_at=obj.started_at,
        finished_at=obj.finished_at, error_code=obj.error_code,
        target=params.get("target") if params.get("target") in ("plant", "tree_crown") else None,
    )


def bbox_center(b: list[float]) -> tuple[float, float]:
    return min(1.0, b[0] + b[2] / 2), min(1.0, b[1] + b[3] / 2)
