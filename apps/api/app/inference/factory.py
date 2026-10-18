from __future__ import annotations

from ..config import Settings
from .base import Detector, UnconfiguredDetector
from .ultralytics_adapter import UltralyticsDetector


def build_detector(settings: Settings) -> Detector:
    if settings.model_path is None:
        return UnconfiguredDetector()
    return UltralyticsDetector(
        model_path=settings.model_path,
        label_map=settings.label_map,
        confidence=settings.confidence,
        imgsz=settings.imgsz,
        model_id=settings.model_id,
        max_det=settings.max_annotations_per_photo,
        config_error=settings.label_map_error,
    )
