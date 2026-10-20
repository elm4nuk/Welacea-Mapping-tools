"""Jalur inferensi. Detector tanaman WAJIB bobot lokal hasil pelatihan tim; tidak ada unduhan otomatis.

Simulasi (`simulation.py`) hanya untuk development dan selalu berlabel SIMULASI — BUKAN AI."""
from .base import (  # noqa: F401
    DIAGNOSTIC_CODES, DetectionOutput, Detector, DetectorInfo, InferenceFailed, ModelNotConfigured, ModelUnavailable,
    RawDetection,
)
from .factory import build_detector  # noqa: F401
