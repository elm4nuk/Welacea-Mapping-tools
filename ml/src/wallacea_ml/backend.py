"""Jembatan ke kode backend (apps/api) agar preprocessing & inferensi TIDAK digandakan.

- Orientasi gambar: `app.imaging.oriented_from_bytes` (EXIF transpose + RGB) — fungsi yang sama dengan
  yang dipakai API untuk dimensi foto, `display`, dan input detektor.
- Inferensi evaluasi: `app.inference.UltralyticsDetector` — adapter yang sama dengan `/analyze`, termasuk
  pemetaan label, clamp & normalisasi bbox `[left, top, width, height]`.

Lokasi apps/api: env `WALLACEA_API_DIR`, default `<repo>/apps/api`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]


def api_dir() -> Path:
    raw = os.getenv("WALLACEA_API_DIR", "").strip()
    return Path(raw).resolve() if raw else REPO_ROOT / "apps" / "api"


def _ensure_api_importable() -> None:
    d = api_dir()
    if not (d / "app" / "imaging.py").is_file():
        raise RuntimeError(f"Kode API tidak ditemukan di {d}. Atur WALLACEA_API_DIR.")
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))


def load_oriented(path: str | Path) -> Image.Image:
    """Gambar RGB terorientasi EXIF, identik dengan yang dilihat editor (`display_url`) dan detektor API."""
    _ensure_api_importable()
    from app.imaging import oriented_from_bytes

    return oriented_from_bytes(Path(path).read_bytes())


def exif_orientation(path: str | Path) -> int:
    with Image.open(path) as im:
        o = int(im.getexif().get(0x0112, 1) or 1)
    return o if 1 <= o <= 8 else 1


def raw_size(path: str | Path) -> tuple[int, int]:
    """Dimensi piksel tersimpan (SEBELUM orientasi EXIF)."""
    with Image.open(path) as im:
        return im.size


def build_api_deepforest(model_dir: str | Path, confidence: float = 0.35, device: str = "cpu",
                         patch_size: int = 400, patch_overlap: float = 0.05, label_map: dict[str, str] | None = None):
    """Adapter DeepForest yang SAMA dengan API (`WALLACEA_DETECTOR=deepforest`): folder bobot lokal, tanpa
    unduhan, input RGB terorientasi, pemetaan label {'Tree': 'plant'} eksplisit."""
    _ensure_api_importable()
    from app.inference.deepforest_adapter import DeepForestDetector

    return DeepForestDetector(Path(model_dir), label_map=label_map, confidence=confidence, device=device,
                              patch_size=patch_size, patch_overlap=patch_overlap)


def default_deepforest_dir() -> Path:
    raw = os.getenv("WALLACEA_DEEPFOREST_DIR", "").strip()
    return Path(raw) if raw else api_dir() / "var" / "models" / "deepforest-tree"


def build_api_detector(weights: str | Path, label_map: dict[str, str], confidence: float = 0.35,
                       imgsz: int = 1280, max_det: int = 3000):
    """Detektor yang sama dengan API. Return objek dengan `.detect(Image) -> DetectionOutput`."""
    _ensure_api_importable()
    from app.inference.ultralytics_adapter import UltralyticsDetector

    return UltralyticsDetector(Path(weights), label_map, confidence=confidence, imgsz=imgsz, max_det=max_det)
