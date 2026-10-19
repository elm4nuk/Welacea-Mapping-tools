"""CLI: python -m wallacea_ml <validate|split|evaluate|train> ...   (jalankan dari apps/api/ml)

Tidak ada perintah yang mengunduh model/dataset. `train` menolak berjalan tanpa manifest valid,
split tanpa kebocoran, label, dan bobot awal LOKAL yang disebut eksplisit.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluate import evaluate, report_dict
from .manifest import load_manifest
from .split import SPLITS, check_leakage, group_split, yolo_dataset_yaml

MIN_LABELED_IMAGES = 50


def cmd_validate(a) -> int:
    m = load_manifest(a.manifest)
    for e in m.errors:
        print("ERROR:", e)
    print(f"{len(m.images)} gambar, {len(m.labeled)} berlabel, tanaman: {m.crop_type or '-'}")
    return 1 if m.errors else 0


def cmd_split(a) -> int:
    m = load_manifest(a.manifest)
    if m.errors:
        print("Manifest tidak valid; jalankan validate.", file=sys.stderr)
        return 1
    r = group_split(m, a.group_by, seed=a.seed)
    out = Path(a.out)
    (out / "splits").mkdir(parents=True, exist_ok=True)
    for s in SPLITS:
        imgs = sorted(i for i, sp in r.assignments.items() if sp == s)
        (out / "splits" / f"{s}.txt").write_text("\n".join(imgs) + "\n", encoding="utf-8")
    (out / "split_report.json").write_text(json.dumps(
        {"group_by": r.group_by, "groups": r.groups, "leaks": r.leaks,
         "is_product_validation": r.is_product_validation}, indent=2), encoding="utf-8")
    (out / "dataset.yaml").write_text(yolo_dataset_yaml(m, str(Path(a.root).resolve())), encoding="utf-8")
    print(json.dumps({"groups": {k: len(v) for k, v in r.groups.items()}, "leaks": r.leaks}, indent=2))
    return 1 if r.leaks else 0


def cmd_evaluate(a) -> int:
    data = json.loads(Path(a.predictions).read_text(encoding="utf-8"))
    leaks = None
    if a.manifest and a.split_dir:
        m = load_manifest(a.manifest)
        assignments = {}
        for s in SPLITS:
            p = Path(a.split_dir) / "splits" / f"{s}.txt"
            if p.is_file():
                assignments.update({ln.strip(): s for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()})
        rep = Path(a.split_dir) / "split_report.json"
        group_by = json.loads(rep.read_text(encoding="utf-8")).get("group_by", "field") if rep.is_file() else "field"
        leaks = check_leakage(m, assignments, group_by)
        wrong = [i["image"] for i in data.get("images", []) if assignments.get(i["image"]) != data.get("split")]
        if wrong:
            leaks.append(f"{len(wrong)} gambar evaluasi tidak berada di split '{data.get('split')}'")
    report = report_dict(evaluate(data, a.label, leaks))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_train(a) -> int:
    m = load_manifest(a.manifest)
    problems = list(m.errors)
    if len(m.labeled) < MIN_LABELED_IMAGES:
        problems.append(f"Baru {len(m.labeled)} gambar berlabel; minimal {MIN_LABELED_IMAGES} sebelum pelatihan.")
    report = Path(a.split_dir) / "split_report.json"
    if not report.is_file():
        problems.append("split_report.json tidak ada; jalankan `split` dahulu.")
    elif json.loads(report.read_text(encoding="utf-8")).get("leaks"):
        problems.append("Split bocor; perbaiki sebelum pelatihan.")
    weights = Path(a.weights)
    if not weights.is_file():
        problems.append(f"Bobot awal lokal tidak ditemukan: {weights} (tidak ada unduhan otomatis).")
    if problems:
        for p in problems:
            print("TIDAK DIJALANKAN:", p, file=sys.stderr)
        return 2
    if a.dry_run:
        print("Pemeriksaan lulus (dry-run). Pelatihan tidak dijalankan.")
        return 0
    from ultralytics import YOLO  # AGPL-3.0/Enterprise — lihat REPO_SELECTION.md

    model = YOLO(str(weights), task="detect")
    model.train(data=str(Path(a.split_dir) / "dataset.yaml"), epochs=a.epochs, imgsz=a.imgsz,
                project=str(Path(a.split_dir) / "runs"), name=a.name, exist_ok=False)
    print("Pelatihan selesai. Evaluasi pada split test dengan `evaluate` sebelum melaporkan metrik.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wallacea_ml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("manifest"); v.set_defaults(fn=cmd_validate)
    s = sub.add_parser("split"); s.add_argument("manifest"); s.add_argument("--root", required=True)
    s.add_argument("--out", required=True); s.add_argument("--group-by", choices=["field", "flight"], default="field")
    s.add_argument("--seed", default="wallacea"); s.set_defaults(fn=cmd_split)
    e = sub.add_parser("evaluate"); e.add_argument("predictions"); e.add_argument("--label", default="plant")
    e.add_argument("--manifest"); e.add_argument("--split-dir"); e.add_argument("--out"); e.set_defaults(fn=cmd_evaluate)
    t = sub.add_parser("train"); t.add_argument("manifest"); t.add_argument("--split-dir", required=True)
    t.add_argument("--weights", required=True, help="Bobot awal LOKAL (.pt)"); t.add_argument("--epochs", type=int, default=100)
    t.add_argument("--imgsz", type=int, default=1280); t.add_argument("--name", default="exp")
    t.add_argument("--dry-run", action="store_true"); t.set_defaults(fn=cmd_train)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
