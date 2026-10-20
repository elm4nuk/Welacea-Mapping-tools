"""Modul geospasial (revisi 5): batas lahan, raster GeoTIFF impor, dan deteksi model di peta.

Dependensi (rasterio, pyproj, shapely, numpy) diimpor di dalam fungsi; `available()` memberi tahu /health dan
endpoint mapping apakah paketnya terpasang, sehingga API tanpa paket ini tetap berjalan (mode foto biasa).
"""
from __future__ import annotations

import importlib.util


def available(*packages: str) -> bool:
    return all(importlib.util.find_spec(p) is not None for p in packages)


def boundaries_available() -> bool:
    return available("shapely", "pyproj")


def rasters_available() -> bool:
    return available("rasterio", "pyproj", "shapely", "numpy")
