from __future__ import annotations

from ..schemas import ErrorEnvelope

_DESC = {
    400: "Permintaan/berkas tidak valid (BAD_REQUEST, INVALID_IMAGE, INVALID_BACKUP)",
    404: "Tidak ditemukan (NOT_FOUND)",
    409: "Konflik (REVISION_CONFLICT, ANALYSIS_EXISTS, ANALYSIS_IN_PROGRESS, DEMO_SURVEY_READONLY)",
    413: "Terlalu besar (PAYLOAD_TOO_LARGE, IMAGE_TOO_LARGE)",
    415: "Format tidak didukung (UNSUPPORTED_MEDIA_TYPE)",
    422: "Validasi gagal (VALIDATION_ERROR, DETECTION_MISMATCH, ANNOTATION_LIMIT_EXCEEDED)",
    428: "If-Match wajib (PRECONDITION_REQUIRED)",
    500: "Kesalahan server (INTERNAL_ERROR, INFERENCE_FAILED)",
    503: "Model tidak tersedia (MODEL_NOT_CONFIGURED, MODEL_UNAVAILABLE)",
    504: "Inferensi melewati batas waktu (INFERENCE_TIMEOUT)",
}


def errors(*statuses: int) -> dict:
    return {st: {"model": ErrorEnvelope, "description": _DESC[st]} for st in statuses}
