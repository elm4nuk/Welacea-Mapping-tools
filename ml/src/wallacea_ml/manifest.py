"""Manifest dataset. Satu baris per gambar (atau tile). Lihat ml/configs/manifest.example.json."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

LABELS = ("plant", "check", "gap")
_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ImageEntry:
    image: str                  # path relatif terhadap root dataset
    sha256: str                 # sha256 berkas (deteksi duplikat lintas split)
    field_id: str               # lahan
    flight_id: str              # penerbangan
    width: int
    height: int
    labels: str | None = None   # path label YOLO relatif (None = belum dilabeli)
    plot_id: str | None = None  # petak (untuk galat hitungan per petak)
    parent_image: str | None = None  # bila ini tile/potongan: gambar induk
    sequence: int | None = None      # urutan dalam penerbangan
    official_split: str | None = None  # split resmi penerbit dataset (train|val|test); dipakai group_by=official
    source: str | None = None        # asal (berkas anotasi + nama berkas asli) untuk penelusuran


@dataclass
class Manifest:
    crop_type: str
    label_map: dict[str, int]
    images: list[ImageEntry]
    notes: str = ""
    errors: list[str] = field(default_factory=list)
    domain: str = ""            # "public:<id dataset>" atau "k919" — hasil evaluasi dilaporkan terpisah per domain

    @property
    def labeled(self) -> list[ImageEntry]:
        return [i for i in self.images if i.labels]


def load_manifest(path: str | Path) -> Manifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    errors: list[str] = []
    crop = str(data.get("crop_type") or "").strip()
    if not crop:
        errors.append("crop_type wajib (model pertama dibatasi SATU jenis tanaman).")
    label_map = data.get("label_map") or {}
    if not isinstance(label_map, dict) or not label_map or any(k not in LABELS for k in label_map):
        errors.append(f"label_map wajib, kunci hanya {LABELS}, nilai = indeks kelas YOLO.")
        label_map = {}
    images: list[ImageEntry] = []
    seen: set[str] = set()
    for n, raw in enumerate(data.get("images") or []):
        try:
            e = ImageEntry(**raw)
        except TypeError as exc:
            errors.append(f"images[{n}]: {exc}")
            continue
        if not _SHA.match(e.sha256):
            errors.append(f"images[{n}]: sha256 tidak valid")
        if not e.field_id or not e.flight_id:
            errors.append(f"images[{n}]: field_id dan flight_id wajib (dasar split)")
        if e.width <= 0 or e.height <= 0:
            errors.append(f"images[{n}]: dimensi tidak valid")
        if e.image in seen:
            errors.append(f"images[{n}]: image duplikat {e.image}")
        if e.official_split is not None and e.official_split not in ("train", "val", "test"):
            errors.append(f"images[{n}]: official_split harus train|val|test")
        seen.add(e.image)
        images.append(e)
    if not images:
        errors.append("Manifest tidak memiliki gambar.")
    return Manifest(crop_type=crop, label_map=label_map, images=images, notes=str(data.get("notes") or ""),
                    errors=errors, domain=str(data.get("domain") or ""))
