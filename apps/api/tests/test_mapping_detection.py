"""AI → peta (revisi 5): jendela ber-overlap, offset & resize, dedup antartile, piksel → WGS84, review, laporan.

Raster = DATA UJI SINTETIS dengan kotak hijau di posisi diketahui; detector = GreenBoxDetector yang hanya melihat
piksel jendela (tidak tahu offset), sehingga test membuktikan pemetaan balik, bukan sekadar menyalin angka.
"""
import json

import pytest
from pyproj import Transformer

from app.geo import detection as gd
from app.inference.simulation import SimulationDetector
from conftest import assert_error, create_survey
from geo_helpers import GreenBoxDetector, make_geotiff
from test_mapping_fields import create_field, metres_square
from test_mapping_rasters import upload_ok

V1 = "/api/v1"
# 3000 × 2000 px; jendela 1024 overlap 128 → langkah 896: batas jendela di x=896,1024,1792,1920 dan y=896,976.
SQUARES = [(100, 100, 40), (1000, 300, 40), (900, 900, 40), (1800, 950, 40), (2950, 1950, 40), (1500, 1500, 30),
           (10, 1800, 40)]


@pytest.fixture
def detector():
    return GreenBoxDetector()


@pytest.fixture
def raster(make_client, detector, tmp_path):
    c = make_client(detector=detector)
    s = create_survey(c)
    r = upload_ok(c, s["id"], make_geotiff(tmp_path / "kotak.tif", 3000, 2000, squares=SQUARES))
    return c, s, r


# ------------------------------------------------------------------ unit
def test_windows_cover_raster_without_padding():
    wins = list(gd.windows(3000, 2000, 1024, 128))
    assert {w.col_off for w in wins} == {0, 896, 1792, 1976} and {w.row_off for w in wins} == {0, 896, 976}
    assert all(w.col_off + w.width <= 3000 and w.row_off + w.height <= 2000 for w in wins)
    assert max(w.col_off + w.width for w in wins) == 3000 and max(w.row_off + w.height for w in wins) == 2000
    assert [(w.width, w.height) for w in gd.windows(300, 200, 1024, 128)] == [(300, 200)]
    with pytest.raises(ValueError):
        list(gd.windows(100, 100, 256, 256))


def test_offset_and_resize_mapping():
    win = gd.Window(896, 976, 1024, 1024)
    # bbox ternormalisasi tidak bergantung ukuran gambar yang diterima model (resize/letterbox sudah dibalik adapter)
    assert gd.to_raster_pixels(win, [0.5, 0.25, 0.1, 0.05]) == (896 + 512, 976 + 256, 102.4, 51.2)


def test_dedup_iou_and_ios():
    a = gd.PixelBox("plant", 100, 100, 40, 40, 0.9, None)
    shifted = gd.PixelBox("plant", 102, 101, 40, 40, 0.8, None)          # IoU tinggi
    fragment = gd.PixelBox("plant", 100, 100, 15, 40, 0.95, None)        # potongan tepi: IoU kecil, IoS = 1
    other_kind = gd.PixelBox("gap", 100, 100, 40, 40, 0.5, None)
    far = gd.PixelBox("plant", 400, 400, 40, 40, 0.7, None)
    kept = gd.deduplicate([a, shifted, fragment, other_kind, far])
    assert fragment in kept and a not in kept and shifted not in kept     # confidence tertinggi menang
    assert other_kind in kept and far in kept and len(kept) == 3
    assert gd.deduplicate([a, shifted], iou_threshold=0.99, ios_threshold=0.99) == [a, shifted]


def test_inner_edge_rule():
    win = gd.Window(896, 0, 1024, 1024)
    assert gd.touches_inner_edge(gd.PixelBox("plant", 896, 10, 20, 20, 1, None), win, 3000, 2000)
    assert not gd.touches_inner_edge(gd.PixelBox("plant", 950, 0, 20, 20, 1, None), win, 3000, 2000)   # tepi raster


