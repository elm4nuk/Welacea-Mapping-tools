"""Raster GeoTIFF impor: validasi, turunan tampilan, footprint, tile XYZ, preview, piksel → WGS84.

Yang diterima: GeoTIFF (driver GTiff), 3 band RGB uint8 atau 4 band RGBA uint8 (band 4 = alpha), CRS geografis
atau proyeksi yang valid, dan geotransform affine yang bukan identitas. Rotasi/shear diterima (ditangani transform).
Raster hanya-GCP, tanpa CRS, atau transform identitas DITOLAK: tidak ada penempelan otomatis ke peta.

Yang disimpan: berkas asli byte-per-byte (sha256), plus turunan tampilan RGBA (tiled 512, DEFLATE, overview
rata-rata) di CRS asli. Turunan dibuat per blok sehingga memori tetap kecil untuk raster besar. Tile web dibuat
per request dari turunan lewat WarpedVRT (EPSG:3857) dengan pembacaan tereduksi yang memakai overview.

Konvensi koordinat: posisi piksel kontinu (col, row) dengan (0, 0) = sudut kiri-atas piksel pertama
(PixelIsArea; GDAL sudah menggeser transform untuk PixelIsPoint). world = transform × (col, row). Semua
transformasi CRS memakai pyproj `always_xy=True`: urutan (x/easting/longitude, y/northing/latitude) — tidak
mengikuti urutan sumbu "lat, lon" EPSG:4326 resmi.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PIPELINE = "wallacea-raster-import/1"
BLOCK = 512
TILE = 256
WEB_MERCATOR_MAX_LAT = 85.05112878
ORIGIN_3857 = 20037508.342789244


class RasterError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


@dataclass
class RasterInfo:
    driver: str
    width: int
    height: int
    band_count: int
    dtype: str
    crs_wkt: str
    crs_epsg: int | None
    crs_name: str
    crs_is_geographic: bool
    transform: list[float]                       # affine a, b, c, d, e, f (rasterio/Affine order)
    bounds_native: list[float]                   # left, bottom, right, top dalam CRS asli
    bounds_wgs84: list[float]                    # west, south, east, north
    footprint_wgs84: dict[str, Any]              # GeoJSON Polygon (tepi didensifikasi)
    footprint_area_m2: float
    pixel_size_native: list[float]               # |a|, |e| dalam satuan CRS
    approx_gsd_m: float                          # perkiraan ukuran piksel di tanah (m), pusat raster
    is_rotated: bool
    nodata: float | None
    has_alpha: bool
    mask_flags: list[str]
    colorinterp: list[str]
    compression: str | None
    warnings: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _transformer(src_crs, dst_crs):
    from pyproj import Transformer
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def _crs(wkt_or_obj):
    from pyproj import CRS
    return CRS.from_user_input(wkt_or_obj)


def apply_affine(t, col: float, row: float) -> tuple[float, float]:
    """x = a·col + b·row + c ; y = d·col + e·row + f (rumus GDAL/affine, tanpa operator Affine yang deprecated)."""
    return t.a * col + t.b * row + t.c, t.d * col + t.e * row + t.f


def _ring_densified(transform, width: int, height: int, n: int = 16) -> list[tuple[float, float]]:
    """Batas raster (sudut piksel) didensifikasi n titik per sisi, searah: kiri-atas → kanan-atas → … ."""
    pts = []
    for i in range(n):
        pts.append((width * i / n, 0.0))
    for i in range(n):
        pts.append((float(width), height * i / n))
    for i in range(n):
        pts.append((width * (n - i) / n, float(height)))
    for i in range(n):
        pts.append((0.0, height * (n - i) / n))
    return [apply_affine(transform, c, r) for c, r in pts]


def inspect(path: Path, max_pixels: int, max_footprint_km2: float) -> RasterInfo:
    import rasterio
    from pyproj import Geod
    from rasterio.enums import ColorInterp, MaskFlags
    from rasterio.errors import NotGeoreferencedWarning, RasterioIOError
    from shapely.geometry import Polygon, mapping

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", NotGeoreferencedWarning)
            src = rasterio.open(path)
    except RasterioIOError as exc:
        raise RasterError(400, "INVALID_RASTER", "Berkas tidak dapat dibaca sebagai raster (rusak atau bukan GeoTIFF).",
                          {"reason": str(exc)[:300]}) from exc
    with src:
        not_georef = any(issubclass(w.category, NotGeoreferencedWarning) for w in caught)
        if src.driver != "GTiff":
            raise RasterError(415, "UNSUPPORTED_RASTER", f"Hanya GeoTIFF yang diterima (driver terbaca: {src.driver}).",
                              {"driver": src.driver})
        if src.count not in (3, 4):
            raise RasterError(415, "UNSUPPORTED_RASTER",
                              f"Raster harus 3 band RGB atau 4 band RGBA (ditemukan {src.count} band).",
                              {"band_count": src.count})
        if any(dt != "uint8" for dt in src.dtypes):
            raise RasterError(415, "UNSUPPORTED_RASTER",
                              f"Tipe piksel harus 8-bit (uint8), ditemukan {sorted(set(src.dtypes))}. Konversi dulu, "
                              "mis. gdal_translate -ot Byte -scale.", {"dtypes": list(src.dtypes)})
        ci = [c.name for c in src.colorinterp]
        has_alpha = src.count == 4
        if has_alpha and src.colorinterp[3] != ColorInterp.alpha:
            raise RasterError(415, "UNSUPPORTED_RASTER",
                              f"Band ke-4 bukan alpha ({ci[3]}). Raster multispektral/NIR belum didukung.",
                              {"colorinterp": ci})
        if src.width * src.height > max_pixels:
            raise RasterError(413, "RASTER_TOO_LARGE",
                              f"Raster {src.width}×{src.height} melebihi {max_pixels:,} piksel. Potong atau turunkan "
                              "resolusi dulu.", {"width": src.width, "height": src.height, "max_pixels": max_pixels})
        t = src.transform
        has_gcps = bool(src.gcps[0])
        if (not_georef or t.is_identity) and has_gcps:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED",
                              "Raster hanya punya GCP (titik kontrol), belum direktifikasi. Lakukan warp/rektifikasi di "
                              "aplikasi GIS (mis. gdalwarp) lalu unggah ulang; API tidak menebak transformasinya.",
                              {"reason": "gcp_only", "has_gcps": True})
        if src.crs is None:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED",
                              "Raster tidak punya CRS. Berkas tanpa georeferensi tidak ditempelkan ke peta; unggah "
                              "sebagai foto biasa atau georeferensikan dulu di aplikasi GIS.",
                              {"reason": "no_crs", "has_gcps": has_gcps})
        if not_georef or t.is_identity:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED", "Geotransform raster kosong/identitas.",
                              {"reason": "identity_transform", "has_gcps": has_gcps})
        if t.a == 0 and t.b == 0 or t.d == 0 and t.e == 0 or abs(t.determinant) == 0:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED", "Geotransform raster degenerate.",
                              {"reason": "degenerate_transform"})
        try:
            crs = _crs(src.crs.to_wkt())
        except Exception as exc:  # noqa: BLE001
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED", "CRS raster tidak dikenali.",
                              {"reason": "invalid_crs"}) from exc
        if not (crs.is_geographic or crs.is_projected):
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED",
                              f"CRS {crs.name!r} bukan CRS geografis/proyeksi (mis. CRS lokal/engineering).",
                              {"reason": "unsupported_crs_kind"})

        to_wgs = _transformer(crs, "EPSG:4326")
        ring = [to_wgs.transform(x, y) for x, y in _ring_densified(t, src.width, src.height)]
        if not all(math.isfinite(v) for p in ring for v in p):
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED", "Batas raster tidak dapat diproyeksikan ke WGS84.",
                              {"reason": "projection_failed"})
        lons, lats = [p[0] for p in ring], [p[1] for p in ring]
        if max(lons) - min(lons) > 180 or min(lats) < -WEB_MERCATOR_MAX_LAT or max(lats) > WEB_MERCATOR_MAX_LAT:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED",
                              "Cakupan raster melintasi antimeridian atau di luar ±85° — georeferensi kemungkinan salah.",
                              {"reason": "bounds_out_of_range"})
        footprint = Polygon(ring + [ring[0]])
        if not footprint.is_valid:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED", "Footprint raster tidak valid setelah proyeksi.",
                              {"reason": "invalid_footprint"})
        geod = Geod(ellps="WGS84")
        fp_area = abs(geod.geometry_area_perimeter(footprint)[0])
        if fp_area > max_footprint_km2 * 1e6:
            raise RasterError(422, "RASTER_NOT_GEOREFERENCED",
                              f"Cakupan raster {fp_area / 1e6:,.0f} km² melebihi batas {max_footprint_km2:,.0f} km² untuk "
                              "peta drone; periksa CRS/pixel size.", {"reason": "footprint_too_large",
                                                                       "footprint_km2": fp_area / 1e6})
        # GSD: jarak geodesik satu piksel di pusat raster (arah kolom & baris), rata-rata.
        cx, cy = src.width / 2, src.height / 2
        p0, px, py = (to_wgs.transform(*apply_affine(t, *q)) for q in ((cx, cy), (cx + 1, cy), (cx, cy + 1)))
        gsd = (geod.inv(p0[0], p0[1], px[0], px[1])[2] + geod.inv(p0[0], p0[1], py[0], py[1])[2]) / 2
        warn = []
        if gsd > 5:
            warn.append(f"Ukuran piksel ±{gsd:.1f} m — terlalu kasar untuk mendeteksi tanaman individual.")
        if gsd < 0.005:
            warn.append(f"Ukuran piksel ±{gsd * 100:.2f} cm — sangat halus; periksa satuan CRS.")
        flags = sorted({f.name for band in src.mask_flag_enums for f in band})
        epsg = crs.to_epsg()
        b = src.bounds
        return RasterInfo(
            driver=src.driver, width=src.width, height=src.height, band_count=src.count, dtype="uint8",
            crs_wkt=crs.to_wkt(), crs_epsg=epsg, crs_name=crs.name, crs_is_geographic=crs.is_geographic,
            transform=[t.a, t.b, t.c, t.d, t.e, t.f], bounds_native=[b.left, b.bottom, b.right, b.top],
            bounds_wgs84=[min(lons), min(lats), max(lons), max(lats)], footprint_wgs84=mapping(footprint),
            footprint_area_m2=fp_area, pixel_size_native=[abs(t.a) or abs(t.b), abs(t.e) or abs(t.d)],
            approx_gsd_m=gsd, is_rotated=bool(t.b or t.d), nodata=src.nodata, has_alpha=has_alpha,
            mask_flags=flags, colorinterp=ci, compression=(src.compression.name if src.compression else None),
            warnings=warn,
        )


def build_display(src_path: Path, dst_path: Path) -> dict[str, Any]:
    """Turunan tampilan RGBA (alpha = mask dataset: nodata/alpha/mask internal) + overview. Ditulis per blok."""
    import numpy as np
    import rasterio
    from rasterio.enums import ColorInterp, Resampling

    with rasterio.open(src_path) as src:
        profile = dict(driver="GTiff", width=src.width, height=src.height, count=4, dtype="uint8", crs=src.crs,
                       transform=src.transform, tiled=True, blockxsize=BLOCK, blockysize=BLOCK, compress="DEFLATE",
                       predictor=2, interleave="pixel", photometric="RGB", BIGTIFF="IF_SAFER")
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.colorinterp = [ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha]
            for _, win in dst.block_windows(1):
                rgb = src.read([1, 2, 3], window=win)
                mask = src.dataset_mask(window=win)
                dst.write(np.concatenate([rgb, mask[np.newaxis]], axis=0), window=win)
            factors, f = [], 2
            while max(src.width, src.height) / f >= BLOCK / 2:
                factors.append(f)
                f *= 2
            if factors:
                dst.build_overviews(factors, Resampling.average)
                dst.update_tags(ns="rio_overview", resampling="average")
    import rasterio as _r
    return {"pipeline": PIPELINE, "display": {"format": "GTiff RGBA uint8", "block": BLOCK, "compress": "DEFLATE",
                                              "alpha": "dataset_mask (nodata/alpha/mask internal)",
                                              "overviews": factors, "overview_resampling": "average"},
            "rasterio_version": _r.__version__, "gdal_version": _r.__gdal_version__}


# ------------------------------------------------------------------ tiles & preview
def tile_bounds_3857(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    size = 2 * ORIGIN_3857 / (2 ** z)
    left = -ORIGIN_3857 + x * size
    top = ORIGIN_3857 - y * size
    return left, top - size, left + size, top


def zoom_range(gsd_m: float, lat: float, overview_count: int) -> tuple[int, int]:
    """maxzoom = zoom yang ukuran piksel tile-nya ≈ GSD; minzoom beberapa level di bawah (memakai overview)."""
    res0 = 2 * math.pi * 6378137 / TILE * math.cos(math.radians(lat))
    maxz = max(0, min(24, math.ceil(math.log2(res0 / max(gsd_m, 1e-3)))))
    return max(0, maxz - overview_count - 3), maxz


def _png(arr) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(arr.transpose(1, 2, 0), mode="RGBA").save(buf, format="PNG", optimize=False)
    return buf.getvalue()


_EMPTY: bytes | None = None


def empty_tile() -> bytes:
    global _EMPTY
    if _EMPTY is None:
        import numpy as np
        _EMPTY = _png(np.zeros((4, TILE, TILE), dtype="uint8"))
    return _EMPTY


def render_tile(display_path: Path, z: int, x: int, y: int) -> bytes:
    """Tile XYZ 256 px (EPSG:3857) dari turunan tampilan. Area di luar raster transparan."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    from rasterio.windows import Window, from_bounds

    tl, tb, tr, tt = tile_bounds_3857(z, x, y)
    with rasterio.open(display_path) as src, WarpedVRT(src, crs="EPSG:3857", resampling=Resampling.bilinear,
                                                        add_alpha=False) as vrt:
        vb = vrt.bounds
        il, ib, ir, it = max(tl, vb.left), max(tb, vb.bottom), min(tr, vb.right), min(tt, vb.top)
        if il >= ir or ib >= it:
            return empty_tile()
        # posisi bagian yang beririsan di dalam tile (piksel tile)
        sx = TILE / (tr - tl)
        c0, c1 = round((il - tl) * sx), round((ir - tl) * sx)
        r0, r1 = round((tt - it) * sx), round((tt - ib) * sx)
        if c1 <= c0 or r1 <= r0:
            return empty_tile()
        win = from_bounds(il, ib, ir, it, vrt.transform)
        win = Window(win.col_off, win.row_off, max(win.width, 1e-6), max(win.height, 1e-6))
        data = vrt.read(window=win, out_shape=(4, r1 - r0, c1 - c0), resampling=Resampling.bilinear)
    out = np.zeros((4, TILE, TILE), dtype="uint8")
    out[:, r0:r1, c0:c1] = data
    return _png(out)


