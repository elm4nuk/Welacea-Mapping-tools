"""Fixture sintetis. Menguji PIPELINE (konversi, orientasi, split, kompatibilitas adapter), BUKAN akurasi tanaman."""
import io
import sys
import types

import pytest
from PIL import Image


def jpeg_with_orientation(raw_size, orientation, rect_raw=None, color=(255, 0, 0), bg=(0, 90, 0)) -> bytes:
    """JPEG berpiksel mentah `raw_size` dengan tag EXIF Orientation. `rect_raw` = kotak merah di piksel MENTAH."""
    img = Image.new("RGB", raw_size, bg)
    if rect_raw:
        img.paste(color, rect_raw)
    exif = Image.Exif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=100, exif=exif.tobytes(), subsampling=0)
    return buf.getvalue()


class Arr:
    def __init__(self, v): self.v = v
    def cpu(self): return self
    def tolist(self): return self.v


class FakeYOLO:
    """Mengembalikan kotak merah yang ditemukan pada gambar input (piksel xyxy) — meniru detektor sempurna
    agar konvensi koordinat ujung-ke-ujung bisa diuji tanpa model nyata."""
    names = {0: "plant"}
    task = "detect"
    seen_sizes: list = []

    def __init__(self, path, task=None):
        pass

    def predict(self, image, **kw):
        FakeYOLO.seen_sizes.append(image.size)
        px = image.load()
        xs, ys = [], []
        for y in range(image.height):
            for x in range(image.width):
                r, g, b = px[x, y]
                if r > 200 and g < 60 and b < 60:
                    xs.append(x)
                    ys.append(y)
        boxes = [[min(xs), min(ys), max(xs) + 1, max(ys) + 1]] if xs else []
        ns = types.SimpleNamespace(xyxy=Arr(boxes), conf=Arr([0.9] * len(boxes)), cls=Arr([0] * len(boxes)))
        return [types.SimpleNamespace(names=self.names, boxes=ns)]


@pytest.fixture
def fake_ultralytics(monkeypatch):
    mod = types.ModuleType("ultralytics")
    mod.YOLO = FakeYOLO
    monkeypatch.setitem(sys.modules, "ultralytics", mod)
    real_find_spec = __import__("importlib.util").util.find_spec
    monkeypatch.setattr("importlib.util.find_spec",
                        lambda name, *a: object() if name == "ultralytics" else real_find_spec(name, *a))
    FakeYOLO.seen_sizes = []
    return FakeYOLO
