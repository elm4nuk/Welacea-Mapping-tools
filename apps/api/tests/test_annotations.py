import pytest

from conftest import assert_error, create_survey, upload_ok


@pytest.fixture
def photo(client):
    s = create_survey(client)
    return upload_ok(client, s["id"])


def ann_url(photo):
    return f"/api/v1/photos/{photo['id']}/annotations"


def test_create_point_and_bbox(client, photo):
    r = client.post(ann_url(photo), json={"kind": "plant", "x": 0.25, "y": 0.75, "note": "tepi"})
    assert r.status_code == 201
    a = r.json()
    assert a["source"] == "manual" and a["review_status"] == "accepted" and a["geometry_type"] == "point"
    assert a["bbox"] is None and a["confidence"] is None and a["revision"] == 1 and r.headers["ETag"] == '"1"'

    b = client.post(ann_url(photo), json={"kind": "check", "geometry_type": "bbox", "bbox": [0.1, 0.2, 0.4, 0.2]}).json()
    assert b["bbox"] == [0.1, 0.2, 0.4, 0.2]
    assert (b["x"], b["y"]) == pytest.approx((0.3, 0.3))

    page = client.get(ann_url(photo)).json()
    assert page["total"] == 2 and page["photo_revision"] == 3  # upload=1, +1 per penanda


@pytest.mark.parametrize("body", [
    {"kind": "plant", "x": 1.5, "y": 0.5},
    {"kind": "plant", "x": -0.1, "y": 0.5},
    {"kind": "plant", "x": 0.5},
    {"kind": "tree", "x": 0.5, "y": 0.5},
    {"kind": "plant", "geometry_type": "bbox", "bbox": [0.9, 0.2, 0.5, 0.1]},
    {"kind": "plant", "geometry_type": "bbox", "bbox": [0.1, 0.2, 0, 0.1]},
    {"kind": "plant", "geometry_type": "bbox", "bbox": [0.1, 0.2, 0.1]},
    {"kind": "plant", "geometry_type": "bbox", "bbox": [0.1, 0.1, 0.1, 0.1], "x": 0.1, "y": 0.1},
    {"kind": "plant", "x": 0.5, "y": 0.5, "bbox": [0.1, 0.1, 0.1, 0.1]},
    # Penanda model tidak boleh dibuat lewat endpoint manual.
    {"kind": "plant", "x": 0.5, "y": 0.5, "source": "model"},
    {"kind": "plant", "x": 0.5, "y": 0.5, "confidence": 0.9},
    {"kind": "plant", "x": 0.5, "y": 0.5, "review_status": "rejected"},
])
def test_invalid_annotations(client, photo, body):
    assert_error(client.post(ann_url(photo), json=body), 422, "VALIDATION_ERROR")


def test_non_finite_rejected(client, photo):
    r = client.post(ann_url(photo), content=b'{"kind":"plant","x":NaN,"y":0.5}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    r = client.post(ann_url(photo), content=b'{"kind":"plant","x":Infinity,"y":0.5}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_revision_required_and_conflict(client, photo):
    a = client.post(ann_url(photo), json={"kind": "plant", "x": 0.5, "y": 0.5}).json()
    url = f"/api/v1/annotations/{a['id']}"
    assert_error(client.patch(url, json={"note": "x"}), 428, "PRECONDITION_REQUIRED")
    r = client.patch(url, json={"note": "dicek", "kind": "check"}, headers={"If-Match": '"1"'})
    assert r.status_code == 200 and r.json()["revision"] == 2 and r.json()["kind"] == "check"
    assert r.headers["ETag"] == '"2"'
    # Klien lain masih memegang revisi 1 → konflik, tidak menimpa.
    err = assert_error(client.patch(url, json={"note": "menimpa"}, headers={"If-Match": '"1"'}),
                       409, "REVISION_CONFLICT")
    assert err["details"]["current"]["note"] == "dicek"
    assert client.get(ann_url(photo)).json()["items"][0]["note"] == "dicek"
    assert_error(client.delete(url, headers={"If-Match": '"1"'}), 409, "REVISION_CONFLICT")
    assert_error(client.delete(url), 428, "PRECONDITION_REQUIRED")
    assert client.delete(url, headers={"If-Match": 'W/"2"'}).status_code == 204
    assert_error(client.patch(url, json={"note": "x"}, headers={"If-Match": '"2"'}), 404, "NOT_FOUND")


def test_geometry_changes(client, photo):
    a = client.post(ann_url(photo), json={"kind": "plant", "x": 0.5, "y": 0.5}).json()
    url = f"/api/v1/annotations/{a['id']}"
    r = client.patch(url, json={"x": 0.2, "y": 0.3}, headers={"If-Match": '"1"'}).json()
    assert (r["x"], r["y"]) == (0.2, 0.3)
    assert_error(client.patch(url, json={"geometry_type": "bbox"}, headers={"If-Match": '"2"'}), 422, "VALIDATION_ERROR")
    assert_error(client.patch(url, json={"x": 0.2}, headers={"If-Match": '"2"'}), 422, "VALIDATION_ERROR")
    r = client.patch(url, json={"geometry_type": "bbox", "bbox": [0.0, 0.0, 0.5, 0.5]}, headers={"If-Match": '"2"'}).json()
    assert r["geometry_type"] == "bbox" and (r["x"], r["y"]) == (0.25, 0.25)
    assert_error(client.patch(url, json={"x": 0.1, "y": 0.1}, headers={"If-Match": '"3"'}), 422, "VALIDATION_ERROR")
    r = client.patch(url, json={"geometry_type": "point"}, headers={"If-Match": '"3"'}).json()
    assert r["geometry_type"] == "point" and r["bbox"] is None and (r["x"], r["y"]) == (0.25, 0.25)
    assert_error(client.patch(url, json={"source": "model"}, headers={"If-Match": '"4"'}), 422, "VALIDATION_ERROR")


def test_annotation_limit(make_client):
    c = make_client(max_annotations_per_photo=2)
    s = create_survey(c)
    p = upload_ok(c, s["id"])
    for _ in range(2):
        assert c.post(ann_url(p), json={"kind": "plant", "x": 0.5, "y": 0.5}).status_code == 201
    assert_error(c.post(ann_url(p), json={"kind": "plant", "x": 0.5, "y": 0.5}), 422, "ANNOTATION_LIMIT_EXCEEDED")


def test_annotations_scoped_to_photo(client):
    s = create_survey(client)
    p1, p2 = upload_ok(client, s["id"]), upload_ok(client, s["id"])
    client.post(ann_url(p1), json={"kind": "plant", "x": 0.5, "y": 0.5})
    assert client.get(ann_url(p2)).json()["total"] == 0
    assert client.get(f"/api/v1/photos/{p1['id']}").json()["counts"]["plant_accepted"] == 1
    assert client.get(f"/api/v1/photos/{p2['id']}").json()["counts"]["plant_accepted"] == 0
