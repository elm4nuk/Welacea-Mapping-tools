"""Evaluasi best.pt pada split dataset BERLABEL (default: test) dan tulis laporan JSON.

    .venv\\Scripts\\python ml\\validate_model.py --model "..\\models\\tanaman-v1.pt" --data "D:\\dataset-jagung\\dataset.yaml"

Precision/recall/mAP hanya berlaku untuk split itu. Angka dari foto yang ikut training (train/val) bukan
ukuran kinerja di lahan baru. Tidak mengunduh apa pun.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR))

import tempfile  # noqa: E402

from yolo_dataset import check_dataset, format_report, write_resolved_yaml  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validasi model YOLO detection pada split berlabel.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--split", default=None, choices=["train", "val", "test"], help="Default: test bila ada, selain itu val")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--conf", type=float, default=0.001, help="Ambang untuk kurva mAP (bukan ambang aplikasi)")
    ap.add_argument("--iou", type=float, default=0.6)
    ap.add_argument("--device", default=None)
    ap.add_argument("--report", type=Path, default=None, help="Berkas JSON hasil (default: <model>.eval.<split>.json)")
    args = ap.parse_args(argv)

    model_path = args.model.expanduser().resolve()
    if not model_path.is_file() or model_path.suffix.lower() != ".pt":
        print(f"[GAGAL] Berkas model .pt tidak ditemukan: {model_path}", file=sys.stderr)
        return 2
    data = args.data.expanduser().resolve()
    rep = check_dataset(data)
    print(format_report(rep))
    if not rep.ok:
        return 2
    split = args.split or ("test" if "test" in rep.splits else "val")
    if split != "test":
        print(f"[PERINGATAN] Mengevaluasi split '{split}'. Split ini dipakai selama training, jadi angkanya cenderung "
              "terlalu optimis. Gunakan split test dari lahan/penerbangan terpisah.")
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[GAGAL] Paket ultralytics belum terpasang (pip install -r requirements-ai.txt).", file=sys.stderr)
        return 1
    os.environ.setdefault("YOLO_OFFLINE", "1")
    model = YOLO(str(model_path), task="detect")
    if getattr(model, "task", "detect") != "detect":
        print(f"[GAGAL] Model task='{model.task}', bukan deteksi.", file=sys.stderr)
        return 1
    model_names = [str(n) for n in (model.names.values() if isinstance(model.names, dict) else model.names)]
    if model_names != rep.names:
        print(f"[PERINGATAN] model.names {model_names} berbeda dengan names dataset {rep.names}. Periksa urutan kelas.")
    resolved = write_resolved_yaml(data, Path(tempfile.mkdtemp(prefix="wallacea-val-")))
    m = model.val(data=str(resolved), split=split, imgsz=args.imgsz, conf=args.conf, iou=args.iou, device=args.device,
                  plots=False, verbose=False)
    box = m.box
    per_class = {}
    for i, cls in enumerate(getattr(box, "ap_class_index", []) or []):
        name = model_names[int(cls)] if int(cls) < len(model_names) else str(cls)
        p, r, ap50, ap = box.class_result(i)
        per_class[name] = {"precision": float(p), "recall": float(r), "map50": float(ap50), "map50_95": float(ap)}
    result = {
        "model": model_path.name, "dataset_yaml": str(data), "split": split,
        "images": rep.splits[split].images, "boxes": rep.splits[split].boxes,
        "precision": float(box.mp), "recall": float(box.mr), "map50": float(box.map50), "map50_95": float(box.map),
        "per_class": per_class, "imgsz": args.imgsz, "iou": args.iou,
        "caveat": "Metrik hanya untuk split ini; bukan jaminan akurasi pada lahan/kamera/ketinggian lain.",
    }
    out = args.report or model_path.with_suffix(f".eval.{split}.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nSplit {split}: {result['images']} gambar, {result['boxes']} kotak berlabel")
    print(f"P={box.mp:.3f}  R={box.mr:.3f}  mAP50={box.map50:.3f}  mAP50-95={box.map:.3f}")
    for name, v in per_class.items():
        print(f"  {name}: P={v['precision']:.3f} R={v['recall']:.3f} mAP50={v['map50']:.3f}")
    print(f"Laporan: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
