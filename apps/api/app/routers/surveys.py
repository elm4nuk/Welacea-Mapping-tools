from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..db import utcnow
from ..deps import PageParams, get_db, get_settings, get_storage
from ..errors import ApiError
from ..photo_store import create_demo
from ..storage import Storage
from . import errors

router = APIRouter(tags=["surveys"])


@router.get("/surveys", response_model=s.SurveyPage, summary="Daftar survei (terbaru dulu)")
def list_surveys(page: PageParams = Depends(), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(m.Survey))
    rows = db.scalars(select(m.Survey).order_by(m.Survey.created_at.desc(), m.Survey.id)
                      .limit(page.limit).offset(page.offset)).all()
    counts = svc.photo_counts_for_surveys(db, [r.id for r in rows])
    return s.SurveyPage(items=[svc.survey_out(r, counts.get(r.id, 0)) for r in rows], total=total,
                        limit=page.limit, offset=page.offset)


@router.post("/surveys", response_model=s.Survey, status_code=201, responses=errors(422),
             summary="Buat survei nyata (is_demo selalu false)")
def create_survey(body: s.SurveyCreate, response: Response, db: Session = Depends(get_db)):
    now = utcnow()
    obj = m.Survey(**body.model_dump(), is_demo=False, created_at=now, updated_at=now)
    db.add(obj)
    db.commit()
    response.headers.update(svc.etag(obj.revision))
    return svc.survey_out(obj, 0)


@router.get("/surveys/{survey_id}", response_model=s.Survey, responses=errors(404))
def get_survey(survey_id: str, response: Response, db: Session = Depends(get_db)):
    obj = svc.get_survey(db, survey_id)
    response.headers.update(svc.etag(obj.revision))
    return svc.survey_out_single(db, obj)


@router.patch("/surveys/{survey_id}", response_model=s.Survey, responses=errors(400, 404, 409, 422),
              summary="Ubah metadata survei. If-Match opsional; bila dikirim harus = revision.")
def update_survey(survey_id: str, body: s.SurveyUpdate, request: Request, response: Response,
                  db: Session = Depends(get_db)):
    expected = svc.parse_if_match(request, required=False)
    obj = svc.get_survey(db, survey_id)
    if expected is not None and expected != obj.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Survei sudah diubah di tempat lain. Muat ulang lalu ulangi.",
                       {"current": svc.survey_out_single(db, obj).model_dump(mode="json")})
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.revision += 1
    obj.updated_at = utcnow()
    db.commit()
    response.headers.update(svc.etag(obj.revision))
    return svc.survey_out_single(db, obj)


@router.delete("/surveys/{survey_id}", status_code=204, responses=errors(400, 404, 409),
               summary="Hapus survei beserta foto, penanda, dan berkasnya")
def delete_survey(survey_id: str, request: Request, db: Session = Depends(get_db),
                  storage: Storage = Depends(get_storage)):
    expected = svc.parse_if_match(request, required=False)
    obj = svc.get_survey(db, survey_id)
    if expected is not None and expected != obj.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Survei sudah diubah di tempat lain.", {"current_revision": obj.revision})
    keys = [k for p in obj.photos for k in (p.storage_key, p.display_key, p.thumbnail_key)]
    db.delete(obj)
    db.commit()
    storage.delete(*keys)
    return Response(status_code=204)


@router.post("/demo/surveys", response_model=s.Survey, status_code=201,
             summary="Buat survei CONTOH berisi gambar ilustrasi (bukan foto drone, bukan hasil AI)")
def create_demo_survey(db: Session = Depends(get_db), storage: Storage = Depends(get_storage),
                       settings=Depends(get_settings)):
    written: list[str] = []
    try:
        survey = create_demo(db, storage, settings.max_pixels, settings.thumbnail_max_side, written=written)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(*written)
        raise
    return svc.survey_out_single(db, survey)
