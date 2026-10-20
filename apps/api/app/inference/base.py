from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class RawDetection:
    label: str                    # plant | check | gap (sudah dipetakan)
    bbox: list[float]             # [left, top, width, height] normalized 0–1 terhadap gambar input
    confidence: float | None = None
    model_label: str | None = None  # nama kelas asli model


# Kode diagnostik (revisi 4): kenapa model tidak siap / mode apa yang aktif. Teks untuk manusia ada di `message`.
DIAGNOSTIC_CODES = (
    "MODEL_PATH_NOT_SET",          # mode manual: WALLACEA_MODEL_PATH kosong
    "DETECTOR_CONFIG_INVALID",     # WALLACEA_DETECTOR tak dikenal / kombinasi env salah / confidence di luar 0–1
    "MODEL_FILE_NOT_FOUND",        # path bobot/folder tidak ada
    "MODEL_FILE_NOT_PT",           # adapter Ultralytics butuh berkas .pt
    "MODEL_FILES_INCOMPLETE",      # folder DeepForest tidak lengkap
    "DEPENDENCY_MISSING",          # ultralytics / deepforest belum terpasang
    "LABEL_MAP_INVALID",           # WALLACEA_LABEL_MAP_JSON bukan JSON objek {kelas: plant|check|gap}
    "LABEL_MAP_MISMATCH",          # tidak ada kelas model yang ada di label map
    "NOT_DETECTION_MODEL",         # bobot bukan task=detect (mis. segmentasi/klasifikasi)
    "MODEL_LOAD_FAILED",           # berkas ada tetapi gagal dibuka
    "GENERIC_COCO_MODEL",          # model COCO umum: berjalan, tetapi BUKAN model tanaman
    "SIMULATION_ACTIVE",           # WALLACEA_DETECTOR=simulation: kotak buatan, BUKAN AI
)


@dataclass(frozen=True)
class DetectorInfo:
    state: str                    # not_configured | configured | loaded | error
    message: str
    model_id: str | None = None
    model_version: str | None = None
    adapter: str | None = None    # ultralytics | deepforest
    target: str | None = None     # apa yang dideteksi model: plant | tree_crown
    target_label: str | None = None  # teks untuk UI, mis. "Kandidat tajuk pohon"
    device: str | None = None     # cpu | cuda | auto
    limitations: tuple[str, ...] = ()
    mode: str = "model"           # manual | model | simulation
    diagnostic_code: str | None = None

    @property
    def available(self) -> bool:
        return self.state in ("configured", "loaded")


def normalize_xyxy(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> list[float] | None:
    """Kotak piksel xyxy (terhadap gambar input terorientasi) → [left, top, width, height] 0–1, di-clip.
    None bila kotak kosong setelah clip. Dipakai semua adapter agar format kontrak identik."""
    l, r = max(0.0, min(1.0, x1 / width)), max(0.0, min(1.0, x2 / width))
    t, b = max(0.0, min(1.0, y1 / height)), max(0.0, min(1.0, y2 / height))
    if r <= l or b <= t:
        return None
    return [l, t, r - l, b - t]


@dataclass
class DetectionOutput:
    model_id: str
    model_version: str | None
    detections: list[RawDetection]
    parameters: dict[str, Any] = field(default_factory=dict)


class ModelNotConfigured(Exception):
    """Tidak ada bobot model tanaman yang dikonfigurasi."""


class ModelUnavailable(Exception):
    """Bobot/dependensi/konfigurasi ada tetapi tidak dapat dipakai."""

    def __init__(self, message: str, diagnostic_code: str | None = None):
        super().__init__(message)
        self.diagnostic_code = diagnostic_code


class InferenceFailed(Exception):
    """Model termuat tetapi prediksi gagal."""


class Detector(ABC):
    @abstractmethod
    def info(self) -> DetectorInfo: ...

    @abstractmethod
    def detect(self, image: Image.Image) -> DetectionOutput:
        """image: RGB, sudah diorientasikan EXIF — sama dengan dimensi Photo.width/height."""

    def preload(self) -> None:
        """Muat model ke memori sebelum request pertama (opsional). Tidak boleh mengunduh apa pun."""


class UnconfiguredDetector(Detector):
    """Mode manual: API jujur bahwa model belum ada. Foto & anotasi manual tetap berfungsi."""

    MESSAGE = ("Model tanaman belum dikonfigurasi (mode manual). Penandaan manual tetap berjalan. Untuk analisis "
               "otomatis, jalankan API lewat scripts\\run-with-model.ps1 dengan bobot YOLO hasil pelatihan "
               "(berkas best.pt) — lihat apps/api/README.md.")

    def __init__(self, message: str = MESSAGE):
        self._message = message

    def info(self) -> DetectorInfo:
        return DetectorInfo(state="not_configured", message=self._message, mode="manual",
                            diagnostic_code="MODEL_PATH_NOT_SET")

    def detect(self, image: Image.Image) -> DetectionOutput:
        raise ModelNotConfigured(self._message)
