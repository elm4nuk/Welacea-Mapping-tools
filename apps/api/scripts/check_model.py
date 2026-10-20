"""Periksa bobot YOLO .pt sebelum dipakai API. Tidak mengunduh bobot dan tidak memasang paket apa pun.

    $env:WALLACEA_LABEL_MAP_JSON = '{"jagung":"plant"}'
    .venv\\Scripts\\python scripts\\check_model.py --model-path "C:\\path dengan spasi\\best.pt" [--image foto.jpg]

Biasanya dipanggil lewat scripts\\check-model.ps1 (label map dikirim lewat env, bukan argumen, karena PowerShell 5.1
membuang tanda kutip ganda di argumen program native). Exit code: 0 = siap, 1 = model bermasalah, 2 = argumen/berkas.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import textwrap
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.config import KINDS, parse_label_map  # noqa: E402
from app.inference.ultralytics_adapter import class_names, is_generic_coco, weights_fingerprint  # noqa: E402

OK, FAIL, USAGE = 0, 1, 2


def _print(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def simple_label_map(label_map: dict[str, str]) -> str:
    """`jagung=plant,gulma=check` bila aman (tanpa tanda kutip, tahan PowerShell 5.1); selain itu JSON."""
    if all(not set(k) & set(',;=:"{}') and k == k.strip() for k in label_map):
        return ",".join(f"{k}={v}" for k, v in label_map.items())
    return json.dumps(label_map, ensure_ascii=False)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def check(model_path: str, label_map_json: str = "", image: str | None = None, confidence: float = 0.35) -> int:
    raw = model_path.strip().strip('"').strip("'")
    if not raw:
        _print("GAGAL", "Path model kosong. Contoh: -ModelPath \"C:\\Model Tanaman\\best.pt\"")
        return USAGE
    path = Path(raw).expanduser()
    path = path if path.is_absolute() else (Path.cwd() / path)
    path = path.resolve()
    _print("INFO", f"Berkas model: {path}")
    if path.is_dir():
        hint = path / "weights" / "best.pt"
        extra = f" Mungkin maksudnya: {hint}" if hint.is_file() else ""
        _print("GAGAL", f"Path ini folder, bukan berkas .pt.{extra}")
        return USAGE
    if not path.is_file():
        _print("GAGAL", "Berkas model tidak ditemukan. Periksa ejaan path; bila ada spasi, bungkus dengan tanda kutip. "
                        "best.pt dihasilkan oleh training (lihat apps/api/ml/README.md) atau diberikan tim ML; "
                        "skrip ini tidak mengunduh bobot.")
        return USAGE
    if path.suffix.lower() != ".pt":
        _print("GAGAL", f"Ekstensi harus .pt (bobot PyTorch Ultralytics), bukan '{path.suffix or '(tanpa ekstensi)'}'.")
        return USAGE
    _print("OK", f"Berkas ada ({path.stat().st_size / 1e6:.1f} MB), ekstensi .pt.")

    if not 0 <= confidence <= 1:
        _print("GAGAL", "Confidence harus di antara 0 dan 1.")
        return USAGE
    label_map, label_error = parse_label_map(label_map_json)
    if label_error:
        _print("GAGAL", label_error)
        return USAGE

    if importlib.util.find_spec("ultralytics") is None:
        _print("GAGAL", "Paket 'ultralytics' belum terpasang di Python ini (" + sys.executable + "). Pasang sendiri "
                        "(berat, +-1 GB PyTorch): .venv\\Scripts\\python -m pip install -r requirements-ai.txt")
        return FAIL
    try:
        from ultralytics import YOLO
        import ultralytics
        _print("OK", f"ultralytics {getattr(ultralytics, '__version__', '?')} terpasang.")
        model = YOLO(str(path), task="detect")
    except Exception as exc:  # noqa: BLE001
        _print("GAGAL", f"Ultralytics tidak dapat membuka berkas ini: {type(exc).__name__}: {exc}. Berkas mungkin "
                        "rusak, bukan bobot Ultralytics (mis. DeepForest/Faster R-CNN), atau versi paket tidak cocok.")
        return FAIL
    task = getattr(model, "task", "detect")
    if task != "detect":
        _print("GAGAL", f"Model ini task='{task}', bukan deteksi ('detect'). WALLACEA butuh model deteksi bounding box.")
        return FAIL
    _print("OK", "Model deteksi (task=detect) berhasil dibuka.")

    names = class_names(model.names)
    pairs = [f"{i}: {n}" for i, n in (model.names.items() if isinstance(model.names, dict) else enumerate(names))]
    print(f"model.names ({len(pairs)} kelas):")
    print(textwrap.fill(" | ".join(pairs), width=110, initial_indent="  ", subsequent_indent="  "))
    if is_generic_coco(model.names):
        _print("PERINGATAN", "Ini model COCO umum (80 kelas benda sehari-hari), BUKAN model tanaman. API akan "
                             "melabelinya 'BUKAN model tanaman'. Gunakan hanya untuk uji integrasi.")

    explicit = bool(label_map_json.strip())
    if not explicit:
        example = json.dumps({names[0] if names else "nama_kelas": "plant"})
        _print("INFO", f"-LabelMapJson tidak diisi; label map bawaan dipakai: {json.dumps(label_map)}. "
                       f"Contoh untuk model ini: {example}")
    matched = [n for n in names if n in label_map]
    unknown = [k for k in label_map if k not in names]
    ignored = [n for n in names if n not in label_map]
    if not matched:
        _print("GAGAL", f"Label map tidak cocok: tidak ada kunci {sorted(label_map)} di model.names. Kunci harus sama "
                        "persis (huruf besar/kecil, spasi) dengan nama kelas di atas; nilai salah satu "
                        f"{list(KINDS)}.")
        return FAIL
    _print("OK", "Label map cocok: " + ", ".join(f"{n} -> {label_map[n]}" for n in matched))
    if unknown and explicit:
        _print("PERINGATAN", f"Kunci label map yang tidak ada di model (salah ketik?): {unknown}")
    if ignored:
        _print("INFO", f"Kelas model yang tidak dipetakan akan diabaikan: {ignored[:15]}{' ...' if len(ignored) > 15 else ''}")

    if image:
        img_path = Path(image).expanduser().resolve()
        if not img_path.is_file():
            _print("GAGAL", f"Foto uji tidak ditemukan: {img_path}")
            return USAGE
        try:
            from PIL import Image, ImageOps
            with Image.open(img_path) as im:
                pic = ImageOps.exif_transpose(im).convert("RGB")
            res = model.predict(pic, conf=confidence, verbose=False)[0]
            labels = [str(res.names[int(c)]) for c in res.boxes.cls.cpu().tolist()] if res.boxes is not None else []
        except Exception as exc:  # noqa: BLE001
            _print("GAGAL", f"Inferensi uji gagal: {type(exc).__name__}: {exc}")
            return FAIL
        kept = [lab for lab in labels if lab in label_map]
        _print("OK", f"Inferensi uji {img_path.name} ({pic.width}x{pic.height}, conf {confidence}): {len(labels)} kotak, "
                     f"{len(kept)} dipetakan ke penanda WALLACEA. Ini uji jalan, BUKAN ukuran akurasi.")

    version = weights_fingerprint(path)
    _print("OK", f"model_version API akan menjadi {version}.")
    lm = simple_label_map(label_map if explicit else {matched[0]: label_map[matched[0]]})
    print("\nSiap. Jalankan API dengan model ini (salin satu baris, dari folder apps\\api):")
    print(f"  powershell -ExecutionPolicy Bypass -File .\\scripts\\run-with-model.ps1 -ModelPath {_ps_quote(str(path))} "
          f"-LabelMap {_ps_quote(lm)}")
    return OK


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:
            pass
    ap = argparse.ArgumentParser(description="Periksa bobot YOLO .pt untuk WALLACEA (tanpa unduhan/instalasi).")
    ap.add_argument("--model-path", required=True, help="Path berkas .pt (bungkus dengan tanda kutip bila ada spasi)")
    # Default dari env: PowerShell 5.1 membuang tanda kutip ganda di argumen program native, jadi check-model.ps1
    # mengirim JSON lewat WALLACEA_LABEL_MAP_JSON, bukan lewat argumen.
    ap.add_argument("--label-map-json", default=os.environ.get("WALLACEA_LABEL_MAP_JSON", ""),
                    help='Mis. {"jagung":"plant"}; default: env WALLACEA_LABEL_MAP_JSON; kosong = label map bawaan')
    ap.add_argument("--image", default=None, help="Opsional: foto untuk satu inferensi uji")
    ap.add_argument("--confidence", type=float, default=0.35)
    args = ap.parse_args(argv)
    return check(args.model_path, args.label_map_json, args.image, args.confidence)


if __name__ == "__main__":
    sys.exit(main())
