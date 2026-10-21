"""Pascal VOC XML (format anotasi NeonTreeEvaluation / sampel DeepForest) → bbox WALLACEA [l, t, w, h] 0–1.

Koordinat VOC = piksel `xmin ymin xmax ymax` terhadap `<size><width><height>` berkas. Dimensi XML dicek
terhadap gambar terorientasi (sama seperti COCO di `prepare`); label dipetakan EKSPLISIT lewat `label_map`.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .coco import TARGET_LABELS


@dataclass
class VocAnnotation:
    filename: str
    width: int
    height: int
    boxes: list[tuple[str, list[float]]]   # (label WALLACEA, [l, t, w, h] 0–1)
    raw_labels: dict[str, int]
    skipped: int = 0


def load_voc(path: str | Path, label_map: dict[str, str]) -> VocAnnotation:
    bad = {v for v in label_map.values() if v not in TARGET_LABELS + ("drop",)}
    if bad:
        raise ValueError(f"label_map tujuan tidak valid: {bad}")
    root = ET.parse(path).getroot()  # noqa: S314 — berkas lokal dari sumber tercatat
    W = int(root.findtext("size/width"))
    H = int(root.findtext("size/height"))
    boxes, raw, skipped = [], {}, 0
    for obj in root.iter("object"):
        name = (obj.findtext("name") or "").strip()
        raw[name] = raw.get(name, 0) + 1
        if name not in label_map:
            raise ValueError(f"Label VOC {name!r} tidak dipetakan di label_map {label_map}")
        if label_map[name] == "drop":
            continue
        bb = obj.find("bndbox")
        x1, y1, x2, y2 = (float(bb.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        l, t = max(0.0, x1) / W, max(0.0, y1) / H
        r, b = min(float(W), x2) / W, min(float(H), y2) / H
        if r <= l or b <= t:
            skipped += 1
            continue
        boxes.append((label_map[name], [l, t, r - l, b - t]))
    return VocAnnotation(root.findtext("filename") or Path(path).stem, W, H, boxes, raw, skipped)
