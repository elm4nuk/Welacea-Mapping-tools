"""Validasi isi gambar (bukan ekstensi/content-type klien), orientasi EXIF, turunan display & thumbnail."""
from __future__ import annotations

import hashlib
import io
import re
import warnings
from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from .errors import ApiError

FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "MPO": ("image/jpeg", ".jpg"),
           "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}
ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp"]

TAG_ORIENTATION = 0x0112
TAG_EXIF_IFD = 0x8769
TAG_GPS_IFD = 0x8825
TAG_DATETIME_ORIGINAL = 0x9003
_EXIF_DT = re.compile(r"^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$")


@dataclass
class InspectedImage:
    data: bytes
    mime_type: str
    ext: str
    width: int              # setelah orientasi
    height: int
    exif_orientation: int
    has_exif_gps: bool
    captured_at: str | None
    sha256: str
    oriented: Image.Image   # RGB, sudah diorientasikan

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def _invalid(message: str = "Gambar rusak atau formatnya tidak didukung. Gunakan JPG, PNG, atau WebP.") -> ApiError:
    return ApiError(400, "INVALID_IMAGE", message)


def _captured_at(exif) -> str | None:
    try:
        raw = exif.get_ifd(TAG_EXIF_IFD).get(TAG_DATETIME_ORIGINAL)
    except Exception:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("ascii", "ignore")
    m = _EXIF_DT.match(str(raw or "").strip().strip("\x00"))
    if not m:
        return None
    try:
        return datetime(*map(int, m.groups())).isoformat()
    except ValueError:
        return None


def inspect_image(data: bytes, max_pixels: int) -> InspectedImage:
    if not data:
        raise _invalid("Berkas kosong.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            src = Image.open(io.BytesIO(data))
            if src.format not in FORMATS:
                raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", "Format tidak didukung. Gunakan JPG, PNG, atau WebP.",
                               {"detected_format": src.format})
            if src.width < 1 or src.height < 1:
                raise _invalid()
            if src.width * src.height > max_pixels:
                raise ApiError(413, "IMAGE_TOO_LARGE", f"Resolusi melebihi batas {max_pixels:,} piksel.",
                               {"width": src.width, "height": src.height, "max_pixels": max_pixels})
            if src.format in ("PNG", "WEBP") and getattr(src, "is_animated", False):
                raise _invalid("Gambar animasi tidak didukung.")
            exif = src.getexif()
            orientation = int(exif.get(TAG_ORIENTATION, 1) or 1)
            if orientation not in range(1, 9):
                orientation = 1
            has_gps = bool(exif.get(TAG_GPS_IFD))
            captured = _captured_at(exif)
            src.load()  # dekode penuh: deteksi berkas terpotong
            oriented = ImageOps.exif_transpose(src)
            if oriented.mode != "RGB":
                oriented = oriented.convert("RGB")
            mime, ext = FORMATS[src.format]
    except ApiError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise _invalid()
    return InspectedImage(
        data=data, mime_type=mime, ext=ext, width=oriented.width, height=oriented.height,
        exif_orientation=orientation, has_exif_gps=has_gps, captured_at=captured,
        sha256=hashlib.sha256(data).hexdigest(), oriented=oriented,
    )


def oriented_from_bytes(data: bytes) -> Image.Image:
    """Gambar yang sama persis dengan yang dipakai untuk dimensi/anotasi (untuk inferensi)."""
    with Image.open(io.BytesIO(data)) as src:
        src.load()
        return ImageOps.exif_transpose(src).convert("RGB")


def encode_display(info: InspectedImage) -> bytes | None:
    """Turunan terorientasi hanya bila orientasi EXIF ≠ 1; selain itu berkas asli dipakai langsung."""
    if info.exif_orientation == 1:
        return None
    buf = io.BytesIO()
    if info.mime_type == "image/png":
        info.oriented.save(buf, format="PNG")
    elif info.mime_type == "image/webp":
        info.oriented.save(buf, format="WEBP", quality=95)
    else:
        info.oriented.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def encode_thumbnail(image: Image.Image, max_side: int) -> bytes:
    thumb = image.copy()
    thumb.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


# ---------------------------------------------------------------- ilustrasi contoh
DEMO_W, DEMO_H = 1200, 800


def demo_illustration() -> tuple[bytes, list[tuple[float, float]], list[tuple[float, float]], tuple[float, float]]:
    """PNG ilustrasi berlabel jelas + posisi tanaman/titik kosong/periksa (normalized).

    Ini gambar buatan untuk mencoba penandaan. Bukan foto drone, bukan hasil AI.
    """
    img = Image.new("RGB", (DEMO_W, DEMO_H), (196, 178, 140))
    d = ImageDraw.Draw(img)
    plants, gaps = [], []
    cols, rows = 8, 4
    for r in range(rows):
        for c in range(cols):
            cx = 140 + c * 130 + (r % 2) * 35
            cy = 150 + r * 150
            if (r, c) in ((1, 4), (2, 1)):
                gaps.append((cx / DEMO_W, cy / DEMO_H))
                d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=(150, 120, 80), width=3)
                continue
            rad = 34 + ((r * 7 + c * 3) % 4) * 4
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(52, 110, 60))
            d.ellipse([cx - rad // 2, cy - rad // 2, cx + rad // 3, cy + rad // 3], fill=(92, 150, 80))
            plants.append((cx / DEMO_W, cy / DEMO_H))
    d.rectangle([0, DEMO_H - 64, DEMO_W, DEMO_H], fill=(24, 59, 50))
    try:
        font = ImageFont.load_default(size=26)
    except TypeError:
        font = ImageFont.load_default()
    d.text((24, DEMO_H - 48), "ILUSTRASI CONTOH — BUKAN FOTO DRONE, BUKAN HASIL AI", fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    check = (0.82, 0.64)
    return buf.getvalue(), plants, gaps, check
