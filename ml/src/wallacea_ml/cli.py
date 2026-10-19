"""CLI: python -m wallacea_ml <perintah> ...   (jalankan dari folder ml/, venv ml/.venv)

  datasets list|info|remote|ls-zip|sample|download   katalog & pengunduh eksplisit (tanpa unduhan otomatis)
  coco-check <coco.json>                             validasi COCO (id, kategori, koordinat piksel)
  prepare <config.yaml> --out DIR                    COCO → YOLO + manifest (piksel terorientasi EXIF)
  validate <manifest.json>                           validasi manifest
  inspect <manifest.json>                            statistik & isu label
  split <manifest.json> --root DIR --out DIR         split per lahan/penerbangan/resmi + cek kebocoran
  train <manifest.json> --split-dir DIR              training (menolak tanpa data valid & bobot lokal)
  predict <manifest.json> --split-dir DIR --split S --weights W   prediksi lewat adapter API
  threshold <pred_val.json>                          pilih confidence di split VALIDATION
  evaluate <predictions.json>                        precision/recall/AP/MAE hitungan

`train` menolak berjalan tanpa manifest valid, split tanpa kebocoran, label, dan bobot awal LOKAL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluate import choose_threshold, evaluate, report_dict, sweep
from .manifest import load_manifest
from .split import SPLITS, check_leakage, group_split, yolo_dataset_yaml

ML_ROOT = Path(__file__).resolve().parents[2]


def _dump(obj, out: str | None = None) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    print(text)


# ------------------------------------------------------------------ datasets
def cmd_datasets(a) -> int:
    from . import datasets as ds

    cat = ds.load_catalog()
    if a.action == "list":
        for d in cat.values():
            print(f"{d['id']:<24} {d['status']:<17} {', '.join(d['crops']):<30} {d['license']['dataset']}")
        return 0
    entry = cat.get(a.dataset)
    if entry is None:
        print(f"Dataset tidak dikenal: {a.dataset}. Pilihan: {list(cat)}", file=sys.stderr)
        return 1
    if a.action == "info":
        _dump(entry)
        return 0
    if a.action == "remote":
        meta, files = ds.remote_files(entry)
        _dump({"metadata": meta, "files": [vars(f) for f in files]})
        return 0
    f = ds.find_file(entry, a.file)
    dest = Path(a.dest) if a.dest else ML_ROOT / "data" / "raw" / ds.safe_dirname(a.dataset)
    if a.action == "ls-zip":
        z, h = ds.remote_zip(f)
        for info in z.infolist():
            print(f"{info.file_size:>12,}  {info.filename}")
        print(f"{len(z.infolist())} entri; dibaca via Range ±{h.bytes_fetched / 1e6:.1f} MB dari {f.size / 1e6:,.0f} MB",
              file=sys.stderr)
        return 0
    if a.action == "sample":
        if not a.pattern:
            print("--pattern wajib (glob anggota zip), mis. --pattern '*/maize/*'", file=sys.stderr)
            return 1
        ds.sample_from_zip(f, a.pattern, dest, a.limit, int(a.max_mb * 1e6))
        return 0
    if a.action == "download":
        print(f"{f.name}: {f.size / 1e6:,.1f} MB, checksum {f.checksum}, tujuan {dest}", file=sys.stderr)
        if not a.yes:
            print("Dry-run. Tambahkan --yes untuk benar-benar mengunduh.", file=sys.stderr)
            return 0
        ds.download(f, dest)
        return 0
    return 1


# ------------------------------------------------------------------ data
def cmd_coco_check(a) -> int:
    from .coco import load_coco, validate_coco

    r = validate_coco(load_coco(a.coco))
    _dump({"summary": r.summary(), "issues": [vars(i) for i in r.issues[: a.max_issues]]})
    return 1 if r.errors else 0


def cmd_prepare(a) -> int:
    from .prepare import load_config, prepare

    cfg = load_config(a.config)
    out = Path(a.out) if a.out else ML_ROOT / "data" / "prepared" / cfg["name"]
    rep = prepare(cfg, out, a.max_images)
    _dump({k: rep[k] for k in ("name", "images_written", "boxes_written", "conversion", "skipped_by_reason")})
    print(f"Manifest: {out / 'manifest.json'}", file=sys.stderr)
    return 0 if rep["images_written"] else 1


def cmd_validate(a) -> int:
    m = load_manifest(a.manifest)
    for e in m.errors:
        print("ERROR:", e)
    print(f"{len(m.images)} gambar, {len(m.labeled)} berlabel, tanaman: {m.crop_type or '-'}")
    return 1 if m.errors else 0


def cmd_inspect(a) -> int:
    from .inspection import find_duplicates, inspect_manifest

    m = load_manifest(a.manifest)
    root = Path(a.root) if a.root else Path(a.manifest).parent
    st = inspect_manifest(m, root, open_images=not a.fast)
    out = {"summary": st.summary(), "issues": [vars(i) for i in st.issues[:200]]}
    if a.duplicates:
        out["duplicates"] = find_duplicates(m, root)
    _dump(out, a.out)
    return 0


def cmd_split(a) -> int:
    m = load_manifest(a.manifest)
    if m.errors:
        print("Manifest tidak valid; jalankan validate.", file=sys.stderr)
        return 1
    ratios = tuple(float(x) for x in a.ratios.split(","))
    if len(ratios) != 3 or abs(sum(ratios) - 1) > 1e-6:
        print("--ratios harus 3 angka train,val,test berjumlah 1", file=sys.stderr)
        return 1
    r = group_split(m, a.group_by, ratios=ratios, seed=a.seed)
    out = Path(a.out)
    root = Path(a.root).resolve()
    (out / "splits").mkdir(parents=True, exist_ok=True)
    (out / "yolo").mkdir(parents=True, exist_ok=True)
    for s in SPLITS:
        imgs = sorted(i for i, sp in r.assignments.items() if sp == s)
        (out / "splits" / f"{s}.txt").write_text("\n".join(imgs) + "\n", encoding="utf-8")
        (out / "yolo" / f"{s}.txt").write_text("".join(f"{(root / i).as_posix()}\n" for i in imgs), encoding="utf-8")
    import hashlib
    report = {"group_by": r.group_by, "seed": a.seed, "ratios": ratios, "groups": r.groups, "leaks": r.leaks,
              "is_product_validation": r.is_product_validation,
              "manifest_sha256": hashlib.sha256(Path(a.manifest).read_bytes()).hexdigest(),
              "images_per_split": {s: sum(1 for v in r.assignments.values() if v == s) for s in SPLITS}}
    (out / "split_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "dataset.yaml").write_text(yolo_dataset_yaml(m, root.as_posix(), (out / "yolo").resolve().as_posix()),
                                      encoding="utf-8")
    print(json.dumps({"groups": r.groups, "images_per_split": report["images_per_split"], "leaks": r.leaks}, indent=2))
    return 1 if r.leaks else 0


# ------------------------------------------------------------------ model
def cmd_train(a) -> int:
    from .train import load_train_config, train

    cfg = load_train_config(a.config, weights=a.weights, epochs=a.epochs, imgsz=a.imgsz, name=a.name,
                            batch=a.batch, device=a.device)
    return train(cfg, Path(a.manifest), Path(a.split_dir), dry_run=a.dry_run)


def cmd_predict(a) -> int:
    from .predict import predict_split

    m = load_manifest(a.manifest)
    root = Path(a.root) if a.root else Path(a.manifest).parent
    label_map = json.loads(a.label_map) if a.label_map else {lab: lab for lab in m.label_map}
    data = predict_split(m, root, a.split_dir, a.split, a.weights, label_map, a.imgsz, a.conf)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    n = sum(len(i["pred"]) for i in data["images"])
    print(f"{len(data['images'])} gambar, {n} prediksi (conf ≥ {a.conf}) → {a.out}; "
          f"inferensi rata-rata {data['inference_seconds']['mean']:.2f} s/gambar", file=sys.stderr)
    return 0


def cmd_threshold(a) -> int:
    data = json.loads(Path(a.predictions).read_text(encoding="utf-8"))
    if data.get("split") != "val":
        print(f"PERINGATAN: threshold dipilih dari split '{data.get('split')}', bukan 'val'.", file=sys.stderr)
        if not a.allow_non_val:
            return 2
    rows = sweep(data, label=a.label)
    best = choose_threshold(rows, a.criterion)
    out = {"split": data.get("split"), "chosen": best, "sweep": rows}
    if a.model_card:
        from .train import update_card

        card = update_card(Path(a.model_card), threshold_selection=out)
        card["api_env"]["WALLACEA_CONFIDENCE"] = best["conf"]
        update_card(Path(a.model_card), api_env=card["api_env"])
    _dump(out, a.out)
    return 0


def _split_leaks(a, data) -> list[str] | None:
    if not (a.manifest and a.split_dir):
        return None
    m = load_manifest(a.manifest)
    assignments = {}
    for s in SPLITS:
        p = Path(a.split_dir) / "splits" / f"{s}.txt"
        if p.is_file():
            assignments.update({ln.strip(): s for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()})
    rep = Path(a.split_dir) / "split_report.json"
    group_by = json.loads(rep.read_text(encoding="utf-8")).get("group_by", "field") if rep.is_file() else "field"
    leaks = check_leakage(m, assignments, "field" if group_by in ("official", "external") else group_by)
    wrong = [i["image"] for i in data.get("images", []) if assignments.get(i["image"]) != data.get("split")]
    if wrong:
        leaks.append(f"{len(wrong)} gambar evaluasi tidak berada di split '{data.get('split')}'")
    return leaks


def cmd_evaluate(a) -> int:
    data = json.loads(Path(a.predictions).read_text(encoding="utf-8"))
    leaks = _split_leaks(a, data)
    conf = a.conf
    if conf is None and a.model_card:
        sel = json.loads(Path(a.model_card).read_text(encoding="utf-8")).get("threshold_selection")
        conf = sel["chosen"]["conf"] if sel else None
    if data.get("split") == "test" and conf is None:
        print("PERINGATAN: evaluasi test tanpa threshold dari split val (--conf / --model-card).", file=sys.stderr)
    report = report_dict(evaluate(data, a.label, leaks, conf_threshold=conf))
    if a.model_card:
        from .train import update_card

        summary = {k: v for k, v in report.items() if k != "per_image"}
        summary["predictions_file"] = str(a.predictions)
        update_card(Path(a.model_card), evaluation=summary)
    _dump(report if a.per_image else {k: v for k, v in report.items() if k != "per_image"}, a.out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wallacea_ml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("datasets", help="katalog & unduhan eksplisit")
    d.add_argument("action", choices=["list", "info", "remote", "ls-zip", "sample", "download"])
    d.add_argument("dataset", nargs="?")
    d.add_argument("file", nargs="?", help="nama berkas di sumber (lihat `remote`)")
    d.add_argument("--pattern", action="append", help="glob anggota zip (sample); boleh berulang")
    d.add_argument("--limit", type=int, default=20)
    d.add_argument("--max-mb", type=float, default=100.0)
    d.add_argument("--dest")
    d.add_argument("--yes", action="store_true", help="benar-benar mengunduh (download)")
    d.set_defaults(fn=cmd_datasets)

    c = sub.add_parser("coco-check"); c.add_argument("coco"); c.add_argument("--max-issues", type=int, default=50)
    c.set_defaults(fn=cmd_coco_check)
    p = sub.add_parser("prepare"); p.add_argument("config"); p.add_argument("--out")
    p.add_argument("--max-images", type=int); p.set_defaults(fn=cmd_prepare)

    v = sub.add_parser("validate"); v.add_argument("manifest"); v.set_defaults(fn=cmd_validate)
    i = sub.add_parser("inspect"); i.add_argument("manifest"); i.add_argument("--root"); i.add_argument("--out")
    i.add_argument("--fast", action="store_true", help="jangan buka gambar"); i.add_argument("--duplicates", action="store_true")
    i.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("split"); s.add_argument("manifest"); s.add_argument("--root", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--group-by", choices=["field", "flight", "official", "external"], default="field",
                   help="external = semua gambar ke test (dataset uji eksternal, tidak untuk training)")
    s.add_argument("--seed", default="wallacea")
    s.add_argument("--ratios", default="0.7,0.15,0.15", help="porsi GRUP train,val,test (min. 1 grup per split)")
    s.set_defaults(fn=cmd_split)

    t = sub.add_parser("train"); t.add_argument("manifest"); t.add_argument("--split-dir", required=True)
    t.add_argument("--config", default=str(ML_ROOT / "configs" / "train" / "baseline_yolo.yaml"))
    t.add_argument("--weights", help="Bobot awal LOKAL (.pt); menimpa config"); t.add_argument("--epochs", type=int)
    t.add_argument("--imgsz", type=int); t.add_argument("--batch", type=int); t.add_argument("--device")
    t.add_argument("--name"); t.add_argument("--dry-run", action="store_true"); t.set_defaults(fn=cmd_train)

    pr = sub.add_parser("predict"); pr.add_argument("manifest"); pr.add_argument("--root")
    pr.add_argument("--split-dir", required=True); pr.add_argument("--split", required=True, choices=SPLITS)
    pr.add_argument("--weights", required=True); pr.add_argument("--imgsz", type=int, default=1280)
    pr.add_argument("--conf", type=float, default=0.01); pr.add_argument("--label-map", help="JSON seperti WALLACEA_LABEL_MAP_JSON")
    pr.add_argument("--out", required=True); pr.set_defaults(fn=cmd_predict)

    th = sub.add_parser("threshold"); th.add_argument("predictions"); th.add_argument("--label", default="plant")
    th.add_argument("--criterion", choices=["count_mae", "f1"], default="count_mae")
    th.add_argument("--model-card"); th.add_argument("--out"); th.add_argument("--allow-non-val", action="store_true")
    th.set_defaults(fn=cmd_threshold)

    e = sub.add_parser("evaluate"); e.add_argument("predictions"); e.add_argument("--label", default="plant")
    e.add_argument("--manifest"); e.add_argument("--split-dir"); e.add_argument("--out")
    e.add_argument("--conf", type=float, help="threshold confidence (default: dari model card)")
    e.add_argument("--model-card", help="ambil threshold & simpan hasil ke model card")
    e.add_argument("--per-image", action="store_true"); e.set_defaults(fn=cmd_evaluate)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
