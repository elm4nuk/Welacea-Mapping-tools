"""Adapter Ultralytics YOLO (deteksi). Lisensi Ultralytics: AGPL-3.0 atau Enterprise — lihat REPO_SELECTION.md.

Model COCO umum BUKAN model tanaman. Label model harus dipetakan eksplisit ke plant/check/gap
lewat WALLACEA_LABEL_MAP_JSON; kelas yang tidak dipetakan diabaikan.
"""
from __future__ import annotations

import hashlib
import importlib.util
import logging
import threading
from pathlib import Path

from PIL import Image

from .base import (DetectionOutput, Detector, DetectorInfo, InferenceFailed, ModelUnavailable, RawDetection,
                   normalize_xyxy)

TARGET_LABEL = "Kandidat tanaman (model deteksi tim)"
LIMITATIONS = ("Hanya akurat untuk tanaman, kamera, dan ketinggian yang sama dengan data latihnya — lihat model card.",)

log = logging.getLogger("wallacea.inference")


def weights_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()[:16]


class UltralyticsDetector(Detector):
    def __init__(self, model_path: Path, label_map: dict[str, str], confidence: float = 0.35, imgsz: int = 1280,
                 model_id: str | None = None, max_det: int = 3000, config_error: str | None = None):
        self.model_path = model_path
        self.label_map = label_map
        self.confidence = confidence
        self.imgsz = imgsz
        self.model_id = model_id or model_path.stem
        self.max_det = max_det
        self.config_error = config_error
        self._lock = threading.Lock()
        self._model = None
        self._fp_cache: tuple[tuple[int, int], str] | None = None

    # ------------------------------------------------------------ status
    def _config_problem(self) -> str | None:
        if self.config_error:
            return self.config_error
        if not 0 <= self.confidence <= 1:
            return "WALLACEA_CONFIDENCE harus 0–1."
        if not self.model_path.is_file():
            return f"Berkas bobot tidak ditemukan: {self.model_path.name}"
        if self.model_path.suffix.lower() != ".pt":
            return "Adapter ini menerima bobot deteksi Ultralytics .pt lokal."
        if importlib.util.find_spec("ultralytics") is None:
            return "Dependensi Ultralytics belum terpasang (pip install -r requirements-ai.txt)."
        return None

    def _version(self) -> str | None:
        try:
            st = self.model_path.stat()
        except OSError:
            return None
        sig = (st.st_size, st.st_mtime_ns)
        if not self._fp_cache or self._fp_cache[0] != sig:
            self._fp_cache = (sig, weights_fingerprint(self.model_path))
        return self._fp_cache[1]

    def info(self) -> DetectorInfo:
        meta = dict(adapter="ultralytics", target="plant", target_label=TARGET_LABEL, device="auto",
                    limitations=LIMITATIONS)
        problem = self._config_problem()
        if problem:
            return DetectorInfo(state="error", message=problem, model_id=self.model_id, **meta)
        version = self._version()
        if self._model is not None:
            return DetectorInfo(state="loaded", message="Model termuat di memori.", model_id=self.model_id,
                                model_version=version, **meta)
        return DetectorInfo(state="configured", message="Bobot ditemukan; dimuat saat analisis pertama.",
                            model_id=self.model_id, model_version=version, **meta)

    def preload(self) -> None:
        with self._lock:
            self._load()

    # ------------------------------------------------------------ inference
    def _load(self):
        if self._model is not None:
            return self._model
        problem = self._config_problem()
        if problem:
            raise ModelUnavailable(problem)
        try:
            from ultralytics import YOLO
            model = YOLO(str(self.model_path), task="detect")
        except Exception as exc:  # noqa: BLE001
            log.exception("Model could not be loaded")
            raise ModelUnavailable("Model tidak dapat dimuat. Periksa bobot dan versi dependensi.") from exc
        if getattr(model, "task", "detect") != "detect":
            raise ModelUnavailable("Bobot bukan model deteksi (task=detect).")
        names = model.names.values() if isinstance(model.names, dict) else model.names
        if not any(str(n) in self.label_map for n in names):
            raise ModelUnavailable("Tidak ada kelas model yang cocok dengan WALLACEA_LABEL_MAP_JSON.")
        self._model = model
        return model

    def detect(self, image: Image.Image) -> DetectionOutput:
        with self._lock:
            model = self._load()
            try:
                result = model.predict(image, conf=self.confidence, imgsz=self.imgsz, max_det=self.max_det, verbose=False)[0]
            except Exception as exc:  # noqa: BLE001
                log.exception("Inference failed")
                raise InferenceFailed("Inferensi gagal. Periksa log server dan kapasitas perangkat.") from exc
        width, height = image.size
        out: list[RawDetection] = []
        boxes = getattr(result, "boxes", None)
        if boxes is not None:
            for (x1, y1, x2, y2), score, cls in zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(),
                                                    boxes.cls.cpu().tolist()):
                name = str(result.names[int(cls)])
                if name not in self.label_map:
                    continue
                bbox = normalize_xyxy(x1, y1, x2, y2, width, height)
                if bbox is None:
                    continue
                out.append(RawDetection(label=self.label_map[name], bbox=bbox,
                                        confidence=max(0.0, min(1.0, float(score))), model_label=name))
        return DetectionOutput(
            model_id=self.model_id, model_version=self._version(), detections=out,
            parameters={"adapter": "ultralytics", "target": "plant", "conf": self.confidence, "imgsz": self.imgsz,
                        "max_det": self.max_det},
        )
