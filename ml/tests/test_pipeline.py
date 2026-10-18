"""Pipeline ujung-ke-ujung dengan fixture sintetis: orientasi EXIF konsisten antara prepare (training),
API (upload/display/detektor), dan evaluasi; split tanpa kebocoran; prediksi lewat adapter API.
Menguji KONVENSI & PIPELINE, bukan akurasi tanaman."""
import io
import json
from pathlib import Path

import pytest
import yaml
from PIL import Image

from conftest import jpeg_with_orientation
from wallacea_ml import backend
from wallacea_ml.cli import main as ml_main
from wallacea_ml.evaluate import average_precision, choose_threshold, evaluate, sweep
from wallacea_ml.inspection import find_duplicates, inspect_manifest
from wallacea_ml.manifest import load_manifest
from wallacea_ml.prepare import load_config, prepare
from wallacea_ml.split import group_split

RAW = (400, 200)                       # piksel tersimpan (lebar × tinggi) SEBELUM orientasi
RECT_RAW = (300, 20, 360, 60)          # kotak merah di piksel mentah
# Orientasi 6 = putar 90° searah jarum jam untuk ditampilkan: (x, y) mentah → (H−1−y, x).
# x ∈ [300,360), y ∈ [20,60) → x' ∈ [200−60, 200−20) = [140,180), y' ∈ [300,360) pada gambar 200×400.
ORIENTED = (200, 400)
BBOX_ORIENTED_PX = [140, 300, 40, 60]


