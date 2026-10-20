"""Impor GeoTIFF (revisi 5): validasi georeferensi, CRS projected/geographic, tile, preview, persistensi.
Semua raster di sini DATA UJI SINTETIS (tests/geo_helpers.py), bukan citra nyata."""
import io

import numpy as np
import pytest
from PIL import Image
from pyproj import Transformer
from rasterio.control import GroundControlPoint
from rasterio.transform import Affine, from_origin

from app.geo.raster import PixelGeo, tile_bounds_3857
from conftest import assert_error, create_survey, png_bytes
from geo_helpers import make_geotiff

V1 = "/api/v1"


@pytest.fixture
def survey(client):
    return create_survey(client)


def upload(client, survey_id, path, name=None, **form):
    with open(path, "rb") as fh:
        return client.post(f"{V1}/surveys/{survey_id}/rasters", files={"file": (name or path.name, fh, "image/tiff")},
                           data=form)


def upload_ok(client, survey_id, path, **form):
    r = upload(client, survey_id, path, **form)
    assert r.status_code == 201, r.text
    return r.json()["raster"]


def stored_files(data_dir):
    return sorted(p.name for p in (data_dir / "uploads").rglob("*.tif"))


def lonlat_to_tile(lon, lat, z):
    t = Transformer.from_crs(4326, 3857, always_xy=True)
    x, y = t.transform(lon, lat)
    size = 2 * 20037508.342789244 / 2 ** z
    return int((x + 20037508.342789244) // size), int((20037508.342789244 - y) // size)


# ------------------------------------------------------------------ impor sah
def test_projected_utm_raster_import_metadata(client, survey, tmp_path, data_dir):
    path = make_geotiff(tmp_path / "uji utm.tif", 800, 600)        # 40 m × 30 m, 5 cm/px, EPSG:32748
    r = upload_ok(client, survey["id"], path, source_description="DATA UJI SINTETIS")
    assert r["product_type"] == "imported_georeferenced_raster" and r["is_verified_orthomosaic"] is False
    assert r["crs"]["epsg"] == 32748 and r["crs"]["is_geographic"] is False
    assert (r["width"], r["height"], r["band_count"]) == (800, 600, 3)
    assert r["transform"] == [0.05, 0.0, 700000.0, 0.0, -0.05, 9270000.0]
    assert r["bounds_native"] == pytest.approx([700000, 9269970, 700040, 9270000])
    assert r["approx_gsd_m"] == pytest.approx(0.05, rel=0.01)
    assert r["footprint_area_m2"] == pytest.approx(1200, rel=0.01)
    w, s_, e, n = r["bounds_wgs84"]
    assert 106 < w < e < 108 and -7 < s_ < n < -6            # urutan [lon, lat], bukan [lat, lon]
    assert r["footprint"]["type"] == "Polygon" and r["footprint"]["coordinates"][0][0] == \
        r["footprint"]["coordinates"][0][-1]
    assert r["processing"]["pipeline"] == "wallacea-raster-import/1" and r["processing"]["display"]["overviews"]
    assert r["source_description"] == "DATA UJI SINTETIS" and r["detection_counts"]["total"] == 0
    assert len(stored_files(data_dir)) == 2                    # asli + turunan tampilan
    orig = client.get(r["content_url"])
    assert orig.status_code == 200 and orig.content == path.read_bytes()      # byte asli utuh
    import hashlib
    assert hashlib.sha256(orig.content).hexdigest() == r["sha256"]


def test_geographic_wgs84_raster(client, survey, tmp_path):
    path = make_geotiff(tmp_path / "geo.tif", 400, 400, crs="EPSG:4326",
                        transform=from_origin(106.8, -6.6, 1e-6, 1e-6))   # ±11 cm/px
    r = upload_ok(client, survey["id"], path)
    assert r["crs"]["is_geographic"] is True and r["crs"]["epsg"] == 4326
    assert r["bounds_wgs84"] == pytest.approx([106.8, -6.6004, 106.8004, -6.6], abs=1e-9)
    assert r["approx_gsd_m"] == pytest.approx(0.11, rel=0.02)


def test_pixel_to_world_known_points_and_axis_order():
    t = [0.05, 0.0, 700000.0, 0.0, -0.05, 9270000.0]
    from pyproj import CRS
    g = PixelGeo(t, CRS.from_epsg(32748).to_wkt())
    assert g.native(0, 0) == (700000.0, 9270000.0)              # sudut kiri-atas piksel pertama
    assert g.native(10.5, 20.5) == pytest.approx((700000.525, 9269998.975))
    lon, lat = g.lonlat(0, 0)
    ref = Transformer.from_crs("EPSG:32748", "EPSG:4326")        # TANPA always_xy → urutan resmi (lat, lon)
    rlat, rlon = ref.transform(700000.0, 9270000.0)
    assert (lon, lat) == pytest.approx((rlon, rlat), abs=1e-12)
    assert 106 < lon < 108 and -7 < lat < -6


def test_rotated_transform_is_accepted_and_footprint_follows_rotation(client, survey, tmp_path):
    import math
    c, s_ = math.cos(math.radians(30)), math.sin(math.radians(30))
    rot = Affine(0.05 * c, 0.05 * s_, 700000, 0.05 * s_, -0.05 * c, 9270000)    # rotasi 30° + skala 5 cm
    r = upload_ok(client, survey["id"], make_geotiff(tmp_path / "rot.tif", 400, 200, transform=rot))
    assert r["metadata"]["is_rotated"] is True
    g = PixelGeo(r["transform"], r["crs"]["wkt"])
    ring = r["footprint"]["coordinates"][0]
    assert ring[0] == pytest.approx(list(g.lonlat(0, 0)))
    assert r["footprint_area_m2"] == pytest.approx(20 * 10, rel=0.01)


# ------------------------------------------------------------------ penolakan
@pytest.mark.parametrize("kwargs, status, code, reason", [
    (dict(crs=None), 422, "RASTER_NOT_GEOREFERENCED", "no_crs"),
    (dict(transform=Affine.identity(), crs=None), 422, "RASTER_NOT_GEOREFERENCED", None),
    (dict(bands=1), 415, "UNSUPPORTED_RASTER", None),
    (dict(dtype="uint16"), 415, "UNSUPPORTED_RASTER", None),
    (dict(transform=from_origin(500000, 9270000, 1000, 1000)), 422, "RASTER_NOT_GEOREFERENCED", "footprint_too_large"),
])
def test_invalid_rasters_are_rejected_and_not_stored(client, survey, tmp_path, data_dir, kwargs, status, code, reason):
    path = make_geotiff(tmp_path / "x.tif", 2000 if "footprint" in str(reason) else 64, 64, **kwargs)
    err = assert_error(upload(client, survey["id"], path), status, code)
    if reason:
        assert err["details"]["reason"] == reason
    assert stored_files(data_dir) == [] and client.get(f"{V1}/surveys/{survey['id']}/rasters").json()["total"] == 0
    assert not any((data_dir / "uploads" / "_tmp").glob("*")) if (data_dir / "uploads" / "_tmp").exists() else True


def test_gcp_only_raster_is_not_placed_on_map(client, survey, tmp_path):
    gcps = [GroundControlPoint(0, 0, 700000, 9270000), GroundControlPoint(0, 63, 700000, 9269997),
            GroundControlPoint(63, 0, 700003, 9270000)]
    path = make_geotiff(tmp_path / "gcp.tif", 64, 64, transform=None, gcps=gcps)
    err = assert_error(upload(client, survey["id"], path), 422, "RASTER_NOT_GEOREFERENCED")
    assert err["details"]["has_gcps"] is True


def test_non_geotiff_and_non_alpha_fourth_band(client, survey, tmp_path):
    p = tmp_path / "foto.png"
    p.write_bytes(png_bytes())
    assert_error(upload(client, survey["id"], p), 415, "UNSUPPORTED_RASTER")
    q = tmp_path / "rusak.tif"
    q.write_bytes(b"II*\x00bukan tiff")
    assert_error(upload(client, survey["id"], q), 400, "INVALID_RASTER")
    nir = make_geotiff(tmp_path / "nir.tif", 64, 64, bands=4)
    import rasterio
    from rasterio.enums import ColorInterp
    with rasterio.open(nir, "r+") as ds:
        ds.colorinterp = [ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.undefined]
    assert_error(upload(client, survey["id"], nir), 415, "UNSUPPORTED_RASTER")


def test_size_limits(make_client, tmp_path):
    c = make_client(max_raster_pixels=10_000)
    s = create_survey(c)
    err = assert_error(upload(c, s["id"], make_geotiff(tmp_path / "big.tif", 200, 100)), 413, "RASTER_TOO_LARGE")
    assert err["details"]["max_pixels"] == 10_000
    c2 = make_client(max_raster_bytes=1000)
    s2 = create_survey(c2)
    assert upload(c2, s2["id"], make_geotiff(tmp_path / "b.tif", 200, 100)).status_code == 413


def test_demo_survey_rejects_raster(client, tmp_path):
    demo = client.post(f"{V1}/demo/surveys").json()
    assert_error(upload(client, demo["id"], make_geotiff(tmp_path / "x.tif", 64, 64)), 409, "DEMO_SURVEY_READONLY")


# ------------------------------------------------------------------ tile & preview
def test_tilejson_tiles_and_preview(client, survey, tmp_path):
    path = make_geotiff(tmp_path / "t.tif", 1200, 900, squares=[(100, 100, 80)])
    r = upload_ok(client, survey["id"], path)
    tj = client.get(r["tilejson_url"]).json()
    assert tj["tilejson"] == "3.0.0" and tj["bounds"] == r["bounds_wgs84"] and tj["maxzoom"] == r["maxzoom"]
    assert 20 <= r["maxzoom"] <= 23 and r["minzoom"] < r["maxzoom"]
    assert "tidak diverifikasi" in tj["attribution"]
    lon, lat = (r["bounds_wgs84"][0] + r["bounds_wgs84"][2]) / 2, (r["bounds_wgs84"][1] + r["bounds_wgs84"][3]) / 2
    for z in (r["minzoom"], r["maxzoom"]):
        x, y = lonlat_to_tile(lon, lat, z)
        resp = client.get(tj["tiles"][0].format(z=z, x=x, y=y))
        assert resp.status_code == 200 and resp.headers["content-type"] == "image/png"
        img = np.asarray(Image.open(io.BytesIO(resp.content)))
        assert img.shape == (256, 256, 4) and img[..., 3].max() == 255       # ada piksel raster
    far = client.get(r["tile_url_template"].format(z=10, x=0, y=0))
    assert np.asarray(Image.open(io.BytesIO(far.content)))[..., 3].max() == 0      # transparan
    assert_error(client.get(r["tile_url_template"].format(z=2, x=9, y=0)), 422, "VALIDATION_ERROR")
    pv = Image.open(io.BytesIO(client.get(r["preview_url"] + "?max_size=300").content))
    assert pv.size == (300, 225) and pv.mode == "RGBA"


def test_tile_bounds_formula():
    assert tile_bounds_3857(0, 0, 0) == pytest.approx((-20037508.342789244, -20037508.342789244,
                                                       20037508.342789244, 20037508.342789244))
    l, b, r, t = tile_bounds_3857(1, 1, 0)
    assert (l, b, r, t) == pytest.approx((0, 0, 20037508.342789244, 20037508.342789244))


def test_nodata_and_alpha_become_transparent(client, survey, tmp_path):
    path = make_geotiff(tmp_path / "a.tif", 512, 512, bands=4, alpha_hole=(0, 0, 256, 512))
    r = upload_ok(client, survey["id"], path)
    assert r["has_alpha"] is True
    pv = np.asarray(Image.open(io.BytesIO(client.get(r["preview_url"] + "?max_size=512").content)))
    assert pv[10, 10, 3] == 0 and pv[10, 400, 3] == 255
    nd = upload_ok(client, survey["id"], make_geotiff(tmp_path / "nd.tif", 128, 128, nodata=0))
    assert nd["nodata"] == 0 and "NODATA" in " ".join(nd["metadata"]["mask_flags"]).upper()


# ------------------------------------------------------------------ CRUD & persistensi
def test_raster_patch_delete_and_restart(make_client, tmp_path, data_dir):
    c1 = make_client()
    s = create_survey(c1)
    r = upload_ok(c1, s["id"], make_geotiff(tmp_path / "p.tif", 300, 300))
    r2 = c1.patch(f"{V1}/rasters/{r['id']}", json={"name": "Blok A Okt"}, headers={"If-Match": '"1"'})
    assert r2.status_code == 200 and r2.json()["revision"] == 2
    assert_error(c1.patch(f"{V1}/rasters/{r['id']}", json={"name": "x"}, headers={"If-Match": '"1"'}), 409,
                 "REVISION_CONFLICT")
    assert c1.patch(f"{V1}/rasters/{r['id']}", json={"transform": [1, 0, 0, 0, 1, 0]}).status_code == 422
    c2 = make_client()                                   # restart: DB + berkas di data_dir yang sama
    again = c2.get(f"{V1}/rasters/{r['id']}").json()
    assert again["name"] == "Blok A Okt" and again["sha256"] == r["sha256"]
    assert c2.get(again["preview_url"]).status_code == 200
    assert c2.delete(f"{V1}/rasters/{r['id']}").status_code == 204
    assert stored_files(data_dir) == []


def test_deleting_survey_removes_raster_files(client, survey, tmp_path, data_dir):
    upload_ok(client, survey["id"], make_geotiff(tmp_path / "d.tif", 128, 128))
    assert client.delete(f"{V1}/surveys/{survey['id']}").status_code == 204
    assert stored_files(data_dir) == []


def test_photo_workflow_unchanged_alongside_rasters(client, survey, tmp_path):
    upload_ok(client, survey["id"], make_geotiff(tmp_path / "x.tif", 128, 128))
    r = client.post(f"{V1}/surveys/{survey['id']}/photos", files={"file": ("f.png", png_bytes(), "image/png")})
    assert r.status_code == 201
    p = r.json()["photo"]
    assert p["georef_status"] == "none"
    a = client.post(f"{V1}/photos/{p['id']}/annotations", json={"kind": "plant", "geometry_type": "point",
                                                                 "x": 0.5, "y": 0.5})
    assert a.status_code == 201 and a.json()["x"] == 0.5          # tetap koordinat gambar 0–1
    assert client.get(f"{V1}/surveys/{survey['id']}").json()["photo_count"] == 1
