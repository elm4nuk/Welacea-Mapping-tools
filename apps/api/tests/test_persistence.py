from conftest import create_survey, png_bytes, upload_ok


def test_everything_persists_after_restart(make_client):
    c1 = make_client()
    s = create_survey(c1)
    data = png_bytes(50, 40)
    p = upload_ok(c1, s["id"], data)
    a = c1.post(f"/api/v1/photos/{p['id']}/annotations", json={"kind": "plant", "x": 0.5, "y": 0.5, "note": "n"}).json()
    c1.patch(f"/api/v1/annotations/{a['id']}", json={"review_status": "rejected"}, headers={"If-Match": '"1"'})
    c1.__exit__(None, None, None)  # server berhenti

    c2 = make_client()  # proses baru, data_dir sama
    assert c2.get(f"/api/v1/surveys/{s['id']}").json()["name"] == s["name"]
    photo = c2.get(f"/api/v1/photos/{p['id']}").json()
    assert photo["sha256"] == p["sha256"] and photo["counts"]["rejected"] == 1
    assert c2.get(photo["content_url"]).content == data
    ann = c2.get(f"/api/v1/photos/{p['id']}/annotations").json()["items"][0]
    assert ann["review_status"] == "rejected" and ann["revision"] == 2 and ann["note"] == "n"
    assert c2.get(f"/api/v1/surveys/{s['id']}/report").json()["photos"][0]["counts"]["plant_accepted"] == 0


def test_migrations_match_models(make_client):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db import Base

    c = make_client()
    with c.app.state.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == [], diff