def make_source(tmp_path, sites=("alpha", "beta", "gamma"), coco_size=ORIENTED, bbox=BBOX_ORIENTED_PX):
    raw_dir = tmp_path / "raw"
    for k, site in enumerate(sites):
        d = raw_dir / f"1_{site}_2024_1"
        d.mkdir(parents=True)
        # latar berbeda per situs: foto identik lintas split akan (benar) ditandai bocor oleh cek sha256
        (d / "plot_1.jpg").write_bytes(jpeg_with_orientation(RAW, 6, RECT_RAW, bg=(0, 60 + 30 * k, 0)))
        (raw_dir / f"1_{site}_2024_1.json").write_text(json.dumps({
            "images": [{"id": 1, "file_name": "plot_1.jpg", "width": coco_size[0], "height": coco_size[1]}],
            "categories": [{"id": 1, "name": "plant"}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": bbox}],
        }), encoding="utf-8")
    cfg = {"name": "synthetic", "crop_type": "maize", "domain": "public:synthetic", "label_map": {"plant": 0},
           "class_map": {"plant": "plant"},
           "sources": [{"annotations": str(raw_dir / "*.json"), "images_dir": "{ann_dir}/{ann_stem}",
                        "match_on": "ann_stem", "match": r"^(?P<p>\d+)_(?P<site>.+)_(?P<year>\d{4})_(?P<n>\d+)$",
                        "field_id": "{site}", "flight_id": "{site}_{year}_{n}"}]}
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


def test_prepare_writes_oriented_pixels_and_matching_labels(tmp_path):
    out = tmp_path / "prep"
    rep = prepare(load_config(make_source(tmp_path)), out)
    assert rep["images_written"] == 3 and rep["skipped"] == []
    m = load_manifest(out / "manifest.json")
    e = m.images[0]
    assert (e.width, e.height) == ORIENTED and e.image.endswith(".png") and e.field_id == "alpha"
    img = Image.open(out / e.image)
    assert img.size == ORIENTED and int(img.getexif().get(0x0112, 1)) == 1   # piksel sudah diputar, tanpa EXIF
    # pusat label YOLO jatuh pada piksel merah di gambar hasil prepare
    cls, cx, cy, w, h = (float(v) for v in (out / e.labels).read_text().split())
    r, g, b = img.getpixel((int(cx * ORIENTED[0]), int(cy * ORIENTED[1])))
    assert cls == 0 and r > 200 and g < 60 and (w, h) == pytest.approx((0.2, 0.15))


def test_prepare_skips_annotations_made_on_unrotated_pixels(tmp_path):
    # pelabel melihat piksel MENTAH (tanpa rotasi EXIF): dimensi & bbox dalam frame mentah
    raw_bbox = [RECT_RAW[0], RECT_RAW[1], RECT_RAW[2] - RECT_RAW[0], RECT_RAW[3] - RECT_RAW[1]]
    rep = prepare(load_config(make_source(tmp_path, coco_size=RAW, bbox=raw_bbox)), tmp_path / "prep")
    assert rep["images_written"] == 0
    assert {s["reason"] for s in rep["skipped"]} == {"ORIENTATION_MISMATCH"}


def test_prepare_dimensions_equal_api_upload_dimensions(tmp_path):
    """Dimensi di manifest training = Photo.width/height yang dihitung API saat upload foto yang sama."""
    backend._ensure_api_importable()
    from app.imaging import inspect_image

    raw = jpeg_with_orientation(RAW, 6, RECT_RAW)
    info = inspect_image(raw, max_pixels=60_000_000)
    out = tmp_path / "prep"
    prepare(load_config(make_source(tmp_path)), out)
    e = load_manifest(out / "manifest.json").images[0]
    assert (info.width, info.height) == (e.width, e.height) == ORIENTED
    assert info.exif_orientation == 6


def test_end_to_end_split_predict_evaluate_through_api_adapter(tmp_path, fake_ultralytics):
    prep = tmp_path / "prep"
    prepare(load_config(make_source(tmp_path)), prep)
    man = prep / "manifest.json"
    split_dir = tmp_path / "split"
    assert ml_main(["split", str(man), "--root", str(prep), "--out", str(split_dir)]) == 0
    rep = json.loads((split_dir / "split_report.json").read_text())
    assert rep["leaks"] == [] and all(rep["images_per_split"][s] == 1 for s in ("train", "val", "test"))
    ds = yaml.safe_load((split_dir / "dataset.yaml").read_text())
    train_list = (split_dir / "yolo" / "train.txt").read_text().split()
    assert ds["names"] == {0: "plant"} and all(Path(p).is_absolute() and "/images/" in p for p in train_list)

    weights = tmp_path / "fake.pt"
    weights.write_bytes(b"bukan-model")
    for split in ("val", "test"):
        assert ml_main(["predict", str(man), "--split-dir", str(split_dir), "--split", split,
                        "--weights", str(weights), "--imgsz", "640", "--out", str(tmp_path / f"pred_{split}.json")]) == 0
    assert fake_ultralytics.seen_sizes == [ORIENTED, ORIENTED]     # detektor API menerima gambar terorientasi
    pred = json.loads((tmp_path / "pred_test.json").read_text())
    assert pred["model_version"].startswith("sha256:") and pred["domain"] == "public:synthetic"
    p0 = pred["images"][0]["pred"][0]
    assert p0["bbox"] == pytest.approx([0.7, 0.75, 0.2, 0.15], abs=0.006)   # = label prepare
    assert pred["images"][0]["gt"][0]["bbox"] == pytest.approx([0.7, 0.75, 0.2, 0.15], abs=1e-6)

    assert ml_main(["threshold", str(tmp_path / "pred_test.json")]) == 2       # threshold bukan dari test
    assert ml_main(["threshold", str(tmp_path / "pred_val.json"), "--out", str(tmp_path / "th.json")]) == 0
    conf = json.loads((tmp_path / "th.json").read_text())["chosen"]["conf"]
    assert ml_main(["evaluate", str(tmp_path / "pred_test.json"), "--manifest", str(man), "--split-dir",
                    str(split_dir), "--conf", str(conf), "--out", str(tmp_path / "ev.json")]) == 0
    ev = json.loads((tmp_path / "ev.json").read_text())
    assert ev["validation_kind"] == "group_held_out" and ev["precision"] == 1 and ev["recall"] == 1
    assert ev["ap"] == 1 and ev["count_mae_per_image"] == 0
    assert any("BUKAN kinerja pada foto K919" in c for c in ev["caveats"])


def test_evaluating_images_from_other_split_is_flagged(tmp_path, fake_ultralytics):
    prep = tmp_path / "prep"
    prepare(load_config(make_source(tmp_path)), prep)
    split_dir = tmp_path / "split"
    ml_main(["split", str(prep / "manifest.json"), "--root", str(prep), "--out", str(split_dir)])
    w = tmp_path / "fake.pt"
    w.write_bytes(b"x")
    ml_main(["predict", str(prep / "manifest.json"), "--split-dir", str(split_dir), "--split", "train",
             "--weights", str(w), "--out", str(tmp_path / "p.json")])
    data = json.loads((tmp_path / "p.json").read_text())
    data["split"] = "test"                                    # mengaku test padahal gambar train
    (tmp_path / "p.json").write_text(json.dumps(data))
    ml_main(["evaluate", str(tmp_path / "p.json"), "--manifest", str(prep / "manifest.json"),
             "--split-dir", str(split_dir), "--conf", "0.5", "--out", str(tmp_path / "e.json")])
    assert json.loads((tmp_path / "e.json").read_text())["validation_kind"] == "leaky_not_product_validation"


def test_official_split_is_preserved_and_duplicates_detected(tmp_path):
    def entry(i, split, sha):
        return {"image": f"images/{i}.png", "sha256": f"{sha:064x}", "field_id": f"official-{split}",
                "flight_id": "2023-08", "width": 10, "height": 10, "labels": None, "official_split": split}
    imgs = [entry(1, "train", 1), entry(2, "train", 2), entry(3, "val", 3), entry(4, "test", 4)]
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"crop_type": "oil_palm", "label_map": {"plant": 0}, "images": imgs}))
    r = group_split(load_manifest(p), "official")
    assert r.assignments == {"images/1.png": "train", "images/2.png": "train", "images/3.png": "val",
                             "images/4.png": "test"} and r.leaks == []
    imgs.append(entry(5, "test", 1))                          # byte identik dengan gambar train
    p.write_text(json.dumps({"crop_type": "oil_palm", "label_map": {"plant": 0}, "images": imgs}))
    assert any(lk.startswith("sha256") for lk in group_split(load_manifest(p), "official").leaks)


