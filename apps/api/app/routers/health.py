from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import API_VERSION, CONTRACT_REVISION
from .. import schemas as s
from ..config import Settings
from ..deps import get_db, get_detector, get_settings
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
                            limitations=list(info.limitations)),
        capabilities=s.Capabilities(),
        limits=s.Limits(
            max_upload_bytes=settings.max_upload_bytes, max_pixels=settings.max_pixels,
            allowed_mime_types=ALLOWED_MIME, max_annotations_per_photo=settings.max_annotations_per_photo,
            max_detection_payload_bytes=settings.max_detection_payload_bytes,
            max_backup_bytes=settings.max_backup_bytes, inference_timeout_s=settings.inference_timeout_s,
        ),
    )
