"""Validasi anotasi COCO dan konversi eksplisit ke label YOLO / bbox WALLACEA.

Konvensi yang DIPERIKSA, bukan diasumsikan:
- COCO `bbox` = [x_min, y_min, width, height] dalam PIKSEL terhadap `images[].width/height`.
- `category_id` dicocokkan ke `categories[].id` (bukan indeks urut); pemetaan ke label WALLACEA
  harus disebut eksplisit lewat `class_map` (nama atau id kategori → plant/check/gap atau "drop").
- YOLO = `<cls> <cx> <cy> <w> <h>` ternormalisasi 0–1; `cls` = indeks dari `label_map` manifest.
- WALLACEA/API = `[left, top, width, height]` ternormalisasi 0–1 terhadap gambar TERORIENTASI EXIF.
- Gambar tanpa anotasi TIDAK dianggap contoh negatif kecuali `empty_images_are_negative=True`
  (hanya bila dokumentasi dataset menyatakannya). Default: dikeluarkan dari dataset & dilaporkan.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TARGET_LABELS = ("plant", "check", "gap")
DROP = "drop"


@dataclass
class CocoIssue:
    level: str       # error | warning
    code: str
    message: str
    image_id: int | None = None
    annotation_id: int | None = None


@dataclass
class CocoReport:
    images: int = 0
    annotations: int = 0
    categories: dict[int, str] = field(default_factory=dict)
    per_category: dict[str, int] = field(default_factory=dict)
    unannotated_images: list[str] = field(default_factory=list)
    issues: list[CocoIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[CocoIssue]:
        return [i for i in self.issues if i.level == "error"]

    def summary(self) -> dict:
        return {"images": self.images, "annotations": self.annotations, "categories": self.categories,
                "per_category": self.per_category, "unannotated_images": len(self.unannotated_images),
                "errors": Counter(i.code for i in self.errors),
                "warnings": Counter(i.code for i in self.issues if i.level == "warning")}


def load_coco(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_coco(coco: dict, tolerance_px: float = 1.0) -> CocoReport:
    """Periksa struktur, id, kategori, dan koordinat piksel. Tidak membuka berkas gambar."""
    r = CocoReport()
    images = coco.get("images") or []
    anns = coco.get("annotations") or []
    cats = coco.get("categories") or []
    r.images, r.annotations = len(images), len(anns)

    for c in cats:
        if c.get("id") in r.categories:
            r.issues.append(CocoIssue("error", "DUP_CATEGORY_ID", f"category id {c.get('id')} ganda"))
        r.categories[c.get("id")] = str(c.get("name"))
    if not cats:
        r.issues.append(CocoIssue("error", "NO_CATEGORIES", "COCO tanpa `categories`; category_id tidak bisa dipetakan."))

    by_id: dict[int, dict] = {}
    names = Counter()
    for im in images:
        iid = im.get("id")
        if iid in by_id:
            r.issues.append(CocoIssue("error", "DUP_IMAGE_ID", f"image id {iid} ganda", iid))
        by_id[iid] = im
        names[im.get("file_name")] += 1
        if not (_finite(im.get("width")) and _finite(im.get("height")) and im["width"] > 0 and im["height"] > 0):
            r.issues.append(CocoIssue("error", "BAD_IMAGE_SIZE", f"{im.get('file_name')}: width/height tidak valid", iid))
    for n, k in names.items():
        if k > 1:
            r.issues.append(CocoIssue("error", "DUP_FILE_NAME", f"file_name {n} dipakai {k} image id"))

    per_cat = Counter()
    seen_boxes: dict[tuple, int] = {}
    with_ann: set = set()
    for a in anns:
        aid, iid, cid = a.get("id"), a.get("image_id"), a.get("category_id")
        im = by_id.get(iid)
        if im is None:
            r.issues.append(CocoIssue("error", "ORPHAN_ANNOTATION", f"annotation {aid}: image_id {iid} tidak ada", iid, aid))
            continue
        with_ann.add(iid)
        if cid not in r.categories:
            r.issues.append(CocoIssue("error", "UNKNOWN_CATEGORY", f"annotation {aid}: category_id {cid} tidak ada di categories", iid, aid))
        else:
            per_cat[r.categories[cid]] += 1
        b = a.get("bbox")
        if not (isinstance(b, list) and len(b) == 4 and all(_finite(v) for v in b)):
            r.issues.append(CocoIssue("error", "BAD_BBOX", f"annotation {aid}: bbox bukan 4 angka finite", iid, aid))
            continue
        x, y, w, h = b
        if w <= 0 or h <= 0:
            r.issues.append(CocoIssue("error", "EMPTY_BBOX", f"annotation {aid}: lebar/tinggi ≤ 0", iid, aid))
            continue
        W, H = im.get("width") or 0, im.get("height") or 0
        if x < -tolerance_px or y < -tolerance_px or x + w > W + tolerance_px or y + h > H + tolerance_px:
            r.issues.append(CocoIssue("warning", "BBOX_OUT_OF_IMAGE",
                                      f"annotation {aid}: [{x:.1f},{y:.1f},{w:.1f},{h:.1f}] keluar dari {W}×{H} (akan di-clip)", iid, aid))
        if W and H and 0 < w <= 1.0 and 0 < h <= 1.0 and W > 2 and H > 2:
            r.issues.append(CocoIssue("warning", "MAYBE_NORMALIZED",
                                      f"annotation {aid}: bbox ≤ 1 px — mungkin sudah ternormalisasi, bukan piksel", iid, aid))
        key = (iid, cid, round(x, 1), round(y, 1), round(w, 1), round(h, 1))
        if key in seen_boxes:
            r.issues.append(CocoIssue("warning", "DUP_BBOX", f"annotation {aid} identik dengan {seen_boxes[key]}", iid, aid))
        else:
            seen_boxes[key] = aid
        if a.get("iscrowd"):
            r.issues.append(CocoIssue("warning", "ISCROWD", f"annotation {aid}: iscrowd=1 (bukan satu tanaman)", iid, aid))
    r.per_category = dict(per_cat)
    r.unannotated_images = sorted(str(by_id[i].get("file_name")) for i in by_id if i not in with_ann)
    return r


def resolve_class_map(coco: dict, class_map: dict[str, str]) -> dict[int, str]:
    """`class_map` kunci = nama kategori ATAU id (string), nilai = plant|check|gap|drop.
    Setiap kategori yang dipakai anotasi WAJIB dipetakan; tidak ada default diam-diam."""
    cats = {c["id"]: str(c["name"]) for c in coco.get("categories") or []}
    out: dict[int, str] = {}
    for cid, name in cats.items():
        target = class_map.get(name, class_map.get(str(cid)))
        if target is None:
            continue
        if target not in TARGET_LABELS + (DROP,):
            raise ValueError(f"class_map[{name!r}] = {target!r}; harus salah satu {TARGET_LABELS + (DROP,)}")
        out[cid] = target
    used = {a.get("category_id") for a in coco.get("annotations") or []}
    missing = sorted(f"{cid}:{cats.get(cid)}" for cid in used if cid not in out)
    if missing:
        raise ValueError(f"Kategori dipakai tetapi tidak dipetakan di class_map: {missing}. "
                         f"Petakan eksplisit ke {TARGET_LABELS} atau '{DROP}'.")
    unknown = [k for k in class_map if k not in cats.values() and k not in {str(c) for c in cats}]
    if unknown:
        raise ValueError(f"class_map menyebut kategori yang tidak ada: {unknown}")
    return out


def coco_to_normalized(bbox_px: list[float], width: float, height: float) -> tuple[list[float], bool]:
    """COCO piksel [x,y,w,h] → [left, top, width, height] 0–1, di-clip ke gambar. Return (bbox, clipped)."""
    x, y, w, h = bbox_px
    l, t = max(0.0, x), max(0.0, y)
    r, b = min(float(width), x + w), min(float(height), y + h)
    clipped = (l, t, r, b) != (x, y, x + w, y + h)
    if r <= l or b <= t:
        return [0.0, 0.0, 0.0, 0.0], True
    return [l / width, t / height, (r - l) / width, (b - t) / height], clipped


def normalized_to_yolo(bbox: list[float], cls: int) -> str:
    l, t, w, h = bbox
    return f"{cls} {l + w / 2:.6f} {t + h / 2:.6f} {w:.6f} {h:.6f}"


def yolo_to_normalized(line: str) -> tuple[int, list[float]]:
    parts = line.split()
    if len(parts) != 5:
        raise ValueError(f"Baris YOLO harus 5 kolom: {line!r}")
    cls = int(parts[0])
    cx, cy, w, h = (float(v) for v in parts[1:])
    return cls, [cx - w / 2, cy - h / 2, w, h]


@dataclass
class ConvertedImage:
    file_name: str
    width: int
    height: int
    boxes: list[tuple[str, list[float]]]   # (label WALLACEA, bbox ternormalisasi)
    clipped: int = 0
    dropped: int = 0


def convert(coco: dict, class_map: dict[str, str], empty_images_are_negative: bool = False,
            min_size_px: float = 2.0) -> tuple[list[ConvertedImage], dict]:
    """COCO → daftar gambar dengan bbox ternormalisasi berlabel WALLACEA.

    Gambar tanpa anotasi dikeluarkan kecuali `empty_images_are_negative`. Gambar yang SEMUA anotasinya
    di-`drop` juga dikeluarkan (berisi objek, tetapi bukan kelas target — bukan contoh negatif).
    """
    cmap = resolve_class_map(coco, class_map)
    anns = defaultdict(list)
    for a in coco.get("annotations") or []:
        anns[a["image_id"]].append(a)
    out: list[ConvertedImage] = []
    stats = Counter()
    for im in coco.get("images") or []:
        W, H = im["width"], im["height"]
        ci = ConvertedImage(im["file_name"], W, H, [])
        raw = anns.get(im["id"], [])
        for a in raw:
            target = cmap[a["category_id"]]
            if target == DROP:
                ci.dropped += 1
                continue
            bb, clipped = coco_to_normalized(a["bbox"], W, H)
            if bb[2] * W < min_size_px or bb[3] * H < min_size_px:
                stats["too_small_after_clip"] += 1
                continue
            ci.clipped += int(clipped)
            ci.boxes.append((target, bb))
        if not raw:
            if not empty_images_are_negative:
                stats["excluded_unannotated"] += 1
                continue
            stats["negative_images"] += 1
        elif not ci.boxes:
            stats["excluded_only_dropped" if ci.dropped == len(raw) else "excluded_no_valid_boxes"] += 1
            continue
        stats["images"] += 1
        stats["boxes"] += len(ci.boxes)
        stats["clipped"] += ci.clipped
        stats["dropped"] += ci.dropped
        out.append(ci)
    return out, dict(stats)
