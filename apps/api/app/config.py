"""Konfigurasi dari environment.

`load_settings()` hanya membaca os.environ (deterministik untuk test). Berkas `.env` dimuat oleh `python -m app`
(lihat app/envfile.py) atau oleh skrip PowerShell di `scripts/`, bukan di sini."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = API_ROOT / "var"
DEFAULT_SAMPLES_DIR = API_ROOT.parents[1] / "samples"   # <repo>/samples (catalog.json + foto contoh berlisensi)
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
DEFAULT_LABEL_MAP = {"plant": "plant", "check": "check", "gap": "gap"}
DETECTORS = ("", "none", "ultralytics", "deepforest", "simulation")
KINDS = ("plant", "check", "gap")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw else default


def _int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw else default


def _parse_simple_label_map(raw: str) -> dict[str, str] | None:
    """Bentuk tanpa tanda kutip: `jagung=plant,gulma=check`, atau JSON yang tanda kutipnya dibuang PowerShell 5.1
    saat memanggil program native (`{jagung:plant}`). None bila tidak berbentuk pasangan kunci/nilai."""
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        text, sep = text[1:-1], ":"
    else:
        sep = "="
    if '"' in text or sep not in text:
        return None
    out = {}
    for part in re.split(r"[,;]", text):
        key, found, value = part.partition(sep)
        if not found or not key.strip():
            return None
        out[key.strip()] = value.strip()
    return out


def parse_label_map(raw: str) -> tuple[dict[str, str], str | None]:
    """WALLACEA_LABEL_MAP_JSON → (peta, pesan_error). Kosong → peta bawaan. Pesan menjelaskan apa yang salah.

    Menerima JSON (`{"jagung":"plant"}`) atau bentuk sederhana `jagung=plant,gulma=check` (aman di semua shell)."""
    if not raw.strip():
        return DEFAULT_LABEL_MAP.copy(), None
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        parsed = _parse_simple_label_map(raw)
        if parsed is None:
            return {}, (f"WALLACEA_LABEL_MAP_JSON bukan JSON yang valid ({exc.msg}, kolom {exc.colno}). "
                        "Contoh: {\"nama_kelas_model\": \"plant\"} atau bentuk sederhana nama_kelas_model=plant.")
    if not isinstance(parsed, dict) or not parsed:
        return {}, "WALLACEA_LABEL_MAP_JSON harus objek JSON tidak kosong, mis. {\"nama_kelas_model\": \"plant\"}."
    bad = [f"{k!r}: {v!r}" for k, v in parsed.items() if not isinstance(k, str) or not k or v not in KINDS]
    if bad:
        return {}, (f"WALLACEA_LABEL_MAP_JSON: nilai harus salah satu {list(KINDS)}; salah: {', '.join(bad[:5])}. "
                    "Kunci = nama kelas model (lihat check-model.ps1), nilai = jenis penanda WALLACEA.")
    return parsed, None


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    allowed_origins: list[str]
    auto_migrate: bool = True

    max_upload_bytes: int = 20 * 1024 * 1024
    max_pixels: int = 60_000_000
    max_annotations_per_photo: int = 3000
    max_detection_payload_bytes: int = 5 * 1024 * 1024
    max_backup_bytes: int = 100 * 1024 * 1024
    thumbnail_max_side: int = 512

    # Mapping (revisi 5). Batas raster GeoTIFF impor & batas lahan; semua dapat diatur lewat env.
    max_raster_bytes: int = 1024 * 1024 * 1024        # 1 GiB berkas asli
    max_raster_pixels: int = 400_000_000              # mis. 20000 × 20000
    max_raster_footprint_km2: float = 2500.0           # cakupan > ini hampir pasti georeferensi salah untuk drone
    max_field_vertices: int = 20_000
    max_field_import_bytes: int = 5 * 1024 * 1024
    max_map_detections: int = 50_000                  # per raster
    raster_analysis_timeout_s: float = 1800.0

    # Detector: "" (otomatis: ultralytics bila MODEL_PATH ada, selain itu manual) | ultralytics | deepforest | none
    #           | simulation (KHUSUS development: kotak buatan deterministik, BUKAN AI; tidak pernah otomatis)
    detector: str = ""
    model_path: Path | None = None
    model_id: str | None = None
    label_map_raw: str = ""
    confidence: float = 0.35
    imgsz: int = 1280
    inference_timeout_s: float = 120.0
    device: str = "cpu"                 # deepforest: cpu | cuda | auto (Ultralytics memilih sendiri)
    patch_size: int = 400               # deepforest predict_tile
    patch_overlap: float = 0.05
    model_preload: bool = False         # muat model saat startup (thread latar), bukan saat request pertama
    samples_dir: Path = DEFAULT_SAMPLES_DIR  # foto contoh berlisensi (GET /samples); tidak ada → katalog kosong

    label_map: dict[str, str] = field(default_factory=dict)
    label_map_error: str | None = None
    config_error: str | None = None

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_settings(**overrides) -> Settings:
    data_dir = Path(overrides.pop("data_dir", None) or _env("WALLACEA_DATA_DIR") or DEFAULT_DATA_DIR).expanduser().resolve()
    database_url = overrides.pop("database_url", None) or _env("WALLACEA_DATABASE_URL") or f"sqlite:///{(data_dir / 'wallacea.db').as_posix()}"
    origins = [o.strip() for o in _env("WALLACEA_ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
    model_raw = _env("WALLACEA_MODEL_PATH")
    label_raw = _env("WALLACEA_LABEL_MAP_JSON")
    label_map, label_error = parse_label_map(label_raw)
    detector = _env("WALLACEA_DETECTOR").lower()
    device = _env("WALLACEA_DEVICE", "cpu").lower()
    config_error = None
    if detector not in DETECTORS:
        config_error = f"WALLACEA_DETECTOR harus salah satu {sorted(d for d in DETECTORS if d)} (atau kosong)."
    elif detector in ("ultralytics", "deepforest") and not model_raw:
        config_error = (f"WALLACEA_DETECTOR={detector} butuh WALLACEA_MODEL_PATH (path ke bobot .pt / folder model lokal). "
                        "Path diisi di environment atau lewat scripts\run-with-model.ps1 -ModelPath, bukan diketik "
                        "sendirian di terminal.")
    values = dict(
        data_dir=data_dir,
        database_url=database_url,
        allowed_origins=origins,
        auto_migrate=_env("WALLACEA_AUTO_MIGRATE", "true").lower() not in ("0", "false", "no"),
        model_path=Path(model_raw).expanduser().resolve() if model_raw else None,
        model_id=_env("WALLACEA_MODEL_ID") or None,
        label_map_raw=label_raw,
        confidence=_float("WALLACEA_CONFIDENCE", 0.35),
        imgsz=_int("WALLACEA_IMGSZ", 1280),
        inference_timeout_s=_float("WALLACEA_INFERENCE_TIMEOUT_S", 120.0),
        detector=detector,
        device=device,
        patch_size=_int("WALLACEA_PATCH_SIZE", 400),
        patch_overlap=_float("WALLACEA_PATCH_OVERLAP", 0.05),
        model_preload=_env("WALLACEA_MODEL_PRELOAD", "false").lower() in ("1", "true", "yes"),
        samples_dir=Path(_env("WALLACEA_SAMPLES_DIR") or DEFAULT_SAMPLES_DIR).expanduser().resolve(),
        max_raster_bytes=_int("WALLACEA_MAX_RASTER_BYTES", 1024 * 1024 * 1024),
        max_raster_pixels=_int("WALLACEA_MAX_RASTER_PIXELS", 400_000_000),
        raster_analysis_timeout_s=_float("WALLACEA_RASTER_ANALYSIS_TIMEOUT_S", 1800.0),
        label_map=label_map,
        label_map_error=label_error,
        config_error=config_error,
    )
    values.update(overrides)
    return Settings(**values)
