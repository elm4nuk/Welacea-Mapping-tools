"""ORM. Perubahan skema wajib lewat migrasi Alembic (apps/api/alembic/versions)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, Float, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow


def new_id() -> str:
    return uuid.uuid4().hex


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    crop_type: Mapped[str] = mapped_column(String(80))
    location_label: Mapped[str] = mapped_column(String(150), default="")
    survey_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Revisi 5: lahan yang disurvei (opsional). Hapus lahan → NULL; survei & fotonya tetap.
    field_id: Mapped[str | None] = mapped_column(ForeignKey("fields.id", ondelete="SET NULL"), nullable=True,
                                                 index=True)

    photos: Mapped[list[Photo]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", passive_deletes=True, order_by="Photo.created_at"
    )


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (Index("ix_photos_survey_sha", "survey_id", "sha256"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    width: Mapped[int] = mapped_column(Integer)          # setelah orientasi EXIF
    height: Mapped[int] = mapped_column(Integer)         # setelah orientasi EXIF
    mime_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    exif_orientation: Mapped[int] = mapped_column(Integer, default=1)
    has_exif_gps: Mapped[bool] = mapped_column(Boolean, default=False)
    captured_at: Mapped[str | None] = mapped_column(String(19), nullable=True)  # ISO waktu lokal kamera, tanpa zona
    georef_status: Mapped[str] = mapped_column(String(16), default="none")
    storage_key: Mapped[str] = mapped_column(String(80))           # berkas asli
    display_key: Mapped[str | None] = mapped_column(String(80), nullable=True)  # turunan terorientasi bila perlu
    thumbnail_key: Mapped[str] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    survey: Mapped[Survey] = relationship(back_populates="photos")
    annotations: Mapped[list[Annotation]] = relationship(
        back_populates="photo", cascade="all, delete-orphan", passive_deletes=True
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running','succeeded','failed')", name="ck_run_status"),
        CheckConstraint("run_type IN ('inference','import')", name="ck_run_type"),
        # Maksimal satu run berstatus running per foto (dicek ulang di DB, bukan hanya di kode).
        Index("uq_run_running_per_photo", "photo_id", unique=True,
              sqlite_where=text("status = 'running'"), postgresql_where=text("status = 'running'")),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    run_type: Mapped[str] = mapped_column(String(16))
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint("kind IN ('plant','check','gap')", name="ck_ann_kind"),
        CheckConstraint("geometry_type IN ('point','bbox')", name="ck_ann_geom"),
        CheckConstraint("source IN ('manual','model')", name="ck_ann_source"),
        CheckConstraint("review_status IN ('pending','accepted','rejected')", name="ck_ann_review"),
        CheckConstraint("x >= 0 AND x <= 1 AND y >= 0 AND y <= 1", name="ck_ann_xy"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_ann_conf"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    photo_id: Mapped[str] = mapped_column(ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(8))
    geometry_type: Mapped[str] = mapped_column(String(8))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    bbox_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_top: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8))
    review_status: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    photo: Mapped[Photo] = relationship(back_populates="annotations")

    @property
    def bbox(self) -> list[float] | None:
        if self.geometry_type != "bbox" or self.bbox_left is None:
            return None
        return [self.bbox_left, self.bbox_top, self.bbox_width, self.bbox_height]


# ---------------------------------------------------------------- mapping (revisi 5)
class Field(Base):
    """Lahan + batasnya. Geometri GeoJSON WGS84 [lon, lat] disimpan apa adanya; ukuran dihitung backend."""
    __tablename__ = "fields"
    __table_args__ = (
        CheckConstraint("geometry_type IN ('Polygon','MultiPolygon')", name="ck_field_geom"),
        CheckConstraint("boundary_source IN ('manual_drawing','geojson_import','gnss_survey',"
                        "'digitized_from_raster','other')", name="ck_field_source"),
        CheckConstraint("area_m2 > 0 AND perimeter_m > 0", name="ck_field_measures"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(Text, default="")
    boundary_source: Mapped[str] = mapped_column(String(24))
    source_note: Mapped[str] = mapped_column(String(500), default="")
    geometry_type: Mapped[str] = mapped_column(String(16))
    geometry_json: Mapped[str] = mapped_column(Text)
    area_m2: Mapped[float] = mapped_column(Float)
    perimeter_m: Mapped[float] = mapped_column(Float)
    exterior_perimeter_m: Mapped[float] = mapped_column(Float)
    min_lon: Mapped[float] = mapped_column(Float)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    label_lon: Mapped[float] = mapped_column(Float)
    label_lat: Mapped[float] = mapped_column(Float)
    vertex_count: Mapped[int] = mapped_column(Integer)
    hole_count: Mapped[int] = mapped_column(Integer, default=0)
    polygon_count: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RasterAsset(Base):
    """GeoTIFF bergeoreferensi yang DIIMPOR pengguna. Terpisah dari Photo: koordinatnya CRS nyata, bukan 0–1 foto."""
    __tablename__ = "raster_assets"
    __table_args__ = (
        CheckConstraint("product_type IN ('imported_georeferenced_raster')", name="ck_raster_product"),
        Index("ix_raster_survey_sha", "survey_id", "sha256"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    original_name: Mapped[str] = mapped_column(String(255))
    product_type: Mapped[str] = mapped_column(String(40), default="imported_georeferenced_raster")
    source_description: Mapped[str] = mapped_column(String(500), default="")   # klaim pengguna, tidak diverifikasi
    storage_key: Mapped[str] = mapped_column(String(80))
    display_key: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    band_count: Mapped[int] = mapped_column(Integer)
    crs_wkt: Mapped[str] = mapped_column(Text)
    crs_epsg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crs_name: Mapped[str] = mapped_column(String(200))
    transform_json: Mapped[str] = mapped_column(Text)
    bounds_native_json: Mapped[str] = mapped_column(Text)
    min_lon: Mapped[float] = mapped_column(Float)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    footprint_json: Mapped[str] = mapped_column(Text)
    footprint_area_m2: Mapped[float] = mapped_column(Float)
    approx_gsd_m: Mapped[float] = mapped_column(Float)
    nodata: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_alpha: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")      # band, mask, kompresi, peringatan
    processing_json: Mapped[str] = mapped_column(Text, default="{}")    # pipeline turunan tampilan & versi pustaka
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RasterAnalysisRun(Base):
    __tablename__ = "raster_analysis_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running','succeeded','failed')", name="ck_rrun_status"),
        Index("uq_rrun_running_per_raster", "raster_id", unique=True,
              sqlite_where=text("status = 'running'"), postgresql_where=text("status = 'running'")),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    raster_id: Mapped[str] = mapped_column(ForeignKey("raster_assets.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adapter: Mapped[str | None] = mapped_column(String(24), nullable=True)
    target: Mapped[str | None] = mapped_column(String(24), nullable=True)
    input_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MapDetection(Base):
    """Kandidat model pada raster: posisi piksel raster asal + poligon WGS84. Selalu dibuat pending."""
    __tablename__ = "map_detections"
    __table_args__ = (
        CheckConstraint("kind IN ('plant','check','gap')", name="ck_mdet_kind"),
        CheckConstraint("source IN ('model')", name="ck_mdet_source"),
        CheckConstraint("review_status IN ('pending','accepted','rejected')", name="ck_mdet_review"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_mdet_conf"),
        CheckConstraint("px_width > 0 AND px_height > 0", name="ck_mdet_box"),
        Index("ix_mdet_raster_review", "raster_id", "review_status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    raster_id: Mapped[str] = mapped_column(ForeignKey("raster_assets.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("raster_analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(8))
    px_left: Mapped[float] = mapped_column(Float)
    px_top: Mapped[float] = mapped_column(Float)
    px_width: Mapped[float] = mapped_column(Float)
    px_height: Mapped[float] = mapped_column(Float)
    center_x: Mapped[float] = mapped_column(Float)      # CRS asli raster
    center_y: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)           # pusat kotak, WGS84
    lat: Mapped[float] = mapped_column(Float)
    geometry_json: Mapped[str] = mapped_column(Text)    # GeoJSON Polygon WGS84 (4 sudut kotak)
    source: Mapped[str] = mapped_column(String(8), default="model")
    review_status: Mapped[str] = mapped_column(String(10), default="pending")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