# ------------------------------------------------------------------ API end-to-end
def test_raster_analysis_maps_every_object_once_to_correct_pixels_and_lonlat(raster, detector):
    c, s, r = raster
    res = c.post(f"{V1}/rasters/{r['id']}/analyze", json={"tile_size": 1024, "overlap_px": 128})
    assert res.status_code == 201, res.text
    body = res.json()
    p = body["run"]["parameters"]
    assert body["candidate_count"] == len(SQUARES) and body["run"]["status"] == "succeeded"
    assert p["window_count"] == 12 and p["raw_detections"] > len(SQUARES)      # objek di overlap terlihat >1 kali
    assert p["dedup"]["method"] == "greedy_nms_per_kind" and "pending" in body["notice"]
    assert body["run"]["input_sha256"] == r["sha256"] and body["run"]["model_id"] == "green-box-test-double"
    dets = c.get(body["detections_url"]).json()
    assert dets["total"] == len(SQUARES) and dets["counts"]["pending_review"] == len(SQUARES)
    got = sorted((round(d["pixel_bbox"][0]), round(d["pixel_bbox"][1]), round(d["pixel_bbox"][2])) for d in dets["items"])
    assert got == sorted(SQUARES)                                              # piksel raster ASLI, tepat
    utm = Transformer.from_crs("EPSG:32748", "EPSG:4326", always_xy=True)
    for d in dets["items"]:
        assert d["review_status"] == "pending" and d["source"] == "model" and d["inside_field"] is None
        l, t, w, h = d["pixel_bbox"]
        ex, ey = 700000 + (l + w / 2) * 0.05, 9270000 - (t + h / 2) * 0.05     # transform dihitung manual
        assert d["center_native"] == pytest.approx([ex, ey])
        assert d["center"] == pytest.approx(list(utm.transform(ex, ey)), abs=1e-9)
        ring = d["geometry"]["coordinates"][0]
        assert len(ring) == 5 and ring[0] == ring[-1]
        assert ring[0] == pytest.approx(list(utm.transform(700000 + l * 0.05, 9270000 - t * 0.05)), abs=1e-9)


def test_resize_scale_keeps_positions(raster, detector):
    c, s, r = raster
    res = c.post(f"{V1}/rasters/{r['id']}/analyze", json={"tile_size": 1024, "overlap_px": 128, "scale": 0.5})
    assert res.status_code == 201, res.text
    assert {sz for sz in detector.sizes} <= {(512, 512), (512, 488), (500, 512), (500, 488)}   # model menerima 50%
    dets = c.get(f"{V1}/rasters/{r['id']}/detections").json()["items"]
    assert len(dets) == len(SQUARES)
    for d in dets:
        l, t, w, _ = d["pixel_bbox"]
        sq = min(SQUARES, key=lambda q: abs(q[0] - l) + abs(q[1] - t))
        assert abs(l - sq[0]) <= 2 and abs(t - sq[1]) <= 2 and abs(w - sq[2]) <= 3


def test_without_overlap_objects_on_seams_are_split(raster):
    c, s, r = raster
    body = c.post(f"{V1}/rasters/{r['id']}/analyze", json={"tile_size": 1024, "overlap_px": 0}).json()
    # tanpa overlap, kotak yang melintasi garis jendela terpotong dua (dedup tidak bisa menyatukan potongan berdampingan)
    assert body["candidate_count"] > len(SQUARES) and body["run"]["parameters"]["dedup"]["edge_rule"] == "none"


