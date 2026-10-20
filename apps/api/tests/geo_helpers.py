"""Pembuat GeoTIFF SINTETIS untuk test mapping. DATA UJI SINTETIS — bukan foto drone, bukan K919, bukan peta nyata.

Raster berisi latar coklat dan kotak hijau di posisi piksel yang diketahui, sehingga transformasi jendela → piksel →
CRS → WGS84 bisa dibuktikan tanpa model sungguhan. `GreenBoxDetector` menemukan kotak hijau dari piksel gambar yang
diterimanya (seperti model sungguhan: hanya melihat gambar jendela, tidak tahu offset).
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np

from app.inference import DetectionOutput, Detector, DetectorInfo, RawDetection

BROWN = (120, 90, 60)
GREEN = (30, 200, 40)
TAG = "DATA UJI SINTETIS WALLACEA — bukan citra nyata"


def make_geotiff(path: Path, width: int, height: int, crs="EPSG:32748", transform=None, squares=(), bands=3,
                 dtype="uint8", nodata=None, alpha_hole=None, gcps=None, driver="GTiff") -> Path:
    """squares: [(col, row, size)] kotak hijau. alpha_hole: (col, row, w, h) area alpha=0 (butuh bands=4)."""
    import rasterio
    from rasterio.enums import ColorInterp
    from rasterio.transform import from_origin

    if transform is None:
        transform = from_origin(700000, 9270000, 0.05, 0.05)    # UTM 48S dekat Bogor, 5 cm/px
    img = np.empty((3, height, width), dtype="uint8")
    for i, v in enumerate(BROWN):
        img[i] = v
    for col, row, size in squares:
        for i, v in enumerate(GREEN):
            img[i, row:row + size, col:col + size] = v
    data = [img[0], img[1], img[2]][:min(bands, 3)] if bands < 3 else [img[0], img[1], img[2]]
    if bands == 4:
        a = np.full((height, width), 255, dtype="uint8")
        if alpha_hole:
            c, r, w, h = alpha_hole
            a[r:r + h, c:c + w] = 0
        data.append(a)
    arr = np.stack(data).astype(dtype)
    if dtype == "uint16":
        arr = arr * 200
    profile = dict(driver=driver, width=width, height=height, count=arr.shape[0], dtype=dtype)
    if driver == "GTiff":
        profile.update(tiled=True, blockxsize=256, blockysize=256, compress="DEFLATE")
    if crs is not None:
        profile["crs"] = crs
    if transform is not None and gcps is None:
        profile["transform"] = transform
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr)
        if bands == 4:
            dst.colorinterp = [ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha]
        if gcps is not None:
            dst.gcps = (gcps, crs)
        if driver == "GTiff":
            dst.update_tags(WALLACEA_TEST_DATA=TAG)
    return path


def green_boxes(arr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Komponen terhubung piksel hijau → [(left, top, width, height)] dalam piksel gambar."""
    mask = (arr[..., 1] > 150) & (arr[..., 0] < 100)
    seen = np.zeros_like(mask)
    out = []
    for r0, c0 in np.argwhere(mask):
        if seen[r0, c0]:
            continue
        q = deque([(r0, c0)])
        seen[r0, c0] = True
        rmin = rmax = r0
        cmin = cmax = c0
        while q:
            r, c = q.popleft()
            rmin, rmax, cmin, cmax = min(rmin, r), max(rmax, r), min(cmin, c), max(cmax, c)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < mask.shape[0] and 0 <= cc < mask.shape[1] and mask[rr, cc] and not seen[rr, cc]:
                    seen[rr, cc] = True
                    q.append((rr, cc))
        out.append((int(cmin), int(rmin), int(cmax - cmin + 1), int(rmax - rmin + 1)))
    return out


class GreenBoxDetector(Detector):
    """Test double yang melihat piksel: kotak hijau → bbox ternormalisasi terhadap gambar input.
    Kotak terpotong tepi gambar diberi confidence lebih rendah (seperti model pada objek terpotong)."""

    def __init__(self):
        self.calls, self.sizes = 0, []

    def info(self):
        return DetectorInfo(state="loaded", message="TEST DOUBLE kotak hijau — bukan model tanaman.",
                            model_id="green-box-test-double", model_version="sha256:test-green", adapter=None,
                            target="plant")

    def detect(self, image):
        self.calls += 1
        self.sizes.append(image.size)
        arr = np.asarray(image.convert("RGB"))
        h, w = arr.shape[:2]
        dets = []
        for left, top, bw, bh in green_boxes(arr):
            cut = left == 0 or top == 0 or left + bw >= w or top + bh >= h
            dets.append(RawDetection("plant", [left / w, top / h, bw / w, bh / h], 0.55 if cut else 0.9, "kotak_hijau"))
        return DetectionOutput("green-box-test-double", "sha256:test-green", dets, {"adapter": "test-double"})
