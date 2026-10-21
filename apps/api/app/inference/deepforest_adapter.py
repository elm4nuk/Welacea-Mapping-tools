"""Adapter DeepForest (RetinaNet tajuk pohon, weecology). Kode DeepForest: MIT. Bobot `weecology/deepforest-tree`:
MIT (model card Hugging Face). Dilatih pada citra RGB PESAWAT NEON ±10 cm/px — hasilnya KANDIDAT TAJUK POHON,
bukan deteksi semua tanaman pertanian.

Diverifikasi terhadap source deepforest 2.1.0 (bukan contoh API lama):
- `main.deepforest(config_args=...)` langsung memuat `config.model.name` di konstruktor; nilai default
  ('weecology/deepforest-tree'@main) akan MENGUNDUH dari Hub. Adapter ini selalu mengisi `model.name` dengan
  FOLDER LOKAL hasil `scripts/download_deepforest.py` dan menyalakan HF_HUB_OFFLINE saat memuat → tidak ada
  unduhan di tengah request.
- Input array dipakai apa adanya (`np.array(image)`); bila diberi path, DeepForest membaca `PIL.convert("RGB")`
  TANPA orientasi EXIF. Jadi model mengharapkan RGB (docstring `predict_tile` yang menyebut BGR sudah usang),
  dan adapter mengirim array RGB dari gambar yang SUDAH diorientasikan API — sama dengan editor.
- Keluaran: DataFrame `xmin, ymin, xmax, ymax, label, score` dalam piksel gambar input.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import logging
import os
import threading
import warnings
from pathlib import Path

from PIL import Image

from .base import (DetectionOutput, Detector, DetectorInfo, InferenceFailed, ModelUnavailable, RawDetection,
                   normalize_xyxy)

log = logging.getLogger("wallacea.inference")

DEFAULT_LABEL_MAP = {"Tree": "plant"}   # label asli model → kind kontrak; eksplisit, dapat ditimpa env
TARGET_LABEL = "Kandidat tajuk pohon (DeepForest pretrained)"
LIMITATIONS = (
    "Model pretrained tajuk pohon dari citra pesawat NEON ±10 cm/px (hutan AS), bukan model tanaman pertanian.",
    "Belum dievaluasi pada foto K919 MAX; ukuran objek bergantung ketinggian terbang dan resolusi.",
    "Tanaman semusim kecil (jagung muda, padi, sayuran) umumnya tidak cocok untuk model ini.",
)
MANIFEST = "wallacea_model.json"
WEIGHTS = "model.safetensors"


def file_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()[:16]


class DeepForestDetector(Detector):
    def __init__(self, model_dir: Path, label_map: dict[str, str] | None = None, confidence: float = 0.35,
                 device: str = "cpu", patch_size: int = 400, patch_overlap: float = 0.05,
                 iou_threshold: float = 0.15, max_det: int = 3000, model_id: str | None = None,
                 log_dir: Path | None = None, config_error: str | None = None):
        self.model_dir = model_dir
        self.label_map = label_map or DEFAULT_LABEL_MAP
        self.confidence = confidence
        self.device = device
        self.patch_size = patch_size
        self.patch_overlap = patch_overlap
        self.iou_threshold = iou_threshold
        self.max_det = max_det
        self.log_dir = log_dir
        self.config_error = config_error
        self._manifest = self._read_manifest()
        self.model_id = model_id or self._manifest.get("repo_id") or model_dir.name
        self._lock = threading.Lock()
        self._model = None
        self._fp_cache: tuple[tuple[int, int], str] | None = None

    # ------------------------------------------------------------ status
    def _read_manifest(self) -> dict:
        try:
            return json.loads((self.model_dir / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _config_problem(self) -> tuple[str, str] | None:
        """(diagnostic_code, pesan) bila model pasti tidak bisa dipakai."""
        if self.config_error:
            return "LABEL_MAP_INVALID", self.config_error
        if not 0 <= self.confidence <= 1:
            return "DETECTOR_CONFIG_INVALID", "WALLACEA_CONFIDENCE harus 0–1."
        if self.device not in ("cpu", "cuda", "auto"):
            return "DETECTOR_CONFIG_INVALID", "WALLACEA_DEVICE harus cpu, cuda, atau auto."
        if not 0 <= self.patch_overlap < 1 or self.patch_size < 64:
            return "DETECTOR_CONFIG_INVALID", "Patch DeepForest tidak valid (patch_size ≥ 64, 0 ≤ overlap < 1)."
        if not self.model_dir.is_dir():
            return "MODEL_FILE_NOT_FOUND", f"Folder model DeepForest tidak ditemukan: {self.model_dir.name}. Jalankan scripts/download_deepforest.py."
        if not (self.model_dir / WEIGHTS).is_file() or not (self.model_dir / "config.json").is_file():
            return "MODEL_FILES_INCOMPLETE", "Folder model DeepForest tidak lengkap (config.json/model.safetensors). Unduh ulang."
        missing = [n for n in self._manifest.get("aux_files", {}) if not (self.model_dir / n).is_file()]
        if not self._manifest.get("aux_files") or missing:
            return "MODEL_FILES_INCOMPLETE", ("Berkas pendukung (backbone torchvision) belum ada di folder model; jalankan ulang "
                    "scripts/download_deepforest.py. API tidak mengunduh saat analisis.")
        if importlib.util.find_spec("deepforest") is None:
            return "DEPENDENCY_MISSING", "Dependensi DeepForest belum terpasang (pip install -r requirements-deepforest.txt)."
        return None

    def _version(self) -> str | None:
        weights = self.model_dir / WEIGHTS
        try:
            st = weights.stat()
        except OSError:
            return None
        sig = (st.st_size, st.st_mtime_ns)
        if not self._fp_cache or self._fp_cache[0] != sig:
            self._fp_cache = (sig, file_fingerprint(weights))
        return self._fp_cache[1]

    def info(self) -> DetectorInfo:
        meta = dict(adapter="deepforest", target="tree_crown", target_label=TARGET_LABEL, device=self.device,
                    limitations=LIMITATIONS)
        problem = self._config_problem()
        if problem:
            return DetectorInfo(state="error", message=problem[1], model_id=self.model_id,
                                diagnostic_code=problem[0], **meta)
        version = self._version()
        if self._model is not None:
            return DetectorInfo(state="loaded", message="Model DeepForest termuat di memori.", model_id=self.model_id,
                                model_version=version, **meta)
        return DetectorInfo(state="configured", message="Bobot DeepForest lokal ditemukan; dimuat saat analisis pertama.",
                            model_id=self.model_id, model_version=version, **meta)

    # ------------------------------------------------------------ inference
    def _accelerator(self) -> str:
        if self.device == "auto":
            import torch
            return "gpu" if torch.cuda.is_available() else "cpu"
        return "gpu" if self.device == "cuda" else "cpu"

    def _load(self):
        if self._model is not None:
            return self._model
        problem = self._config_problem()
        if problem:
            raise ModelUnavailable(problem[1], problem[0])
        prev = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "TORCH_HOME")}
        os.environ["HF_HUB_OFFLINE"] = "1"          # jaminan: tidak mengunduh dari Hub saat memuat
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["TORCH_HOME"] = str(self.model_dir / "torch_home")   # backbone torchvision lokal (sudah dicek ada)
        try:
            for name in ("lightning.pytorch", "pytorch_lightning", "lightning.fabric"):
                logging.getLogger(name).setLevel(logging.WARNING)   # sembunyikan "GPU available"/tips di log server
            from deepforest import main as df_main
            log_root = str(self.log_dir or (self.model_dir / "_logs"))
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                warnings.simplefilter("ignore")
                model = df_main.deepforest(config_args={
                    # name = folder lokal → from_pretrained membaca disk; revision wajib str di config DeepForest
                    "model": {"name": str(self.model_dir), "revision": self._manifest.get("revision") or "local"},
                    "score_thresh": float(self.confidence),
                    "accelerator": self._accelerator(), "devices": 1, "workers": 0, "log_root": log_root,
                })
                model.create_trainer(logger=False, enable_progress_bar=False, enable_model_summary=False)
            model.model.eval()
        except Exception as exc:  # noqa: BLE001
            log.exception("DeepForest model could not be loaded")
            raise ModelUnavailable("Model DeepForest tidak dapat dimuat. Periksa folder bobot dan versi dependensi.",
                                   "MODEL_LOAD_FAILED") from exc
        finally:
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        labels = set(model.label_dict)
        if not labels & set(self.label_map):
            raise ModelUnavailable(f"Label model {sorted(labels)} tidak ada di WALLACEA_LABEL_MAP_JSON.",
                                   "LABEL_MAP_MISMATCH")
        self._model = model
        return model

    def preload(self) -> None:
        with self._lock:
            self._load()

    def _predict(self, model, image: Image.Image):
        import numpy as np

        arr = np.asarray(image.convert("RGB"), dtype=np.float32)   # HWC, RGB, 0–255 (DeepForest menormalkan sendiri)
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            if max(image.size) <= self.patch_size:
                return model.predict_image(image=arr), "image"
            return model.predict_tile(image=arr, patch_size=self.patch_size, patch_overlap=self.patch_overlap,
                                      iou_threshold=self.iou_threshold, dataloader_strategy="single"), "tile"

    def detect(self, image: Image.Image) -> DetectionOutput:
        with self._lock:
            model = self._load()
            try:
                df, mode = self._predict(model, image)
            except Exception as exc:  # noqa: BLE001
                log.exception("DeepForest inference failed")
                raise InferenceFailed("Inferensi DeepForest gagal. Periksa log server dan kapasitas perangkat.") from exc
        width, height = image.size
        out: list[RawDetection] = []
        if df is not None and len(df):
            rows = df.sort_values("score", ascending=False).head(self.max_det)
            for x1, y1, x2, y2, label, score in zip(rows.xmin, rows.ymin, rows.xmax, rows.ymax, rows.label, rows.score):
                name = str(label)
                if name not in self.label_map or float(score) < self.confidence:
                    continue
                bbox = normalize_xyxy(float(x1), float(y1), float(x2), float(y2), width, height)
                if bbox is None:
                    continue
                out.append(RawDetection(label=self.label_map[name], bbox=bbox,
                                        confidence=max(0.0, min(1.0, float(score))), model_label=name))
        return DetectionOutput(
            model_id=self.model_id, model_version=self._version(), detections=out,
            parameters={"adapter": "deepforest", "target": "tree_crown", "mode": mode, "conf": self.confidence,
                        "patch_size": self.patch_size, "patch_overlap": self.patch_overlap,
                        "iou_threshold": self.iou_threshold, "device": self.device,
                        "hf_repo": self._manifest.get("repo_id"), "hf_revision": self._manifest.get("revision"),
                        "deepforest_version": _pkg_version("deepforest")},
        )


def _pkg_version(name: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:  # noqa: BLE001
        return None
