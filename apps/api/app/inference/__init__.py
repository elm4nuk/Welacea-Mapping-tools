"""Jalur inferensi. Detector tanaman WAJIB bobot lokal hasil pelatihan tim; tidak ada unduhan otomatis."""
from .base import (  # noqa: F401
    DetectionOutput, Detector, DetectorInfo, InferenceFailed, ModelNotConfigured, ModelUnavailable, RawDetection,
)
from .factory import build_detector  # noqa: F401