def test_repeat_analysis_controls_and_review_flow(raster):
    c, s, r = raster
    first = c.post(f"{V1}/rasters/{r['id']}/analyze").json()
    assert_error(c.post(f"{V1}/rasters/{r['id']}/analyze"), 409, "ANALYSIS_EXISTS")
    items = c.get(f"{V1}/rasters/{r['id']}/detections").json()["items"]
    d = items[0]
    assert_error(c.patch(f"{V1}/map-detections/{d['id']}", json={"review_status": "accepted"}), 428,
                 "PRECONDITION_REQUIRED")
    ok = c.patch(f"{V1}/map-detections/{d['id']}", json={"review_status": "accepted", "note": "dicek"},
                 headers={"If-Match": '"1"'})
    assert ok.status_code == 200 and ok.json()["revision"] == 2 and ok.headers["ETag"] == '"2"'
    assert_error(c.patch(f"{V1}/map-detections/{d['id']}", json={"review_status": "rejected"},
                         headers={"If-Match": '"1"'}), 409, "REVISION_CONFLICT")
    c.patch(f"{V1}/map-detections/{items[1]['id']}", json={"review_status": "rejected"}, headers={"If-Match": '"1"'})
    counts = c.get(f"{V1}/rasters/{r['id']}").json()["detection_counts"]
    assert counts == {"plant_accepted": 1, "plant_accepted_inside_field": None, "pending_review": len(SQUARES) - 2,
                      "rejected": 1, "total": len(SQUARES)}
    # replace_pending: kandidat pending lama diganti, yang sudah direview dipertahankan
    rep = c.post(f"{V1}/rasters/{r['id']}/analyze", json={"on_existing": "replace_pending"}).json()
    assert rep["replaced_detection_count"] == len(SQUARES) - 2
    after = c.get(f"{V1}/rasters/{r['id']}/detections").json()
    assert after["counts"]["plant_accepted"] == 1 and after["counts"]["rejected"] == 1
    assert after["total"] == 2 + len(SQUARES)
    runs = c.get(f"{V1}/rasters/{r['id']}/analysis-runs").json()
    assert runs["total"] == 2 and runs["items"][1]["id"] == first["run"]["id"]
    gj = c.get(f"{V1}/rasters/{r['id']}/detections.geojson?review_status=accepted")
    assert gj.headers["content-type"].startswith("application/geo+json")
    fc = gj.json()
    assert len(fc["features"]) == 1 and fc["properties"]["counts_are_unique_plants"] is False
    assert fc["features"][0]["geometry"]["type"] == "Polygon"


def test_masked_area_detections_dropped(make_client, detector, tmp_path):
    c = make_client(detector=detector)
    s = create_survey(c)
    path = make_geotiff(tmp_path / "m.tif", 800, 400, bands=4, squares=[(100, 100, 40), (600, 100, 40)],
                        alpha_hole=(0, 0, 400, 400))
    r = upload_ok(c, s["id"], path)
    body = c.post(f"{V1}/rasters/{r['id']}/analyze", json={"tile_size": 512, "overlap_px": 64}).json()
    assert body["candidate_count"] == 1 and body["run"]["parameters"]["dropped_masked"] >= 1
    assert c.get(f"{V1}/rasters/{r['id']}/detections").json()["items"][0]["pixel_bbox"][0] == pytest.approx(600)


def test_inside_field_and_survey_report(make_client, detector, tmp_path):
    c = make_client(detector=detector)
    utm = Transformer.from_crs("EPSG:32748", "EPSG:4326", always_xy=True)
    # lahan = separuh kiri raster (x 700000..700075 m = kolom 0..1500)
    ring = [list(utm.transform(x, y)) for x, y in [(699999, 9270001), (700075, 9270001), (700075, 9269899),
                                                   (699999, 9269899), (699999, 9270001)]]
    f = c.post(f"{V1}/fields", json={"name": "Petak kiri", "boundary_source": "digitized_from_raster",
                                     "geometry": {"type": "Polygon", "coordinates": [ring]}}).json()
    s = create_survey(c, field_id=f["id"])
    r = upload_ok(c, s["id"], make_geotiff(tmp_path / "k.tif", 3000, 2000, squares=SQUARES))
    c.post(f"{V1}/rasters/{r['id']}/analyze")
    items = c.get(f"{V1}/rasters/{r['id']}/detections").json()["items"]
    for d in items:
        c.patch(f"{V1}/map-detections/{d['id']}", json={"review_status": "accepted"}, headers={"If-Match": '"1"'})
    inside = [d for d in c.get(f"{V1}/rasters/{r['id']}/detections").json()["items"] if d["inside_field"]]
    expected_inside = [q for q in SQUARES if q[0] + q[2] / 2 < 1500]
    assert len(inside) == len(expected_inside)
    rep = c.get(f"{V1}/surveys/{s['id']}/report").json()
    mp = rep["mapping"]
    assert mp["field"]["id"] == f["id"] and mp["field"]["measures"]["method"] == "geodesic_wgs84"
    assert mp["counts_are_unique_plants"] is False
    assert mp["rasters"][0]["counts"]["plant_accepted"] == len(SQUARES)
    assert mp["rasters"][0]["counts"]["plant_accepted_inside_field"] == len(expected_inside)
    text = " ".join(rep["disclaimers"])
    assert "dihitung geodesik" in text and "digitasi di atas raster impor" in text
    assert "DIIMPOR pengguna" in text and "Jangan menjumlahkan raster" in text
    assert rep["totals"]["plant_accepted_sum_across_photos"] == 0      # deteksi peta tidak bercampur hitungan foto


