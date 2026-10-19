"""Foto contoh berlisensi dari `<repo>/samples/catalog.json` — katalog yang SAMA dengan `GET /api/v1/samples`.

Setiap berkas diverifikasi sha256-nya terhadap katalog sebelum dipakai notebook. Anotasi manusia (VOC) hanya
untuk evaluasi; tidak pernah dikirim ke API sebagai hasil inferensi.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .backend import REPO_ROOT


def samples_dir() -> Path:
    raw = os.getenv("WALLACEA_SAMPLES_DIR", "").strip()
    return Path(raw).resolve() if raw else REPO_ROOT / "samples"


@dataclass(frozen=True)
class Sample:
    id: str
    title: str
    path: Path
    sha256: str
    annotations: Path | None
    annotation_labels: dict[str, int]
    source_name: str
    source_url: str
    license_name: str
    license_url: str
    attribution: str
    imagery: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_samples(directory: str | Path | None = None, verify: bool = True) -> list[Sample]:
    d = Path(directory) if directory else samples_dir()
    data = json.loads((d / "catalog.json").read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    out = []
    for raw in data["samples"]:
        e = {**defaults, **raw}
        path = (d / e["file"]).resolve()
        if verify and _sha256(path) != e["sha256"]:
            raise ValueError(f"sha256 {path.name} tidak cocok dengan katalog — berkas berubah atau rusak.")
        ann = e.get("annotations") or {}
        ann_path = (d / ann["file"]).resolve() if ann.get("file") else None
        if verify and ann_path is not None and ann.get("sha256") and _sha256(ann_path) != ann["sha256"]:
            raise ValueError(f"sha256 anotasi {ann_path.name} tidak cocok dengan katalog.")
        out.append(Sample(e["id"], e["title"], path, e["sha256"], ann_path, dict(ann.get("labels") or {}),
                          e["source_name"], e["source_url"], e["license_name"], e["license_url"],
                          e["attribution"], e["imagery"]))
    return out
