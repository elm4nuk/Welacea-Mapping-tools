"""Gambar bbox di atas foto terorientasi (untuk notebook). Koordinat = [left, top, width, height] 0–1."""
from __future__ import annotations

from PIL import Image, ImageDraw

COLORS = {"plant": (46, 204, 113), "check": (241, 196, 15), "gap": (231, 76, 60), "pred": (52, 152, 219)}


def draw_boxes(img: Image.Image, boxes: list[tuple[str, list[float]]], width: int | None = None,
               max_side: int | None = 1600) -> Image.Image:
    """boxes: [(label, [l, t, w, h])]. Label tak dikenal digambar biru (prediksi)."""
    out = img.convert("RGB").copy()
    if max_side and max(out.size) > max_side:
        out.thumbnail((max_side, max_side))
    W, H = out.size
    d = ImageDraw.Draw(out)
    lw = width or max(1, round(max(W, H) / 600))
    for label, (l, t, w, h) in boxes:
        d.rectangle([l * W, t * H, (l + w) * W, (t + h) * H], outline=COLORS.get(label, COLORS["pred"]), width=lw)
    return out
