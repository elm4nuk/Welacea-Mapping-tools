"""Inspeksi dataset untuk notebook 01/02/04: ukuran & orientasi gambar, distribusi kelas & ukuran objek,
label hilang/tidak valid, berkas duplikat (byte identik & hampir identik), dan perbandingan domain
(dataset publik vs foto K919).

Semua koordinat label dibaca sebagai YOLO ternormalisasi terhadap gambar TERORIENTASI.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from . import backend
from .coco import yolo_to_normalized
from .manifest import Manifest

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


@dataclass
class LabelIssue:
    image: str
    code: str      # MISSING_LABEL_FILE | EMPTY_LABEL_FILE | BAD_LINE | UNKNOWN_CLASS | OUT_OF_RANGE | NON_POSITIVE_SIZE | DUP_BOX
    detail: str = ""


@dataclass
class DatasetStats:
    images: list[dict] = field(default_factory=list)        # satu baris per gambar
    boxes: list[dict] = field(default_factory=list)         # satu baris per box (px & relatif)
    issues: list[LabelIssue] = field(default_factory=list)
    class_counts: Counter = field(default_factory=Counter)

    def summary(self) -> dict:
        n = len(self.images)
        per_img = [r["boxes"] for r in self.images]
        w_px = [b["w_px"] for b in self.boxes]
        return {
            "images": n,
            "boxes": len(self.boxes),
            "classes": dict(self.class_counts),
            "boxes_per_image": _describe(per_img),
            "box_width_px": _describe(w_px),
            "box_rel_area": _describe([b["w"] * b["h"] for b in self.boxes]),
            "image_sizes": dict(Counter(f"{r['width']}x{r['height']}" for r in self.images).most_common(8)),
            "orientation": dict(Counter("landscape" if r["width"] >= r["height"] else "portrait" for r in self.images)),
            "issues": dict(Counter(i.code for i in self.issues)),
        }


def _describe(values: list[float]) -> dict | None:
    if not values:
        return None
    a = np.asarray(values, dtype=float)
    return {"n": int(a.size), "min": float(a.min()), "p05": float(np.percentile(a, 5)), "median": float(np.median(a)),
            "p95": float(np.percentile(a, 95)), "max": float(a.max()), "mean": float(a.mean())}


def read_yolo_labels(path: Path, n_classes: int) -> tuple[list[tuple[int, list[float]]], list[str]]:
    """Return (boxes, masalah). Box ternormalisasi [left, top, w, h]."""
    boxes, problems = [], []
    for k, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cls, bb = yolo_to_normalized(line)
        except ValueError as exc:
            problems.append(f"BAD_LINE:{k}:{exc}")
            continue
        if not 0 <= cls < n_classes:
            problems.append(f"UNKNOWN_CLASS:{k}:{cls}")
        if not all(math.isfinite(v) for v in bb) or bb[2] <= 0 or bb[3] <= 0:
            problems.append(f"NON_POSITIVE_SIZE:{k}")
            continue
        l, t, w, h = bb
        if l < -1e-4 or t < -1e-4 or l + w > 1 + 1e-4 or t + h > 1 + 1e-4:
            problems.append(f"OUT_OF_RANGE:{k}:{[round(v, 4) for v in bb]}")
        boxes.append((cls, bb))
    return boxes, problems


def inspect_manifest(manifest: Manifest, root: str | Path, open_images: bool = True) -> DatasetStats:
    root = Path(root)
    names = {i: lab for lab, i in manifest.label_map.items()}
    st = DatasetStats()
    for e in manifest.images:
        row = {"image": e.image, "field_id": e.field_id, "flight_id": e.flight_id, "width": e.width,
               "height": e.height, "boxes": 0, "split": e.official_split}
        if open_images and (root / e.image).is_file():
            img = backend.load_oriented(root / e.image)
            row["exif_orientation"] = backend.exif_orientation(root / e.image)
            if img.size != (e.width, e.height):
                st.issues.append(LabelIssue(e.image, "SIZE_MISMATCH", f"manifest {e.width}x{e.height} ≠ {img.size}"))
        if not e.labels:
            st.issues.append(LabelIssue(e.image, "UNLABELED", "labels=null (belum dilabeli; BUKAN contoh negatif)"))
            st.images.append(row)
            continue
        lp = root / e.labels
        if not lp.is_file():
            st.issues.append(LabelIssue(e.image, "MISSING_LABEL_FILE", str(lp)))
            st.images.append(row)
            continue
        boxes, problems = read_yolo_labels(lp, len(manifest.label_map))
        for p in problems:
            code, _, detail = p.partition(":")
            st.issues.append(LabelIssue(e.image, code, detail))
        if not boxes:
            st.issues.append(LabelIssue(e.image, "EMPTY_LABEL_FILE", "berkas label kosong = negatif eksplisit; pastikan disengaja"))
        seen = set()
        for cls, (l, t, w, h) in boxes:
            key = (cls, round(l, 4), round(t, 4), round(w, 4), round(h, 4))
            if key in seen:
                st.issues.append(LabelIssue(e.image, "DUP_BOX", str(key)))
            seen.add(key)
            st.class_counts[names.get(cls, f"?{cls}")] += 1
            st.boxes.append({"image": e.image, "cls": cls, "l": l, "t": t, "w": w, "h": h,
                             "w_px": w * e.width, "h_px": h * e.height})
        row["boxes"] = len(boxes)
        st.images.append(row)
    return st


def dhash(img: Image.Image, size: int = 8) -> int:
    g = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def find_duplicates(manifest: Manifest, root: str | Path, near_threshold: int = 4) -> dict:
    """Byte identik (sha256) dan hampir identik (dHash, jarak Hamming ≤ threshold) — mis. ekspor ulang,
    foto yang sama dengan kompresi berbeda. Hampir-identik lintas grup = calon kebocoran."""
    root = Path(root)
    by_sha = defaultdict(list)
    for e in manifest.images:
        by_sha[e.sha256].append(e.image)
    exact = [v for v in by_sha.values() if len(v) > 1]
    hashes = []
    for e in manifest.images:
        p = root / e.image
        if p.is_file():
            hashes.append((e.image, e.field_id, dhash(backend.load_oriented(p))))
    near = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            d = bin(hashes[i][2] ^ hashes[j][2]).count("1")
            if d <= near_threshold:
                near.append({"a": hashes[i][0], "b": hashes[j][0], "hamming": d,
                             "cross_group": hashes[i][1] != hashes[j][1]})
    return {"exact": exact, "near": near}


def photo_folder_stats(folder: str | Path) -> list[dict]:
    """Statistik foto tanpa label (mis. folder foto K919 mentah): dimensi mentah & terorientasi, orientasi EXIF,
    kecerahan, dan ketajaman relatif (varians Laplacian sederhana). Tidak mengubah berkas."""
    rows = []
    for p in sorted(Path(folder).rglob("*")):
        if p.suffix.lower() not in IMAGE_EXT:
            continue
        with Image.open(p) as im:
            exif = im.getexif()
            make, model = exif.get(0x010F), exif.get(0x0110)
            raw = im.size
        img = backend.load_oriented(p)
        small = img.copy()
        small.thumbnail((1024, 1024))
        g = np.asarray(small.convert("L"), dtype=np.float32)
        lap = g[1:-1, 1:-1] * -4 + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
        rows.append({"image": str(p.relative_to(folder)), "raw_size": f"{raw[0]}x{raw[1]}",
                     "width": img.width, "height": img.height, "exif_orientation": backend.exif_orientation(p),
                     "camera": f"{make or ''} {model or ''}".strip() or None, "bytes": p.stat().st_size,
                     "brightness": float(g.mean()), "sharpness_lapvar_1024": float(lap.var())})
    return rows


def compare_domains(summaries: dict[str, dict]) -> list[dict]:
    """Tabel ringkas antar domain (mis. {'public:uavmulticrop': summary, 'k919': summary})."""
    rows = []
    for name, s in summaries.items():
        bw = s.get("box_width_px") or {}
        bpi = s.get("boxes_per_image") or {}
        rows.append({"domain": name, "images": s.get("images"), "boxes": s.get("boxes"),
                     "image_sizes": s.get("image_sizes"), "box_w_px_median": bw.get("median"),
                     "boxes_per_image_median": bpi.get("median")})
    return rows
