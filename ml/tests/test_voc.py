"""Parser VOC (anotasi NEON/DeepForest) & detail TP/FP/FN. Fixture sintetis + sampel resmi bila ada."""
from pathlib import Path

import pytest

from wallacea_ml.evaluate import match_details
from wallacea_ml.voc import load_voc

XML = """<annotation><filename>x.tif</filename><size><width>200</width><height>100</height><depth>3</depth></size>
<object><name>Tree</name><bndbox><xmin>20</xmin><ymin>10</ymin><xmax>60</xmax><ymax>40</ymax></bndbox></object>
<object><name>Tree</name><bndbox><xmin>190</xmin><ymin>90</ymin><xmax>230</xmax><ymax>130</ymax></bndbox></object>
<object><name>Snag</name><bndbox><xmin>0</xmin><ymin>0</ymin><xmax>5</xmax><ymax>5</ymax></bndbox></object>
</annotation>"""
SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "deepforest-neon"


def test_voc_pixels_to_normalized_with_clip_and_explicit_labels(tmp_path):
    p = tmp_path / "a.xml"
    p.write_text(XML)
    v = load_voc(p, {"Tree": "plant", "Snag": "drop"})
    assert (v.width, v.height) == (200, 100) and v.raw_labels == {"Tree": 2, "Snag": 1}
    assert v.boxes[0] == ("plant", pytest.approx([0.1, 0.1, 0.2, 0.3]))
    assert v.boxes[1] == ("plant", pytest.approx([0.95, 0.9, 0.05, 0.1]))   # di-clip ke tepi
    with pytest.raises(ValueError, match="tidak dipetakan"):
        load_voc(p, {"Tree": "plant"})


def test_match_details_lists_fp_and_missed():
    gt = [{"label": "plant", "bbox": [0.1, 0.1, 0.1, 0.1]}, {"label": "plant", "bbox": [0.5, 0.5, 0.1, 0.1]}]
    pred = [{"label": "plant", "confidence": 0.9, "bbox": [0.1, 0.1, 0.1, 0.1]},
            {"label": "plant", "confidence": 0.8, "bbox": [0.8, 0.8, 0.1, 0.1]}]
    m = match_details(gt, pred, 0.5, "plant")
    assert len(m["tp"]) == 1 and m["fp"] == [pred[1]] and m["fn"] == [gt[1]]


@pytest.mark.skipif(not SAMPLES.is_dir(), reason="sampel belum ada")
def test_packaged_samples_match_image_dimensions():
    from wallacea_ml import backend

    counts = {}
    for png in sorted(SAMPLES.glob("*.png")):
        v = load_voc(png.with_suffix(".xml"), {"Tree": "plant", "Alive": "plant", "Dead": "plant"})
        assert (v.width, v.height) == backend.load_oriented(png).size
        counts[png.name] = len(v.boxes)
    assert counts == {"2019_YELL_2_541000_4977000_image_crop.png": 279, "OSBS_029.png": 61, "SOAP_061.png": 37}
