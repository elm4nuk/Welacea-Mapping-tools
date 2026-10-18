from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import load_settings
from app.inference import DetectionOutput, Detector, DetectorInfo, RawDetection
from app.main import create_app

ORIGIN = "http://localhost:5173"


class FakeDetector(Detector):
    """Test double. Ini contract test pipeline, BUKAN uji akurasi model."""

    def __init__(self, detections=None, state="loaded", raises: Exception | None = None, sleep: float = 0,
                 model_id="fake-plant-detector", model_version="sha256:test0001"):
        self.detections = detections if detections is not None else [
            RawDetection("plant", [0.10, 0.10, 0.20, 0.20], 0.91, "tanaman"),
            RawDetection("plant", [0.50, 0.50, 0.10, 0.10], 0.55, "tanaman"),
            RawDetection("gap", [0.70, 0.20, 0.10, 0.10], 0.40, "kosong"),
        ]
        self.state, self.raises, self.sleep = state, raises, sleep
        self.model_id, self.model_version = model_id, model_version
        self.calls = 0
        self.last_size = None

    def info(self):
        return DetectorInfo(state=self.state, message="fake", model_id=self.model_id, model_version=self.model_version)

    def detect(self, image):
        self.calls += 1
        self.last_size = image.size
        if self.sleep:
            time.sleep(self.sleep)
        if self.raises:
            raise self.raises
        return DetectionOutput(self.model_id, self.model_version, list(self.detections), {"adapter": "fake"})


def png_bytes(w=100, h=80, color=(40, 120, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def webp_bytes(w=64, h=48) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 200, 10)).save(buf, format="WEBP")
    return buf.getvalue()


def jpeg_bytes(w=120, h=60, orientation: int | None = None, gps=False, taken: str | None = None) -> bytes:
    img = Image.new("RGB", (w, h), (90, 140, 70))
    img.paste((255, 0, 0), (0, 0, w // 4, h // 4))  # penanda pojok kiri atas sebelum rotasi
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if taken:
        exif.get_ifd(0x8769)[0x9003] = taken
    if gps:
        exif.get_ifd(0x8825)[1] = "S"
        exif.get_ifd(0x8825)[2] = (6.0, 10.0, 0.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes(), quality=90)
    return buf.getvalue()


@pytest.fixture
def data_dir(tmp_path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def make_client(data_dir):
    clients = []

    def _make(detector: Detector | None = None, raise_server_exceptions: bool = True, **overrides) -> TestClient:
        settings = load_settings(data_dir=data_dir, allowed_origins=[ORIGIN], **overrides)
        client = TestClient(create_app(settings, detector=detector), raise_server_exceptions=raise_server_exceptions)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for c in clients:
        try:
            c.__exit__(None, None, None)
        except Exception:
            pass


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


SURVEY = {"name": "Kebun Jagung Blok A", "crop_type": "Jagung", "location_label": "Desa Contoh",
          "survey_date": "2026-10-18", "notes": "Penerbangan pagi"}


def create_survey(client, **kw) -> dict:
    r = client.post("/api/v1/surveys", json={**SURVEY, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, survey_id, data: bytes | None = None, name="foto.png", mime="image/png"):
    return client.post(f"/api/v1/surveys/{survey_id}/photos", files={"file": (name, data or png_bytes(), mime)})


def upload_ok(client, survey_id, data: bytes | None = None, name="foto.png", mime="image/png") -> dict:
    r = upload(client, survey_id, data, name, mime)
    assert r.status_code == 201, r.text
    return r.json()["photo"]


def assert_error(r, status: int, code: str):
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) == {"error"}, body
    assert body["error"]["code"] == code, body
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["request_id"]
    return body["error"]
