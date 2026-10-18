import hashlib
import io

from PIL import Image

from conftest import assert_error, create_survey, jpeg_bytes, png_bytes, upload, upload_ok, webp_bytes


def test_upload_png_jpeg_webp(client):
    s = create_survey(client)
    for data, name, mime, exp in [(png_bytes(), "a.png", "image/png", "image/png"),
                                  (jpeg_bytes(), "b.jpg", "image/jpeg", "image/jpeg"),
                                  (webp_bytes(), "c.webp", "image/webp", "image/webp")]:
        p = upload_ok(client, s["id"], data, name, mime)
        assert p["mime_type"] == exp
        assert p["sha256"] == hashlib.sha256(data).hexdigest()
        assert p["georef_status"] == "none"
        assert p["content_url"] == f"/api/v1/photos/{p['id']}/content"
        content = client.get(p["content_url"])
        assert content.status_code == 200 and content.content == data  # byte asli persis
        assert content.headers["content-type"].startswith(exp)
    assert client.get(f"/api/v1/surveys/{s['id']}").json()["photo_count"] == 3


def test_mime_from_content_not_client(client):
    s = create_survey(client)
    # PNG asli dikirim dengan nama .jpg dan content-type salah → disimpan sebagai PNG.
    p = upload_ok(client, s["id"], png_bytes(), "palsu.jpg", "application/octet-stream")
    assert p["mime_type"] == "image/png"
    # SVG / teks berkedok PNG → ditolak.
    assert_error(upload(client, s["id"], b"<svg xmlns='http://www.w3.org/2000/svg'/>", "x.png", "image/png"),
                 400, "INVALID_IMAGE")
    assert_error(upload(client, s["id"], b"not an image", "x.jpg", "image/jpeg"), 400, "INVALID_IMAGE")
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    assert_error(upload(client, s["id"], gif.getvalue(), "x.gif", "image/gif"), 415, "UNSUPPORTED_MEDIA_TYPE")


def test_truncated_image_rejected(client):
    s = create_survey(client)
    data = jpeg_bytes(400, 300)
    assert_error(upload(client, s["id"], data[: len(data) // 2], "t.jpg", "image/jpeg"), 400, "INVALID_IMAGE")


def test_size_and_pixel_limits(make_client):
    c = make_client(max_upload_bytes=2000, max_pixels=50 * 50)
    s = create_survey(c)
    big = png_bytes(40, 40) + b"\0" * 5000
    assert_error(upload(c, s["id"], big), 413, "PAYLOAD_TOO_LARGE")
    assert_error(upload(c, s["id"], png_bytes(60, 60)), 413, "IMAGE_TOO_LARGE")
    assert upload(c, s["id"], png_bytes(40, 40)).status_code == 201


def test_exif_orientation_metadata_and_display(client):
    s = create_survey(client)
    data = jpeg_bytes(120, 60, orientation=6, gps=True, taken="2026:10:18 09:12:33")
    p = upload_ok(client, s["id"], data, "drone.jpg", "image/jpeg")
    # Orientation 6 = rotasi 90°: dimensi pasca-orientasi tertukar.
    assert (p["width"], p["height"]) == (60, 120)
    assert p["exif_orientation"] == 6
    assert p["has_exif_gps"] is True and p["georef_status"] == "none"
    assert p["captured_at"] == "2026-10-18T09:12:33"
    disp = Image.open(io.BytesIO(client.get(p["display_url"]).content))
    assert disp.size == (60, 120)
    assert client.get(p["content_url"]).content == data  # asli tetap utuh
    thumb = Image.open(io.BytesIO(client.get(p["thumbnail_url"]).content))
    assert thumb.format == "JPEG" and thumb.size == (60, 120)


def test_thumbnail_is_bounded(client):
    s = create_survey(client)
    p = upload_ok(client, s["id"], png_bytes(1600, 900))
    thumb = Image.open(io.BytesIO(client.get(p["thumbnail_url"]).content))
    assert max(thumb.size) == 512


def test_duplicate_warning_keeps_both(client):
    s = create_survey(client)
    data = png_bytes(30, 30)
    first = upload_ok(client, s["id"], data)
    r = upload(client, s["id"], data)
    assert r.status_code == 201
    body = r.json()
    assert body["warnings"][0]["code"] == "DUPLICATE_IN_SURVEY"
    assert body["warnings"][0]["details"]["photo_ids"] == [first["id"]]
    items = client.get(f"/api/v1/surveys/{s['id']}/photos").json()["items"]
    assert len(items) == 2
    assert items[0]["duplicate_photo_ids"] == [body["photo"]["id"]]
    # Survei lain dengan foto sama: bukan duplikat dalam survei.
    other = create_survey(client)
    assert upload(client, other["id"], data).json()["warnings"] == []


def test_filename_is_metadata_only(client, data_dir):
    s = create_survey(client)
    p = upload_ok(client, s["id"], png_bytes(), "..\\..\\etc/passwd.png")
    assert p["original_name"] == "passwd.png"
    files = [f for f in (data_dir / "uploads").rglob("*") if f.is_file()]
    assert all("passwd" not in f.name for f in files)
    assert all(data_dir / "uploads" in f.parents for f in files)


def test_upload_to_missing_or_demo_survey(client):
    assert_error(upload(client, "doesnotexist"), 404, "NOT_FOUND")
    demo = client.post("/api/v1/demo/surveys").json()
    assert_error(upload(client, demo["id"]), 409, "DEMO_SURVEY_READONLY")


def test_delete_photo(client, data_dir):
    s = create_survey(client)
    p = upload_ok(client, s["id"])
    client.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "x": 0.1, "y": 0.1})
    assert_error(client.delete(f"/api/v1/photos/{p['id']}", headers={"If-Match": '"1"'}), 409, "REVISION_CONFLICT")
    assert client.delete(f"/api/v1/photos/{p['id']}").status_code == 204
    assert_error(client.get(f"/api/v1/photos/{p['id']}"), 404, "NOT_FOUND")
    assert_error(client.get(f"/api/v1/photos/{p['id']}/content"), 404, "NOT_FOUND")
    assert not [f for f in (data_dir / "uploads").rglob("*") if f.is_file()]


def test_failed_db_write_cleans_files(make_client, data_dir, monkeypatch):
    import sqlalchemy.orm

    c = make_client(raise_server_exceptions=False)
    s = create_survey(c)
    real_commit = sqlalchemy.orm.Session.commit

    def boom(self):
        raise RuntimeError("db down")

    monkeypatch.setattr(sqlalchemy.orm.Session, "commit", boom)
    r = upload(c, s["id"])
    monkeypatch.setattr(sqlalchemy.orm.Session, "commit", real_commit)
    assert_error(r, 500, "INTERNAL_ERROR")
    assert not [f for f in (data_dir / "uploads").rglob("*") if f.is_file()]
    assert c.get(f"/api/v1/surveys/{s['id']}/photos").json()["total"] == 0
