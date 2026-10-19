"""Katalog foto contoh berlisensi (revisi 3, CR-FE-002). Read-only; sumber: <repo>/samples/catalog.json.

Foto ini tidak masuk survei secara otomatis: frontend mengambil berkasnya lalu mengunggah lewat
`POST /surveys/{id}/photos` biasa (validasi sama), dan hasil ML hanya muncul setelah `/analyze` sungguhan.
"""
from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from PIL import Image

from .. import schemas as s
from ..config import Settings
from ..deps import get_settings
from ..errors import ApiError
from . import errors

router = APIRouter(tags=["samples"])
log = logging.getLogger("wallacea")
MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


@lru_cache(maxsize=4)
def _load(samples_dir: Path, mtime_ns: int) -> tuple[tuple[s.SamplePhoto, Path], ...]:
    data = json.loads((samples_dir / "catalog.json").read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    out = []
    for raw in data.get("samples", []):
        e = {**defaults, **raw}
        path = (samples_dir / e["file"]).resolve()
        if samples_dir not in path.parents or path.suffix.lower() not in MEDIA or not path.is_file():
            log.warning("Sampel %s dilewati: berkas tidak ada/tidak aman", e.get("id"))
            continue
        blob = path.read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != e["sha256"]:
            log.warning("Sampel %s dilewati: sha256 tidak cocok dengan katalog", e["id"])
            continue
        with Image.open(path) as im:
            w, h = im.size
        out.append((s.SamplePhoto(
            id=e["id"], title=e["title"], file_url=f"/api/v1/samples/{e['id']}/file", filename=path.name,
            media_type=MEDIA[path.suffix.lower()], size_bytes=len(blob), sha256=digest, width=w, height=h,
            source_name=e["source_name"], source_url=e["source_url"], license_name=e["license_name"],
            license_url=e["license_url"], attribution=e["attribution"], imagery=e["imagery"],
            has_human_annotations=bool(e.get("annotations")),
        ), path))
    return tuple(out)


def catalog(settings: Settings) -> tuple[tuple[s.SamplePhoto, Path], ...]:
    d = settings.samples_dir
    f = d / "catalog.json"
    if not f.is_file():
        return ()
    return _load(d, f.stat().st_mtime_ns)


@router.get("/samples", response_model=s.SamplePage,
            summary="Katalog foto contoh berlisensi (sumber & lisensi) untuk demo unggah",
            description="Read-only. Berkas diambil lewat `file_url` lalu diunggah dengan endpoint upload biasa. "
                        "Bukan foto K919 dan bukan hasil inferensi. Katalog kosong bila folder samples tidak ada.")
def list_samples(settings: Settings = Depends(get_settings)):
    items = [p for p, _ in catalog(settings)]
    return s.SamplePage(items=items, total=len(items))


@router.get("/samples/{sample_id}/file", response_class=FileResponse, responses={
    200: {"content": {"image/png": {}, "image/jpeg": {}, "image/webp": {}}, "description": "Byte foto contoh"},
    **errors(404)}, summary="Unduh berkas foto contoh (byte asli, sha256 = katalog)")
def sample_file(sample_id: str, settings: Settings = Depends(get_settings)):
    for photo, path in catalog(settings):
        if photo.id == sample_id:
            return FileResponse(path, media_type=photo.media_type, filename=photo.filename,
                                headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"})
    raise ApiError(404, "NOT_FOUND", "Foto contoh tidak ditemukan.")
