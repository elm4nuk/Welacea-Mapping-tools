"""Latih detektor YOLO tanaman dari dataset MILIK PENGGUNA → best.pt untuk WALLACEA API.

    .venv\\Scripts\\python ml\\train.py --data "D:\\dataset-jagung\\dataset.yaml" --base-weights "D:\\bobot\\yolo11n.pt"
    .venv\\Scripts\\python ml\\train.py --data ... --check-only      # hanya periksa dataset, tanpa Ultralytics

Tidak ada unduhan diam-diam: `--base-weights` wajib berkas lokal yang sudah ada (atau arsitektur .yaml untuk melatih
dari nol). AMP dimatikan secara default karena pemeriksaan AMP Ultralytics mengunduh bobot kecil; `--amp` menyalakannya
secara sadar. Plot dimatikan secara default karena Ultralytics dapat mengunduh font untuk plot; `--plots` menyalakannya.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR))

from yolo_dataset import check_dataset, format_report, write_resolved_yaml  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Latih YOLO detection untuk WALLACEA (dataset milik pengguna).")
    ap.add_argument("--data", required=True, type=Path, help="dataset.yaml (lihat dataset.yaml.example)")
    ap.add_argument("--base-weights", type=Path, help="Bobot awal LOKAL, mis. yolo11n.pt (tidak diunduh otomatis)")
    ap.add_argument("--name", default="tanaman-v1", help="Nama run & model (dipakai sebagai model_id)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=1280, help="Sama dengan WALLACEA_IMGSZ API (default 1280)")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default=None, help="cpu | 0 (GPU pertama). Default: pilihan Ultralytics")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--patience", type=int, default=50)
    ap.add_argument("--project", type=Path, default=ML_DIR / "runs", help="Folder hasil run (tidak masuk Git)")
    ap.add_argument("--out", type=Path, default=ML_DIR.parent / "models", help="Tujuan salinan best.pt + model card")
    ap.add_argument("--amp", action="store_true", help="Nyalakan AMP (GPU). Pemeriksaan AMP dapat mengunduh bobot kecil.")
    ap.add_argument("--plots", action="store_true", help="Simpan plot training (dapat mengunduh font sekali).")
    ap.add_argument("--check-only", action="store_true", help="Hanya periksa dataset; tidak melatih")
    args = ap.parse_args(argv)

    data = args.data.expanduser().resolve()
    rep = check_dataset(data)
    print(format_report(rep))
    if not rep.ok:
        print("\nTraining TIDAK dijalankan: perbaiki dataset dulu.", file=sys.stderr)
        return 2
    if args.check_only:
        print("\nDataset lulus pemeriksaan (--check-only). Training tidak dijalankan.")
        return 0

    if not args.base_weights:
        print("[GAGAL] --base-weights wajib: path bobot awal lokal (mis. yolo11n.pt dari rilis resmi Ultralytics, "
              "diunduh sendiri secara sadar) atau arsitektur yolo11n.yaml untuk melatih dari nol.", file=sys.stderr)
        return 2
    base = args.base_weights.expanduser().resolve()
    if base.suffix.lower() == ".pt" and not base.is_file():
        print(f"[GAGAL] Bobot awal tidak ditemukan: {base}. Skrip ini tidak mengunduh bobot.", file=sys.stderr)
        return 2
    if base.suffix.lower() not in (".pt", ".yaml", ".yml"):
        print("[GAGAL] --base-weights harus .pt (fine-tune) atau .yaml (dari nol).", file=sys.stderr)
        return 2
    try:
        from ultralytics import YOLO  # AGPL-3.0/Enterprise — lihat docs/architecture/REPO_SELECTION.md
    except ImportError:
        print("[GAGAL] Paket ultralytics belum terpasang. Pasang sendiri: "
              ".venv\\Scripts\\python -m pip install -r requirements-ai.txt", file=sys.stderr)
        return 1

    os.environ.setdefault("YOLO_OFFLINE", "1")    # Ultralytics: jangan cek/unduh aset online bila didukung versi ini
    resolved = write_resolved_yaml(data, args.project.resolve() / f"{args.name}-data")
    model = YOLO(str(base), task="detect")
    model.train(data=str(resolved), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, device=args.device,
                workers=args.workers, seed=args.seed, deterministic=True, patience=args.patience,
                project=str(args.project.resolve()), name=args.name, exist_ok=False, amp=args.amp, plots=args.plots)
    run_dir = Path(model.trainer.save_dir)
    best = run_dir / "weights" / "best.pt"
    if not best.is_file():
        print(f"[GAGAL] best.pt tidak ditemukan di {best}", file=sys.stderr)
        return 1

    # Evaluasi pada split test bila ada (selain itu val). Angka ini hanya berlaku untuk split tersebut.
    split = "test" if "test" in rep.splits else "val"
    metrics = YOLO(str(best), task="detect").val(data=str(resolved), split=split, imgsz=args.imgsz, plots=False,
                                                 verbose=False)
    box = metrics.box
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{args.name}.pt"
    shutil.copyfile(best, final)
    card = {
        "model_id": args.name,
        "weights_file": final.name,
        "weights_sha256": sha256_file(final),
        "api_model_version": "sha256:" + sha256_file(final)[:16],
        "task": "detect",
        "names": rep.names,
        "suggested_label_map": {n: "plant" for n in rep.names},
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_weights": base.name,
        "dataset_yaml": str(data),
        "dataset_counts": {s: vars(st) for s, st in rep.splits.items()},
        "train_args": {"epochs": args.epochs, "imgsz": args.imgsz, "batch": args.batch, "seed": args.seed},
        "evaluation": {"split": split, "precision": float(box.mp), "recall": float(box.mr),
                       "map50": float(box.map50), "map50_95": float(box.map)},
        "caveat": "Metrik hanya berlaku untuk split di atas. Belum berarti akurat untuk lahan, kamera, atau "
                  "ketinggian terbang lain. Kandidat tetap harus ditinjau manusia di aplikasi.",
        "run_dir": str(run_dir),
    }
    (out_dir / f"{args.name}.model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n",
                                                          encoding="utf-8")
    print(f"\nSelesai. best.pt disalin ke: {final}")
    print(f"Evaluasi split {split}: P={box.mp:.3f} R={box.mr:.3f} mAP50={box.map50:.3f} mAP50-95={box.map:.3f}")
    print("Langkah berikut (dari folder apps\\api):")
    lm = ",".join(f"{n}=plant" for n in rep.names)
    print(f"  powershell -ExecutionPolicy Bypass -File .\\scripts\\check-model.ps1 -ModelPath '{final}' -LabelMap '{lm}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
