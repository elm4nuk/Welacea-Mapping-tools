"""Skema kontrak API v1. packages/contracts/openapi.yaml di-generate dari sini.

Konvensi koordinat: x, y, dan bbox dinormalisasi 0–1 terhadap foto SETELAH orientasi EXIF
diterapkan (lebar/tinggi = Photo.width/height = dimensi display_url). bbox = [left, top, width, height].
Ini koordinat gambar, BUKAN lintang/bujur.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from .errors import ERROR_CODES

Kind = Literal["plant", "check", "gap"]
GeometryType = Literal["point", "bbox"]
Source = Literal["manual", "model"]
ReviewStatus = Literal["pending", "accepted", "rejected"]
GeorefStatus = Literal["none"]
RunStatus = Literal["running", "succeeded", "failed"]
RunType = Literal["inference", "import"]
OnExisting = Literal["reject", "replace_pending", "append"]
ModelState = Literal["not_configured", "configured", "loaded", "error"]
ErrorCode = Literal[ERROR_CODES]  # type: ignore[valid-type]

Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
EPS = 1e-9


def check_bbox(value: list[float] | None) -> list[float] | None:
    if value is None:
        return None
    if len(value) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in value):
        raise ValueError("bbox harus [left, top, width, height] dengan 4 angka finite")
    left, top, width, height = (float(v) for v in value)
    if left < 0 or top < 0 or width <= 0 or height <= 0:
        raise ValueError("bbox: left/top ≥ 0, width/height > 0")
    if left + width > 1 + EPS or top + height > 1 + EPS:
        raise ValueError("bbox keluar dari batas gambar (left+width ≤ 1, top+height ≤ 1)")
    return [left, top, min(width, 1 - left), min(height, 1 - top)]


BBox = Annotated[
    list[float],
    Field(min_length=4, max_length=4, description="[left, top, width, height], semua 0–1 relatif gambar terorientasi."),
]


class StrictIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------- errors
class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str = Field(description="Pesan untuk pengguna (Bahasa Indonesia).")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class Warning(BaseModel):
    code: Literal["DUPLICATE_IN_SURVEY", "DEMO_IMAGE_REPLACED", "BBOX_DROPPED"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- health
class ModelStatus(BaseModel):
    state: ModelState = Field(description="not_configured: tidak ada bobot; configured: bobot ada, belum dimuat; "
                                          "loaded: sudah dimuat di memori; error: konfigurasi/dependensi bermasalah.")
    available: bool = Field(description="True bila analyze dapat dicoba (state configured/loaded).")
    model_id: str | None = None
    model_version: str | None = Field(None, description="Sidik jari bobot (sha256 terpotong) bila diketahui.")
    message: str
    # Revisi 2 (aditif): apa yang sebenarnya dideteksi model, agar UI tidak menebak.
    adapter: Literal["ultralytics", "deepforest"] | None = Field(
        None, description="Jenis detector aktif. null bila mode manual / konfigurasi salah.")
    target: Literal["plant", "tree_crown"] | None = Field(
        None, description="Objek yang dideteksi model. tree_crown = tajuk pohon (DeepForest pretrained), BUKAN semua "
                          "tanaman. Kandidat tetap disimpan sebagai kind=plant (lihat Annotation.model_label).")
    target_label: str | None = Field(None, description="Teks siap tampil, mis. 'Kandidat tajuk pohon (DeepForest pretrained)'.")
    device: str | None = Field(None, description="cpu | cuda | auto. Inferensi CPU dapat memakan puluhan detik per foto besar.")
    limitations: list[str] = Field(default_factory=list, description="Keterbatasan model yang perlu ditampilkan ke pengguna.")


class Capabilities(BaseModel):
    flight_control: Literal[False] = False
    live_video: Literal[False] = False
    georeferencing: Literal[False] = False
    orthomosaic: Literal[False] = False


class Limits(BaseModel):
    max_upload_bytes: int
    max_pixels: int
    allowed_mime_types: list[str]
    max_annotations_per_photo: int
    max_detection_payload_bytes: int
    max_backup_bytes: int
    inference_timeout_s: float


class Health(BaseModel):
    status: Literal["ok"]
    api_version: str
    contract_revision: int
    database: Literal["ok"]
    model: ModelStatus
    capabilities: Capabilities
    limits: Limits


# ---------------------------------------------------------------- surveys
class SurveyCreate(StrictIn):
    name: str = Field(min_length=1, max_length=100)
    crop_type: str = Field(min_length=1, max_length=80)
    location_label: str = Field("", max_length=150, description="Teks bebas, bukan koordinat.")
    survey_date: dt.date
    notes: str = Field("", max_length=2000)


class SurveyUpdate(StrictIn):
    name: str | None = Field(None, min_length=1, max_length=100)
    crop_type: str | None = Field(None, min_length=1, max_length=80)
    location_label: str | None = Field(None, max_length=150)
    survey_date: dt.date | None = None
    notes: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus diubah")
        for f in ("name", "crop_type", "survey_date"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} tidak boleh null")
        return self


class Survey(BaseModel):
    id: str
    name: str
    crop_type: str
    location_label: str
    survey_date: dt.date
    notes: str
    is_demo: bool = Field(description="True = data contoh/ilustrasi, bukan foto drone atau hasil AI.")
    revision: int
    photo_count: int
    created_at: dt.datetime
    updated_at: dt.datetime


class SurveyPage(BaseModel):
    items: list[Survey]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------- photos
class AnnotationCounts(BaseModel):
    plant_accepted: int = Field(description="Hitungan tanaman resmi foto ini: kind=plant & review_status=accepted.")
    plant_pending: int
    check_accepted: int
    gap_accepted: int
    pending_review: int = Field(description="Semua penanda pending (belum ditinjau), semua kind.")
    rejected: int
    total: int


class Photo(BaseModel):
    id: str
    survey_id: str
    original_name: str
    width: int = Field(description="Lebar piksel setelah orientasi EXIF.")
    height: int = Field(description="Tinggi piksel setelah orientasi EXIF.")
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int
    sha256: str = Field(description="SHA-256 berkas asli (byte persis yang diunggah).")
    exif_orientation: int = Field(description="Tag Orientation EXIF berkas asli (1 = normal).")
    has_exif_gps: bool = Field(description="Berkas memuat tag GPS EXIF. Itu posisi kamera, bukan lokasi tanaman; tidak dipakai.")
    captured_at: str | None = Field(None, description="DateTimeOriginal EXIF, ISO tanpa zona waktu (jam lokal kamera).")
    georef_status: GeorefStatus
    revision: int = Field(description="Naik setiap kali penanda foto ini berubah.")
    created_at: dt.datetime
    content_url: str = Field(description="Berkas asli apa adanya (relatif terhadap base URL API).")
    display_url: str = Field(description="Gambar terorientasi untuk editor; dimensinya = width × height.")
    thumbnail_url: str = Field(description="JPEG terorientasi, sisi terpanjang ≤ 512 px.")
    duplicate_photo_ids: list[str] = Field(description="Foto lain di survei yang sama dengan sha256 identik.")
    counts: AnnotationCounts


class PhotoPage(BaseModel):
    items: list[Photo]
    total: int
    limit: int
    offset: int


class PhotoUploadResult(BaseModel):
    photo: Photo
    warnings: list[Warning]


# ---------------------------------------------------------------- annotations
class AnnotationCreate(StrictIn):
    kind: Kind
    geometry_type: GeometryType = "point"
    x: Unit | None = Field(None, description="Wajib untuk point. Untuk bbox dihitung server (pusat kotak).")
    y: Unit | None = None
    bbox: BBox | None = Field(None, description="Wajib untuk bbox.")
    note: str = Field("", max_length=1000)
    review_status: Literal["accepted", "pending"] = Field(
        "accepted", description="Penanda manual boleh langsung accepted. source selalu manual di endpoint ini.")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        return check_bbox(v)

    @model_validator(mode="after")
    def _geometry(self):
        if self.geometry_type == "point":
            if self.x is None or self.y is None:
                raise ValueError("point membutuhkan x dan y")
            if self.bbox is not None:
                raise ValueError("point tidak boleh memiliki bbox")
        else:
            if self.bbox is None:
                raise ValueError("bbox membutuhkan bbox")
            if self.x is not None or self.y is not None:
                raise ValueError("Untuk bbox, x/y dihitung server; jangan dikirim")
        return self


class AnnotationUpdate(StrictIn):
    """Kirim HANYA field yang berubah. Field yang dikirim tidak boleh null, kecuali `bbox: null` saat berubah ke
    titik. `x`/`y` dikirim bersama dan hanya untuk titik (untuk bbox, pusat dihitung server — jangan kirim x/y)."""
    # Revisi 3 (CR-FE-001): None hanya nilai "tidak dikirim"; skema tidak lagi mengiklankan null (runtime sama).
    kind: Kind | SkipJsonSchema[None] = None
    note: str | SkipJsonSchema[None] = Field(None, max_length=1000)
    review_status: ReviewStatus | SkipJsonSchema[None] = None
    geometry_type: GeometryType | SkipJsonSchema[None] = None
    x: Unit | SkipJsonSchema[None] = Field(None, description="Hanya untuk titik; wajib bersama y.")
    y: Unit | SkipJsonSchema[None] = Field(None, description="Hanya untuk titik; wajib bersama x.")
    bbox: BBox | None = Field(None, description="[left, top, width, height] 0–1; null = ubah ke titik.")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        return check_bbox(v)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus diubah")
        for f in ("kind", "note", "review_status", "geometry_type", "x", "y"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} tidak boleh null")
        if ("x" in self.model_fields_set) != ("y" in self.model_fields_set):
            raise ValueError("x dan y harus dikirim bersama")
        return self


class Annotation(BaseModel):
    id: str
    photo_id: str
    analysis_run_id: str | None
    kind: Kind
    geometry_type: GeometryType
    x: float
    y: float
    bbox: list[float] | None
    source: Source
    review_status: ReviewStatus
    confidence: float | None = Field(description="Keluaran model 0–1 (bukan akurasi). Null untuk manual.")
    model_label: str | None = Field(description="Nama kelas asli dari model/impor, bila ada.")
    note: str
    revision: int
    created_at: dt.datetime
    updated_at: dt.datetime


class AnnotationPage(BaseModel):
    items: list[Annotation]
    total: int
    limit: int
    offset: int
    photo_revision: int


# ---------------------------------------------------------------- analysis
class AnalysisRun(BaseModel):
    id: str
    photo_id: str
    run_type: RunType
    model_id: str | None
    model_version: str | None
    input_sha256: str
    status: RunStatus
    candidate_count: int
    parameters: dict[str, Any]
    started_at: dt.datetime
    finished_at: dt.datetime | None
    error_code: str | None
    # Revisi 3 (CR-FE-003): semantik kandidat run ini, sama dengan health.model.target saat run dibuat.
    target: Literal["plant", "tree_crown"] | None = Field(
        None, description="Arti bbox kandidat run ini: plant = tanaman (model tim), tree_crown = tajuk pohon "
                          "(DeepForest pretrained). null = tidak diketahui (mis. impor, run lama) → pakai istilah generik.")


class AnalysisRunPage(BaseModel):
    items: list[AnalysisRun]
    total: int
    limit: int
    offset: int


class AnalyzeRequest(StrictIn):
    on_existing: OnExisting = Field(
        "reject",
        description="Bila foto sudah punya run sukses dengan model+versi yang sama: reject → 409 ANALYSIS_EXISTS; "
                    "replace_pending → hapus kandidat pending dari run lama foto ini lalu tambah yang baru; "
                    "append → tambah tanpa menghapus.")


class DetectionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: Kind
    confidence: Unit | None = None
    bbox: BBox

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        return check_bbox(v)


class DetectionImportRequest(BaseModel):
    """Format impor starter v0.1 (kompatibel), plus field opsional untuk identitas."""
    model_config = ConfigDict(extra="ignore")
    image_width: int = Field(gt=0, description="Harus sama dengan Photo.width (terorientasi).")
    image_height: int = Field(gt=0)
    model: str = Field(min_length=1, max_length=120)
    model_version: str | None = Field(None, max_length=120)
    image_sha256: str | None = Field(None, pattern=r"^[0-9a-f]{64}$", description="Bila ada, harus sama dengan Photo.sha256.")
    detections: list[DetectionIn] = Field(max_length=3000)
    on_existing: OnExisting = "reject"


class AnalysisResult(BaseModel):
    run: AnalysisRun
    candidates: list[Annotation] = Field(description="Semua kandidat review_status=pending, source=model.")
    replaced_annotation_ids: list[str]
    notice: str


# ---------------------------------------------------------------- reports
class PhotoReportRow(BaseModel):
    photo_id: str
    original_name: str
    width: int
    height: int
    captured_at: str | None
    duplicate_photo_ids: list[str]
    counts: AnnotationCounts


class Finding(BaseModel):
    annotation_id: str
    photo_id: str
    photo_name: str
    kind: Literal["check", "gap"]
    review_status: ReviewStatus
    source: Source
    x: float
    y: float
    note: str


class ReportTotals(BaseModel):
    photo_count: int
    plant_accepted_sum_across_photos: int = Field(
        description="Penjumlahan hitungan per foto. BUKAN jumlah tanaman unik bila foto bertumpang tindih.")
    pending_review: int
    check_accepted: int
    gap_accepted: int
    counts_are_unique_plants: Literal[False] = False


class SurveyReport(BaseModel):
    survey: Survey
    generated_at: dt.datetime
    photos: list[PhotoReportRow]
    totals: ReportTotals
    findings: list[Finding]
    disclaimers: list[str]


# ---------------------------------------------------------------- imports
class StarterBackupImportResult(BaseModel):
    surveys: list[Survey]
    photo_count: int
    annotation_count: int
    warnings: list[Warning]


# ---------------------------------------------------------------- samples (revisi 3, CR-FE-002)
class SamplePhoto(BaseModel):
    """Foto contoh berlisensi untuk demo. Diunduh lewat `file_url`, lalu diunggah lewat endpoint upload BIASA.
    Bukan hasil inferensi; anotasi manusia (bila ada) hanya untuk evaluasi di notebook."""
    id: str
    title: str
    file_url: str = Field(description="Relatif terhadap base API, mis. /api/v1/samples/neon-osbs-029/file")
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int
    source_name: str
    source_url: str
    license_name: str
    license_url: str
    attribution: str
    imagery: str = Field(description="Jenis citra & keterbatasan (mis. pesawat ±10 cm/px, bukan K919).")
    has_human_annotations: bool


class SamplePage(BaseModel):
    items: list[SamplePhoto]
    total: int
