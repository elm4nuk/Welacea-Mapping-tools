"""Konversi label COCO → WALLACEA/YOLO: category_id, piksel, normalisasi, class map — eksplisit."""
import pytest

from wallacea_ml.coco import (coco_to_normalized, convert, normalized_to_yolo, resolve_class_map, validate_coco,
                              yolo_to_normalized)


def coco(**kw):
    base = {
        "images": [{"id": 10, "file_name": "a.png", "width": 200, "height": 100},
                   {"id": 11, "file_name": "kosong.png", "width": 200, "height": 100},
                   {"id": 12, "file_name": "gulma.png", "width": 200, "height": 100}],
        # id kategori TIDAK berurutan & tidak mulai dari 0: pemetaan harus lewat id/nama, bukan indeks
        "categories": [{"id": 7, "name": "maize"}, {"id": 3, "name": "weed"}],
        "annotations": [
            {"id": 1, "image_id": 10, "category_id": 7, "bbox": [20, 10, 40, 30]},
            {"id": 2, "image_id": 10, "category_id": 3, "bbox": [100, 50, 10, 10]},
            {"id": 3, "image_id": 10, "category_id": 7, "bbox": [190, 90, 20, 20]},   # keluar tepi → clip
            {"id": 4, "image_id": 12, "category_id": 3, "bbox": [5, 5, 10, 10]},
        ],
    }
    base.update(kw)
    return base


def test_pixel_to_normalized_and_yolo_roundtrip():
    bb, clipped = coco_to_normalized([20, 10, 40, 30], 200, 100)
    assert bb == pytest.approx([0.1, 0.1, 0.2, 0.3]) and not clipped
    line = normalized_to_yolo(bb, 0)
    assert line == "0 0.200000 0.250000 0.200000 0.300000"     # cx = (20+20)/200, cy = (10+15)/100
    cls, back = yolo_to_normalized(line)
    assert cls == 0 and back == pytest.approx(bb)


def test_clip_out_of_image():
    bb, clipped = coco_to_normalized([190, 90, 20, 20], 200, 100)
    assert clipped and bb == pytest.approx([0.95, 0.9, 0.05, 0.1])


def test_class_map_by_name_and_id_explicit():
    c = coco()
    assert resolve_class_map(c, {"maize": "plant", "weed": "drop"}) == {7: "plant", 3: "drop"}
    assert resolve_class_map(c, {"7": "plant", "3": "drop"}) == {7: "plant", 3: "drop"}
    with pytest.raises(ValueError, match="tidak dipetakan"):
        resolve_class_map(c, {"maize": "plant"})                 # weed dipakai tapi tidak dipetakan
    with pytest.raises(ValueError, match="tidak ada"):
        resolve_class_map(c, {"maize": "plant", "weed": "drop", "jagung": "plant"})
    with pytest.raises(ValueError, match="harus salah satu"):
        resolve_class_map(c, {"maize": "tanaman", "weed": "drop"})


def test_convert_excludes_unannotated_and_dropped_only_images():
    out, stats = convert(coco(), {"maize": "plant", "weed": "drop"})
    assert [o.file_name for o in out] == ["a.png"]
    a = out[0]
    assert [lab for lab, _ in a.boxes] == ["plant", "plant"] and a.dropped == 1 and a.clipped == 1
    assert stats["excluded_unannotated"] == 1 and stats["excluded_only_dropped"] == 1
    # hanya bila dokumentasi dataset menyatakan gambar kosong = negatif
    out2, stats2 = convert(coco(), {"maize": "plant", "weed": "drop"}, empty_images_are_negative=True)
    assert {o.file_name for o in out2} == {"a.png", "kosong.png"} and stats2["negative_images"] == 1


def test_tiny_boxes_dropped():
    c = coco(annotations=[{"id": 1, "image_id": 10, "category_id": 7, "bbox": [0, 0, 1, 1]}])
    out, stats = convert(c, {"maize": "plant", "weed": "drop"})
    assert out == [] and stats["too_small_after_clip"] == 1


def test_validate_detects_structural_errors():
    c = coco()
    c["images"].append({"id": 10, "file_name": "a.png", "width": 0, "height": 100})
    c["annotations"] += [
        {"id": 5, "image_id": 99, "category_id": 7, "bbox": [0, 0, 5, 5]},
        {"id": 6, "image_id": 10, "category_id": 42, "bbox": [0, 0, 5, 5]},
        {"id": 7, "image_id": 10, "category_id": 7, "bbox": [0, 0, float("nan"), 5]},
        {"id": 8, "image_id": 10, "category_id": 7, "bbox": [0, 0, -3, 5]},
        {"id": 9, "image_id": 10, "category_id": 7, "bbox": [20, 10, 40, 30]},           # duplikat id 1
        {"id": 10, "image_id": 11, "category_id": 7, "bbox": [0.1, 0.2, 0.3, 0.4]},      # tampak ternormalisasi
    ]
    codes = {i.code for i in validate_coco(c).issues}
    assert {"DUP_IMAGE_ID", "DUP_FILE_NAME", "BAD_IMAGE_SIZE", "ORPHAN_ANNOTATION", "UNKNOWN_CATEGORY",
            "BAD_BBOX", "EMPTY_BBOX", "DUP_BBOX", "MAYBE_NORMALIZED", "BBOX_OUT_OF_IMAGE"} <= codes


def test_validate_reports_unannotated_images_separately():
    r = validate_coco(coco())
    assert r.unannotated_images == ["kosong.png"] and r.errors == []
