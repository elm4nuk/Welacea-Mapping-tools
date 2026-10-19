"""Kontrak revisi 3: katalog foto contoh (CR-FE-002), AnalysisRun.target (CR-FE-003),
AnnotationUpdate non-nullable (CR-FE-001)."""
from __future__ import annotations

import hashlib
import json

from conftest import FakeDetector, create_survey, png_bytes
from app.inference import DetectorInfo


def test_sample_catalog_lists_license_and_serves_exact_bytes(client):
    r = client.get("/api/v1/samples")
    assert r.status_code == 200
    items = r.json()["items"]
    assert {i["id"] for i in items} == {"neon-osbs-029", "neon-soap-061", "neon-yell-crop"}
    for i in items:
        assert i["license_name"] and i["license_url"].startswith("https://") and i["source_url"].startswith("https://")
        assert "bukan drone" in i["imagery"] and i["has_human_annotations"]
        f = client.get(i["file_url"])
        assert f.status_code == 200 and f.headers["content-type"] == i["media_type"]
        assert hashlib.sha256(f.content).hexdigest() == i["sha256"] and len(f.content) == i["size_bytes"]
    assert client.get("/api/v1/samples/tidak-ada/file").json()["error"]["code"] == "NOT_FOUND"


def test_sample_goes_through_normal_upload(client):
    item = client.get("/api/v1/samples").json()["items"][0]
    data = client.get(item["file_url"]).content
    s = create_survey(client)
    up = client.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": (item["filename"], data, item["media_type"])})
    assert up.status_code == 201
    p = up.json()["photo"]
    assert (p["width"], p["height"]) == (item["width"], item["height"]) and p["sha256"] == item["sha256"]
    assert client.get(f"/api/v1/photos/{p['id']}/annotations").json()["items"] == []   # tidak ada anotasi bawaan


def test_catalog_skips_tampered_or_missing_files(make_client, tmp_path):
    d = tmp_path / "samples"
    (d / "x").mkdir(parents=True)
    (d / "x" / "a.png").write_bytes(png_bytes())
    entry = {"id": "a", "title": "A", "file": "x/a.png", "sha256": "0" * 64}
    escape = {"id": "b", "title": "B", "file": "../../etc.png", "sha256": "0" * 64}
    (d / "catalog.json").write_text(json.dumps({"defaults": {"source_name": "s", "source_url": "https://x",
        "license_name": "l", "license_url": "https://y", "attribution": "a", "imagery": "i"},
        "samples": [entry, escape]}))
    c = make_client(samples_dir=d)
    assert c.get("/api/v1/samples").json() == {"items": [], "total": 0}          # sha256 salah & path keluar → dilewati
    c2 = make_client(samples_dir=tmp_path / "tidak-ada")
    assert c2.get("/api/v1/samples").json()["total"] == 0


class TreeDetector(FakeDetector):
    def info(self):
        return DetectorInfo(state="loaded", message="fake", model_id="fake-tree", model_version="sha256:t",
                            adapter="deepforest", target="tree_crown", target_label="Kandidat tajuk pohon")


def test_run_target_matches_health_target(make_client):
    c = make_client(detector=TreeDetector())
    assert c.get("/api/v1/health").json()["model"]["target"] == "tree_crown"
    s = create_survey(c)
    p = c.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": ("a.png", png_bytes(), "image/png")}).json()["photo"]
    run = c.post(f"/api/v1/photos/{p['id']}/analyze").json()["run"]
    assert run["target"] == "tree_crown"
    assert c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]["target"] == "tree_crown"


def test_failed_run_still_carries_target(make_client):
    from app.inference import InferenceFailed

    det = TreeDetector(raises=InferenceFailed("x"))
    c = make_client(detector=det)
    s = create_survey(c)
    p = c.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": ("a.png", png_bytes(), "image/png")}).json()["photo"]
    assert c.post(f"/api/v1/photos/{p['id']}/analyze").status_code == 500
    run = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["status"] == "failed" and run["target"] == "tree_crown"


def test_annotation_update_schema_matches_runtime(client):
    spec = client.get("/api/v1/openapi.json").json()["components"]["schemas"]["AnnotationUpdate"]["properties"]
    for f in ("kind", "note", "review_status", "geometry_type", "x", "y"):
        assert "anyOf" not in spec[f] or all(a.get("type") != "null" for a in spec[f]["anyOf"]), f
    assert any(a.get("type") == "null" for a in spec["bbox"]["anyOf"])            # bbox:null tetap = ubah ke titik
    s = create_survey(client)
    p = client.post(f"/api/v1/surveys/{s['id']}/photos", files={"file": ("a.png", png_bytes(), "image/png")}).json()["photo"]
    a = client.post(f"/api/v1/photos/{p['id']}/annotations",
                    json={"kind": "plant", "geometry_type": "bbox", "bbox": [0.1, 0.1, 0.2, 0.2]}).json()
    bad = client.patch(f"/api/v1/annotations/{a['id']}", json={"kind": None}, headers={"If-Match": '"1"'})
    assert bad.status_code == 422                                                  # runtime tetap menolak null
    ok = client.patch(f"/api/v1/annotations/{a['id']}", json={"bbox": [0.2, 0.2, 0.1, 0.1]}, headers={"If-Match": '"1"'})
    assert ok.status_code == 200 and ok.json()["x"] == 0.25                        # bbox tanpa x/y diterima
