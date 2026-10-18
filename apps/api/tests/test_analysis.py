"""Contract test pipeline model → pending → accepted. Detector adalah test double; BUKAN uji akurasi model."""
import hashlib

import pytest

from app.inference import InferenceFailed, ModelUnavailable, RawDetection
from conftest import FakeDetector, assert_error, create_survey, jpeg_bytes, png_bytes, upload_ok


def setup(c, data=None, mime="image/png"):
    s = create_survey(c)
    return upload_ok(c, s["id"], data, "f.jpg" if mime == "image/jpeg" else "f.png", mime)


def counts(c, photo_id):
    return c.get(f"/api/v1/photos/{photo_id}").json()["counts"]


def test_without_model_manual_still_works(client):
    p = setup(client)
    err = assert_error(client.post(f"/api/v1/photos/{p['id']}/analyze"), 503, "MODEL_NOT_CONFIGURED")
    assert "manual" in err["message"]
    assert client.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["total"] == 0  # tidak ada run palsu
    assert client.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "x": .5, "y": .5}).status_code == 201
    assert counts(client, p["id"])["plant_accepted"] == 1


def test_pipeline_pending_then_review_changes_count(make_client):
    det = FakeDetector()
    c = make_client(detector=det)
    p = setup(c)
    c.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "x": .9, "y": .9})
    r = c.post(f"/api/v1/photos/{p['id']}/analyze")
    assert r.status_code == 201, r.text
    body = r.json()
    run = body["run"]
    assert run["status"] == "succeeded" and run["run_type"] == "inference" and run["candidate_count"] == 3
    assert run["input_sha256"] == p["sha256"] and run["model_id"] == "fake-plant-detector"
    assert run["model_version"] == "sha256:test0001" and run["finished_at"]
    assert all(a["review_status"] == "pending" and a["source"] == "model" and a["analysis_run_id"] == run["id"]
               and a["geometry_type"] == "bbox" for a in body["candidates"])
    assert det.last_size == (p["width"], p["height"])
    # Pending tidak masuk hitungan.
    cnt = counts(c, p["id"])
    assert cnt["plant_accepted"] == 1 and cnt["plant_pending"] == 2 and cnt["pending_review"] == 3

    plant1, plant2, gap = body["candidates"]
    ok = c.patch(f"/api/v1/annotations/{plant1['id']}", json={"review_status": "accepted"}, headers={"If-Match": '"1"'})
    assert ok.status_code == 200 and ok.json()["source"] == "model"  # source tetap model
    c.patch(f"/api/v1/annotations/{plant2['id']}", json={"review_status": "rejected"}, headers={"If-Match": '"1"'})
    c.patch(f"/api/v1/annotations/{gap['id']}", json={"kind": "plant", "review_status": "accepted"},
            headers={"If-Match": '"1"'})
    cnt = counts(c, p["id"])
    assert cnt["plant_accepted"] == 3 and cnt["plant_pending"] == 0 and cnt["rejected"] == 1
    report = c.get(f"/api/v1/surveys/{p['survey_id']}/report").json()
    assert report["photos"][0]["counts"]["plant_accepted"] == 3


def test_repeat_analysis_is_controlled(make_client):
    c = make_client(detector=FakeDetector())
    p = setup(c)
    url = f"/api/v1/photos/{p['id']}/analyze"
    first = c.post(url).json()
    err = assert_error(c.post(url), 409, "ANALYSIS_EXISTS")
    assert err["details"]["run_id"] == first["run"]["id"]
    assert c.get(f"/api/v1/photos/{p['id']}/annotations").json()["total"] == 3  # tidak digandakan

    keep = first["candidates"][0]
    c.patch(f"/api/v1/annotations/{keep['id']}", json={"review_status": "accepted"}, headers={"If-Match": '"1"'})
    rep = c.post(url, json={"on_existing": "replace_pending"})
    assert rep.status_code == 201
    replaced = set(rep.json()["replaced_annotation_ids"])
    assert replaced == {a["id"] for a in first["candidates"][1:]}  # yang sudah accepted tidak disentuh
    items = c.get(f"/api/v1/photos/{p['id']}/annotations").json()["items"]
    assert len(items) == 4 and any(a["id"] == keep["id"] for a in items)

    app_ = c.post(url, json={"on_existing": "append"})
    assert app_.status_code == 201 and c.get(f"/api/v1/photos/{p['id']}/annotations").json()["total"] == 7
    runs = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()
    assert runs["total"] == 3 and len({r["id"] for r in runs["items"]}) == 3
    assert_error(c.post(url, json={"on_existing": "overwrite"}), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("exc,status,code", [
    (ModelUnavailable("bobot rusak"), 503, "MODEL_UNAVAILABLE"),
    (InferenceFailed("OOM"), 500, "INFERENCE_FAILED"),
    (RuntimeError("bug"), 500, "INFERENCE_FAILED"),
])
def test_detector_failures_mark_run_failed(make_client, exc, status, code):
    c = make_client(detector=FakeDetector(raises=exc))
    p = setup(c)
    err = assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), status, code)
    run = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["id"] == err["details"]["run_id"] and run["status"] == "failed" and run["error_code"] == code
    assert c.get(f"/api/v1/photos/{p['id']}/annotations").json()["total"] == 0
    # Setelah gagal, run baru boleh dicoba (tidak macet "running").
    assert c.post(f"/api/v1/photos/{p['id']}/analyze").status_code == status


