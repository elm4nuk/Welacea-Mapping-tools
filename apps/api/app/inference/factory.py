from __future__ import annotations

from ..config import Settings
from .base import Detector, DetectorInfo, ModelUnavailable, UnconfiguredDetector
from .deepforest_adapter import DEFAULT_LABEL_MAP as DEEPFOREST_LABEL_MAP
from .deepforest_adapter import DeepForestDetector
from .ultralytics_adapter import UltralyticsDetector


class MisconfiguredDetector(Detector):
    """Konfigurasi detector salah (mis. WALLACEA_DETECTOR tak dikenal). Jujur sebagai error, tanpa analisis."""

    def __init__(self, message: str):
        self._message = message

    def info(self) -> DetectorInfo:
        return DetectorInfo(state="error", message=self._message)

    def detect(self, image):
        raise ModelUnavailable(self._message)


def build_detector(settings: Settings) -> Detector:
    """WALLACEA_DETECTOR: kosong = otomatis (ultralytics bila WALLACEA_MODEL_PATH ada, selain itu manual),
    `none` = manual, `ultralytics` = bobot YOLO .pt, `deepforest` = folder bobot DeepForest lokal."""
    if settings.config_error:
        return MisconfiguredDetector(settings.config_error)
    kind = settings.detector or ("ultralytics" if settings.model_path else "none")
    if kind == "none" or settings.model_path is None:
        return UnconfiguredDetector()
    if kind == "deepforest":
        return DeepForestDetector(
            model_dir=settings.model_path,
            # Tanpa WALLACEA_LABEL_MAP_JSON: pemetaan eksplisit bawaan adapter {"Tree": "plant"}.
            label_map=settings.label_map if settings.label_map_raw else DEEPFOREST_LABEL_MAP,
            confidence=settings.confidence,
            device=settings.device,
            patch_size=settings.patch_size,
            patch_overlap=settings.patch_overlap,
            max_det=settings.max_annotations_per_photo,
            model_id=settings.model_id,
            log_dir=settings.data_dir / "model_logs",
            config_error=settings.label_map_error,
        )
    return UltralyticsDetector(
        model_path=settings.model_path,
        label_map=settings.label_map,
        confidence=settings.confidence,
        imgsz=settings.imgsz,
        model_id=settings.model_id,
        max_det=settings.max_annotations_per_photo,
        config_error=settings.label_map_error,
    )
