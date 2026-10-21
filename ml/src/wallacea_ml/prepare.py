"""Siapkan dataset deteksi dari anotasi COCO → layout YOLO + manifest WALLACEA.

Keluaran `<out>/`:
  images/<field>/<flight>/<nama>.<png|jpg>   piksel TERORIENTASI EXIF (lewat app.imaging, sama dengan API)
  labels/<field>/<flight>/<nama>.txt          label YOLO (layout yang dibaca Ultralytics: images/ → labels/)
  manifest.json                               input `split`/`train`/`evaluate`
  prepare_report.json                         validasi COCO, pemetaan kelas, statistik konversi, gambar dilewati

Pemeriksaan orientasi: dimensi COCO harus sama dengan dimensi gambar SETELAH orientasi EXIF. Bila sama dengan
dimensi mentah sementara EXIF memutar 90° (orientasi 5–8), anotasi dibuat pada piksel mentah → gambar dilewati
(`ORIENTATION_MISMATCH`), tidak diputar diam-diam.
"""
from __future__ import annotations

import fnmatch
import glob
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import yaml

from . import backend
from .coco import convert, load_coco, normalized_to_yolo, validate_coco

ML_ROOT = Path(__file__).resolve().parents[2]
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(s: str) -> str:
    return _SAFE.sub("_", s).strip("_") or "x"


def load_config(path: str | Path) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cmap = cfg["class_map"]
    if isinstance(cmap, str):
        cfg["class_map"] = yaml.safe_load((ML_ROOT / "configs" / cmap).read_text(encoding="utf-8"))
    for key in ("name", "crop_type", "label_map", "class_map", "sources"):
        if not cfg.get(key):
            raise ValueError(f"Konfigurasi prepare wajib punya `{key}`.")
    return cfg


def _group_ids(src: dict, ann_path: Path, file_name: str) -> tuple[str, str]:
    subject = {"ann_stem": ann_path.stem, "file_name": file_name}[src.get("match_on", "file_name")]
    if "groups" in src:
        for g in src["groups"]:
            if fnmatch.fnmatch(subject, g["pattern"]):
                return g.get("field_id", src.get("field_id")), g["flight_id"]
        raise ValueError(f"{subject!r} tidak cocok dengan pola `groups` mana pun.")
    vars_ = {}
    if src.get("match"):
        m = re.match(src["match"], subject)
        if not m:
            raise ValueError(f"{subject!r} tidak cocok dengan regex `match` {src['match']!r}.")
        vars_ = m.groupdict()
    vars_.update(src.get("_vars", {}))
    return src["field_id"].format(**vars_), src["flight_id"].format(**vars_)


