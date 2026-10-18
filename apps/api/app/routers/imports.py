"""Impor backup starter v0.1 (IndexedDB → JSON, schemaVersion 1) sebagai SALINAN.

Data yang sudah ada tidak pernah ditimpa. Seluruh impor atomik: gagal satu, batal semua (berkas dibersihkan).
Pemetaan: status confirmed→accepted, pending→pending; source ai→model, manual→manual; box→bbox.
Foto contoh (SVG ilustrasi) diganti PNG placeholder berlabel karena API hanya menerima JPEG/PNG/WebP.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import math
import re
from datetime import date

from fastapi import APIRouter, File, Request, UploadFile
from PIL import Image, ImageDraw, ImageFont
from starlette.concurrency import run_in_threadpool

from .. import models as m
from .. import schemas as s
from .. import services as svc
from ..db import utcnow
from ..errors import ApiError
from ..imaging import inspect_image
from ..photo_store import store_photo_files
from .photos import read_limited
from . import errors

router = APIRouter(tags=["imports"])

_DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,(.*)$", re.S)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KINDS = ("plant", "check", "gap")


def _bad(message: str, **loc) -> ApiError:
    return ApiError(400, "INVALID_BACKUP", message, loc)


def demo_placeholder(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), (214, 206, 178))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=max(14, width // 45))
    except TypeError:
        font = ImageFont.load_default()
    d.rectangle([0, height - height // 10, width, height], fill=(24, 59, 50))
    d.text((width // 40, height - height // 13), "ILUSTRASI CONTOH (gambar SVG starter tidak diimpor) — bukan foto drone",
           fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _finite01(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1


def _survey_date(raw) -> date:
    if isinstance(raw, str) and _DATE.match(raw):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()


@router.post("/imports/starter-backup", response_model=s.StarterBackupImportResult, status_code=201,
             responses=errors(400, 413, 415),
             summary="Impor backup JSON starter v0.1 (schemaVersion 1) sebagai salinan survei baru")
async def import_starter_backup(request: Request, file: UploadFile = File(...)):
    st = request.app.state
    settings = st.settings
    raw = await read_limited(file, settings.max_backup_bytes)

    def process():
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            raise _bad("Berkas bukan JSON yang valid.")
        if not isinstance(data, dict) or data.get("schemaVersion") != 1 or not isinstance(data.get("surveys"), list):
            raise _bad("Format backup WALLACEA tidak sesuai (butuh schemaVersion 1).")
        if len(data["surveys"]) > 100:
            raise _bad("Maksimal 100 survei per backup.")
        warnings: list[s.Warning] = []
        written: list[str] = []
        created_surveys: list[m.Survey] = []
        n_photos = n_ann = 0
        demo_warned = False
        with st.sessionmaker() as db:
            try:
                for si, src in enumerate(data["surveys"]):
                    if not isinstance(src, dict) or not isinstance(src.get("photos", []), list):
                        raise _bad("Data survei tidak valid.", survey_index=si)
                    is_demo = src.get("isDemo") is True
                    now = utcnow()
                    survey = m.Survey(
                        name=(str(src.get("name") or "Survei").strip()[:90] or "Survei") + " (salinan)",
                        crop_type=str(src.get("crop") or "").strip()[:80] or "Tidak diisi",
                        location_label=str(src.get("location") or "").strip()[:150],
                        survey_date=_survey_date(src.get("date")),
                        notes=str(src.get("notes") or "")[:2000], is_demo=is_demo, created_at=now, updated_at=now)
                    db.add(survey)
                    db.flush()
                    created_surveys.append(survey)
                    for pi, p in enumerate(src.get("photos", [])):
                        loc = dict(survey_index=si, photo_index=pi)
                        if not isinstance(p, dict) or not isinstance(p.get("annotations"), list):
                            raise _bad("Data foto tidak valid.", **loc)
                        if len(p["annotations"]) > settings.max_annotations_per_photo:
                            raise _bad(f"Maksimal {settings.max_annotations_per_photo} penanda per foto.", **loc)
                        if is_demo:
                            w, h = p.get("width"), p.get("height")
                            ok = all(isinstance(v, int) and 1 <= v <= 8000 for v in (w, h))
                            info = inspect_image(demo_placeholder(w if ok else 1200, h if ok else 800), settings.max_pixels)
                            if not demo_warned:
                                warnings.append(s.Warning(code="DEMO_IMAGE_REPLACED",
                                                          message="Gambar ilustrasi SVG pada survei contoh diganti placeholder PNG berlabel.",
                                                          details={"survey_index": si}))
                                demo_warned = True
                        else:
                            mt = _DATA_URL.match(p.get("dataUrl") or "") if isinstance(p.get("dataUrl"), str) else None
                            if not mt:
                                raise _bad("Format gambar backup tidak didukung (butuh data URL JPEG/PNG/WebP).", **loc)
                            try:
                                blob = base64.b64decode(mt.group(2), validate=True)
                            except (binascii.Error, ValueError):
                                raise _bad("Data gambar base64 rusak.", **loc)
                            if len(blob) > settings.max_upload_bytes:
                                raise ApiError(413, "PAYLOAD_TOO_LARGE", "Foto dalam backup melebihi batas ukuran.", loc)
                            try:
                                info = inspect_image(blob, settings.max_pixels)
                            except ApiError as exc:
                                exc.details.update(loc)
                                raise
                        name = str(p.get("name") or "foto").replace("\\", "/").split("/")[-1][:255] or "foto"
                        photo = store_photo_files(db, st.storage, survey.id, name, info, settings.thumbnail_max_side, written)
                        n_photos += 1
                        run = None
                        for ai, a in enumerate(p["annotations"]):
                            if not isinstance(a, dict) or a.get("kind") not in KINDS or not _finite01(a.get("x")) or not _finite01(a.get("y")):
                                raise _bad("Koordinat atau jenis penanda tidak valid.", **loc, annotation_index=ai)
                            source = "model" if a.get("source") == "ai" else "manual"
                            bbox = None
                            if a.get("box") is not None:
                                try:
                                    bbox = s.check_bbox(list(a["box"])) if isinstance(a["box"], list) else None
                                except (ValueError, TypeError):
                                    bbox = None
                                if bbox is None:
                                    warnings.append(s.Warning(code="BBOX_DROPPED", message="bbox tidak valid; disimpan sebagai titik.",
                                                              details={**loc, "annotation_index": ai}))
                            if source == "model" and run is None:
                                run = m.AnalysisRun(photo_id=photo.id, run_type="import", model_id="starter-v01-backup",
                                                    model_version=None, input_sha256=photo.sha256, status="succeeded",
                                                    started_at=now, finished_at=now,
                                                    parameters_json=json.dumps({"source": "starter_backup_schema_v1"}))
                                db.add(run)
                                db.flush()
                            x, y = svc.bbox_center(bbox) if bbox else (float(a["x"]), float(a["y"]))
                            conf = a.get("confidence")
                            db.add(m.Annotation(
                                photo_id=photo.id, analysis_run_id=run.id if source == "model" else None,
                                kind=a["kind"], geometry_type="bbox" if bbox else "point", x=x, y=y,
                                bbox_left=bbox[0] if bbox else None, bbox_top=bbox[1] if bbox else None,
                                bbox_width=bbox[2] if bbox else None, bbox_height=bbox[3] if bbox else None,
                                source=source, review_status="pending" if a.get("status") == "pending" else "accepted",
                                confidence=float(conf) if _finite01(conf) else None,
                                note=str(a.get("note") or "")[:1000], created_at=now, updated_at=now))
                            n_ann += 1
                        if run is not None:
                            run.candidate_count = sum(1 for a in p["annotations"] if a.get("source") == "ai")
                db.commit()
            except Exception:
                db.rollback()
                st.storage.delete(*written)
                raise
            counts = svc.photo_counts_for_surveys(db, [x.id for x in created_surveys])
            return s.StarterBackupImportResult(
                surveys=[svc.survey_out(x, counts.get(x.id, 0)) for x in created_surveys],
                photo_count=n_photos, annotation_count=n_ann, warnings=warnings)

    return await run_in_threadpool(process)
