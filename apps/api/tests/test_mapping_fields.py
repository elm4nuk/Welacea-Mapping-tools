"""Batas lahan (revisi 5): ukuran geodesik pada geometri referensi, validasi, CRUD, impor/ekspor GeoJSON, persistensi."""
import json

import pytest
from pyproj import Transformer
from shapely.geometry import Polygon, shape

from app.geo.boundary import GeometryError, measure, normalize_geometry
from conftest import assert_error, create_survey

V1 = "/api/v1"


def rect(lon0, lat0, dlon, dlat, holes=()):
    ring = [[lon0, lat0], [lon0 + dlon, lat0], [lon0 + dlon, lat0 + dlat], [lon0, lat0 + dlat], [lon0, lat0]]
    return {"type": "Polygon", "coordinates": [ring, *holes]}


def metres_square(lon0, lat0, size_m, epsg_utm=32748):
    """Persegi `size_m` meter di UTM, dikembalikan dalam lon/lat (untuk geometri referensi berukuran meter)."""
    fwd = Transformer.from_crs(4326, epsg_utm, always_xy=True)
    inv = Transformer.from_crs(epsg_utm, 4326, always_xy=True)
    x0, y0 = fwd.transform(lon0, lat0)
    pts = [(x0, y0), (x0 + size_m, y0), (x0 + size_m, y0 + size_m), (x0, y0 + size_m), (x0, y0)]
    return [list(inv.transform(x, y)) for x, y in pts]


def projected_area(geom, epsg):
    """Pembanding independen: shoelace pada proyeksi equal-area/UTM (bukan pyproj.Geod)."""
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    g = shape(geom)
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    area = 0.0
    for p in polys:
        area += Polygon([t.transform(*c) for c in p.exterior.coords],
                        [[t.transform(*c) for c in i.coords] for i in p.interiors]).area
    return area


# ------------------------------------------------------------------ ukuran pada geometri referensi
def test_one_degree_cell_matches_geographiclib_reference():
    # Sel 1°×1° di ekuator pada elipsoid WGS84: 12 308 778 361.469 m² (nilai Planimeter GeographicLib).
    m = measure(normalize_geometry(rect(0, 0, 1, 1), 100))
    assert m.area_m2 == pytest.approx(12_308_778_361.469, abs=0.01)
    # sisi selatan = 1° busur ekuator = a·π/180 = 111 319.4908 m
    assert m.perimeter_m > 4 * 110_000 and m.exterior_perimeter_m == pytest.approx(m.perimeter_m)


def test_small_field_matches_equal_area_projection_not_degrees():
    ring = metres_square(106.8, -6.6, 100.0)            # 1 ha di Bogor
    geom = {"type": "Polygon", "coordinates": [ring]}
    m = measure(normalize_geometry(geom, 100))
    assert m.area_m2 == pytest.approx(projected_area(geom, 6933), rel=1e-5)     # EASE-Grid 2.0 equal-area
    assert m.area_m2 == pytest.approx(10_000, rel=2e-3)                         # UTM skala ±0.9996²
    assert m.perimeter_m == pytest.approx(400, rel=2e-3)
    assert shape(geom).area < 1e-6          # shapely.area pada derajat ≈ 8e-8 "derajat²" — bukan m²


def test_polygon_with_hole_and_multipolygon():
    outer = metres_square(106.8, -6.6, 100.0)
    hole = metres_square(106.8003, -6.5997, 20.0)
    holed = {"type": "Polygon", "coordinates": [outer, hole[::-1]]}
    m = measure(normalize_geometry(holed, 100))
    assert m.hole_count == 1
    assert m.area_m2 == pytest.approx(projected_area(holed, 6933), rel=1e-5)
    assert m.area_m2 == pytest.approx(10_000 - 400, rel=3e-3)
    assert m.perimeter_m == pytest.approx(480, rel=3e-3) and m.exterior_perimeter_m == pytest.approx(400, rel=3e-3)
    multi = {"type": "MultiPolygon", "coordinates": [[outer], [metres_square(106.81, -6.6, 50.0)]]}
    mm = measure(normalize_geometry(multi, 100))
    assert mm.polygon_count == 2 and mm.area_m2 == pytest.approx(12_500, rel=3e-3)


