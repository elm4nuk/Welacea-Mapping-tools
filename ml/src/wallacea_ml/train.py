"""Training detektor YOLO (Ultralytics) + model card.

Pemeriksaan sebelum training (menolak berjalan bila gagal): manifest valid, ≥ MIN_LABELED_IMAGES berlabel,
split_report tanpa kebocoran, bobot awal LOKAL ada. Tidak ada unduhan otomatis.

Keluaran `artifacts/models/<name>/`:
  <name>.pt          salinan best.pt (bobot dipilih Ultralytics berdasarkan metrik split VAL)
  model_card.json    dataset, kelas, preprocessing, konfigurasi, seed, versi lingkungan, metrik, env API
Run lengkap Ultralytics: `artifacts/runs/<name>/`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from .manifest import load_manifest

ML_ROOT = Path(__file__).resolve().parents[2]
MIN_LABELED_IMAGES = 50
PREPROCESSING = ("Gambar dibaca dengan orientasi EXIF diterapkan (app.imaging.oriented_from_bytes → RGB), sama dengan "
                 "API/editor. Training & inferensi memakai FOTO PENUH di-letterbox ke imgsz (tanpa tiling). "
                 "Label YOLO ternormalisasi terhadap gambar terorientasi.")


def load_train_config(path: str | Path, **overrides) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    return cfg


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def api_model_version(path: Path) -> str:
    """Sama dengan `weights_fingerprint` di adapter API (model_version pada AnalysisRun)."""
    return "sha256:" + sha256_file(path)[:16]


def preflight(manifest_path: str | Path, split_dir: str | Path, weights: str | Path) -> list[str]:
    m = load_manifest(manifest_path)
    problems = list(m.errors)
    if len(m.labeled) < MIN_LABELED_IMAGES:
        problems.append(f"Baru {len(m.labeled)} gambar berlabel; minimal {MIN_LABELED_IMAGES} sebelum pelatihan.")
    report = Path(split_dir) / "split_report.json"
    if not report.is_file():
        problems.append("split_report.json tidak ada; jalankan `split` dahulu.")
    elif json.loads(report.read_text(encoding="utf-8")).get("leaks"):
        problems.append("Split bocor; perbaiki sebelum pelatihan.")
    if not Path(weights).is_file():
        problems.append(f"Bobot awal lokal tidak ditemukan: {weights} (tidak ada unduhan otomatis).")
    return problems


def _git() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ML_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def _environment() -> dict:
    env = {"python": platform.python_version(), "platform": platform.platform()}
    for mod in ("torch", "ultralytics", "PIL", "numpy"):
        try:
            env[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001
            env[mod] = None
    try:
        import torch
        env["cuda_device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        env["cuda_device"] = None
    return env


def split_counts(manifest_path: Path, split_dir: Path) -> dict:
    m = load_manifest(manifest_path)
    root = manifest_path.parent
    by = {e.image: e for e in m.images}
    out = {}
    for s in ("train", "val", "test"):
        p = split_dir / "splits" / f"{s}.txt"
        imgs = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.is_file() else []
        boxes = sum(sum(1 for ln in (root / by[i].labels).read_text(encoding="utf-8").splitlines() if ln.strip())
                    for i in imgs if by[i].labels and (root / by[i].labels).is_file())
        out[s] = {"images": len(imgs), "boxes": boxes}
    return out


def train(cfg: dict, manifest_path: Path, split_dir: Path, dry_run: bool = False) -> int:
    weights = Path(cfg["weights"])
    weights = weights if weights.is_absolute() else ML_ROOT / weights
    problems = preflight(manifest_path, split_dir, weights)
    if problems:
        for p in problems:
            print("TIDAK DIJALANKAN:", p, file=sys.stderr)
        return 2
    if dry_run:
        print("Pemeriksaan lulus (dry-run). Pelatihan tidak dijalankan.")
        return 0
    from ultralytics import YOLO  # AGPL-3.0/Enterprise — lihat docs/architecture/REPO_SELECTION.md

    name = cfg["name"]
    runs = ML_ROOT / "artifacts" / "runs"
    model = YOLO(str(weights), task="detect")
    results = model.train(
        data=str(split_dir / "dataset.yaml"), epochs=cfg["epochs"], imgsz=cfg["imgsz"], batch=cfg["batch"],
        workers=cfg.get("workers", 2), device=cfg.get("device"), seed=cfg["seed"],
        deterministic=cfg.get("deterministic", True), patience=cfg.get("patience", 50),
        project=str(runs), name=name, exist_ok=False, plots=True, **(cfg.get("augment") or {}),
    )
    run_dir = Path(model.trainer.save_dir)
    best = run_dir / "weights" / "best.pt"
    out_dir = ML_ROOT / "artifacts" / "models" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{name}.pt"
    shutil.copyfile(best, final)
    m = load_manifest(manifest_path)
    split_report = json.loads((split_dir / "split_report.json").read_text(encoding="utf-8"))
    class_names = {i: lab for lab, i in m.label_map.items()}
    card = {
        "model_id": name,
        "model_version": api_model_version(final),
        "weights_file": str(final.relative_to(ML_ROOT)),
        "weights_sha256": sha256_file(final),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git": _git(),
        "task": "detect",
        "classes": class_names,
        "api_env": {"WALLACEA_MODEL_PATH": str(final), "WALLACEA_MODEL_ID": name,
                    "WALLACEA_LABEL_MAP_JSON": json.dumps({lab: lab for lab in m.label_map}),
                    "WALLACEA_IMGSZ": cfg["imgsz"], "WALLACEA_CONFIDENCE": None},
        "dataset": {"manifest": str(manifest_path), "manifest_sha256": sha256_file(manifest_path),
                    "crop_type": m.crop_type, "domain": m.domain, "split_dir": str(split_dir),
                    "split_report": split_report, "counts": split_counts(manifest_path, split_dir)},
        "preprocessing": PREPROCESSING,
        "train_config": cfg,
        "base_weights": {"path": str(weights), "sha256": sha256_file(weights),
                         "license": "Ultralytics AGPL-3.0/Enterprise (bobot pretrained COCO)"},
        "environment": _environment(),
        "ultralytics_metrics_val": {k: float(v) for k, v in (getattr(results, "results_dict", {}) or {}).items()},
        "ultralytics_run_dir": str(run_dir),
        "evaluations": [],
        "threshold_selection": None,
        "limitations": [
            "Metrik Ultralytics di atas dihitung pada split VAL (dipakai memilih best.pt) — bukan evaluasi akhir.",
            "Evaluasi akhir = `evaluate` pada split TEST lewat adapter API (lihat `evaluations`).",
            "Belum diuji pada foto K919 kecuali ada entri evaluations dengan domain 'k919'.",
            "Kandidat model di aplikasi tetap `pending` sampai ditinjau manusia.",
        ],
    }
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Bobot: {final}\nModel card: {out_dir / 'model_card.json'}\n"
          "Lanjut: predict → threshold (val) → evaluate (test) sebelum melaporkan metrik.")
    return 0


def update_card(card_path: Path, **sections) -> dict:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    for k, v in sections.items():
        if k == "evaluation":
            card.setdefault("evaluations", []).append(v)
        else:
            card[k] = v
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return card
