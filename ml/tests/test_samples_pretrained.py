"""Katalog sampel (sha256 terverifikasi) dan runner inferensi pretrained. Detector palsu = uji pipeline, bukan akurasi."""
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from wallacea_ml import pretrained
from wallacea_ml.samples import load_samples, samples_dir


def test_repo_catalog_loads_and_verifies_checksums():
    s = load_samples()
    assert [x.id for x in s] == ["neon-osbs-029", "neon-soap-061", "neon-yell-crop"]
    assert all(x.path.is_file() and x.annotations.is_file() and x.license_url.startswith("https://") for x in s)
    assert s[1].annotation_labels == {"Alive": 9, "Dead": 28}


def test_tampered_sample_is_rejected(tmp_path):
    d = tmp_path / "samples"
    shutil.copytree(samples_dir(), d)
    p = d / "deepforest-neon" / "OSBS_029.png"
    Image.open(p).convert("RGB").save(p)                      # byte berubah walau gambar tampak sama
    with pytest.raises(ValueError, match="sha256"):
        load_samples(d)


class FakeDet:
    def __init__(self):
        self.loads = 0
        self.seen = []

    def info(self):
        from types import SimpleNamespace
        return SimpleNamespace(available=True, message="ok", model_id="fake", model_version="sha256:x",
                               adapter="deepforest", target="tree_crown", target_label="Kandidat tajuk pohon",
                               device="cpu")

    def preload(self):
        self.loads += 1

    def detect(self, img):
        from types import SimpleNamespace
        self.seen.append(img.size)
        d = SimpleNamespace(label="plant", model_label="Tree", confidence=0.9, bbox=[0.1, 0.1, 0.2, 0.2])
        return SimpleNamespace(detections=[d], parameters={"mode": "image", "conf": 0.35})


def test_run_on_samples_measures_time_loads_once_and_roundtrips(tmp_path):
    det = FakeDet()
    res = pretrained.run_on_samples(det, load_samples(), repeats=2)
    assert det.loads == 1 and len(det.seen) == 6                             # 3 foto × 2 pengulangan
    assert det.seen[0] == (400, 400) and res["target"] == "tree_crown"
    rec = res["images"][0]
    assert len(rec["seconds"]) == 2 and rec["seconds_median"] >= 0 and rec["pred"][0]["model_label"] == "Tree"
    out = pretrained.save(res, tmp_path / "p.json")
    assert pretrained.load(out) == json.loads(Path(out).read_text(encoding="utf-8"))
