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

    def __init__(self, message: str = "Model tanaman belum dikonfigurasi. Atur WALLACEA_MODEL_PATH ke bobot lokal hasil pelatihan tim."):
        self._message = message

    def info(self) -> DetectorInfo:
        return DetectorInfo(state="not_configured", message=self._message)

    def detect(self, image: Image.Image) -> DetectionOutput:
        raise ModelNotConfigured(self._message)