def test_ring_orientation_does_not_change_area_and_is_kept():
    ccw = rect(106.8, -6.6, 0.001, 0.001)
    cw = {"type": "Polygon", "coordinates": [ccw["coordinates"][0][::-1]]}
    assert measure(normalize_geometry(cw, 100)).area_m2 == pytest.approx(measure(normalize_geometry(ccw, 100)).area_m2)
    assert normalize_geometry(cw, 100) == cw


@pytest.mark.parametrize("geom, fragment", [
    ({"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}, "Self-intersection"),
    ({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}, "tidak tertutup"),
    ({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}, "minimal 4 posisi"),
    ({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 0], [0, 0]]]}, "3 titik berbeda"),
    ({"type": "Polygon", "coordinates": []}, "kosong"),
    ({"type": "Polygon", "coordinates": [[[200, 0], [201, 0], [201, 1], [200, 0]]]}, "longitude"),
    ({"type": "Polygon", "coordinates": [[[-6.6, 106.8], [-6.5, 106.8], [-6.5, 106.9], [-6.6, 106.8]]]},
     "mungkin tertukar"),
    ({"type": "Polygon", "coordinates": [[[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 0, 5]]]}, "3D"),
    ({"type": "Point", "coordinates": [0, 0]}, "Polygon atau MultiPolygon"),
    ({"type": "Polygon", "coordinates": [[[179, 0], [-179, 0], [-179, 1], [179, 0]]]}, "antimeridian"),
    ({"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                                         [[20, 20], [21, 20], [21, 21], [20, 20]]]}, "tidak valid"),
])
def test_invalid_geometry_is_rejected_not_repaired(geom, fragment):
    with pytest.raises(GeometryError) as exc:
        measure(normalize_geometry(geom, 100))
    assert fragment in str(exc.value)


def test_vertex_limit():
    ring = [[106.8 + 0.0001 * i, -6.6] for i in range(60)] + [[106.8, -6.59], [106.8, -6.6]]
    with pytest.raises(GeometryError, match="Terlalu banyak titik"):
        normalize_geometry({"type": "Polygon", "coordinates": [ring]}, 50)


# ------------------------------------------------------------------ API
FIELD = {"name": "Blok Jagung A", "boundary_source": "gnss_survey", "source_note": "Diukur GNSS genggam",
         "geometry": {"type": "Polygon", "coordinates": [metres_square(106.8, -6.6, 100.0)]}}


def create_field(client, **kw):
    r = client.post(f"{V1}/fields", json={**FIELD, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_field_crud_revision_and_measures_from_backend(client):
    f = create_field(client)
    assert f["measures"]["area_ha"] == pytest.approx(1.0, rel=2e-3) and f["measures"]["method"] == "geodesic_wgs84"
    assert f["geometry"] == FIELD["geometry"] and f["revision"] == 1 and f["survey_ids"] == []
    assert f["bbox"][0] == pytest.approx(106.8) and len(f["label_point"]) == 2
    # klien tidak bisa mengirim luas sendiri
    r = client.post(f"{V1}/fields", json={**FIELD, "area_m2": 1})
    assert r.status_code == 422
    # ubah nama + geometri (If-Match benar)
    new_geom = {"type": "Polygon", "coordinates": [metres_square(106.8, -6.6, 200.0)]}
    r = client.patch(f"{V1}/fields/{f['id']}", json={"name": "Blok A2", "geometry": new_geom},
                     headers={"If-Match": '"1"'})
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 2 and r.json()["measures"]["area_ha"] == pytest.approx(4.0, rel=2e-3)
    assert r.headers["ETag"] == '"2"'
    err = assert_error(client.patch(f"{V1}/fields/{f['id']}", json={"name": "x"}, headers={"If-Match": '"1"'}),
                       409, "REVISION_CONFLICT")
    assert err["details"]["current"]["revision"] == 2
    assert client.get(f"{V1}/fields").json()["total"] == 1
    assert client.delete(f"{V1}/fields/{f['id']}").status_code == 204
    assert_error(client.get(f"{V1}/fields/{f['id']}"), 404, "NOT_FOUND")


def test_invalid_geometry_via_api_is_422_and_nothing_saved(client):
    bow = {"type": "Polygon", "coordinates": [[[106.8, -6.6], [106.81, -6.59], [106.81, -6.6], [106.8, -6.59],
                                                [106.8, -6.6]]]}
    err = assert_error(client.post(f"{V1}/fields", json={**FIELD, "geometry": bow}), 422, "INVALID_GEOMETRY")
    assert "Self-intersection" in err["message"] and err["details"]["reason"].startswith("Self-intersection")
    nan = '{"name": "x", "boundary_source": "other", "geometry": {"type": "Polygon", "coordinates": ' \
          '[[[NaN, 0], [1, 0], [1, 1], [NaN, 0]]]}}'
    r = client.post(f"{V1}/fields", content=nan, headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert client.get(f"{V1}/fields").json()["total"] == 0


def test_payload_limit(client):
    huge = {"type": "Polygon", "coordinates": [[[106.8, -6.6]] * 200_000]}
    r = client.post(f"{V1}/fields", json={**FIELD, "geometry": huge})
    assert_error(r, 413, "PAYLOAD_TOO_LARGE")


def test_survey_links_field_and_delete_sets_null(client):
    f = create_field(client)
    s = create_survey(client, field_id=f["id"])
    assert s["field_id"] == f["id"]
    assert client.get(f"{V1}/fields/{f['id']}").json()["survey_ids"] == [s["id"]]
    assert_error(client.post(f"{V1}/surveys", json={**{k: s[k] for k in ("name", "crop_type", "survey_date")},
                                                    "field_id": "0" * 32}), 422, "VALIDATION_ERROR")
    assert client.patch(f"{V1}/surveys/{s['id']}", json={"field_id": None}).json()["field_id"] is None
    client.patch(f"{V1}/surveys/{s['id']}", json={"field_id": f["id"]})
    client.delete(f"{V1}/fields/{f['id']}")
    assert client.get(f"{V1}/surveys/{s['id']}").json()["field_id"] is None   # survei tetap ada


def test_geojson_import_export_roundtrip(client):
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "Petak 1"}, "geometry": FIELD["geometry"]},
        {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": [
            [metres_square(106.81, -6.6, 50.0)], [metres_square(106.82, -6.6, 50.0)]]}}]}
    r = client.post(f"{V1}/fields/import", files={"file": ("lahan.geojson", json.dumps(fc), "application/geo+json")})
    assert r.status_code == 201, r.text
    names = [f["name"] for f in r.json()["fields"]]
    assert names == ["Petak 1", "Lahan impor 2"]
    assert all(f["boundary_source"] == "geojson_import" for f in r.json()["fields"])
    exp = client.get(f"{V1}/fields-export.geojson")
    assert exp.headers["content-type"].startswith("application/geo+json")
    feats = {f["properties"]["name"]: f for f in exp.json()["features"]}
    assert feats["Petak 1"]["geometry"] == FIELD["geometry"]                  # koordinat tidak berubah
    assert feats["Lahan impor 2"]["properties"]["area_ha"] == pytest.approx(0.5, rel=3e-3)
    one = client.get(f"{V1}/fields/{r.json()['fields'][0]['id']}/geojson").json()
    assert one["type"] == "Feature" and one["properties"]["measure_method"] == "geodesic_wgs84"


def test_geojson_import_is_all_or_nothing_and_rejects_other_crs(client):
    bad = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "ok"}, "geometry": FIELD["geometry"]},
        {"type": "Feature", "properties": {"name": "rusak"},
         "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}}]}
    err = assert_error(client.post(f"{V1}/fields/import", files={"file": ("x.geojson", json.dumps(bad))}),
                       422, "INVALID_GEOMETRY")
    assert "Feature 2 (rusak)" in err["message"] and err["details"]["feature_index"] == 1
    assert client.get(f"{V1}/fields").json()["total"] == 0
    utm = {**bad, "features": bad["features"][:1],
           "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32748"}}}
    assert_error(client.post(f"{V1}/fields/import", files={"file": ("x.geojson", json.dumps(utm))}),
                 422, "INVALID_GEOMETRY")
    assert_error(client.post(f"{V1}/fields/import", files={"file": ("x.geojson", b"{bukan json")}), 400, "BAD_REQUEST")


def test_fields_persist_after_restart(make_client):
    c1 = make_client()
    f = create_field(c1)
    c2 = make_client()
    again = c2.get(f"{V1}/fields/{f['id']}").json()
    assert again["geometry"] == f["geometry"] and again["measures"] == f["measures"]
