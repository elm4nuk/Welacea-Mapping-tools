import csv
import io

from app.routers.reports import CSV_COLUMNS, csv_cell
from conftest import FakeDetector, assert_error, create_survey, upload_ok


def test_report_counts_and_disclaimers(make_client):
    c = make_client(detector=FakeDetector())
    s = create_survey(c)
    p1, p2 = upload_ok(c, s["id"]), upload_ok(c, s["id"])
    for x in (0.1, 0.2):
        c.post(f"/api/v1/photos/{p1['id']}/annotations", json={"kind": "plant", "x": x, "y": 0.5})
    c.post(f"/api/v1/photos/{p2['id']}/annotations", json={"kind": "plant", "x": 0.3, "y": 0.5})
    c.post(f"/api/v1/photos/{p2['id']}/annotations", json={"kind": "gap", "x": 0.4, "y": 0.5, "note": "kosong?"})
    c.post(f"/api/v1/photos/{p2['id']}/analyze")

    rep = c.get(f"/api/v1/surveys/{s['id']}/report").json()
    assert [r["counts"]["plant_accepted"] for r in rep["photos"]] == [2, 1]
    assert rep["photos"][1]["counts"]["plant_pending"] == 2
    t = rep["totals"]
    assert t["plant_accepted_sum_across_photos"] == 3 and t["counts_are_unique_plants"] is False
    assert t["pending_review"] == 3 and t["gap_accepted"] == 1
    assert any("tidak boleh dijumlahkan" in d for d in rep["disclaimers"])
    assert any("bukan lintang/bujur" in d for d in rep["disclaimers"])
    kinds = sorted(f["kind"] + ":" + f["review_status"] for f in rep["findings"])
    assert kinds == ["gap:accepted", "gap:pending"]
    assert_error(c.get("/api/v1/surveys/nope/report"), 404, "NOT_FOUND")


def test_csv_export_and_formula_injection(client):
    s = create_survey(client, name="=HYPERLINK(\"http://evil\")", location_label="+cmd")
    p = upload_ok(client, s["id"], name="@foto.png")
    client.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "x": 0.5, "y": 0.25, "note": "-1+2"})
    client.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "check", "geometry_type": "bbox",
                                                                "bbox": [0.1, 0.1, 0.2, 0.2], "review_status": "pending"})
    r = client.get(f"/api/v1/surveys/{s['id']}/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    assert list(rows[0].keys()) == CSV_COLUMNS and len(rows) == 2
    assert rows[0]["survey_name"].startswith("'=")
    assert rows[0]["location_label"] == "'+cmd" and rows[0]["photo_name"] == "'@foto.png"
    assert rows[0]["note"] == "'-1+2"
    assert rows[0]["counted_as_plant"] == "ya" and rows[1]["counted_as_plant"] == "tidak"
    assert rows[1]["bbox_width"] == "0.2" and rows[0]["bbox_width"] == ""
    assert float(rows[0]["y"]) == 0.25


def test_csv_cell():
    assert csv_cell("=SUM(A1)") == "'=SUM(A1)"
    assert csv_cell("\tx") == "'\tx"
    assert csv_cell("normal") == "normal"
    assert csv_cell(None) == "" and csv_cell(True) == "ya" and csv_cell(3) == "3"
