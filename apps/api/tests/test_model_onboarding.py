"""Revisi 4: onboarding model (diagnostik), mode simulasi development, pemuat .env, dan scripts/check_model.py.

Modul `ultralytics` di sini PALSU (tanpa PyTorch). Ini contract test alur dan pesan, bukan uji akurasi model.
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from app.config import load_settings, parse_label_map
from app.envfile import EnvFileError, load_env_file
from app.inference import build_detector
from app.inference.base import UnconfiguredDetector
from app.inference.simulation import LABEL, MODEL_ID, SimulationDetector
from app.inference.ultralytics_adapter import UltralyticsDetector
from conftest import assert_error, create_survey, jpeg_bytes, png_bytes, upload_ok

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
COCO_NAMES = {i: n for i, n in enumerate(
    ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"]
    + [f"coco_{i}" for i in range(9, 58)] + ["potted plant"] + [f"coco_{i}" for i in range(59, 79)] + ["toothbrush"])}


class Arr:
    def __init__(self, v): self.v = v
    def cpu(self): return self
    def tolist(self): return self.v


def make_yolo(names=None, task="detect", load_error: Exception | None = None):
    class FakeYOLO:
        loads = 0

        def __init__(self, path, task_=None, **kw):
            FakeYOLO.loads += 1
            if load_error:
                raise load_error
            self.names = names if names is not None else {0: "jagung", 1: "gulma"}
            self.task = task

        def predict(self, image, **kw):
            boxes = types.SimpleNamespace(xyxy=Arr([[10, 10, 30, 30]]), conf=Arr([0.8]), cls=Arr([0]))
            return [types.SimpleNamespace(names=self.names, boxes=boxes)]
    return FakeYOLO


@pytest.fixture
def fake_ultralytics(monkeypatch):
    real_find_spec = importlib.util.find_spec

    def install(**kw):
        mod = types.ModuleType("ultralytics")
        mod.YOLO = make_yolo(**kw)
        mod.__version__ = "0.0-fake"
        monkeypatch.setitem(sys.modules, "ultralytics", mod)
        monkeypatch.setattr("importlib.util.find_spec",
                            lambda name, *a: object() if name == "ultralytics" else real_find_spec(name, *a))
        return mod
    return install


@pytest.fixture
def no_ultralytics(monkeypatch):
    real_find_spec = importlib.util.find_spec
    monkeypatch.delitem(sys.modules, "ultralytics", raising=False)
    monkeypatch.setattr("importlib.util.find_spec",
                        lambda name, *a: None if name == "ultralytics" else real_find_spec(name, *a))


@pytest.fixture
def weights(tmp_path) -> Path:
    d = tmp_path / "Model Tanaman"          # spasi di path, seperti folder Windows biasa
    d.mkdir()
    w = d / "best.pt"
    w.write_bytes(b"weights")
    return w


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("WALLACEA_DETECTOR", "WALLACEA_MODEL_PATH", "WALLACEA_LABEL_MAP_JSON", "WALLACEA_CONFIDENCE"):
        monkeypatch.delenv(k, raising=False)


def health_model(client) -> dict:
    r = client.get("/api/v1/health")
    assert r.status_code == 200, r.text
    return r.json()["model"]


# ------------------------------------------------------------------ default tanpa model
def test_default_without_model_is_manual_with_clear_message(client):
    m = health_model(client)
    assert m["state"] == "not_configured" and m["available"] is False
    assert m["mode"] == "manual" and m["diagnostic_code"] == "MODEL_PATH_NOT_SET"
    assert m["adapter"] is None and m["model_id"] is None
    assert "mode manual" in m["message"] and "run-with-model.ps1" in m["message"]
    s = create_survey(client)
    p = upload_ok(client, s["id"])
    err = assert_error(client.post(f"/api/v1/photos/{p['id']}/analyze"), 503, "MODEL_NOT_CONFIGURED")
    assert err["details"] == {"model_state": "not_configured", "diagnostic_code": "MODEL_PATH_NOT_SET"}
    assert client.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["total"] == 0


def test_simulation_is_never_an_implicit_fallback(tmp_path):
    assert isinstance(build_detector(load_settings(data_dir=tmp_path)), UnconfiguredDetector)
    broken = build_detector(load_settings(data_dir=tmp_path, model_path=tmp_path / "tidak-ada.pt"))
    info = broken.info()
    assert not isinstance(broken, SimulationDetector)
    assert info.state == "error" and info.mode == "model" and info.diagnostic_code == "MODEL_FILE_NOT_FOUND"


# ------------------------------------------------------------------ diagnostik model
def test_model_path_not_found(make_client, tmp_path):
    missing = tmp_path / "folder dengan spasi" / "best.pt"
    c = make_client(model_path=missing)
    m = health_model(c)
    assert m["state"] == "error" and m["diagnostic_code"] == "MODEL_FILE_NOT_FOUND"
    assert str(missing) in m["message"] and m["adapter"] == "ultralytics"
    p = upload_ok(c, create_survey(c)["id"])
    err = assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), 503, "MODEL_UNAVAILABLE")
    assert err["details"]["diagnostic_code"] == "MODEL_FILE_NOT_FOUND"


def test_model_path_is_folder(tmp_path):
    info = UltralyticsDetector(tmp_path, {"plant": "plant"}).info()
    assert info.state == "error" and info.diagnostic_code == "MODEL_FILE_NOT_PT" and "folder" in info.message


def test_wrong_extension(tmp_path):
    w = tmp_path / "model.onnx"
    w.write_bytes(b"x")
    assert UltralyticsDetector(w, {"plant": "plant"}).info().diagnostic_code == "MODEL_FILE_NOT_PT"


def test_ultralytics_not_installed(weights, no_ultralytics):
    info = UltralyticsDetector(weights, {"jagung": "plant"}).info()
    assert info.state == "error" and info.diagnostic_code == "DEPENDENCY_MISSING"
    assert "requirements-ai.txt" in info.message


@pytest.mark.parametrize("raw, fragment", [
    ("{jagung: plant", "bukan JSON"),
    ("[]", "objek JSON"),
    ('{"jagung": "tree"}', "nilai harus salah satu"),
    ('{"jagung": 1}', "nilai harus salah satu"),
])
def test_invalid_label_map_messages(raw, fragment):
    mapping, err = parse_label_map(raw)
    assert mapping == {} and fragment in err


def test_simple_label_map_forms_survive_powershell_quote_stripping():
    # PowerShell 5.1 mengubah '{"jagung":"plant"}' menjadi {jagung:plant} saat memanggil program native.
    assert parse_label_map("{jagung:plant}") == ({"jagung": "plant"}, None)
    assert parse_label_map("jagung=plant, gulma=check") == ({"jagung": "plant", "gulma": "check"}, None)
    assert parse_label_map('{"potted plant": "plant"}') == ({"potted plant": "plant"}, None)


def test_invalid_label_map_env_is_error_in_health(monkeypatch, make_client, weights):
    monkeypatch.setenv("WALLACEA_LABEL_MAP_JSON", '{"jagung": "tanaman"}')
    c = make_client(model_path=weights)
    m = health_model(c)
    assert m["state"] == "error" and m["diagnostic_code"] == "LABEL_MAP_INVALID"
    assert "'jagung': 'tanaman'" in m["message"]


def test_label_map_mismatch_reported_with_model_classes(make_client, weights, fake_ultralytics):
    fake_ultralytics(names={0: "Jagung", 1: "gulma"})
    c = make_client(detector=UltralyticsDetector(weights, {"jagung": "plant"}))
    assert health_model(c)["state"] == "configured"
    p = upload_ok(c, create_survey(c)["id"])
    err = assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), 503, "MODEL_UNAVAILABLE")
    assert err["details"]["diagnostic_code"] == "LABEL_MAP_MISMATCH" and "Jagung" in err["message"]
    m = health_model(c)                       # kegagalan muat diingat: tidak lagi "configured"
    assert m["state"] == "error" and m["diagnostic_code"] == "LABEL_MAP_MISMATCH"
    run = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["status"] == "failed" and run["error_code"] == "MODEL_UNAVAILABLE"


def test_not_detection_model(weights, fake_ultralytics):
    fake_ultralytics(task="segment")
    det = UltralyticsDetector(weights, {"jagung": "plant"})
    with pytest.raises(Exception) as exc:
        det.detect(Image.new("RGB", (40, 40)))
    assert exc.value.diagnostic_code == "NOT_DETECTION_MODEL"
    assert det.info().diagnostic_code == "NOT_DETECTION_MODEL"


def test_load_failure_then_replaced_file_is_retried(weights, fake_ultralytics):
    import os

    fake_ultralytics(load_error=RuntimeError("pickle rusak"))
    det = UltralyticsDetector(weights, {"jagung": "plant"})
    with pytest.raises(Exception):
        det.detect(Image.new("RGB", (40, 40)))
    assert det.info().diagnostic_code == "MODEL_LOAD_FAILED"
    fake_ultralytics()                        # bobot diganti versi yang benar
    weights.write_bytes(b"weights-v2")
    os.utime(weights, ns=(1, 2_000_000_000))
    assert det.info().state == "configured"
    assert len(det.detect(Image.new("RGB", (40, 40))).detections) == 1


def test_generic_coco_model_is_labelled_not_a_plant_model(weights, fake_ultralytics):
    fake_ultralytics(names=COCO_NAMES)
    det = UltralyticsDetector(weights, {"potted plant": "plant"})
    det.detect(Image.new("RGB", (40, 40)))
    info = det.info()
    assert info.state == "loaded" and info.diagnostic_code == "GENERIC_COCO_MODEL"
    assert "BUKAN model tanaman" in info.target_label and "COCO" in info.limitations[0]


def test_inference_failure_is_specific(make_client, weights, fake_ultralytics):
    mod = fake_ultralytics()
    mod.YOLO.predict = lambda self, image, **kw: (_ for _ in ()).throw(RuntimeError("CUDA out of memory"))
    c = make_client(detector=UltralyticsDetector(weights, {"jagung": "plant"}))
    p = upload_ok(c, create_survey(c)["id"])
    err = assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), 500, "INFERENCE_FAILED")
    assert "Ultralytics" in err["message"]
    assert health_model(c)["state"] == "loaded"   # model tetap termuat; hanya request ini yang gagal


def test_valid_model_runs_analysis(make_client, weights, fake_ultralytics):
    fake_ultralytics()
    c = make_client(detector=UltralyticsDetector(weights, {"jagung": "plant"}))
    p = upload_ok(c, create_survey(c)["id"])
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 201, r.text
    assert [a["model_label"] for a in r.json()["candidates"]] == ["jagung"]
    m = health_model(c)
    assert m["state"] == "loaded" and m["mode"] == "model" and m["diagnostic_code"] is None


# ------------------------------------------------------------------ simulasi
def test_simulation_requires_explicit_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WALLACEA_DETECTOR", "simulation")
    assert isinstance(build_detector(load_settings(data_dir=tmp_path)), SimulationDetector)


def test_simulation_health_is_labelled(make_client):
    m = health_model(make_client(detector=SimulationDetector()))
    assert m["state"] == "loaded" and m["available"] is True
    assert m["mode"] == "simulation" and m["diagnostic_code"] == "SIMULATION_ACTIVE"
    assert m["adapter"] == "simulation" and m["target"] == "simulation"
    assert m["model_id"] == MODEL_ID == "simulation-not-ai"
    assert m["target_label"] == "SIMULASI — BUKAN AI" and m["message"].startswith("SIMULASI — BUKAN AI")
    assert any("keputusan lapangan" in x for x in m["limitations"])


def test_simulation_is_deterministic():
    det = SimulationDetector()
    a = Image.new("RGB", (200, 120), (40, 120, 60))
    first, second = det.detect(a), det.detect(a.copy())
    assert [d.bbox for d in first.detections] == [d.bbox for d in second.detections]
    assert 3 <= len(first.detections) <= 8
    other = det.detect(Image.new("RGB", (200, 120), (200, 30, 30)))
    assert [d.bbox for d in other.detections] != [d.bbox for d in first.detections]
    for d in first.detections:
        left, top, w, h = d.bbox
        assert 0 <= left and 0 <= top and w > 0 and h > 0 and left + w <= 1 and top + h <= 1
        assert d.confidence is None and d.model_label == LABEL and d.label == "plant"


def test_simulation_candidates_pending_and_labelled(make_client):
    c = make_client(detector=SimulationDetector())
    s = create_survey(c)
    p = upload_ok(c, s["id"], jpeg_bytes(160, 90), "DJI_0001.JPG", "image/jpeg")
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["notice"].startswith("SIMULASI — BUKAN AI")
    assert body["run"]["target"] == "simulation" and body["run"]["model_id"] == "simulation-not-ai"
    assert body["run"]["parameters"]["not_ai"] is True
    cands = body["candidates"]
    assert cands and all(a["review_status"] == "pending" and a["source"] == "model" for a in cands)
    assert all(a["model_label"] == "SIMULASI — BUKAN AI" and a["confidence"] is None for a in cands)
    photo = c.get(f"/api/v1/photos/{p['id']}").json()
    assert photo["counts"]["plant_accepted"] == 0      # pending tidak dihitung
    # deterministik lewat API: analisis ulang (append) memberi kotak identik
    again = c.post(f"/api/v1/photos/{p['id']}/analyze", json={"on_existing": "append"}).json()["candidates"]
    assert [a["bbox"] for a in again] == [a["bbox"] for a in cands]
    # laporan memuat disclaimer simulasi
    report = c.get(f"/api/v1/surveys/{s['id']}/report").json()
    assert any(d.startswith("SIMULASI — BUKAN AI") for d in report["disclaimers"])


def test_manual_workflow_unchanged_in_simulation_mode(make_client):
    c = make_client(detector=SimulationDetector())
    s = create_survey(c)
    p = upload_ok(c, s["id"], png_bytes())
    r = c.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "geometry_type": "point", "x": 0.5, "y": 0.5})
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "manual" and r.json()["review_status"] == "accepted"
    assert c.get(f"/api/v1/photos/{p['id']}").json()["counts"]["plant_accepted"] == 1
    report = c.get(f"/api/v1/surveys/{s['id']}/report").json()
    assert not any("SIMULASI" in d for d in report["disclaimers"])   # tanpa kandidat simulasi → tanpa disclaimer


def test_manual_workflow_unchanged_without_model(client):
    s = create_survey(client)
    p = upload_ok(client, s["id"])
    r = client.post(f"/api/v1/photos/{p['id']}/annotations",
                    json={"kind": "check", "geometry_type": "bbox", "bbox": [0.1, 0.1, 0.2, 0.2], "note": "cek"})
    assert r.status_code == 201, r.text
    ann = r.json()
    r = client.patch(f"/api/v1/annotations/{ann['id']}", json={"note": "cek lagi"}, headers={"If-Match": '"1"'})
    assert r.status_code == 200 and r.json()["revision"] == 2


# ------------------------------------------------------------------ .env
def test_env_file_parsing_keeps_windows_paths(tmp_path):
    f = tmp_path / ".env"
    f.write_text("# komentar\n\nWALLACEA_MODEL_PATH=C:\\Users\\nama\\Model Tanaman\\best.pt\n"
                 "export WALLACEA_DETECTOR=\"ultralytics\"\nWALLACEA_LABEL_MAP_JSON={\"jagung\":\"plant\"}\n"
                 "WALLACEA_CONFIDENCE='0.25'\n", encoding="utf-8")
    env = {"WALLACEA_CONFIDENCE": "0.5"}           # nilai dari terminal tidak ditimpa
    applied = load_env_file(f, env)
    assert env["WALLACEA_MODEL_PATH"] == r"C:\Users\nama\Model Tanaman\best.pt"
    assert env["WALLACEA_DETECTOR"] == "ultralytics" and env["WALLACEA_LABEL_MAP_JSON"] == '{"jagung":"plant"}'
    assert env["WALLACEA_CONFIDENCE"] == "0.5" and "WALLACEA_CONFIDENCE" not in applied


def test_env_file_rejects_bare_path_line(tmp_path):
    f = tmp_path / ".env"
    f.write_text("models\\best.pt\n", encoding="utf-8")
    with pytest.raises(EnvFileError, match="NAMA=nilai"):
        load_env_file(f, {})


# ------------------------------------------------------------------ scripts/check_model.py
@pytest.fixture
def check_model():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import check_model as mod
        yield mod
    finally:
        sys.path.remove(str(SCRIPTS))


def test_check_model_missing_file(check_model, tmp_path, capsys):
    assert check_model.main(["--model-path", str(tmp_path / "models" / "best.pt")]) == 2
    assert "tidak ditemukan" in capsys.readouterr().out


def test_check_model_wrong_extension(check_model, tmp_path, capsys):
    w = tmp_path / "best.onnx"
    w.write_bytes(b"x")
    assert check_model.main(["--model-path", str(w)]) == 2
    assert "Ekstensi harus .pt" in capsys.readouterr().out


def test_check_model_without_ultralytics_does_not_install(check_model, weights, no_ultralytics, capsys, monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("tidak boleh memasang paket"))
    assert check_model.main(["--model-path", str(weights), "--label-map-json", "jagung=plant"]) == 1
    assert "belum terpasang" in capsys.readouterr().out


def test_check_model_label_map_mismatch(check_model, weights, fake_ultralytics, capsys):
    fake_ultralytics(names={0: "maize"})
    assert check_model.main(["--model-path", str(weights), "--label-map-json", '{"jagung":"plant"}']) == 1
    out = capsys.readouterr().out
    assert "0: maize" in out and "Label map tidak cocok" in out


def test_check_model_ok_prints_names_and_ready_command(check_model, weights, fake_ultralytics, capsys, monkeypatch):
    fake_ultralytics()
    monkeypatch.setenv("WALLACEA_LABEL_MAP_JSON", "{jagung:plant}")   # seperti dari check-model.ps1
    assert check_model.main(["--model-path", str(weights)]) == 0
    out = capsys.readouterr().out
    assert "0: jagung | 1: gulma" in out and "jagung -> plant" in out and "gulma" in out
    assert "run-with-model.ps1" in out and "-LabelMap 'jagung=plant'" in out and str(weights) in out


def test_check_model_not_detection(check_model, weights, fake_ultralytics, capsys):
    fake_ultralytics(task="classify")
    assert check_model.main(["--model-path", str(weights)]) == 1
    assert "bukan deteksi" in capsys.readouterr().out


def test_check_model_warns_on_coco(check_model, weights, fake_ultralytics, capsys):
    fake_ultralytics(names=COCO_NAMES)
    assert check_model.main(["--model-path", str(weights), "--label-map-json", "potted plant=plant"]) == 0
    assert "BUKAN model tanaman" in capsys.readouterr().out
