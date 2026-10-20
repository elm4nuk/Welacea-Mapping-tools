"""Detector SIMULASI — khusus development, BUKAN AI.

Tujuan satu-satunya: menguji alur UI end-to-end (analisis → kandidat pending → terima/tolak → simpan → laporan)
tanpa bobot model. Kotak dibuat deterministik dari sidik jari piksel gambar (gambar sama → kotak sama), tidak
melihat isi tanaman sama sekali.

Aturan:
- Hanya aktif bila WALLACEA_DETECTOR=simulation diset eksplisit. Tidak pernah menjadi fallback otomatis;
  tanpa konfigurasi API tetap mode manual (503 MODEL_NOT_CONFIGURED).
- model_id `simulation-not-ai`, adapter/target `simulation`, model_label setiap kandidat "SIMULASI — BUKAN AI".
- confidence = null: tidak ada skor model yang bisa disalahartikan sebagai keyakinan.
- Kandidat tetap source=model, review_status=pending seperti kandidat model lain.
"""
from __future__ import annotations

import hashlib
import logging
import math
import random

from PIL import Image

from .base import DetectionOutput, Detector, DetectorInfo, RawDetection

MODEL_ID = "simulation-not-ai"
MODEL_VERSION = "simulation-v1"
LABEL = "SIMULASI — BUKAN AI"
MESSAGE = ("SIMULASI — BUKAN AI. Mode development (WALLACEA_DETECTOR=simulation): kotak kandidat dibuat deterministik "
           "dari sidik jari gambar, bukan deteksi tanaman. Jangan dipakai untuk keputusan lapangan.")
LIMITATIONS = (
    "SIMULASI — BUKAN AI: kandidat tidak berasal dari model dan tidak melihat tanaman di foto.",
    "Hanya untuk menguji alur aplikasi (analisis, review, simpan, laporan). Jangan dipakai untuk keputusan lapangan.",
    "Matikan dengan menjalankan API tanpa WALLACEA_DETECTOR=simulation.",
)
NOTICE = ("SIMULASI — BUKAN AI. Kandidat ini dibuat untuk menguji alur aplikasi, bukan hasil deteksi tanaman. "
          "Kandidat tetap pending dan tidak dihitung sampai ditinjau; jangan dipakai untuk keputusan lapangan.")

log = logging.getLogger("wallacea.inference")


def image_seed(image: Image.Image) -> int:
    """Sidik jari stabil: ukuran + piksel thumbnail 32×32 RGB (tidak bergantung format/EXIF berkas)."""
    small = image.convert("RGB").resize((32, 32), Image.Resampling.BILINEAR)
    h = hashlib.sha256(f"{image.width}x{image.height}".encode() + small.tobytes())
    return int.from_bytes(h.digest()[:8], "big")


class SimulationDetector(Detector):
    def __init__(self, min_boxes: int = 3, max_boxes: int = 8):
        self.min_boxes, self.max_boxes = min_boxes, max_boxes
        log.warning("WALLACEA_DETECTOR=simulation aktif: hasil analisis adalah SIMULASI — BUKAN AI.")

    def info(self) -> DetectorInfo:
        return DetectorInfo(state="loaded", message=MESSAGE, model_id=MODEL_ID, model_version=MODEL_VERSION,
                            adapter="simulation", target="simulation", target_label=LABEL, device="cpu",
                            limitations=LIMITATIONS, mode="simulation", diagnostic_code="SIMULATION_ACTIVE")

    def detect(self, image: Image.Image) -> DetectionOutput:
        seed = image_seed(image)
        rng = random.Random(seed)
        out = []
        for _ in range(rng.randint(self.min_boxes, self.max_boxes)):
            w, h = rng.uniform(0.05, 0.15), rng.uniform(0.05, 0.15)
            left, top = rng.uniform(0.0, 1.0 - w), rng.uniform(0.0, 1.0 - h)
            bbox = [math.floor(v * 1e6) / 1e6 for v in (left, top, w, h)]   # dibulatkan ke bawah: tetap di dalam 0–1
            out.append(RawDetection(label="plant", bbox=bbox, confidence=None, model_label=LABEL))
        return DetectionOutput(MODEL_ID, MODEL_VERSION, out,
                               {"adapter": "simulation", "target": "simulation", "simulation": True,
                                "seed": f"{seed:016x}", "not_ai": True})
