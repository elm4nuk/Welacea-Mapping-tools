"""Menulis berkas foto + baris Photo, dan pembuatan survei contoh. Dipakai upload, demo, impor backup."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from . import models as m
from .db import utcnow
from .imaging import DEMO_H, DEMO_W, InspectedImage, demo_illustration, encode_display, encode_thumbnail, inspect_image
from .storage import Storage


def create_demo(db: Session, storage: Storage, max_pixels: int, thumb_side: int, *, name: str = "Parsel demonstrasi",
                written: list[str] | None = None) -> m.Survey:
    png, plants, gaps, check = demo_illustration()
    info = inspect_image(png, max_pixels)
    assert (info.width, info.height) == (DEMO_W, DEMO_H)
    now = utcnow()
    survey = m.Survey(name=name, crop_type="Tanaman perkebunan", location_label="Lokasi ilustrasi",
                      survey_date=date.today(), is_demo=True, created_at=now, updated_at=now,
                      notes="Data contoh untuk mencoba penandaan. Tidak mewakili hasil penerbangan atau analisis AI.")
    db.add(survey)
    db.flush()
    photo = store_photo_files(db, storage, survey.id, "parsel-contoh-ilustrasi.png", info, thumb_side, written)
    marks = [(x, y, "plant", f"Penanda contoh {i + 1}") for i, (x, y) in enumerate(plants)]
    marks += [(x, y, "gap", "Contoh: titik tanpa kanopi pada ilustrasi.") for x, y in gaps]
    marks.append((check[0], check[1], "check", "Contoh lokasi untuk pemeriksaan petugas."))
    for x, y, kind, note in marks:
        db.add(m.Annotation(photo_id=photo.id, kind=kind, geometry_type="point", x=x, y=y, source="manual",
                            review_status="accepted", note=note, created_at=now, updated_at=now))
    return survey


def store_photo_files(db: Session, storage: Storage, survey_id: str, original_name: str, info: InspectedImage, thumb_side: int,
                      written: list[str] | None = None, display_bytes: bytes | None = None) -> m.Photo:
    """Tulis berkas asli/turunan lalu tambah baris Photo (belum commit). `written` mencatat key untuk cleanup."""
    base = storage.new_base()
    original_key = f"{base}{info.ext}"
    thumb_key = f"{base}_thumb.jpg"
    display = display_bytes if display_bytes is not None else encode_display(info)
    display_key = f"{base}_display{info.ext}" if display is not None else None
    track = written if written is not None else []
    storage.write(original_key, info.data)
    track.append(original_key)
    if display is not None:
        storage.write(display_key, display)
        track.append(display_key)
    storage.write(thumb_key, encode_thumbnail(info.oriented, thumb_side))
    track.append(thumb_key)
    photo = m.Photo(
        survey_id=survey_id, original_name=original_name[:255], width=info.width, height=info.height,
        mime_type=info.mime_type, size_bytes=info.size_bytes, sha256=info.sha256,
        exif_orientation=info.exif_orientation, has_exif_gps=info.has_exif_gps, captured_at=info.captured_at,
        georef_status="none", storage_key=original_key, display_key=display_key, thumbnail_key=thumb_key,
        created_at=utcnow(),
    )
    db.add(photo)
    db.flush()
    return photo
