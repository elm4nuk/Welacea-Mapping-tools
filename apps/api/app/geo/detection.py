"""Deteksi model pada raster besar: jendela ber-overlap → koordinat piksel raster asal → deduplikasi.

1. Jendela: raster dibagi jendela `tile_size` px dengan langkah `tile_size - overlap`. Jendela terakhir di tiap
   sumbu digeser agar berakhir tepat di tepi raster (tanpa padding), kecuali raster lebih kecil dari tile_size.
2. Resize: jendela boleh dibaca dengan skala `scale` (mis. 0.5 untuk menyamakan GSD dengan data latih). Detector
   mengembalikan bbox ternormalisasi 0–1 terhadap gambar yang IA terima, jadi posisi asli =
   offset_jendela + bbox_norm × ukuran_jendela_asli — tidak bergantung skala atau letterbox internal detector
   (adapter Ultralytics/DeepForest sudah mengembalikan koordinat pada gambar input, bukan gambar letterbox).
3. Kotak yang menempel tepi DALAM jendela (bukan tepi raster) dibuang bila overlap > 0: objek yang lebih kecil
   dari overlap selalu terlihat utuh di jendela tetangga. Objek lebih besar dari overlap bisa hilang → atur
   overlap ≥ ukuran objek terbesar (dicatat di parameter run).
4. Deduplikasi (per `kind`): urutkan confidence menurun (None = 0), lalu NMS rakus: kotak dibuang bila
   IoU ≥ `iou_threshold` (0.5) ATAU intersection/area-terkecil ≥ `ios_threshold` (0.8) terhadap kotak yang sudah
   dipertahankan. IoS menangkap potongan kotak di jendela berbeda yang IoU-nya kecil.
5. Kotak yang pusatnya jatuh di piksel mask = 0 (nodata/alpha) dibuang.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class Window:
    col_off: int
    row_off: int
    width: int
    height: int


@dataclass
class PixelBox:
    kind: str
    left: float
    top: float
    width: float
    height: float
    confidence: float | None
    model_label: str | None

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def area(self) -> float:
        return self.width * self.height


def _starts(size: int, tile: int, step: int) -> list[int]:
    if size <= tile:
        return [0]
    out = list(range(0, size - tile, step))
    out.append(size - tile)
    return sorted(set(out))


def windows(width: int, height: int, tile_size: int, overlap: int) -> Iterator[Window]:
    if not 0 <= overlap < tile_size:
        raise ValueError("overlap harus 0 ≤ overlap < tile_size")
    step = tile_size - overlap
    for r in _starts(height, tile_size, step):
        for c in _starts(width, tile_size, step):
            yield Window(c, r, min(tile_size, width - c), min(tile_size, height - r))


def to_raster_pixels(win: Window, bbox_norm: list[float]) -> tuple[float, float, float, float]:
    """bbox [left, top, width, height] ternormalisasi terhadap gambar jendela → piksel raster asal."""
    l, t, w, h = bbox_norm
    return win.col_off + l * win.width, win.row_off + t * win.height, w * win.width, h * win.height


def touches_inner_edge(box: PixelBox, win: Window, raster_w: int, raster_h: int, tol: float = 1.0) -> bool:
    if win.col_off > 0 and box.left <= win.col_off + tol:
        return True
    if win.row_off > 0 and box.top <= win.row_off + tol:
        return True
    if win.col_off + win.width < raster_w and box.right >= win.col_off + win.width - tol:
        return True
    if win.row_off + win.height < raster_h and box.bottom >= win.row_off + win.height - tol:
        return True
    return False


def _overlap(a: PixelBox, b: PixelBox) -> tuple[float, float]:
    iw = min(a.right, b.right) - max(a.left, b.left)
    ih = min(a.bottom, b.bottom) - max(a.top, b.top)
    if iw <= 0 or ih <= 0:
        return 0.0, 0.0
    inter = iw * ih
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0, inter / min(a.area, b.area) if min(a.area, b.area) > 0 else 0.0


def deduplicate(boxes: list[PixelBox], iou_threshold: float = 0.5, ios_threshold: float = 0.8) -> list[PixelBox]:
    """NMS rakus per kind (lihat docstring modul). O(n²) per sel grid; cukup untuk ribuan kotak."""
    order = sorted(boxes, key=lambda b: -(b.confidence if b.confidence is not None else 0.0))
    kept: list[PixelBox] = []
    grid: dict[tuple[str, int, int], list[PixelBox]] = {}
    cell = max(64.0, max((max(b.width, b.height) for b in boxes), default=64.0) * 2)
    for b in order:
        cx, cy = int((b.left + b.width / 2) // cell), int((b.top + b.height / 2) // cell)
        dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((b.kind, cx + dx, cy + dy), ()):
                    iou, ios = _overlap(b, k)
                    if iou >= iou_threshold or ios >= ios_threshold:
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if not dup:
            kept.append(b)
            grid.setdefault((b.kind, cx, cy), []).append(b)
    return kept
