"""WALLACEA local inference bridge. Requires trusted, crop-specific weights."""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import warnings
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="WALLACEA inference bridge", version="0.1.0")
origins = [s.strip() for s in os.getenv("WALLACEA_ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080").split(",") if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=False)
MAX_BYTES = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 60_000_000
lock = threading.Lock()
model = None
loaded_path = None
log = logging.getLogger("wallacea")


def configured_path() -> Path | None:
    value = os.getenv("WALLACEA_MODEL_PATH", "").strip()
    return Path(value).expanduser().resolve() if value else None


@app.get("/health")
def health():
    path = configured_path()
    return {"status": "ok", "model_configured": bool(path and path.is_file()), "model_loaded": model is not None,
            "mode": "post-flight", "flight_control": False}


def infer(image: Image.Image):
    global model, loaded_path
    path = configured_path()
    if not path or not path.is_file():
        raise HTTPException(503, "Model tanaman belum tersedia. Atur WALLACEA_MODEL_PATH ke bobot lokal hasil pelatihan tim.")
    if path.suffix.lower() != ".pt":
        raise HTTPException(503, "Bridge versi ini menerima model deteksi Ultralytics .pt lokal.")
    try:
        mapping = json.loads(os.getenv("WALLACEA_LABEL_MAP_JSON", '{"plant":"plant","check":"check","gap":"gap"}'))
        if not isinstance(mapping, dict) or not mapping or any(not isinstance(k, str) or v not in ("plant", "check", "gap") for k, v in mapping.items()):
            raise ValueError()
        confidence = float(os.getenv("WALLACEA_CONFIDENCE", "0.35"))
        if not 0 <= confidence <= 1:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(503, "Konfigurasi label atau confidence backend tidak valid.")
    with lock:
        if model is None or loaded_path != str(path):
            try:
                from ultralytics import YOLO
                candidate = YOLO(str(path), task="detect")
                if getattr(candidate, "task", None) != "detect":
                    raise ValueError("detection model required")
                model, loaded_path = candidate, str(path)
            except ImportError:
                raise HTTPException(503, "Dependensi Ultralytics belum diinstal. Jalankan pip install -r requirements-ai.txt.")
            except Exception:
                log.exception("Model could not be loaded")
                raise HTTPException(503, "Model tidak dapat dimuat. Periksa bobot dan versi dependensi di server.")
        names = model.names.values() if isinstance(model.names, dict) else model.names
        if not any(str(name) in mapping for name in names):
            raise HTTPException(503, "Label model tidak cocok. Atur WALLACEA_LABEL_MAP_JSON sesuai nama kelas model tanaman Anda.")
        try:
            result = model.predict(image, conf=confidence, imgsz=1280, max_det=3000, verbose=False)[0]
        except Exception:
            log.exception("Inference failed")
            raise HTTPException(500, "Inferensi gagal. Periksa log dan kapasitas perangkat server.")
        width, height = image.size
        detections = []
        if result.boxes is not None:
            for box, score, cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                name = str(result.names[int(cls)])
                if name not in mapping:
                    continue
                x1, y1, x2, y2 = box
                x1, x2 = max(0.0, min(1.0, x1 / width)), max(0.0, min(1.0, x2 / width))
                y1, y2 = max(0.0, min(1.0, y1 / height)), max(0.0, min(1.0, y2 / height))
                if x2 <= x1 or y2 <= y1:
                    continue
                detections.append({"label": mapping[name], "confidence": float(score), "bbox": [x1, y1, x2-x1, y2-y1]})
        return {"image_width": width, "image_height": height, "model": path.stem, "detections": detections,
                "requires_review": True, "georeferenced": False}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Gunakan JPG, PNG, atau WebP.")
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Foto melebihi 20 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError()
                if source.width * source.height > 60_000_000:
                    raise ValueError()
                image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "Gambar rusak, format tidak sesuai, atau resolusinya terlalu besar.")
    return await run_in_threadpool(infer, image)
