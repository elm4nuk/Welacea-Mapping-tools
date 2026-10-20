from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import API_VERSION, CONTRACT_REVISION
from .. import schemas as s
from ..config import Settings
from ..deps import get_db, get_detector, get_settings
from .. import geo
from ..imaging import ALLOWED_MIME
from ..inference import Detector

router = APIRouter(tags=["health"])


@router.get("/health", response_model=s.Health, summary="Status API dan kesiapan model yang sebenarnya")
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
           detector: Detector = Depends(get_detector)):
    db.execute(text("SELECT 1"))
    info = detector.info()
    return s.Health(
        status="ok", api_version=API_VERSION, contract_revision=CONTRACT_REVISION, database="ok",
        model=s.ModelStatus(state=info.state, available=info.available, model_id=info.model_id,
                            model_version=info.model_version, message=info.message, adapter=info.adapter,
                            target=info.target, target_label=info.target_label, device=info.device,
                            limitations=list(info.limitations), mode=info.mode,
                            diagnostic_code=info.diagnostic_code),
        capabilities=s.Capabilities(field_boundaries=geo.boundaries_available(),
                                    georeferenced_raster_import=geo.rasters_available(),
                                    map_ai_detections=geo.rasters_available()),
        limits=s.Limits(
            max_upload_bytes=settings.max_upload_bytes, max_pixels=settings.max_pixels,
            allowed_mime_types=ALLOWED_MIME, max_annotations_per_photo=settings.max_annotations_per_photo,
            max_detection_payload_bytes=settings.max_detection_payload_bytes,
            max_backup_bytes=settings.max_backup_bytes, inference_timeout_s=settings.inference_timeout_s,
            max_raster_bytes=settings.max_raster_bytes, max_raster_pixels=settings.max_raster_pixels,
            max_raster_footprint_km2=settings.max_raster_footprint_km2, max_field_vertices=settings.max_field_vertices,
            max_field_import_bytes=settings.max_field_import_bytes,
            raster_analysis_timeout_s=settings.raster_analysis_timeout_s,
        ),
    )
