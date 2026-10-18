"""Impor backup starter v0.1 (schemaVersion 1) sebagai salinan."""
import base64
import json

from conftest import assert_error, create_survey, jpeg_bytes, png_bytes

SVG = "data:image/svg+xml;charset=utf-8," + "%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E"


def data_url(b: bytes, mime="image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(b).decode()


def starter_backup():
    """Bentuk sama dengan exportBackup() di legacy/starter-v01/dist/app.js."""
    return {
        "schemaVersion": 1, "exportedAt": "2026-10-18T04:00:00.000Z",
        "surveys": [
            {"id": "demo1", "name": "Parsel demonstrasi", "crop": "Tanaman perkebunan", "location": "Lokasi ilustrasi",
             "date": "2026-10-18", "notes": "Data contoh untuk mencoba penandaan.", "isDemo": True,
             "createdAt": "2026-10-18T04:00:00.000Z",
             "photos": [{"id": "p0", "name": "parsel-contoh.svg", "dataUrl": SVG, "width": 1200, "height": 800,
                         "createdAt": "2026-10-18T04:00:00.000Z",
                         "annotations": [{"id": "a", "x": 0.2, "y": 0.3, "kind": "plant", "note": "Penanda contoh 1",
                                          "source": "manual", "status": "confirmed"}]}]},
            {"id": "s1", "name": "Kebun Sawit Muda", "crop": "Kelapa sawit", "location": "Blok 3", "date": "2026-10-17",
             "notes": "Catatan lapangan: tanah basah", "isDemo": False, "createdAt": "2026-10-18T04:00:00.000Z",
             "photos": [{"id": "p1", "name": "DJI_0001.JPG", "dataUrl": data_url(jpeg_bytes(80, 40), "image/jpeg"),
                         "width": 80, "height": 40, "createdAt": "2026-10-18T04:00:00.000Z",
                         "annotations": [
                             {"id": "a1", "x": 0.5, "y": 0.5, "kind": "plant", "note": "", "source": "manual",
                              "status": "confirmed"},
                             {"id": "a2", "x": 0.25, "y": 0.4, "kind": "plant", "note": "Model: tim-v0",
                              "source": "ai", "status": "pending", "confidence": 0.7, "box": [0.1, 0.2, 0.3, 0.4]},
                             {"id": "a3", "x": 0.6, "y": 0.6, "kind": "gap", "note": "cek", "source": "ai",
                              "status": "confirmed", "confidence": 0.5},
                         ]}]},
        ],
    }


def post_backup(c, payload) -> object:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return c.post("/api/v1/imports/starter-backup", files={"file": ("wallacea-backup.json", raw, "application/json")})


def test_import_starter_backup_as_copy(client):
    existing = create_survey(client, name="Kebun Sawit Muda")
    r = post_backup(client, starter_backup())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["photo_count"] == 2 and body["annotation_count"] == 4
    assert [w["code"] for w in body["warnings"]] == ["DEMO_IMAGE_REPLACED"]
    demo, real = body["surveys"]
    assert demo["is_demo"] is True and demo["name"] == "Parsel demonstrasi (salinan)"
    assert real["is_demo"] is False and real["name"] == "Kebun Sawit Muda (salinan)"
    assert real["notes"] == "Catatan lapangan: tanah basah" and real["survey_date"] == "2026-10-17"
    assert real["crop_type"] == "Kelapa sawit" and real["location_label"] == "Blok 3"
    # Survei lama tidak ditimpa.
    assert client.get(f"/api/v1/surveys/{existing['id']}").json()["name"] == "Kebun Sawit Muda"

    photo = client.get(f"/api/v1/surveys/{real['id']}/photos").json()["items"][0]
    assert photo["original_name"] == "DJI_0001.JPG" and (photo["width"], photo["height"]) == (80, 40)
    anns = {a["note"]: a for a in client.get(f"/api/v1/photos/{photo['id']}/annotations").json()["items"]}
    assert anns[""]["source"] == "manual" and anns[""]["review_status"] == "accepted"
    ai = anns["Model: tim-v0"]
    assert ai["source"] == "model" and ai["review_status"] == "pending" and ai["confidence"] == 0.7
    assert ai["geometry_type"] == "bbox" and ai["bbox"] == [0.1, 0.2, 0.3, 0.4] and ai["analysis_run_id"]
    assert anns["cek"]["review_status"] == "accepted" and anns["cek"]["kind"] == "gap"
    assert photo["counts"]["plant_accepted"] == 1 and photo["counts"]["plant_pending"] == 1
    run = client.get(f"/api/v1/photos/{photo['id']}/analysis-runs").json()["items"][0]
    assert run["run_type"] == "import" and run["model_id"] == "starter-v01-backup" and run["candidate_count"] == 2

    demo_photo = client.get(f"/api/v1/surveys/{demo['id']}/photos").json()["items"][0]
    assert demo_photo["mime_type"] == "image/png" and (demo_photo["width"], demo_photo["height"]) == (1200, 800)
    demo_ann = client.get(f"/api/v1/photos/{demo_photo['id']}/annotations").json()["items"][0]
    assert demo_ann["note"] == "Penanda contoh 1"

    # Impor kedua = salinan baru lagi, bukan menimpa.
    assert post_backup(client, starter_backup()).status_code == 201
    assert client.get("/api/v1/surveys").json()["total"] == 5


def test_invalid_backups_are_atomic(client, data_dir):
    assert_error(post_backup(client, b"{not json"), 400, "INVALID_BACKUP")
    assert_error(post_backup(client, {"schemaVersion": 2, "surveys": []}), 400, "INVALID_BACKUP")
    bad = starter_backup()
    bad["surveys"][1]["photos"][0]["annotations"][0]["x"] = 1.7
    err = assert_error(post_backup(client, bad), 400, "INVALID_BACKUP")
    assert err["details"] == {"survey_index": 1, "photo_index": 0, "annotation_index": 0}
    svg_real = starter_backup()
    svg_real["surveys"][1]["photos"][0]["dataUrl"] = SVG  # SVG pada survei nyata ditolak
    assert_error(post_backup(client, svg_real), 400, "INVALID_BACKUP")
    corrupt = starter_backup()
    corrupt["surveys"][1]["photos"][0]["dataUrl"] = data_url(b"bukan gambar")
    assert_error(post_backup(client, corrupt), 400, "INVALID_IMAGE")
    # Tidak ada survei/berkas setengah jadi.
    assert client.get("/api/v1/surveys").json()["total"] == 0
    assert not [f for f in (data_dir / "uploads").rglob("*") if f.is_file()]


def test_backup_png_and_invalid_box_kept_as_point(client):
    b = starter_backup()
    b["surveys"] = [b["surveys"][1]]
    b["surveys"][0]["photos"][0]["dataUrl"] = data_url(png_bytes(20, 20))
    b["surveys"][0]["photos"][0]["annotations"][1]["box"] = [0.9, 0.9, 0.5, 0.5]
    body = post_backup(client, b).json()
    assert [w["code"] for w in body["warnings"]] == ["BBOX_DROPPED"]
