"""Unit test toolkit ML dengan data sintetis. Menguji logika metrik/split, BUKAN performa model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
from wallacea_ml.cli import main as ml_main  # noqa: E402
from wallacea_ml.evaluate import evaluate, iou  # noqa: E402
from wallacea_ml.manifest import load_manifest  # noqa: E402
from wallacea_ml.split import check_leakage, group_split  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[1] / "ml" / "dataset_manifest.example.json"


def sha(n: int) -> str:
    return f"{n:064x}"


def manifest_file(tmp_path, fields=4, per_field=3, extra=None) -> Path:
    imgs = []
    k = 0
    for f in range(fields):
        for i in range(per_field):
            k += 1
            imgs.append({"image": f"f{f}/{i}.jpg", "sha256": sha(k), "field_id": f"lahan{f}",
                         "flight_id": f"fl{f}", "width": 100, "height": 100, "labels": f"f{f}/{i}.txt"})
    imgs += extra or []
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"crop_type": "Jagung", "label_map": {"plant": 0}, "images": imgs}), encoding="utf-8")
    return p


def test_example_manifest_is_valid():
    m = load_manifest(EXAMPLE)
    assert m.errors == [] and len(m.labeled) == 4


def test_manifest_validation_errors(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"label_map": {"person": 0}, "images": [
        {"image": "a", "sha256": "xyz", "field_id": "", "flight_id": "f", "width": 0, "height": 1}]}), encoding="utf-8")
    errs = " | ".join(load_manifest(p).errors)
    assert "crop_type" in errs and "label_map" in errs and "sha256" in errs and "field_id" in errs


def test_group_split_has_no_leak_and_keeps_tiles_with_parent(tmp_path):
    tile = {"image": "tiles/f0_0_t1.jpg", "sha256": sha(999), "field_id": "lahan0", "flight_id": "fl0",
            "width": 50, "height": 50, "labels": "t.txt", "parent_image": "f0/0.jpg"}
    m = load_manifest(manifest_file(tmp_path, fields=6, extra=[tile]))
    r = group_split(m, "field")
    assert r.leaks == [] and r.is_product_validation
    assert r.assignments["tiles/f0_0_t1.jpg"] == r.assignments["f0/0.jpg"]
    for f in range(6):  # seluruh foto satu lahan di split yang sama
        assert len({r.assignments[f"f{f}/{i}.jpg"] for i in range(3)}) == 1
    assert all(r.groups[s] for s in ("train", "val", "test"))


def test_random_per_photo_split_is_flagged_as_leak(tmp_path):
    m = load_manifest(manifest_file(tmp_path, fields=3))
    order = ["train", "val", "test"]
    random_like = {e.image: order[i % 3] for i, e in enumerate(m.images)}  # foto berurutan tersebar
    leaks = check_leakage(m, random_like)
    assert any(lk.startswith("field") for lk in leaks) and any(lk.startswith("flight") for lk in leaks)


def test_duplicate_file_across_splits_is_leak(tmp_path):
    dup = {"image": "copy.jpg", "sha256": sha(1), "field_id": "lahan9", "flight_id": "x", "width": 1, "height": 1}
    m = load_manifest(manifest_file(tmp_path, fields=3, extra=[dup]))
    a = {e.image: "train" for e in m.images}
    a["copy.jpg"] = "test"
    assert any(lk.startswith("sha256") for lk in check_leakage(m, a))


def test_too_few_groups(tmp_path):
    with pytest.raises(ValueError):
        group_split(load_manifest(manifest_file(tmp_path, fields=2)))


def test_iou():
    assert iou([0, 0, 0.5, 0.5], [0, 0, 0.5, 0.5]) == pytest.approx(1.0)
    assert iou([0, 0, 0.2, 0.2], [0.5, 0.5, 0.2, 0.2]) == 0.0
    assert iou([0, 0, 0.2, 0.2], [0.1, 0, 0.2, 0.2]) == pytest.approx(1 / 3)


def test_metrics_math():
    data = {"split": "test", "images": [
        {"image": "a", "plot_id": "P1",
         "gt": [{"label": "plant", "bbox": [0.1, 0.1, 0.1, 0.1]}, {"label": "plant", "bbox": [0.5, 0.5, 0.1, 0.1]}],
         "pred": [{"label": "plant", "confidence": 0.9, "bbox": [0.1, 0.1, 0.1, 0.1]},   # TP
                  {"label": "plant", "confidence": 0.8, "bbox": [0.11, 0.1, 0.1, 0.1]},  # duplikat → FP
                  {"label": "plant", "confidence": 0.7, "bbox": [0.8, 0.8, 0.1, 0.1]}]},  # FP; GT kedua FN
        {"image": "b", "plot_id": "P1", "gt": [{"label": "plant", "bbox": [0.2, 0.2, 0.2, 0.2]}], "pred": []},
    ]}
    r = evaluate(data, leaks=[])
    assert (r.tp, r.fp, r.fn) == (1, 2, 2)
    assert r.precision == pytest.approx(1 / 3) and r.recall == pytest.approx(1 / 3)
    assert [row["count_error"] for row in r.per_image] == [1, -1]
    assert r.count_mae_per_image == 1 and r.count_mean_error_per_image == 0
    assert r.count_mae_per_plot == 0  # +1 dan -1 saling meniadakan per petak — itu sebabnya MAE per foto juga dilaporkan
    assert r.validation_kind == "group_held_out"
    assert evaluate(data).validation_kind == "unverified_split"
    assert evaluate(data, leaks=["x"]).validation_kind == "leaky_not_product_validation"


def test_train_refuses_without_data(tmp_path, capsys):
    m = manifest_file(tmp_path, fields=3, per_field=2)
    code = ml_main(["train", str(m), "--split-dir", str(tmp_path / "none"), "--weights", str(tmp_path / "w.pt"),
                    "--dry-run"])
    err = capsys.readouterr().err
    assert code == 2 and "minimal 50" in err and "split_report" in err and "Bobot awal lokal" in err


def test_split_cli_and_train_dry_run(tmp_path):
    m = manifest_file(tmp_path, fields=5, per_field=12)
    out = tmp_path / "split"
    assert ml_main(["split", str(m), "--root", str(tmp_path), "--out", str(out)]) == 0
    assert (out / "dataset.yaml").read_text(encoding="utf-8").count("0: plant") == 1
    w = tmp_path / "base.pt"
    w.write_bytes(b"x")
    assert ml_main(["train", str(m), "--split-dir", str(out), "--weights", str(w), "--dry-run"]) == 0
