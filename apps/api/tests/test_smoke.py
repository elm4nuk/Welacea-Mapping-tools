from conftest import create_survey, upload_ok


def test_smoke(client):
    assert client.get("/api/v1/health").status_code == 200
    s = create_survey(client)
    p = upload_ok(client, s["id"])
    r = client.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "x": 0.5, "y": 0.5})
    assert r.status_code == 201, r.text
    assert client.get(f"/api/v1/surveys/{s['id']}/report").status_code == 200
    assert client.post("/api/v1/demo/surveys").status_code == 201