def render_preview(display_path: Path, max_side: int) -> bytes:
    """Gambar ringkas di ruang piksel ASLI (tidak diproyeksi ulang). Untuk peta gunakan tile."""
    import rasterio
    from rasterio.enums import Resampling

    with rasterio.open(display_path) as src:
        scale = min(1.0, max_side / max(src.width, src.height))
        h, w = max(1, round(src.height * scale)), max(1, round(src.width * scale))
        data = src.read(out_shape=(4, h, w), resampling=Resampling.average)
    return _png(data)


# ------------------------------------------------------------------ piksel → dunia
class PixelGeo:
    """Konversi posisi piksel kontinu raster (col, row) → CRS asli → WGS84 (lon, lat)."""

    def __init__(self, transform: list[float], crs_wkt: str):
        from affine import Affine
        self.affine = Affine(*transform)
        self.to_wgs = _transformer(_crs(crs_wkt), "EPSG:4326")

    def native(self, col: float, row: float) -> tuple[float, float]:
        return apply_affine(self.affine, col, row)

    def lonlat(self, col: float, row: float) -> tuple[float, float]:
        return self.to_wgs.transform(*self.native(col, row))

    def box_polygon(self, left: float, top: float, width: float, height: float) -> dict[str, Any]:
        """Kotak piksel → GeoJSON Polygon WGS84 dari 4 sudut (benar juga untuk raster berotasi)."""
        corners = [(left, top), (left + width, top), (left + width, top + height), (left, top + height)]
        ring = [list(self.lonlat(c, r)) for c, r in corners]
        return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
