"""Konfigurasi dari environment. Tidak ada file .env yang dimuat otomatis."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = API_ROOT / "var"
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
DEFAULT_LABEL_MAP = {"plant": "plant", "check": "check", "gap": "gap"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw else default


def _int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw else default


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

    model_path: Path | None = None
    model_id: str | None = None
    label_map_raw: str = ""
    confidence: float = 0.35
    imgsz: int = 1280
    inference_timeout_s: float = 120.0

    label_map: dict[str, str] = field(default_factory=dict)
    label_map_error: str | None = None

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


def load_settings(**overrides) -> Settings:
    data_dir = Path(overrides.pop("data_dir", None) or _env("WALLACEA_DATA_DIR") or DEFAULT_DATA_DIR).expanduser().resolve()
    database_url = overrides.pop("database_url", None) or _env("WALLACEA_DATABASE_URL") or f"sqlite:///{(data_dir / 'wallacea.db').as_posix()}"
    origins = [o.strip() for o in _env("WALLACEA_ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
    model_raw = _env("WALLACEA_MODEL_PATH")
    label_raw = _env("WALLACEA_LABEL_MAP_JSON")
    label_map, label_error = DEFAULT_LABEL_MAP.copy(), None
    if label_raw:
        try:
            parsed = json.loads(label_raw)
            if not isinstance(parsed, dict) or not parsed or any(
                not isinstance(k, str) or v not in ("plant", "check", "gap") for k, v in parsed.items()
            ):
                raise ValueError
            label_map = parsed
        except (ValueError, TypeError):
            label_map, label_error = {}, "WALLACEA_LABEL_MAP_JSON tidak valid."
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
        label_map=label_map,
        label_map_error=label_error,
    )
    values.update(overrides)
    return Settings(**values)