def test_report_without_mapping_is_unchanged(client):
    s = create_survey(client)
    rep = client.get(f"{V1}/surveys/{s['id']}/report").json()
    assert rep["mapping"] is None and not any("geodesik" in d or "raster" in d.lower() for d in rep["disclaimers"])


def test_raster_analysis_without_model_and_with_simulation(make_client, tmp_path):
    c = make_client()
    s = create_survey(c)
    r = upload_ok(c, s["id"], make_geotiff(tmp_path / "n.tif", 600, 400))
    err = assert_error(c.post(f"{V1}/rasters/{r['id']}/analyze"), 503, "MODEL_NOT_CONFIGURED")
    assert err["details"]["diagnostic_code"] == "MODEL_PATH_NOT_SET"
    assert c.get(f"{V1}/rasters/{r['id']}/analysis-runs").json()["total"] == 0
    sim = make_client(detector=SimulationDetector())
    s2 = create_survey(sim)
    r2 = upload_ok(sim, s2["id"], make_geotiff(tmp_path / "sim.tif", 600, 400))
    body = sim.post(f"{V1}/rasters/{r2['id']}/analyze", json={"tile_size": 512, "overlap_px": 64}).json()
    assert body["run"]["target"] == "simulation" and body["notice"].startswith("SIMULASI — BUKAN AI")
    d = sim.get(f"{V1}/rasters/{r2['id']}/detections").json()["items"]
    assert d and all(x["confidence"] is None and x["model_label"] == "SIMULASI — BUKAN AI" for x in d)
    assert any(x.startswith("SIMULASI") for x in sim.get(f"{V1}/surveys/{s2['id']}/report").json()["disclaimers"])


def test_detections_persist_after_restart(make_client, detector, tmp_path):
    c1 = make_client(detector=detector)
    s = create_survey(c1)
    r = upload_ok(c1, s["id"], make_geotiff(tmp_path / "p.tif", 600, 400, squares=[(50, 50, 30)]))
    c1.post(f"{V1}/rasters/{r['id']}/analyze")
    before = c1.get(f"{V1}/rasters/{r['id']}/detections.geojson").json()
    c2 = make_client(detector=GreenBoxDetector())
    assert c2.get(f"{V1}/rasters/{r['id']}/detections.geojson").json() == before


def test_real_deepforest_on_neon_geotiff_if_available(make_client, tmp_path):
    """Inferensi NYATA DeepForest pada GeoTIFF NEON (bukan K919). Di-skip bila paket/bobot tidak ada."""
    from pathlib import Path

    from app.config import API_ROOT
    from app.inference.deepforest_adapter import DeepForestDetector
    sample = API_ROOT.parents[1] / "samples" / "georeferenced" / "OSBS_029.tif"
    det = DeepForestDetector(API_ROOT / "var" / "models" / "deepforest-tree")
    if not sample.is_file() or det.info().state == "error":
        pytest.skip(f"Butuh {sample} dan DeepForest + bobot ({det.info().message})")
    c = make_client(detector=det)
    s = create_survey(c)
    r = upload_ok(c, s["id"], Path(sample))
    assert r["crs"]["epsg"] == 32617 and r["approx_gsd_m"] == pytest.approx(0.1, rel=0.01)
    body = c.post(f"{V1}/rasters/{r['id']}/analyze", json={"tile_size": 400, "overlap_px": 0}).json()
    assert body["run"]["target"] == "tree_crown" and body["candidate_count"] > 10
    from shapely.geometry import Point, shape
    fp = shape(r["footprint"])
    items = c.get(f"{V1}/rasters/{r['id']}/detections").json()["items"]
    assert all(fp.buffer(1e-6).covers(Point(*d["center"])) for d in items)
    assert all(d["review_status"] == "pending" for d in items)