def test_near_duplicate_across_fields_is_reported(tmp_path):
    import random

    rnd = random.Random(1)
    base = Image.new("RGB", (256, 128))
    for bx in range(0, 256, 32):                              # blok kontras tinggi: struktur tetap setelah kompresi
        for by in range(0, 128, 32):
            v = rnd.randrange(0, 256)
            base.paste((v, 255 - v, v // 2), (bx, by, bx + 32, by + 32))
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    base.save(tmp_path / "a" / "x.jpg", quality=95)
    base.save(tmp_path / "b" / "y.jpg", quality=60)           # ekspor ulang, byte berbeda
    imgs = [{"image": "a/x.jpg", "sha256": f"{1:064x}", "field_id": "L1", "flight_id": "f", "width": 256, "height": 128},
            {"image": "b/y.jpg", "sha256": f"{2:064x}", "field_id": "L2", "flight_id": "g", "width": 256, "height": 128}]
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"crop_type": "maize", "label_map": {"plant": 0}, "images": imgs}))
    d = find_duplicates(load_manifest(p), tmp_path)
    assert d["exact"] == [] and d["near"] and d["near"][0]["cross_group"]


def test_inspect_flags_label_problems(tmp_path):
    (tmp_path / "l").mkdir()
    (tmp_path / "l" / "ok.txt").write_text("0 0.5 0.5 0.2 0.2\n0 0.5 0.5 0.2 0.2\n")
    (tmp_path / "l" / "bad.txt").write_text("3 0.5 0.5 0.2 0.2\n0 0.95 0.5 0.2 0.2\n0 0.5 0.5 0 0.1\nx y\n")
    (tmp_path / "l" / "empty.txt").write_text("")
    def e(name, labels):
        return {"image": f"{name}.jpg", "sha256": f"{len(name):064x}", "field_id": "L", "flight_id": "f",
                "width": 100, "height": 100, "labels": labels}
    imgs = [e("ok", "l/ok.txt"), e("bad", "l/bad.txt"), e("emptyy", "l/empty.txt"), e("missing", "l/none.txt"),
            e("unlabeled", None)]
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"crop_type": "maize", "label_map": {"plant": 0}, "images": imgs}))
    codes = {i.code for i in inspect_manifest(load_manifest(p), tmp_path, open_images=False).issues}
    assert {"DUP_BOX", "UNKNOWN_CLASS", "OUT_OF_RANGE", "NON_POSITIVE_SIZE", "BAD_LINE", "EMPTY_LABEL_FILE",
            "MISSING_LABEL_FILE", "UNLABELED"} <= codes


