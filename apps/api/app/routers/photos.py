from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..deps import PageParams, get_db, get_storage
from ..errors import ApiError
from ..imaging import inspect_image
from ..photo_store import store_photo_files
from ..storage import Storage
from . import errors

router = APIRouter(tags=["photos"])

IMMUTABLE = {"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}


def clean_filename(raw: str | None) -> str:
    name = re.split(r"[\\/]", raw or "")[-1]
    name = "".join(ch for ch in unicodedata.normalize("NFC", name) if unicodedata.category(ch)[0] != "C").strip()
    return name[:255] or "foto"


async def read_limited(file: UploadFile, limit: int) -> bytes:
    chunks, total = [], 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ApiError(413, "PAYLOAD_TOO_LARGE", f"Foto melebihi {limit // (1024 * 1024)} MB.",
                           {"max_upload_bytes": limit})
        chunks.append(chunk)
    await file.close()
    return b"".join(chunks)


@router.post(
    "/surveys/{survey_id}/photos", response_model=s.PhotoUploadResult, status_code=201,
    responses=errors(400, 404, 409, 413, 415),
    summary="Unggah SATU foto asli (multipart field `file`). Satu request per berkas agar progres per berkas.",
    description="Isi berkas divalidasi (JPEG/PNG/WebP sungguhan), bukan ekstensi atau content-type klien. "
                "Duplikat (sha256 sama dalam survei) tetap disimpan dan diberi warning DUPLICATE_IN_SURVEY.",
)
async def upload_photo(survey_id: str, request: Request, file: UploadFile = File(...)):
    settings = request.app.state.settings
    storage: Storage = request.app.state.storage

    def precheck():
        with request.app.state.sessionmaker() as db:
            survey = svc.get_survey(db, survey_id)
            if survey.is_demo:
                raise ApiError(409, "DEMO_SURVEY_READONLY",
                               "Survei contoh tidak menerima foto asli. Buat survei nyata dahulu.")

    await run_in_threadpool(precheck)
    data = await read_limited(file, settings.max_upload_bytes)
    name = clean_filename(file.filename)

    def process():
        info = inspect_image(data, settings.max_pixels)
        with request.app.state.sessionmaker() as db:
            survey = svc.get_survey(db, survey_id)
            dup_ids = db.scalars(select(m.Photo.id).where(m.Photo.survey_id == survey.id, m.Photo.sha256 == info.sha256)
                                 .order_by(m.Photo.created_at)).all()
            written: list[str] = []
            try:
                photo = store_photo_files(db, storage, survey.id, name, info, settings.thumbnail_max_side, written)
                db.commit()
            except Exception:
                db.rollback()
                storage.delete(*written)
                raise
            warnings = []
            if dup_ids:
                warnings.append(s.Warning(code="DUPLICATE_IN_SURVEY",
                                          message="Foto identik (sha256 sama) sudah ada di survei ini. Tetap disimpan; "
                                                  "hapus bila tidak diperlukan agar tidak terhitung ganda.",
                                          details={"photo_ids": list(dup_ids)}))
            return s.PhotoUploadResult(photo=svc.photo_out_single(db, photo), warnings=warnings)

    return await run_in_threadpool(process)


@router.get("/surveys/{survey_id}/photos", response_model=s.PhotoPage, responses=errors(404),
            summary="Daftar foto survei (urutan unggah)")
def list_photos(survey_id: str, page: PageParams = Depends(), db: Session = Depends(get_db)):
    svc.get_survey(db, survey_id)
    total = db.scalar(select(func.count()).select_from(m.Photo).where(m.Photo.survey_id == survey_id))
    rows = db.scalars(select(m.Photo).where(m.Photo.survey_id == survey_id)
                      .order_by(m.Photo.created_at, m.Photo.id).limit(page.limit).offset(page.offset)).all()
    counts = svc.counts_for(db, [r.id for r in rows])
    dups = svc.duplicates_for(db, survey_id)
    return s.PhotoPage(items=[svc.photo_out(r, counts[r.id], dups.get(r.id, [])) for r in rows],
                       total=total, limit=page.limit, offset=page.offset)


@router.get("/photos/{photo_id}", response_model=s.Photo, responses=errors(404))
def get_photo(photo_id: str, response: Response, db: Session = Depends(get_db)):
    obj = svc.get_photo(db, photo_id)
    response.headers.update(svc.etag(obj.revision))
    return svc.photo_out_single(db, obj)


def _file(storage: Storage, key: str, media_type: str, filename: str | None = None) -> FileResponse:
    path = storage.path(key)
    if not path.is_file():
        raise ApiError(404, "NOT_FOUND", "Berkas foto tidak ditemukan di penyimpanan server.", {"entity": "photo_file"})
    return FileResponse(path, media_type=media_type, headers=IMMUTABLE, filename=filename,
                        content_disposition_type="inline")


_FILE_RESPONSES = {200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}},
                         "description": "Byte gambar"}, **errors(404)}


@router.get("/photos/{photo_id}/content", response_class=FileResponse, responses=_FILE_RESPONSES,
            summary="Berkas asli apa adanya (EXIF utuh). Untuk editor gunakan /display.")
def photo_content(photo_id: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)):
    p = svc.get_photo(db, photo_id)
    return _file(storage, p.storage_key, p.mime_type, p.original_name)


@router.get("/photos/{photo_id}/display", response_class=FileResponse, responses=_FILE_RESPONSES,
            summary="Gambar terorientasi EXIF; dimensi = Photo.width × Photo.height. Dasar koordinat penanda.")
def photo_display(photo_id: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)):
    p = svc.get_photo(db, photo_id)
    return _file(storage, p.display_key or p.storage_key, p.mime_type)


@router.get("/photos/{photo_id}/thumbnail", response_class=FileResponse,
            responses={200: {"content": {"image/jpeg": {}}, "description": "JPEG"}, **errors(404)},
            summary="Thumbnail JPEG terorientasi, sisi terpanjang ≤ 512 px")
def photo_thumbnail(photo_id: str, db: Session = Depends(get_db), storage: Storage = Depends(get_storage)):
    p = svc.get_photo(db, photo_id)
    return _file(storage, p.thumbnail_key, "image/jpeg")


@router.delete("/photos/{photo_id}", status_code=204, responses=errors(400, 404, 409),
               summary="Hapus foto, penanda, analysis run, dan berkasnya. If-Match (revision foto) opsional.")
def delete_photo(photo_id: str, request: Request, db: Session = Depends(get_db),
                 storage: Storage = Depends(get_storage)):
    expected = svc.parse_if_match(request, required=False)
    p = svc.get_photo(db, photo_id)
    if expected is not None and expected != p.revision:
        raise ApiError(409, "REVISION_CONFLICT", "Foto sudah berubah di tempat lain.", {"current_revision": p.revision})
    keys = (p.storage_key, p.display_key, p.thumbnail_key)
    db.delete(p)
    db.commit()
    storage.delete(*keys)
    return Response(status_code=204)
