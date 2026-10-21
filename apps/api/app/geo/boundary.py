"""Batas lahan: validasi GeoJSON Polygon/MultiPolygon (WGS84) dan ukuran geodesik.

Konvensi (RFC 7946): posisi = [longitude, latitude] dalam derajat WGS84, tanpa altitude. Ring wajib tertutup
(posisi pertama = terakhir) dan minimal 4 posisi. Geometri yang tidak valid DITOLAK dengan alasan dan lokasinya;
tidak ada perbaikan otomatis (buffer(0)/make_valid) dan tidak ada penutupan ring diam-diam.

Luas & keliling: `pyproj.Geod(ellps="WGS84").geometry_area_perimeter` (algoritme Karney, geodesik pada elipsoid),
BUKAN `shapely.area` pada derajat. Lubang dikurangkan dari luas. Keliling = total panjang semua ring (batas luar +
lubang), sama dengan `$perimeter` QGIS; `exterior_perimeter_m` hanya batas luar.

Orientasi ring (searah/berlawanan jarum jam) diterima apa adanya dan disimpan tanpa diubah.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

GEOMETRY_TYPES = ("Polygon", "MultiPolygon")


class GeometryError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


@dataclass(frozen=True)
class BoundaryMeasures:
    area_m2: float
    perimeter_m: float
    exterior_perimeter_m: float
    bbox: tuple[float, float, float, float]          # min_lon, min_lat, max_lon, max_lat
    label_point: tuple[float, float]                  # lon, lat — titik di dalam poligon (bukan sentroid)
    polygon_count: int
    hole_count: int
    vertex_count: int


def _position(p: Any, where: str) -> list[float]:
    if not isinstance(p, (list, tuple)):
        raise GeometryError(f"{where}: posisi harus array [longitude, latitude].", {"path": where})
    if len(p) == 3:
        raise GeometryError(f"{where}: koordinat 3D (altitude) tidak didukung; kirim hanya [longitude, latitude].",
                            {"path": where})
    if len(p) != 2:
        raise GeometryError(f"{where}: posisi harus tepat 2 angka [longitude, latitude].", {"path": where})
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p):
        raise GeometryError(f"{where}: koordinat harus angka.", {"path": where})
    lon, lat = float(p[0]), float(p[1])
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise GeometryError(f"{where}: koordinat harus finite (bukan NaN/Infinity).", {"path": where})
    if not -180 <= lon <= 180:
        raise GeometryError(f"{where}: longitude {lon} di luar -180..180.", {"path": where, "lon": lon})
    if not -90 <= lat <= 90:
        hint = " Urutan GeoJSON adalah [longitude, latitude] — mungkin tertukar." if -180 <= lat <= 180 else ""
        raise GeometryError(f"{where}: latitude {lat} di luar -90..90.{hint}", {"path": where, "lat": lat})
    return [lon, lat]


def _ring(r: Any, where: str) -> list[list[float]]:
    if not isinstance(r, list):
        raise GeometryError(f"{where}: ring harus array posisi.", {"path": where})
    pts = [_position(p, f"{where}[{i}]") for i, p in enumerate(r)]
    if len(pts) < 4:
        raise GeometryError(f"{where}: ring minimal 4 posisi (3 titik unik + penutup), ditemukan {len(pts)}.",
                            {"path": where})
    if pts[0] != pts[-1]:
        raise GeometryError(f"{where}: ring tidak tertutup (posisi pertama ≠ terakhir). Tutup ring di sumber data; "
                            "API tidak menutupnya otomatis.", {"path": where})
    if len({tuple(p) for p in pts[:-1]}) < 3:
        raise GeometryError(f"{where}: ring harus punya minimal 3 titik berbeda.", {"path": where})
    return pts


def normalize_geometry(geom: Any, max_vertices: int) -> dict[str, Any]:
    """Periksa struktur + rentang, kembalikan salinan bersih {"type", "coordinates"} (float). Tidak mengubah isi."""
    if not isinstance(geom, dict):
        raise GeometryError("geometry harus objek GeoJSON.")
    gtype = geom.get("type")
    if gtype not in GEOMETRY_TYPES:
        raise GeometryError(f"geometry.type harus Polygon atau MultiPolygon (diterima: {gtype!r}).", {"type": gtype})
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords:
        raise GeometryError("geometry.coordinates kosong.")
    polys = [coords] if gtype == "Polygon" else coords
    out = []
    for pi, poly in enumerate(polys):
        base = "coordinates" if gtype == "Polygon" else f"coordinates[{pi}]"
        if not isinstance(poly, list) or not poly:
            raise GeometryError(f"{base}: poligon kosong.", {"path": base})
        out.append([_ring(r, f"{base}[{ri}]") for ri, r in enumerate(poly)])
    n = sum(len(r) for poly in out for r in poly)
    if n > max_vertices:
        raise GeometryError(f"Terlalu banyak titik ({n}); maksimal {max_vertices}. Sederhanakan batas di aplikasi GIS.",
                            {"vertex_count": n, "max_vertices": max_vertices})
    lons = [p[0] for poly in out for r in poly for p in r]
    if max(lons) - min(lons) > 180:
        raise GeometryError("Poligon melintasi antimeridian (±180°) atau terlalu lebar; belum didukung.")
    return {"type": gtype, "coordinates": out[0] if gtype == "Polygon" else out}


def measure(geom: dict[str, Any]) -> BoundaryMeasures:
    """Validasi topologi (Shapely, planar pada lon/lat — cukup untuk lahan kecil) lalu ukur secara geodesik."""
    import shapely
    from pyproj import Geod
    from shapely.geometry import shape

    g = shape(geom)
    if g.is_empty:
        raise GeometryError("Geometri kosong.")
    if not g.is_valid:
        reason = shapely.is_valid_reason(g)
        raise GeometryError(f"Geometri tidak valid: {reason}. Perbaiki di sumber (mis. QGIS: Periksa Validitas); "
                            "API tidak memperbaikinya otomatis.", {"reason": reason})
    geod = Geod(ellps="WGS84")
    area = abs(geod.geometry_area_perimeter(g)[0])
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]

    def ring_len(ring) -> float:
        lons, lats = zip(*ring.coords)
        return geod.line_length(lons, lats)

    # Dihitung per ring: geometry_area_perimeter pyproj 3.8 hanya mengembalikan keliling batas luar.
    exterior = sum(ring_len(p.exterior) for p in polys)
    perimeter = exterior + sum(ring_len(i) for p in polys for i in p.interiors)
    if area <= 0:
        raise GeometryError("Luas geometri nol.")
    lp = g.representative_point()
    return BoundaryMeasures(
        area_m2=area, perimeter_m=abs(perimeter), exterior_perimeter_m=exterior, bbox=tuple(g.bounds),
        label_point=(lp.x, lp.y), polygon_count=len(polys), hole_count=sum(len(p.interiors) for p in polys),
        vertex_count=sum(len(p.exterior.coords) + sum(len(i.coords) for i in p.interiors) for p in polys),
    )


def features_from_geojson(obj: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """FeatureCollection | Feature | Geometry → [(geometry, properties)]. Tipe lain ditolak."""
    if not isinstance(obj, dict):
        raise GeometryError("Isi GeoJSON harus objek.")
    t = obj.get("type")
    if t == "FeatureCollection":
        feats = obj.get("features")
        if not isinstance(feats, list) or not feats:
            raise GeometryError("FeatureCollection tidak berisi features.")
        return [_feature(f, f"features[{i}]") for i, f in enumerate(feats)]
    if t == "Feature":
        return [_feature(obj, "feature")]
    if t in GEOMETRY_TYPES:
        return [(obj, {})]
    raise GeometryError(f"type GeoJSON {t!r} tidak didukung (FeatureCollection, Feature, Polygon, MultiPolygon).")


def _feature(f: Any, where: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(f, dict) or f.get("type") != "Feature":
        raise GeometryError(f"{where}: harus Feature.", {"path": where})
    if f.get("geometry") is None:
        raise GeometryError(f"{where}: geometry kosong (null).", {"path": where})
    props = f.get("properties") if isinstance(f.get("properties"), dict) else {}
    return f["geometry"], props
