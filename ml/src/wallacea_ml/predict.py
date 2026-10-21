"""Buat `predictions.json` (format evaluate.py) untuk satu split memakai ADAPTER API yang sama dengan `/analyze`.

Jalur gambar = `app.imaging.oriented_from_bytes` (sama dengan API), detektor = `UltralyticsDetector`
(pemetaan label, clamp, normalisasi [l,t,w,h] sama dengan API). Yang dievaluasi = yang akan dilihat pengguna.
Confidence prediksi sengaja rendah (default 0.01) agar threshold bisa dipilih di split validation.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import backend
from .inspection import read_yolo_labels
from .manifest import Manifest
from .split import SPLITS


def read_split(split_dir: str | Path, split: str) -> list[str]:
    p = Path(split_dir) / "splits" / f"{split}.txt"
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def predict_split(manifest: Manifest, root: str | Path, split_dir: str | Path, split: str, weights: str | Path,
                  label_map: dict[str, str], imgsz: int, conf: float = 0.01, max_det: int = 3000) -> dict:
    if split not in SPLITS:
        raise ValueError(f"split harus {SPLITS}")
    root = Path(root)
    names = {i: lab for lab, i in manifest.label_map.items()}
    by_image = {e.image: e for e in manifest.images}
    det = backend.build_api_detector(weights, label_map, confidence=conf, imgsz=imgsz, max_det=max_det)
    info = det.info()
    if not info.available:
        raise RuntimeError(f"Detektor tidak siap: {info.message}")
    images, model_version, params, seconds = [], None, {}, []
    for rel in read_split(split_dir, split):
        e = by_image[rel]
        gt = []
        if e.labels:
            boxes, problems = read_yolo_labels(root / e.labels, len(names))
            if problems:
                raise ValueError(f"Label tidak valid untuk {rel}: {problems[:3]}")
            gt = [{"label": names[c], "bbox": bb} for c, bb in boxes]
        img = backend.load_oriented(root / rel)
        t0 = time.perf_counter()
        out = det.detect(img)
        seconds.append(time.perf_counter() - t0)
        model_version, params = out.model_version, out.parameters
        images.append({"image": rel, "plot_id": e.plot_id, "width": img.width, "height": img.height, "gt": gt,
                       "pred": [{"label": d.label, "confidence": d.confidence, "bbox": d.bbox,
                                 "model_label": d.model_label} for d in out.detections]})
    return {"model_id": Path(weights).stem, "model_version": model_version, "split": split,
            "domain": manifest.domain or None, "iou_threshold": 0.5, "adapter_parameters": params,
            "inference_seconds": {"mean": sum(seconds) / len(seconds) if seconds else None,
                                  "max": max(seconds) if seconds else None},
            "images": images}