def test_unavailable_model_state(make_client):
    c = make_client(detector=FakeDetector(state="error"))
    p = setup(c)
    assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), 503, "MODEL_UNAVAILABLE")
    assert c.get("/api/v1/health").json()["model"]["available"] is False


def test_timeout(make_client):
    c = make_client(detector=FakeDetector(sleep=1.0), inference_timeout_s=0.2)
    p = setup(c)
    err = assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), 504, "INFERENCE_TIMEOUT")
    run = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["status"] == "failed" and run["error_code"] == "INFERENCE_TIMEOUT" and run["id"] == err["details"]["run_id"]


def test_capacity_limit_on_candidates(make_client):
    c = make_client(detector=FakeDetector(), max_annotations_per_photo=2)
    p = setup(c)
    assert_error(c.post(f"/api/v1/photos/{p['id']}/analyze"), 422, "ANNOTATION_LIMIT_EXCEEDED")
    run = c.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["status"] == "failed"


def test_interrupted_runs_marked_failed_on_restart(make_client):
    from app import models as m
    from app.db import utcnow

    c = make_client()
    p = setup(c)
    with c.app.state.sessionmaker() as db:
        db.add(m.AnalysisRun(photo_id=p["id"], run_type="inference", model_id="x", input_sha256=p["sha256"],
                             status="running", started_at=utcnow()))
        db.commit()
    c.__exit__(None, None, None)
    c2 = make_client()
    run = c2.get(f"/api/v1/photos/{p['id']}/analysis-runs").json()["items"][0]
    assert run["status"] == "failed" and run["error_code"] == "INTERRUPTED" and run["finished_at"]


def test_detection_uses_oriented_image(make_client):
    det = FakeDetector(detections=[RawDetection("plant", [0.0, 0.0, 0.5, 0.5], 0.8)])
    c = make_client(detector=det)
    p = setup(c, jpeg_bytes(120, 60, orientation=6), "image/jpeg")
    assert c.post(f"/api/v1/photos/{p['id']}/analyze").status_code == 201
    assert det.last_size == (60, 120) == (p["width"], p["height"])


# ------------------------------------------------------------------ import
def det_payload(p, **kw):
    return {"image_width": p["width"], "image_height": p["height"], "model": "tim-ml-v0",
            "detections": [{"label": "plant", "confidence": 0.8, "bbox": [0.1, 0.2, 0.3, 0.4]},
                           {"label": "check", "confidence": None, "bbox": [0.5, 0.5, 0.1, 0.1]}], **kw}


def test_import_detections(client):
    p = setup(client)
    payload = det_payload(p, image_sha256=p["sha256"], requires_review=True, georeferenced=False)
    r = client.post(f"/api/v1/photos/{p['id']}/detections/import", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["run"]["run_type"] == "import" and body["run"]["model_id"] == "tim-ml-v0"
    assert body["run"]["parameters"]["sha256_verified"] is True
    a = body["candidates"][0]
    assert a["review_status"] == "pending" and a["bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert (a["x"], a["y"]) == pytest.approx((0.25, 0.4))  # sama dengan starter: pusat kotak
    assert counts(client, p["id"])["plant_accepted"] == 0
    assert_error(client.post(f"/api/v1/photos/{p['id']}/detections/import", json=payload), 409, "ANALYSIS_EXISTS")


def test_import_validation(client):
    p = setup(client, jpeg_bytes(120, 60, orientation=6), "image/jpeg")
    url = f"/api/v1/photos/{p['id']}/detections/import"
    err = assert_error(client.post(url, json=det_payload(p, image_width=120, image_height=60)), 422, "DETECTION_MISMATCH")
    assert "orientasi EXIF" in err["message"]
    assert_error(client.post(url, json=det_payload(p, image_sha256=hashlib.sha256(b"x").hexdigest())), 422,
                 "DETECTION_MISMATCH")
    bad_box = det_payload(p)
    bad_box["detections"] = [{"label": "plant", "confidence": 0.8, "bbox": [0.9, 0.2, 0.5, 0.1]}]
    assert_error(client.post(url, json=bad_box), 422, "VALIDATION_ERROR")
    coco = det_payload(p)
    coco["detections"] = [{"label": "person", "confidence": 0.8, "bbox": [0.1, 0.1, 0.1, 0.1]}]
    assert_error(client.post(url, json=coco), 422, "VALIDATION_ERROR")
    nan_conf = det_payload(p)
    nan_conf["detections"] = [{"label": "plant", "confidence": 1.5, "bbox": [0.1, 0.1, 0.1, 0.1]}]
    assert_error(client.post(url, json=nan_conf), 422, "VALIDATION_ERROR")
    assert client.get(f"/api/v1/photos/{p['id']}/annotations").json()["total"] == 0


def test_import_payload_limit(make_client):
    c = make_client(max_detection_payload_bytes=500)
    p = setup(c)
    payload = det_payload(p, model="x" * 100)
    payload["detections"] *= 10
    r = c.post(f"/api/v1/photos/{p['id']}/detections/import", json=payload)
    assert_error(r, 413, "PAYLOAD_TOO_LARGE")
