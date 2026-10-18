from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..config import Settings
from ..db import utcnow
from ..deps import get_db, get_settings
from ..errors import ApiError
from . import errors

router = APIRouter(tags=["annotations"])


def ensure_capacity(db: Session, photo_id: str, adding: int, limit: int, removing: int = 0) -> None:
    current = db.scalar(select(func.count()).select_from(m.Annotation).where(m.Annotation.photo_id == photo_id))
    if current - removing + adding > limit:
        raise ApiError(422, "ANNOTATION_LIMIT_EXCEEDED", f"Maksimal {limit} penanda per foto.",
                       {"current": current, "adding": adding, "limit": limit})


@router.get("/photos/{photo_id}/annotations", response_model=s.AnnotationPage, responses=errors(404),
            summary="Semua penanda satu foto (default sampai 3000 = batas per foto)")
def list_annotations(photo_id: str, limit: int = Query(3000, ge=1, le=3000), offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db)):
    photo = svc.get_photo(db, photo_id)
    total = db.scalar(select(func.count()).select_from(m.Annotation).where(m.Annotation.photo_id == photo_id))
    rows = db.scalars(select(m.Annotation).where(m.Annotation.photo_id == photo_id)
                      .order_by(m.Annotation.created_at, m.Annotation.id).limit(limit).offset(offset)).all()
    return s.AnnotationPage(items=[svc.annotation_out(a) for a in rows], total=total, limit=limit, offset=offset,
                            photo_revision=photo.revision)


@router.post("/photos/{photo_id}/annotations", response_model=s.Annotation, status_code=201,
             responses=errors(404, 422),
             summary="Tambah penanda MANUAL. Kandidat model hanya lewat /analyze atau /detections/import.")
def create_annotation(photo_id: str, body: s.AnnotationCreate, response: Response, db: Session = Depends(get_db),
                      settings: Settings = Depends(get_settings)):
    svc.get_photo(db, photo_id)
    ensure_capacity(db, photo_id, 1, settings.max_annotations_per_photo)
    if body.geometry_type == "bbox":
        x, y = svc.bbox_center(body.bbox)
        bbox = body.bbox
    else:
        x, y, bbox = body.x, body.y, [None] * 4
    now = utcnow()
    obj = m.Annotation(photo_id=photo_id, kind=body.kind, geometry_type=body.geometry_type, x=x, y=y,
                       bbox_left=bbox[0], bbox_top=bbox[1], bbox_width=bbox[2], bbox_height=bbox[3],
                       source="manual", review_status=body.review_status, note=body.note,
                       created_at=now, updated_at=now)
    db.add(obj)
    svc.bump_photo_revision(db, photo_id)
    db.commit()
    response.headers.update(svc.etag(obj.revision))
    return svc.annotation_out(obj)


def _conflict(db: Session, annotation_id: str) -> ApiError:
    db.rollback()
    current = svc.get_annotation(db, annotation_id)
    return ApiError(409, "REVISION_CONFLICT",
                    "Penanda sudah diubah di tempat lain. Perubahan Anda tidak disimpan; tinjau versi terbaru.",
                    {"current": svc.annotation_out(current).model_dump(mode="json")},
                    headers=svc.etag(current.revision))


@router.patch("/annotations/{annotation_id}", response_model=s.Annotation,
              responses=errors(400, 404, 409, 422, 428),
              summary="Ubah kind/catatan/status review/geometri. Wajib If-Match: \"<revision>\".",
              description="source tidak bisa diubah. Untuk kandidat model, menerima/menolak = ubah review_status. "
                          "409 REVISION_CONFLICT mengembalikan details.current (versi server).")
def update_annotation(annotation_id: str, body: s.AnnotationUpdate, request: Request, response: Response,
                      db: Session = Depends(get_db)):
    expected = svc.parse_if_match(request, required=True)
    obj = svc.get_annotation(db, annotation_id)
    if obj.revision != expected:
        raise _conflict(db, annotation_id)

    fields = body.model_fields_set
    values: dict = {k: getattr(body, k) for k in ("kind", "note", "review_status") if k in fields}
    target = body.geometry_type or obj.geometry_type
    if target == "point":
        if "bbox" in fields and body.bbox is not None:
            raise ApiError(422, "VALIDATION_ERROR", "Penanda point tidak memiliki bbox.", {"field": "bbox"})
        if "x" in fields:
            values.update(x=body.x, y=body.y)
        elif obj.geometry_type == "bbox":  # bbox → point tanpa x/y: pakai pusat kotak
            values.update(x=obj.x, y=obj.y)
        if obj.geometry_type == "bbox" or body.geometry_type == "point":
            values.update(geometry_type="point", bbox_left=None, bbox_top=None, bbox_width=None, bbox_height=None)
    else:
        if "x" in fields:
            raise ApiError(422, "VALIDATION_ERROR", "Untuk bbox, kirim bbox; x/y dihitung server.", {"field": "x"})
        if "bbox" in fields and body.bbox is not None:
            cx, cy = svc.bbox_center(body.bbox)
            values.update(geometry_type="bbox", x=cx, y=cy, bbox_left=body.bbox[0], bbox_top=body.bbox[1],
                          bbox_width=body.bbox[2], bbox_height=body.bbox[3])
        elif obj.geometry_type != "bbox":
            raise ApiError(422, "VALIDATION_ERROR", "Mengubah ke bbox membutuhkan field bbox.", {"field": "bbox"})

    values.update(revision=m.Annotation.revision + 1, updated_at=utcnow())
    res = db.execute(update(m.Annotation).where(m.Annotation.id == annotation_id, m.Annotation.revision == expected)
                     .values(**values))
    if res.rowcount != 1:
        raise _conflict(db, annotation_id)
    svc.bump_photo_revision(db, obj.photo_id)
    db.commit()
    db.refresh(obj)
    response.headers.update(svc.etag(obj.revision))
    return svc.annotation_out(obj)


@router.delete("/annotations/{annotation_id}", status_code=204, responses=errors(400, 404, 409, 428),
               summary="Hapus penanda. Wajib If-Match. Untuk kandidat model, lebih baik review_status=rejected.")
def delete_annotation(annotation_id: str, request: Request, db: Session = Depends(get_db)):
    expected = svc.parse_if_match(request, required=True)
    obj = svc.get_annotation(db, annotation_id)
    photo_id = obj.photo_id
    res = db.execute(delete(m.Annotation).where(m.Annotation.id == annotation_id, m.Annotation.revision == expected))
    if res.rowcount != 1:
        raise _conflict(db, annotation_id)
    svc.bump_photo_revision(db, photo_id)
    db.commit()
    return Response(status_code=204)
