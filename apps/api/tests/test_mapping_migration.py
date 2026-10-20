"""Migrasi 0002 pada database yang SUDAH berisi data revisi ≤ 4: tidak ada foto/penanda yang hilang (risiko batch
SQLite + ON DELETE CASCADE), FK surveys.field_id benar-benar ON DELETE SET NULL, downgrade/upgrade aman."""
import sqlite3

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event

from app.config import API_ROOT


def cfg(url: str) -> Config:
    c = Config(str(API_ROOT / "alembic.ini"))
    c.set_main_option("script_location", str(API_ROOT / "alembic"))
    c.set_main_option("sqlalchemy.url", url)
    return c


def run(url: str, fn, *args):
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _fk(dbapi, _):        # sama dengan aplikasi: foreign_keys=ON
        dbapi.execute("PRAGMA foreign_keys=ON")

    c = cfg(url)
    with engine.begin() as conn:
        c.attributes["connection"] = conn
        fn(c, *args)
    engine.dispose()


def test_upgrade_from_0001_keeps_existing_photos_and_annotations(tmp_path):
    db = tmp_path / "lama.db"
    url = f"sqlite:///{db.as_posix()}"
    run(url, command.upgrade, "0001")
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("INSERT INTO surveys VALUES ('s1','Lama','Jagung','','2026-10-01','',0,1,'2026-10-01 00:00:00',"
                "'2026-10-01 00:00:00')")
    con.execute("INSERT INTO photos (id, survey_id, original_name, width, height, mime_type, size_bytes, sha256, "
                "exif_orientation, has_exif_gps, georef_status, storage_key, thumbnail_key, revision, created_at) "
                "VALUES ('p1','s1','a.jpg',10,10,'image/jpeg',1,'x',1,0,'none','k','t',1,'2026-10-01 00:00:00')")
    con.execute("INSERT INTO annotations (id, photo_id, kind, geometry_type, x, y, source, review_status, note, "
                "revision, created_at, updated_at) VALUES ('a1','p1','plant','point',0.5,0.5,'manual','accepted','',1,"
                "'2026-10-01 00:00:00','2026-10-01 00:00:00')")
    con.commit()
    con.close()

    run(url, command.upgrade, "head")
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=ON")
    assert [con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("surveys", "photos", "annotations")] == \
        [1, 1, 1]
    fk = con.execute("PRAGMA foreign_key_list(surveys)").fetchall()
    assert [(r[2], r[3], r[4], r[6]) for r in fk] == [("fields", "field_id", "id", "SET NULL")]
    con.execute("INSERT INTO fields (id, name, notes, boundary_source, source_note, geometry_type, geometry_json, "
                "area_m2, perimeter_m, exterior_perimeter_m, min_lon, min_lat, max_lon, max_lat, label_lon, label_lat, "
                "vertex_count, hole_count, polygon_count, revision, created_at, updated_at) VALUES ('f1','L','',"
                "'other','','Polygon','{}',1,1,1,0,0,1,1,0,0,4,0,1,1,'2026-10-20 00:00:00','2026-10-20 00:00:00')")
    con.execute("UPDATE surveys SET field_id='f1'")
    con.execute("DELETE FROM fields WHERE id='f1'")
    assert con.execute("SELECT field_id FROM surveys").fetchone()[0] is None      # SET NULL, survei tetap
    assert con.execute("SELECT count(*) FROM photos").fetchone()[0] == 1
    con.commit()
    con.close()

    run(url, command.downgrade, "0001")
    run(url, command.upgrade, "head")                     # kolom sisa downgrade SQLite dikenali, tidak ditambah ulang
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM annotations").fetchone()[0] == 1
    assert {r[1] for r in con.execute("PRAGMA table_info(surveys)")} >= {"field_id"}
    assert con.execute("SELECT name FROM sqlite_master WHERE name='map_detections'").fetchone()
    con.close()
