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

    @property
    def available(self) -> bool:
        return self.state in ("configured", "loaded")


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


class UnconfiguredDetector(Detector):
    """Mode manual: API jujur bahwa model belum ada. Foto & anotasi manual tetap berfungsi."""

    def __init__(self, message: str = "Model tanaman belum dikonfigurasi. Atur WALLACEA_MODEL_PATH ke bobot lokal hasil pelatihan tim."):
        self._message = message

    def info(self) -> DetectorInfo:
        return DetectorInfo(state="not_configured", message=self._message)

    def detect(self, image: Image.Image) -> DetectionOutput:
        raise ModelNotConfigured(self._message)
