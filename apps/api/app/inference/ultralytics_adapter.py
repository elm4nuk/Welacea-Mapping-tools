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
COCO_TARGET_LABEL = "Kandidat dari model COCO umum (BUKAN model tanaman)"
COCO_LIMITATION = ("Bobot ini model COCO umum (80 kelas benda sehari-hari: person, car, potted plant, …), bukan model "
                   "tanaman hasil pelatihan foto drone. Hanya untuk uji integrasi; jangan dipakai untuk hitungan lapangan.")
# Sebagian nama kelas COCO-80; bila semuanya ada di model.names, bobot hampir pasti yolo*n.pt umum.
COCO_MARKERS = {"person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "potted plant",
                "toothbrush"}

log = logging.getLogger("wallacea.inference")


def class_names(names) -> list[str]:
    return [str(n) for n in (names.values() if isinstance(names, dict) else names)]


def is_generic_coco(names) -> bool:
    values = set(class_names(names))
    return len(values) >= 80 and COCO_MARKERS <= values


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
        self._generic_coco = False
        # (kode, pesan, sig berkas) dari percobaan muat terakhir yang gagal; berkas yang diganti dicoba lagi
        self._load_problem: tuple[str, str, tuple[int, int] | None] | None = None
        self._fp_cache: tuple[tuple[int, int], str] | None = None

    # ------------------------------------------------------------ status
    def _config_problem(self) -> tuple[str, str] | None:
        """(diagnostic_code, pesan) bila model pasti tidak bisa dipakai; dicek tanpa memuat bobot."""
        if self.config_error:
            return "LABEL_MAP_INVALID", self.config_error
        if not 0 <= self.confidence <= 1:
            return "DETECTOR_CONFIG_INVALID", "WALLACEA_CONFIDENCE harus 0–1."
        if self.model_path.is_dir():
            return "MODEL_FILE_NOT_PT", (f"WALLACEA_MODEL_PATH menunjuk folder ({self.model_path}), bukan berkas .pt. "
                                         "Hasil training Ultralytics biasanya ada di <folder run>\\weights\\best.pt.")
        if not self.model_path.is_file():
            return "MODEL_FILE_NOT_FOUND", (f"Berkas bobot tidak ditemukan: {self.model_path}. Periksa path (pakai path "
                                            "lengkap; bungkus dengan tanda kutip bila ada spasi).")
        if self.model_path.suffix.lower() != ".pt":
            return "MODEL_FILE_NOT_PT", ("Adapter Ultralytics menerima bobot deteksi .pt lokal, bukan "
                                         f"'{self.model_path.suffix or '(tanpa ekstensi)'}'.")
        if importlib.util.find_spec("ultralytics") is None:
            return "DEPENDENCY_MISSING", ("Paket ultralytics belum terpasang di venv API. Pasang sekali: "
                                          ".venv\\Scripts\\python -m pip install -r requirements-ai.txt")
        return None

    def _sig(self) -> tuple[int, int] | None:
        try:
            st = self.model_path.stat()
        except OSError:
            return None
        return st.st_size, st.st_mtime_ns

    def _remembered_load_problem(self) -> tuple[str, str] | None:
        if self._model is None and self._load_problem and self._load_problem[2] == self._sig():
            return self._load_problem[0], self._load_problem[1]
        return None

    def _version(self) -> str | None:
        sig = self._sig()
        if sig is None:
            return None
        if not self._fp_cache or self._fp_cache[0] != sig:
            self._fp_cache = (sig, weights_fingerprint(self.model_path))
        return self._fp_cache[1]

    def info(self) -> DetectorInfo:
        meta = dict(adapter="ultralytics", target="plant", target_label=TARGET_LABEL, device="auto",
                    limitations=LIMITATIONS)
        if self._generic_coco:
            meta.update(target_label=COCO_TARGET_LABEL, limitations=(COCO_LIMITATION,) + LIMITATIONS)
        problem = self._config_problem() or self._remembered_load_problem()
        if problem:
            return DetectorInfo(state="error", message=problem[1], model_id=self.model_id, diagnostic_code=problem[0],
                                **meta)
        version = self._version()
        if self._model is not None:
            if self._generic_coco:
                return DetectorInfo(state="loaded", message="Model COCO umum termuat — BUKAN model tanaman.",
                                    model_id=self.model_id, model_version=version,
                                    diagnostic_code="GENERIC_COCO_MODEL", **meta)
            return DetectorInfo(state="loaded", message="Model termuat di memori.", model_id=self.model_id,
                                model_version=version, **meta)
        return DetectorInfo(state="configured", message="Bobot ditemukan; dimuat saat analisis pertama.",
                            model_id=self.model_id, model_version=version, **meta)

    def preload(self) -> None:
        with self._lock:
            self._load()

    # ------------------------------------------------------------ inference
    def _fail_load(self, code: str, message: str, exc: Exception | None = None):
        # Diingat agar /health menunjukkan state=error + kode yang sama, bukan "configured" yang menyesatkan.
        self._load_problem = (code, message, self._sig())
        raise ModelUnavailable(message, code) from exc

    def _load(self):
        if self._model is not None:
            return self._model
        problem = self._config_problem() or self._remembered_load_problem()
        if problem:
            raise ModelUnavailable(problem[1], problem[0])
        try:
            from ultralytics import YOLO
            model = YOLO(str(self.model_path), task="detect")
        except Exception as exc:  # noqa: BLE001
            log.exception("Model could not be loaded")
            self._fail_load("MODEL_LOAD_FAILED", "Berkas .pt tidak dapat dibuka oleh Ultralytics (rusak, bukan bobot "
                            "Ultralytics, atau versi paket tidak cocok). Jalankan scripts\\check-model.ps1 untuk detail.",
                            exc)
        task = getattr(model, "task", "detect")
        if task != "detect":
            self._fail_load("NOT_DETECTION_MODEL", f"Bobot ini model task={task!r}, bukan deteksi (task='detect'). "
                            "Latih ulang dengan model deteksi YOLO (mis. yolo11n.pt, bukan -seg/-cls/-pose).")
        names = class_names(model.names)
        if not any(n in self.label_map for n in names):
            shown = ", ".join(names[:12]) + (" …" if len(names) > 12 else "")
            self._fail_load("LABEL_MAP_MISMATCH", "Tidak ada kelas model yang ada di WALLACEA_LABEL_MAP_JSON "
                            f"(kunci: {sorted(self.label_map)}). Kelas model: {shown}.")
        self._generic_coco = is_generic_coco(model.names)
        if self._generic_coco:
            log.warning("Bobot %s adalah model COCO umum, BUKAN model tanaman.", self.model_path.name)
        self._load_problem = None
        self._model = model
        return model

    def detect(self, image: Image.Image) -> DetectionOutput:
        with self._lock:
            model = self._load()
            try:
                result = model.predict(image, conf=self.confidence, imgsz=self.imgsz, max_det=self.max_det, verbose=False)[0]
            except Exception as exc:  # noqa: BLE001
                log.exception("Inference failed")
                raise InferenceFailed("Inferensi gagal di dalam Ultralytics. Periksa log server (memori, ukuran foto) "
                                      "dan versi paket.") from exc
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
                        "max_det": self.max_det, "generic_coco": self._generic_coco},
        )
