"""Inferensi model pretrained (DeepForest) pada foto contoh lewat ADAPTER API, dengan waktu yang diukur.

Dipakai notebook 02 (inferensi) dan 03 (evaluasi). Hasil disimpan ke `artifacts/eval/<nama>/predictions.json`
dalam format `evaluate.py` (+ waktu, parameter, identitas model), tanpa ground truth — GT ditambahkan di 03.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics
import time
from pathlib import Path

from . import backend
from .samples import Sample

ML_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ML_ROOT / "artifacts" / "eval" / "deepforest_samples" / "predictions.json"


def run_on_samples(det, samples: list[Sample], repeats: int = 1) -> dict:
    """`det` = detector API (mis. `backend.build_api_deepforest`). Model dimuat SEKALI di luar pengukuran
    per foto (`load_seconds`). `repeats` > 1 mengulang inferensi untuk median latensi."""
    info = det.info()
    if not info.available:
        raise RuntimeError(f"Detector tidak siap: {info.message}")
    t0 = time.perf_counter()
    det.preload()
    load_s = time.perf_counter() - t0
    images = []
    params = {}
    for s in samples:
        img = backend.load_oriented(s.path)
        secs, out = [], None
        for _ in range(max(1, repeats)):
            t = time.perf_counter()
            out = det.detect(img)
            secs.append(time.perf_counter() - t)
        params = out.parameters
        images.append({
            "image": s.id, "file": s.path.name, "width": img.width, "height": img.height,
            "exif_orientation": backend.exif_orientation(s.path),
            "seconds": [round(x, 3) for x in secs], "seconds_median": round(statistics.median(secs), 3),
            "mode": out.parameters.get("mode"),
            "pred": [{"label": d.label, "model_label": d.model_label, "confidence": d.confidence, "bbox": d.bbox}
                     for d in out.detections],
        })
    info = det.info()
    return {"model_id": info.model_id, "model_version": info.model_version, "adapter": info.adapter,
            "target": info.target, "target_label": info.target_label, "device": info.device,
            "parameters": params, "load_seconds": round(load_s, 3), "repeats": repeats,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "domain": "public:neon-deepforest-samples", "split": "sampel", "iou_threshold": 0.5, "images": images}


def save(result: dict, path: str | Path = DEFAULT_OUT) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return p


def load(path: str | Path = DEFAULT_OUT) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
