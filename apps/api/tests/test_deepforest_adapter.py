"""Adapter DeepForest. Bagian 1 memakai modul `deepforest` PALSU (kontrak pipeline: pemuatan lokal tanpa unduhan,
RGB terorientasi, pemetaan label, format bbox, pending) — BUKAN uji akurasi. Bagian 2 menjalankan model ASLI
bila bobot sudah diunduh (scripts/download_deepforest.py); dilewati bila tidak ada."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from app.config import load_settings
from app.inference import build_detector
from app.inference.base import normalize_xyxy
from app.inference.deepforest_adapter import DeepForestDetector
from app.inference.factory import MisconfiguredDetector
from app.inference.base import UnconfiguredDetector
from app.inference.ultralytics_adapter import UltralyticsDetector
from conftest import create_survey

AUX = "torch_home/hub/checkpoints/resnet50-0676ba61.pth"
# Adapter mengubah gambar ke array numpy (numpy ikut terpasang bersama deepforest; tidak ada di lock API minimum).
needs_numpy = pytest.mark.skipif(importlib.util.find_spec("numpy") is None, reason="numpy tidak terpasang (venv API minimum)")


def model_dir(tmp_path, aux=True) -> Path:
    d = tmp_path / "deepforest-tree"
    d.mkdir()
    (d / "config.json").write_text('{"label_dict": {"Tree": 0}}')
    (d / "model.safetensors").write_bytes(b"bukan-bobot-asli")
    (d / "wallacea_model.json").write_text(json.dumps({
        "repo_id": "weecology/deepforest-tree", "revision": "cc21436bc5d572dde8ff5f93c1e71a32f563cace",
        "aux_files": {AUX: {"sha256": "x"}}}))
    if aux:
        (d / AUX).parent.mkdir(parents=True)
        (d / AUX).write_bytes(b"x")
    return d


class FakeFrame:
    """Subset DataFrame yang dipakai adapter (kolom xmin..score, sort_values, head)."""

    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def sort_values(self, col, ascending=True):
        return FakeFrame(sorted(self.rows, key=lambda r: r[col], reverse=not ascending))

    def head(self, n):
        return FakeFrame(self.rows[:n])

    def __getattr__(self, name):
        return [r[name] for r in self.rows]


class FakeDeepForest:
    """Meniru deepforest.main.deepforest 2.1.0: konstruktor memuat config.model.name. Mencari piksel MERAH pada
    array RGB (kanal 0) — bila adapter mengirim BGR, kotak tidak ditemukan."""
    instances: list = []
    env_seen: list = []

    def __init__(self, config_args=None):
        FakeDeepForest.instances.append(self)
        FakeDeepForest.env_seen.append({k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TORCH_HOME")})
        self.config_args = config_args
        self.label_dict = {"Tree": 0}
        self.model = types.SimpleNamespace(eval=lambda: None)
        self.calls = []

    def create_trainer(self, **kw):
        self.trainer_kw = kw

    def _boxes(self, arr):
        import numpy as np
        red = (arr[..., 0] > 200) & (arr[..., 1] < 60) & (arr[..., 2] < 60)
        ys, xs = np.nonzero(red)
        rows = [{"xmin": float(xs.min()), "ymin": float(ys.min()), "xmax": float(xs.max() + 1),
                 "ymax": float(ys.max() + 1), "label": "Tree", "score": 0.9}] if len(xs) else []
        rows.append({"xmin": 0.0, "ymin": 0.0, "xmax": 5.0, "ymax": 5.0, "label": "Shrub", "score": 0.99})  # tak dipetakan
        rows.append({"xmin": 1.0, "ymin": 1.0, "xmax": 9.0, "ymax": 9.0, "label": "Tree", "score": 0.1})   # < conf
        return FakeFrame(rows)

    def predict_image(self, image=None, path=None):
        assert path is None and image.dtype.name == "float32" and image.shape[-1] == 3
        self.calls.append(("image", image.shape))
        return self._boxes(image)

    def predict_tile(self, image=None, path=None, patch_size=400, patch_overlap=0.05, iou_threshold=0.15,
                     dataloader_strategy="single"):
        assert path is None
        self.calls.append(("tile", image.shape, patch_size, patch_overlap))
        return self._boxes(image)


@pytest.fixture
def fake_deepforest(monkeypatch):
    pkg = types.ModuleType("deepforest")
    main = types.ModuleType("deepforest.main")
    main.deepforest = FakeDeepForest
    pkg.main = main
    monkeypatch.setitem(sys.modules, "deepforest", pkg)
    monkeypatch.setitem(sys.modules, "deepforest.main", main)
    real = __import__("importlib.util").util.find_spec
    monkeypatch.setattr("importlib.util.find_spec", lambda n, *a: object() if n == "deepforest" else real(n, *a))
    FakeDeepForest.instances, FakeDeepForest.env_seen = [], []
    return FakeDeepForest


def oriented_jpeg() -> bytes:
    """Mentah 400×200 + EXIF orientasi 6 (putar 90° searah jarum jam). Kotak merah mentah x∈[300,360) y∈[20,60)
    → setelah orientasi (200×400): x∈[140,180) y∈[300,360)."""
    img = Image.new("RGB", (400, 200), (30, 100, 30))
    img.paste((255, 0, 0), (300, 20, 360, 60))
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=100, subsampling=0, exif=exif.tobytes())
    return buf.getvalue()


# ------------------------------------------------------------------ konfigurasi
def test_detector_selection_by_config(monkeypatch, tmp_path):
    for k in ("WALLACEA_DETECTOR", "WALLACEA_MODEL_PATH", "WALLACEA_LABEL_MAP_JSON"):
        monkeypatch.delenv(k, raising=False)
    assert isinstance(build_detector(load_settings(data_dir=tmp_path)), UnconfiguredDetector)
    monkeypatch.setenv("WALLACEA_MODEL_PATH", str(tmp_path / "m.pt"))
    assert isinstance(build_detector(load_settings(data_dir=tmp_path)), UltralyticsDetector)   # perilaku lama
    monkeypatch.setenv("WALLACEA_DETECTOR", "none")
    assert isinstance(build_detector(load_settings(data_dir=tmp_path)), UnconfiguredDetector)
    monkeypatch.setenv("WALLACEA_DETECTOR", "deepforest")
    monkeypatch.setenv("WALLACEA_MODEL_PATH", str(model_dir(tmp_path)))
    det = build_detector(load_settings(data_dir=tmp_path))
    assert isinstance(det, DeepForestDetector) and det.label_map == {"Tree": "plant"} and det.device == "cpu"
    monkeypatch.setenv("WALLACEA_DETECTOR", "yolo")
    bad = build_detector(load_settings(data_dir=tmp_path))
    assert isinstance(bad, MisconfiguredDetector) and bad.info().state == "error"
    monkeypatch.setenv("WALLACEA_DETECTOR", "deepforest")
    monkeypatch.delenv("WALLACEA_MODEL_PATH")
    assert "WALLACEA_MODEL_PATH" in build_detector(load_settings(data_dir=tmp_path)).info().message


def test_normalize_xyxy_clips_and_rejects_empty():
    assert normalize_xyxy(10, 20, 30, 60, 100, 200) == pytest.approx([0.1, 0.1, 0.2, 0.2])
    assert normalize_xyxy(-5, -5, 50, 250, 100, 200) == pytest.approx([0.0, 0.0, 0.5, 1.0])
    assert normalize_xyxy(120, 0, 130, 10, 100, 200) is None


# ------------------------------------------------------------------ status jujur
def test_missing_weights_or_aux_file_is_error_without_download(tmp_path, make_client):
    det = DeepForestDetector(tmp_path / "belum-diunduh")
    info = det.info()
    assert info.state == "error" and info.adapter == "deepforest" and info.target == "tree_crown"
    assert "download_deepforest.py" in info.message
    assert "tidak mengunduh" in DeepForestDetector(model_dir(tmp_path, aux=False)).info().message
    c = make_client(detector=det)
    h = c.get("/api/v1/health").json()["model"]
    assert h["adapter"] == "deepforest" and h["target_label"].startswith("Kandidat tajuk pohon") and h["limitations"]
    s = create_survey(c)
    from conftest import png_bytes
    p = c.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": ("a.png", png_bytes(), "image/png")}).json()["photo"]
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"] == []        # tidak ada run palsu


# ------------------------------------------------------------------ pipeline dengan model palsu
@needs_numpy
def test_loads_local_folder_once_offline_and_maps_oriented_rgb_boxes(tmp_path, fake_deepforest, make_client):
    d = model_dir(tmp_path)
    det = DeepForestDetector(d, confidence=0.35, patch_size=400, log_dir=tmp_path / "logs")
    c = make_client(detector=det)
    s = create_survey(c)
    p = c.post(f"/api/v1/surveys/{s['id']}/photos",
               files={"file": ("DJI_0001.JPG", oriented_jpeg(), "image/jpeg")}).json()["photo"]
    assert (p["width"], p["height"]) == (200, 400)
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 201, r.text
    body = r.json()
    # konstruktor DeepForest diberi FOLDER LOKAL (bukan repo Hub) dan dimuat dalam mode offline
    inst = fake_deepforest.instances[0]
    assert inst.config_args["model"]["name"] == str(d)
    assert inst.config_args["accelerator"] == "cpu" and inst.config_args["score_thresh"] == 0.35
    assert fake_deepforest.env_seen[0] == {"HF_HUB_OFFLINE": "1", "TORCH_HOME": str(d / "torch_home")}
    assert os.environ.get("TORCH_HOME") != str(d / "torch_home")                     # env dipulihkan setelah muat
    assert inst.calls[0][0] == "image" and inst.calls[0][1] == (400, 200, 3)        # HWC terorientasi
    # satu kandidat: 'Shrub' tidak dipetakan, skor 0.1 < confidence
    cands = body["candidates"]
    assert len(cands) == 1
    a = cands[0]
    assert a["bbox"] == pytest.approx([0.7, 0.75, 0.2, 0.15], abs=0.01)                # = posisi di editor
    assert (a["kind"], a["model_label"], a["source"], a["review_status"]) == ("plant", "Tree", "model", "pending")
    run = body["run"]
    assert run["parameters"]["adapter"] == "deepforest" and run["parameters"]["target"] == "tree_crown"
    assert run["model_id"] == "weecology/deepforest-tree" and run["model_version"].startswith("sha256:")
    assert c.get(f"/api/v1/photos/{p['id']}").json()["counts"]["plant_accepted"] == 0  # pending tidak dihitung
    # model tidak dimuat ulang pada request berikutnya
    c.post(f"/api/v1/photos/{p['id']}/analyze", json={"on_existing": "replace_pending"})
    assert len(fake_deepforest.instances) == 1
    assert c.get("/api/v1/health").json()["model"]["state"] == "loaded"


@needs_numpy
def test_large_images_use_tiles(tmp_path, fake_deepforest):
    det = DeepForestDetector(model_dir(tmp_path), patch_size=400, patch_overlap=0.1)
    img = Image.new("RGB", (1200, 900), (30, 100, 30))
    img.paste((255, 0, 0), (600, 450, 660, 510))
    out = det.detect(img)
    call = fake_deepforest.instances[0].calls[0]
    assert call == ("tile", (900, 1200, 3), 400, 0.1) and out.parameters["mode"] == "tile"
    assert out.detections[0].bbox == pytest.approx([0.5, 0.5, 0.05, 60 / 900])


def test_load_failure_is_model_unavailable(tmp_path, monkeypatch, fake_deepforest, make_client):
    def boom(config_args=None):
        raise RuntimeError("bobot rusak")
    monkeypatch.setattr(sys.modules["deepforest.main"], "deepforest", boom)
    c = make_client(detector=DeepForestDetector(model_dir(tmp_path)))
    s = create_survey(c)
    from conftest import png_bytes
    p = c.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": ("a.png", png_bytes(), "image/png")}).json()["photo"]
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 503 and r.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    run = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["status"] == "failed" and run["error_code"] == "MODEL_UNAVAILABLE"


def test_preload_on_startup(tmp_path, fake_deepforest, make_client):
    import time
    c = make_client(detector=DeepForestDetector(model_dir(tmp_path)), model_preload=True)
    for _ in range(50):
        if c.get("/api/v1/health").json()["model"]["state"] == "loaded":
            break
        time.sleep(0.05)
    assert c.get("/api/v1/health").json()["model"]["state"] == "loaded" and len(fake_deepforest.instances) == 1


# ------------------------------------------------------------------ model ASLI (opsional)
REAL_DIR = Path(os.getenv("WALLACEA_TEST_DEEPFOREST_DIR", Path(__file__).resolve().parents[1] / "var/models/deepforest-tree"))


@pytest.mark.skipif(not (REAL_DIR / "wallacea_model.json").is_file(), reason="bobot DeepForest belum diunduh")
def test_real_deepforest_inference_on_packaged_sample(tmp_path, make_client):
    """INFERENSI NYATA pada sampel resmi DeepForest (OSBS_029.png, NEON). Smoke test format & alur — bukan akurasi."""
    pytest.importorskip("deepforest")
    sample = Path(__file__).resolve().parents[3] / "samples" / "deepforest-neon" / "OSBS_029.png"
    if not sample.is_file():
        from deepforest import get_data
        sample = Path(get_data("OSBS_029.png"))
    det = DeepForestDetector(REAL_DIR, confidence=0.35, log_dir=tmp_path / "logs")
    c = make_client(detector=det)
    s = create_survey(c)
    p = c.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": (sample.name, sample.read_bytes(), "image/png")}).json()["photo"]
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 201, r.text
    cands = r.json()["candidates"]
    assert cands and all(a["review_status"] == "pending" and a["model_label"] == "Tree" for a in cands)
    assert all(0 <= v <= 1 for a in cands for v in a["bbox"]) and all(0.35 <= a["confidence"] <= 1 for a in cands)
    assert r.json()["run"]["model_version"] == json.loads((REAL_DIR / "wallacea_model.json").read_text())["model_version"]