def test_ap_and_threshold_selection():
    assert average_precision([(0.9, True), (0.8, True)], 2) == 1.0
    # TP, FP, TP dengan 2 GT: presisi envelope [1, 2/3, 2/3] → AP = 0.5·1 + 0.5·(2/3)
    assert average_precision([(0.9, True), (0.8, False), (0.7, True)], 2) == pytest.approx(0.5 + 1 / 3)
    assert average_precision([], 0) is None
    gt = [{"label": "plant", "bbox": [0.1 * i, 0.1, 0.05, 0.05]} for i in range(4)]
    pred = [{"label": "plant", "confidence": 0.9, "bbox": b["bbox"]} for b in gt]
    pred += [{"label": "plant", "confidence": 0.2, "bbox": [0.5, 0.8, 0.05, 0.05]}]   # FP confidence rendah
    data = {"split": "val", "images": [{"image": "a", "gt": gt, "pred": pred}]}
    best = choose_threshold(sweep(data))
    assert 0.2 < best["conf"] <= 0.9 and best["count_mae_per_image"] == 0
    r = evaluate(data, leaks=[], conf_threshold=best["conf"])
    assert (r.tp, r.fp, r.fn) == (4, 0, 0) and r.ap == 1.0           # AP tidak bergantung threshold


def test_catalog_entries_have_required_fields():
    from wallacea_ml.datasets import load_catalog

    cat = load_catalog()
    assert {"uavmulticrop", "matchplant", "oilpalm-ganoderma-v2", "neon-tree-evaluation"} <= set(cat)
    for d in cat.values():
        assert d["url"].startswith("https://") and d["version"] and d["annotation_format"] and d["limitations"]
        assert {"dataset", "code", "weights"} <= set(d["license"])
        assert d["status"] in ("diperiksa", "diunduh-sebagian", "diunduh", "belum-tersedia")
    assert "BUKAN checkpoint Ultralytics" in cat["matchplant"]["weights_note"]
    assert "geografis" in cat["oilpalm-ganoderma-v2"]["splits"] and cat["oilpalm-ganoderma-v2"]["class_merge_for_census"]


def test_load_oriented_matches_api_function_bytes(tmp_path):
    raw = jpeg_with_orientation(RAW, 6, RECT_RAW)
    f = tmp_path / "x.jpg"
    f.write_bytes(raw)
    backend._ensure_api_importable()
    from app.imaging import oriented_from_bytes

    a, b = backend.load_oriented(f), oriented_from_bytes(raw)
    buf_a, buf_b = io.BytesIO(), io.BytesIO()
    a.save(buf_a, "PNG")
    b.save(buf_b, "PNG")
    assert buf_a.getvalue() == buf_b.getvalue()


def test_external_split_puts_everything_in_test_and_ratios_are_validated(tmp_path):
    prep = tmp_path / "prep"
    prepare(load_config(make_source(tmp_path)), prep)
    man = prep / "manifest.json"
    out = tmp_path / "ext"
    assert ml_main(["split", str(man), "--root", str(prep), "--out", str(out), "--group-by", "external"]) == 0
    rep = json.loads((out / "split_report.json").read_text())
    assert rep["images_per_split"] == {"train": 0, "val": 0, "test": 3} and rep["group_by"] == "external"
    assert ml_main(["split", str(man), "--root", str(prep), "--out", str(out), "--ratios", "0.5,0.5"]) == 1


def test_split_ratios_assign_whole_groups(tmp_path):
    def e(f, i):
        return {"image": f"{f}/{i}.jpg", "sha256": f"{int(f[4:]) * 10 + i:064x}", "field_id": f,
                "flight_id": "x", "width": 1, "height": 1, "labels": "l.txt"}
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"crop_type": "maize", "label_map": {"plant": 0},
                             "images": [e(f"site{k}", i) for k in range(9) for i in range(3)]}))
    r = group_split(load_manifest(p), "field", ratios=(0.6, 0.2, 0.2))
    assert [len(r.groups[s]) for s in ("train", "val", "test")] == [5, 2, 2] and r.leaks == []
