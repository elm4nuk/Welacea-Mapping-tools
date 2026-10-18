"""Adapter Ultralytics diuji dengan modul `ultralytics` palsu. Tidak ada model nyata, bukan uji akurasi."""
import sys
import types

import pytest
from PIL import Image

from app.config import load_settings
from app.inference import ModelUnavailable, build_detector
from app.inference.base import UnconfiguredDetector
from app.inference.ultralytics_adapter import UltralyticsDetector


class Arr:
    def __init__(self, v): self.v = v
    def cpu(self): return self
    def tolist(self): return self.v


class FakeYOLO:
    names = {0: "sawit_muda", 1: "person"}
    task = "detect"
    loads = 0

    def __init__(self, path, task=None):
        FakeYOLO.loads += 1

    def predict(self, image, **kw):
        boxes = types.SimpleNamespace(xyxy=Arr([[10, 16, 30, 40], [0, 0, 5, 5], [50, 50, 50, 60]]),
                                      conf=Arr([0.87, 0.99, 0.5]), cls=Arr([0, 1, 0]))
        return [types.SimpleNamespace(names=self.names, boxes=boxes)]


@pytest.fixture
def fake_ultralytics(monkeypatch):
    mod = types.ModuleType("ultralytics")
    mod.YOLO = FakeYOLO
    mod.__spec__ = types.SimpleNamespace(name="ultralytics", loader=None, origin="fake", submodule_search_locations=None)
    monkeypatch.setitem(sys.modules, "ultralytics", mod)
    monkeypatch.setattr("importlib.util.find_spec", lambda name, *a: object() if name == "ultralytics" else None)
    FakeYOLO.loads = 0
    return mod


def test_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("WALLACEA_MODEL_PATH", raising=False)
    assert isinstance(build_detector(load_settings()), UnconfiguredDetector)


def test_missing_weights_is_error_state(tmp_path):
    det = UltralyticsDetector(tmp_path / "nope.pt", {"plant": "plant"})
    info = det.info()
    assert info.state == "error" and not info.available
    with pytest.raises(ModelUnavailable):
        det.detect(Image.new("RGB", (10, 10)))


def test_wrong_suffix(tmp_path):
    w = tmp_path / "m.onnx"
    w.write_bytes(b"x")
    assert UltralyticsDetector(w, {"plant": "plant"}).info().state == "error"


def test_maps_labels_and_normalizes(tmp_path, fake_ultralytics):
    w = tmp_path / "sawit.pt"
    w.write_bytes(b"weights")
    det = UltralyticsDetector(w, {"sawit_muda": "plant"})
    info = det.info()
    assert info.state == "configured" and info.model_id == "sawit" and info.model_version.startswith("sha256:")
    out = det.detect(Image.new("RGB", (100, 80)))
    assert det.info().state == "loaded"
    assert [d.label for d in out.detections] == ["plant"]  # person (tak dipetakan) & kotak degenerate dibuang
    d = out.detections[0]
    assert d.bbox == pytest.approx([0.1, 0.2, 0.2, 0.3]) and d.confidence == pytest.approx(0.87)
    assert d.model_label == "sawit_muda" and out.parameters["adapter"] == "ultralytics"
    det.detect(Image.new("RGB", (100, 80)))
    assert FakeYOLO.loads == 1  # dimuat sekali


def test_label_map_without_match_is_unavailable(tmp_path, fake_ultralytics):
    w = tmp_path / "coco.pt"
    w.write_bytes(b"weights")
    with pytest.raises(ModelUnavailable):
        UltralyticsDetector(w, {"plant": "plant"}).detect(Image.new("RGB", (10, 10)))


def test_invalid_label_map_env(monkeypatch, tmp_path):
    w = tmp_path / "m.pt"
    w.write_bytes(b"x")
    monkeypatch.setenv("WALLACEA_MODEL_PATH", str(w))
    monkeypatch.setenv("WALLACEA_LABEL_MAP_JSON", '{"car": "vehicle"}')
    det = build_detector(load_settings())
    assert det.info().state == "error" and "LABEL_MAP" in det.info().message


def test_api_with_adapter_end_to_end(tmp_path, fake_ultralytics, make_client):
    """Jalur API → adapter → kandidat pending, dengan modul palsu. Contract test, bukan akurasi."""
    from conftest import create_survey, upload_ok

    w = tmp_path / "sawit.pt"
    w.write_bytes(b"weights")
    c = make_client(detector=UltralyticsDetector(w, {"sawit_muda": "plant"}))
    assert c.get("/api/v1/health").json()["model"]["state"] == "configured"
    s = create_survey(c)
    p = upload_ok(c, s["id"])
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["run"]["model_version"].startswith("sha256:") and body["run"]["parameters"]["conf"] == 0.35
    assert [a["review_status"] for a in body["candidates"]] == ["pending"]
    assert c.get("/api/v1/health").json()["model"]["state"] == "loaded"