def _expand_sources(cfg: dict) -> list[tuple[dict, Path, str | None]]:
    """(source, path anotasi, split resmi atau None)."""
    out = []
    for src in cfg["sources"]:
        if "splits" in src:
            for raw, ours in src["splits"].items():
                pattern = src["annotations"].format(split=raw)
                s = {**src, "_vars": {"split": ours, "split_raw": raw}}
                out += [(s, Path(p), ours) for p in sorted(glob.glob(str(ML_ROOT / pattern)))]
        else:
            out += [(src, Path(p), None) for p in sorted(glob.glob(str(ML_ROOT / src["annotations"])))]
    return out


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare(cfg: dict, out: Path, max_images: int | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    label_idx = cfg["label_map"]
    entries, skipped, coco_summaries = [], [], {}
    stats = Counter()
    for src, ann_path, split in _expand_sources(cfg):
        coco = load_coco(ann_path)
        rep = validate_coco(coco)
        key = ann_path.relative_to(ML_ROOT) if ann_path.is_relative_to(ML_ROOT) else ann_path
        coco_summaries[str(key)] = rep.summary()
        bad_images = {i.image_id for i in rep.errors if i.image_id is not None}
        if any(i.image_id is None for i in rep.errors):
            skipped.append({"annotations": ann_path.name, "reason": "COCO_ERRORS",
                            "details": [i.message for i in rep.errors][:10]})
            continue
        converted, conv_stats = convert(coco, cfg["class_map"], cfg.get("empty_images_are_negative", False),
                                        cfg.get("min_size_px", 2.0))
        stats.update(conv_stats)
        by_name = {im["file_name"]: im["id"] for im in coco["images"]}
        vars_ = {"ann_dir": str(ann_path.parent), "ann_stem": ann_path.stem, **src.get("_vars", {})}
        img_dir = Path(src["images_dir"].format(**vars_))
        img_dir = img_dir if img_dir.is_absolute() else ML_ROOT / img_dir
        for ci in converted:
            if max_images and len(entries) >= max_images:
                break
            if by_name[ci.file_name] in bad_images:
                skipped.append({"image": ci.file_name, "reason": "COCO_IMAGE_ERRORS"})
                continue
            path = img_dir / ci.file_name
            if not path.is_file():
                skipped.append({"image": ci.file_name, "reason": "MISSING_IMAGE", "expected": str(path)})
                continue
            raw_w, raw_h = backend.raw_size(path)
            orient = backend.exif_orientation(path)
            oriented = backend.load_oriented(path)
            if (oriented.width, oriented.height) != (ci.width, ci.height):
                reason = ("ORIENTATION_MISMATCH" if (raw_w, raw_h) == (ci.width, ci.height) and orient >= 5
                          else "DIMENSION_MISMATCH")
                skipped.append({"image": ci.file_name, "reason": reason, "coco": [ci.width, ci.height],
                                "raw": [raw_w, raw_h], "oriented": list(oriented.size), "exif_orientation": orient})
                continue
            field_id, flight_id = _group_ids(src, ann_path, ci.file_name)
            stem = _safe(Path(ci.file_name).stem)
            rel_dir = Path(_safe(field_id)) / _safe(flight_id)
            ext = path.suffix.lower()
            if orient == 1 and ext in (".jpg", ".jpeg", ".png"):
                rel_img = Path("images") / rel_dir / f"{stem}{ext}"
                (out / rel_img).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, out / rel_img)          # byte asli: tanpa kompresi ulang
            else:
                rel_img = Path("images") / rel_dir / f"{stem}.png"
                (out / rel_img).parent.mkdir(parents=True, exist_ok=True)
                oriented.save(out / rel_img, format="PNG")      # piksel terorientasi, lossless
                stats["reencoded_png"] += 1
            rel_lbl = Path("labels") / rel_dir / f"{stem}.txt"
            (out / rel_lbl).parent.mkdir(parents=True, exist_ok=True)
            (out / rel_lbl).write_text("".join(normalized_to_yolo(bb, label_idx[lab]) + "\n" for lab, bb in ci.boxes),
                                       encoding="utf-8")
            entries.append({"image": rel_img.as_posix(), "sha256": _sha256(out / rel_img), "field_id": field_id,
                            "flight_id": flight_id, "width": oriented.width, "height": oriented.height,
                            "labels": rel_lbl.as_posix(), "official_split": split,
                            "source": f"{ann_path.name}::{ci.file_name}"})
    manifest = {"crop_type": cfg["crop_type"], "domain": cfg.get("domain", ""), "label_map": label_idx,
                "notes": f"Dibuat oleh wallacea_ml.prepare dari konfigurasi {cfg['name']}.", "images": entries}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    report = {"name": cfg["name"], "class_map": cfg["class_map"], "label_map": label_idx,
              "empty_images_are_negative": cfg.get("empty_images_are_negative", False),
              "images_written": len(entries), "boxes_written": sum(1 for e in entries for _ in
                                                                    (out / e["labels"]).read_text().splitlines()),
              "conversion": dict(stats), "skipped": skipped,
              "skipped_by_reason": dict(Counter(s["reason"] for s in skipped)), "coco_validation": coco_summaries}
    (out / "prepare_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str),
                                             encoding="utf-8")
    return report
