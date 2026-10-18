from conftest import ORIGIN, SURVEY, assert_error, create_survey, upload_ok


def test_health_is_honest_without_model(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["model"]["state"] == "not_configured"
    assert body["model"]["available"] is False
    assert body["capabilities"] == {"flight_control": False, "live_video": False, "georeferencing": False,
                                    "orthomosaic": False}
    assert body["limits"]["max_upload_bytes"] == 20 * 1024 * 1024
    assert r.headers["X-Request-ID"]


def test_survey_crud_and_pagination(client):
    a = create_survey(client, name="A")
    b = create_survey(client, name="B")
    assert a["is_demo"] is False and a["revision"] == 1 and a["photo_count"] == 0
    assert a["created_at"].endswith("Z") or a["created_at"].endswith("+00:00")

    page = client.get("/api/v1/surveys?limit=1&offset=0").json()
    assert page["total"] == 2 and page["limit"] == 1 and len(page["items"]) == 1
    assert page["items"][0]["id"] == b["id"]  # terbaru dulu

    r = client.patch(f"/api/v1/surveys/{a['id']}", json={"notes": "baru"}, headers={"If-Match": '"1"'})
    assert r.status_code == 200 and r.json()["notes"] == "baru" and r.json()["revision"] == 2
    assert r.headers["ETag"] == '"2"'

    err = assert_error(client.patch(f"/api/v1/surveys/{a['id']}", json={"notes": "x"}, headers={"If-Match": '"1"'}),
                       409, "REVISION_CONFLICT")
    assert err["details"]["current"]["revision"] == 2

    assert client.delete(f"/api/v1/surveys/{a['id']}").status_code == 204
    assert_error(client.get(f"/api/v1/surveys/{a['id']}"), 404, "NOT_FOUND")


def test_survey_validation(client):
    assert_error(client.post("/api/v1/surveys", json={**SURVEY, "name": "  "}), 422, "VALIDATION_ERROR")
    assert_error(client.post("/api/v1/surveys", json={**SURVEY, "survey_date": "18-10-2026"}), 422, "VALIDATION_ERROR")
    # Klien tidak boleh menandai survei sebagai demo / menambah field tak dikenal.
    assert_error(client.post("/api/v1/surveys", json={**SURVEY, "is_demo": True}), 422, "VALIDATION_ERROR")
    s = create_survey(client)
    assert_error(client.patch(f"/api/v1/surveys/{s['id']}", json={}), 422, "VALIDATION_ERROR")
    assert_error(client.patch(f"/api/v1/surveys/{s['id']}", json={"name": None}), 422, "VALIDATION_ERROR")
    assert_error(client.patch(f"/api/v1/surveys/{s['id']}", json={"name": "x"}, headers={"If-Match": "abc"}),
                 400, "BAD_REQUEST")


def test_unknown_route_and_bad_query_use_envelope(client):
    assert_error(client.get("/api/v1/nope"), 404, "NOT_FOUND")
    assert_error(client.get("/api/v1/surveys?limit=0"), 422, "VALIDATION_ERROR")
    assert_error(client.get("/api/v1/surveys?limit=201"), 422, "VALIDATION_ERROR")


def test_request_id_is_echoed(client):
    r = client.get("/api/v1/surveys/missing", headers={"X-Request-ID": "abc12345-req"})
    assert r.headers["X-Request-ID"] == "abc12345-req"
    assert r.json()["error"]["request_id"] == "abc12345-req"


def test_delete_survey_removes_files(client, data_dir):
    s = create_survey(client)
    upload_ok(client, s["id"])
    files = [p for p in (data_dir / "uploads").rglob("*") if p.is_file()]
    assert len(files) == 2  # asli + thumbnail (orientasi normal → tanpa turunan display)
    assert client.delete(f"/api/v1/surveys/{s['id']}").status_code == 204
    assert not [p for p in (data_dir / "uploads").rglob("*") if p.is_file()]


def test_demo_survey_is_labelled(client):
    r = client.post("/api/v1/demo/surveys")
    assert r.status_code == 201
    demo = r.json()
    assert demo["is_demo"] is True and demo["photo_count"] == 1
    photo = client.get(f"/api/v1/surveys/{demo['id']}/photos").json()["items"][0]
    assert photo["counts"]["plant_accepted"] > 0
    report = client.get(f"/api/v1/surveys/{demo['id']}/report").json()
    assert any("DATA CONTOH" in d for d in report["disclaimers"])
    assert_error(client.post(f"/api/v1/photos/{photo['id']}/analyze"), 409, "DEMO_SURVEY_READONLY")


def test_cors_only_allows_configured_origin(client):
    ok = client.options("/api/v1/surveys", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "PATCH",
                                                    "Access-Control-Request-Headers": "if-match"})
    assert ok.headers.get("access-control-allow-origin") == ORIGIN
    bad = client.options("/api/v1/surveys", headers={"Origin": "https://evil.example",
                                                     "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
    r = client.get("/api/v1/health", headers={"Origin": ORIGIN})
    assert "ETag" in r.headers.get("access-control-expose-headers", "") or r.headers.get("access-control-allow-origin") == ORIGIN
