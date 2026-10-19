"""Unduh bobot DeepForest dari sumber resmi (Hugging Face `weecology/deepforest-tree`) ke folder LOKAL.

Dijalankan SEKALI secara eksplisit — API tidak pernah mengunduh bobot saat request analisis.

    .venv\\Scripts\\python scripts\\download_deepforest.py
    .venv\\Scripts\\python scripts\\download_deepforest.py --revision <commit> --dest var\\models\\deepforest-tree

Revisi dikunci ke commit Hub yang sudah diuji (bukan `main` yang bisa berubah). Menulis `wallacea_model.json`
(repo, revisi, sha256 tiap berkas, lisensi) yang dibaca adapter untuk identitas model.
Lisensi bobot: MIT (model card Hugging Face weecology/deepforest-tree). Kode DeepForest: MIT.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "weecology/deepforest-tree"
# Commit Hub yang diuji 2026-10-19 (lastModified 2024-09-20). Ubah hanya setelah menguji ulang.
TESTED_REVISION = "cc21436bc5d572dde8ff5f93c1e71a32f563cace"
FILES = ["config.json", "model.safetensors", "README.md"]   # NEON.pt (format lama) tidak dibutuhkan 2.x


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-id", default=REPO_ID)
    ap.add_argument("--revision", default=TESTED_REVISION, help="commit Hub (default: revisi yang diuji)")
    ap.add_argument("--dest", default=str(API_ROOT / "var" / "models" / "deepforest-tree"))
    a = ap.parse_args(argv)
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        print("huggingface_hub belum terpasang: pip install -r requirements-deepforest.txt", file=sys.stderr)
        return 1
    dest = Path(a.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(a.repo_id, revision=a.revision)
    files = {}
    for name in FILES:
        path = Path(hf_hub_download(a.repo_id, name, revision=info.sha, local_dir=dest))
        files[name] = {"sha256": sha256(path), "size": path.stat().st_size}
        print(f"{name}: {files[name]['size']:,} B  sha256={files[name]['sha256'][:16]}…")
    # DeepForest 2.1.0 membangun RetinaNet via torchvision `retinanet_resnet50_fpn(weights=None)`, yang tetap
    # memuat backbone ImageNet (ResNet50_Weights.IMAGENET1K_V1) dari download.pytorch.org — lalu ditimpa
    # model.safetensors. Diambil di sini agar API tidak mengunduhnya saat request (adapter memakai TORCH_HOME ini).
    import os

    torch_home = dest / "torch_home"
    os.environ["TORCH_HOME"] = str(torch_home)
    from torchvision.models import ResNet50_Weights

    backbone = ResNet50_Weights.IMAGENET1K_V1
    backbone.get_state_dict(progress=True)
    bpath = torch_home / "hub" / "checkpoints" / Path(backbone.url).name
    aux = {f"torch_home/hub/checkpoints/{bpath.name}": {
        "sha256": sha256(bpath), "size": bpath.stat().st_size, "source": backbone.url,
        "license": "torchvision (BSD-3-Clause kode; bobot ImageNet — lihat ketentuan torchvision)",
        "note": "Hanya untuk konstruksi arsitektur; nilainya ditimpa model.safetensors."}}
    print(f"{bpath.name}: {bpath.stat().st_size:,} B (backbone torchvision, dibutuhkan saat konstruksi)")
    card = getattr(info, "card_data", None) or {}
    manifest = {
        "repo_id": a.repo_id, "revision": info.sha, "source": f"https://huggingface.co/{a.repo_id}/tree/{info.sha}",
        "license": (card.get("license") if hasattr(card, "get") else None) or "lihat model card",
        "files": files, "aux_files": aux, "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "model_version": "sha256:" + files["model.safetensors"]["sha256"][:16],
        "target": "tree_crown",
        "note": "Pretrained tajuk pohon (citra pesawat NEON ±10 cm/px). Bukan model tanaman pertanian.",
    }
    (dest / "wallacea_model.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nTersimpan di {dest}\nmodel_version = {manifest['model_version']}\n\nJalankan API (PowerShell):\n"
          f"  $env:WALLACEA_DETECTOR = \"deepforest\"\n  $env:WALLACEA_MODEL_PATH = \"{dest}\"\n"
          "  .venv\\Scripts\\python -m app")
    return 0


if __name__ == "__main__":
    sys.exit(main())
