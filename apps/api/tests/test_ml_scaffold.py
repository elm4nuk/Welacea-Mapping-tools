"""apps/api/ml: pemeriksaan dataset YOLO & penolakan train.py — tanpa Ultralytics/PyTorch. Bukan uji akurasi."""
import sys
from pathlib import Path

import pytest
import yaml

ML = Path(__file__).resolve().parents[1] / "ml"


@pytest.fixture
def ml(monkeypatch):
    monkeypatch.syspath_prepend(str(ML))
    import train
    import yolo_dataset
    return yolo_dataset, train


def make_dataset(root: Path, label_line="0 0.5 0.5 0.1 0.1", splits=("train", "val", "test"), extra=None) -> Path:
    for split in splits:
        (root / "images" / split).mkdir(parents=True)
        (root / "labels" / split).mkdir(parents=True)
        (root / "images" / split / "a.jpg").write_bytes(b"x")
        (root / "labels" / split / "a.txt").write_text(label_line + "\n", encoding="utf-8")
    cfg = {"path": ".", **{s: f"images/{s}" for s in splits}, "names": {0: "jagung"}, **(extra or {})}
    y = root / "dataset.yaml"
    y.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return y


def test_example_yaml_is_valid_yolo_config():
    cfg = yaml.safe_load((ML / "dataset.yaml.example").read_text(encoding="utf-8"))
    assert {"path", "train", "val", "test", "names"} <= set(cfg) and cfg["names"] == {0: "jagung"}


def test_valid_dataset_with_spaces_in_path(ml, tmp_path):
    yd, _ = ml
    rep = yd.check_dataset(make_dataset(tmp_path / "dataset jagung"))
    assert rep.ok, rep.errors
    assert rep.names == ["jagung"] and rep.splits["train"].boxes == 1 and not rep.warnings


@pytest.mark.parametrize("line, fragment", [
    ("0 120 80 30 30", "dinormalisasi"),
    ("3 0.5 0.5 0.1 0.1", "di luar names"),
    ("0 0.1 0.1 0.2 0.1 0.3 0.4", "harus 5 angka"),
    ("jagung 0.5 0.5 0.1 0.1", "bukan angka"),
])
def test_bad_label_lines_are_reported(ml, tmp_path, line, fragment):
    yd, _ = ml
    rep = yd.check_dataset(make_dataset(tmp_path, label_line=line))
    assert not rep.ok and any(fragment in e for e in rep.errors), rep.errors


def test_missing_test_split_warns_and_missing_val_fails(ml, tmp_path):
    yd, _ = ml
    rep = yd.check_dataset(make_dataset(tmp_path / "a", splits=("train", "val")))
    assert rep.ok and any("test" in w for w in rep.warnings)
    rep = yd.check_dataset(make_dataset(tmp_path / "b", splits=("train",)))
    assert not rep.ok and any("`val` wajib" in e for e in rep.errors)


def test_resolved_yaml_is_absolute_and_drops_download(ml, tmp_path):
    yd, _ = ml
    y = make_dataset(tmp_path / "ds", extra={"download": "https://example.invalid/data.zip"})
    assert any("download" in w for w in yd.check_dataset(y).warnings)
    out = yaml.safe_load(yd.write_resolved_yaml(y, tmp_path / "run").read_text(encoding="utf-8"))
    assert Path(out["path"]).is_absolute() and Path(out["path"]) == (tmp_path / "ds").resolve()
    assert "download" not in out


def test_train_check_only_does_not_need_ultralytics(ml, tmp_path, monkeypatch, capsys):
    _, train = ml
    monkeypatch.setitem(sys.modules, "ultralytics", None)      # import ultralytics → ImportError
    assert train.main(["--data", str(make_dataset(tmp_path)), "--check-only"]) == 0
    assert "lulus pemeriksaan" in capsys.readouterr().out


def test_train_refuses_missing_base_weights_without_downloading(ml, tmp_path, monkeypatch, capsys):
    _, train = ml
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    y = make_dataset(tmp_path)
    assert train.main(["--data", str(y)]) == 2
    assert train.main(["--data", str(y), "--base-weights", str(tmp_path / "yolo11n.pt")]) == 2
    assert "tidak mengunduh" in capsys.readouterr().err


def test_train_refuses_invalid_dataset(ml, tmp_path):
    _, train = ml
    assert train.main(["--data", str(make_dataset(tmp_path, label_line="0 2 2 2 2")), "--check-only"]) == 2
