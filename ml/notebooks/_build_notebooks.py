"""Generator notebook (sumber kebenaran isi sel): 01–03 prototype (data, inferensi pretrained, evaluasi) dan
`training/01–04` (alur training model tim). Jalankan ulang setelah mengubah sel:

    .venv\\Scripts\\python notebooks\\_build_notebooks.py --only 02_pretrained_inference.ipynb   # satu notebook
    .venv\\Scripts\\python notebooks\\_build_notebooks.py                                        # semua (menimpa!)

Notebook hanya memanggil modul `wallacea_ml` — tidak ada logika preprocessing/metrik di notebook.
"""
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
KERNEL = {"name": "wallacea-ml", "display_name": "Python (wallacea-ml)", "language": "python"}

SETUP = """\
%matplotlib inline
import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from IPython.display import display

import wallacea_ml
from wallacea_ml.prepare import ML_ROOT
print("wallacea_ml", wallacea_ml.__version__, "| ML_ROOT =", ML_ROOT)


def _df(rows):
    \"\"\"Tabel: pandas bila terpasang (opsional), selain itu list apa adanya.\"\"\"
    try:
        import pandas as pd
        return pd.DataFrame(rows)
    except ImportError:
        return rows
"""

NB = {
    "training/01_dataset_inspection.ipynb": [
        ("md", """\
# 01 — Inspeksi dataset

Tujuan: memahami dataset SEBELUM training — sumber & lisensi, ukuran/orientasi gambar, distribusi kelas,
ukuran objek, jumlah objek per foto, dan contoh visual dengan bounding box.

Prasyarat (sekali, dari folder `ml/`):
```powershell
.venv\\Scripts\\python -m wallacea_ml datasets sample uavmulticrop UAVmulticrop.zip --pattern "*/maize/*" --limit 200 --max-mb 400
.venv\\Scripts\\python -m wallacea_ml prepare configs\\prepare\\uavmulticrop_maize.yaml
```
Kernel: **Python (wallacea-ml)**."""),
        ("code", SETUP),
        ("md", "## Katalog dataset (diperiksa ke sumber asli)"),
        ("code", """\
from wallacea_ml.datasets import load_catalog
cat = load_catalog()
display(_df([{"id": d["id"], "status": d["status"], "tanaman": ", ".join(d["crops"]),
              "lisensi dataset": d["license"]["dataset"], "lisensi kode": d["license"]["code"],
              "bobot": d["license"]["weights"], "format": d["annotation_format"][:60]} for d in cat.values()]))"""),
        ("md", "## Pilih dataset yang sudah di-`prepare`"),
        ("code", """\
DATASET = "uavmulticrop_maize"          # nama folder di data/prepared/
ROOT = ML_ROOT / "data" / "prepared" / DATASET
from wallacea_ml.manifest import load_manifest
from wallacea_ml.inspection import inspect_manifest
m = load_manifest(ROOT / "manifest.json")
assert not m.errors, m.errors
st = inspect_manifest(m, ROOT)
summary = st.summary()
print(json.dumps(summary, indent=1, default=str))"""),
        ("md", "## Gambar per grup (lahan/penerbangan) — dasar split"),
        ("code", """\
from collections import Counter
display(_df([{"field_id": f, "images": n, "boxes": sum(r["boxes"] for r in st.images if r["field_id"] == f)}
             for f, n in sorted(Counter(r["field_id"] for r in st.images).items())]))"""),
        ("md", "## Distribusi ukuran gambar, objek per foto, dan ukuran objek"),
        ("code", """\
fig, ax = plt.subplots(1, 3, figsize=(15, 3.5))
ax[0].hist([r["boxes"] for r in st.images], bins=20); ax[0].set_title("objek per foto")
ax[1].hist([b["w_px"] for b in st.boxes], bins=40); ax[1].set_title("lebar box (px, gambar terorientasi)")
ax[2].hist([b["w"] * b["h"] for b in st.boxes], bins=40, log=True); ax[2].set_title("luas box relatif (log)")
plt.tight_layout(); plt.show()
print("ukuran gambar:", summary["image_sizes"], "| orientasi:", summary["orientation"])
print("Catatan: API memprediksi FOTO PENUH di-letterbox ke WALLACEA_IMGSZ. Objek sangat kecil relatif terhadap foto akan hilang saat diperkecil.")"""),
        ("md", "## Contoh visual (piksel terorientasi EXIF, sama dengan editor WALLACEA)"),
        ("code", """\
from wallacea_ml import backend
from wallacea_ml.inspection import read_yolo_labels
from wallacea_ml.viz import draw_boxes
names = {i: lab for lab, i in m.label_map.items()}
sample = [e for e in m.images if e.labels][:: max(1, len(m.labeled) // 4)][:4]
fig, axes = plt.subplots(1, len(sample), figsize=(5 * len(sample), 4))
for ax, e in zip(axes if len(sample) > 1 else [axes], sample):
    boxes, _ = read_yolo_labels(ROOT / e.labels, len(names))
    ax.imshow(draw_boxes(backend.load_oriented(ROOT / e.image), [(names[c], bb) for c, bb in boxes]))
    ax.set_title(f"{e.field_id} · {len(boxes)} box"); ax.axis("off")
plt.tight_layout(); plt.show()"""),
    ],
    "training/02_annotation_validation.ipynb": [
        ("md", """\
# 02 — Validasi anotasi

Memeriksa: struktur COCO (id, `category_id`, koordinat piksel), pemetaan kelas eksplisit, gambar yang dilewati
`prepare` (dan alasannya), label YOLO hilang/tidak valid, berkas duplikat (byte identik & hampir identik),
serta kebocoran split.

Gambar tanpa anotasi **tidak** dianggap contoh negatif kecuali dokumentasi dataset menyatakannya
(`empty_images_are_negative` di config prepare)."""),
        ("code", SETUP),
        ("md", "## 1. COCO mentah"),
        ("code", """\
import glob
from wallacea_ml.coco import load_coco, validate_coco
rows = []
for p in sorted(glob.glob(str(ML_ROOT / "data/raw/uavmulticrop/UAVmulticrop/maize/*.json"))):
    r = validate_coco(load_coco(p))
    s = r.summary()
    rows.append({"file": Path(p).name, "images": s["images"], "boxes": s["annotations"], "categories": s["categories"],
                 "unannotated": s["unannotated_images"], "errors": dict(s["errors"]), "warnings": dict(s["warnings"])})
display(_df(rows))"""),
        ("md", "## 2. Pemetaan kelas (harus eksplisit; kategori tak terpetakan = error)"),
        ("code", """\
import yaml
from wallacea_ml.coco import resolve_class_map
cmap = yaml.safe_load((ML_ROOT / "configs/class_maps/uavmulticrop.yaml").read_text(encoding="utf-8"))
print("class_map:", cmap)
print("category_id → label:", resolve_class_map(load_coco(p), cmap))"""),
        ("md", "## 3. Laporan `prepare` — gambar dilewati & statistik konversi"),
        ("code", """\
DATASET = "uavmulticrop_maize"
ROOT = ML_ROOT / "data" / "prepared" / DATASET
rep = json.loads((ROOT / "prepare_report.json").read_text(encoding="utf-8"))
print("ditulis:", rep["images_written"], "gambar,", rep["boxes_written"], "box")
print("konversi:", rep["conversion"])
print("dilewati per alasan:", rep["skipped_by_reason"])
display(_df(rep["skipped"][:50]))"""),
        ("md", "## 4. Label YOLO hasil prepare + duplikat"),
        ("code", """\
from wallacea_ml.manifest import load_manifest
from wallacea_ml.inspection import inspect_manifest, find_duplicates
m = load_manifest(ROOT / "manifest.json")
st = inspect_manifest(m, ROOT)
print("isu label:", st.summary()["issues"] or "tidak ada")
display(_df([vars(i) for i in st.issues[:50]]))
dups = find_duplicates(m, ROOT)
print("byte identik:", dups["exact"] or "tidak ada")
print("hampir identik:", len(dups["near"]), "pasang;", sum(d["cross_group"] for d in dups["near"]), "lintas grup (calon kebocoran)")
display(_df(dups["near"][:30]))"""),
        ("md", "## 5. Box mencurigakan (sangat kecil / menyentuh tepi)"),
        ("code", """\
from wallacea_ml import backend
from wallacea_ml.viz import draw_boxes
tiny = sorted(st.boxes, key=lambda b: b["w_px"] * b["h_px"])[:5]
print([(b["image"], round(b["w_px"], 1), round(b["h_px"], 1)) for b in tiny])
if tiny:
    e = tiny[0]
    img = backend.load_oriented(ROOT / e["image"])
    plt.figure(figsize=(8, 5)); plt.imshow(draw_boxes(img, [("check", [e["l"], e["t"], e["w"], e["h"]])])); plt.axis("off"); plt.show()"""),
        ("md", "## 6. Split & kebocoran"),
        ("code", """\
SPLIT_DIR = ML_ROOT / "data" / "splits" / DATASET
rep = json.loads((SPLIT_DIR / "split_report.json").read_text(encoding="utf-8"))
print(json.dumps(rep, indent=1))
assert not rep["leaks"], "Split bocor — jangan training/evaluasi sebelum diperbaiki"
"""),
    ],
    "training/03_model_experiments.ipynb": [
        ("md", """\
# 03 — Eksperimen model

Training dijalankan lewat CLI/modul yang sama (`wallacea_ml.train`), bukan kode notebook. Notebook ini:
menampilkan konfigurasi & pemeriksaan awal, (opsional) menjalankan training, lalu membaca kurva & model card.

Bobot awal harus berkas LOKAL (lisensi Ultralytics AGPL-3.0/Enterprise). `best.pt` dipilih Ultralytics
berdasarkan split **val**; angka evaluasi akhir hanya dari notebook 04 pada split **test**."""),
        ("code", SETUP),
        ("code", """\
import yaml
from wallacea_ml.train import load_train_config, preflight
DATASET = "uavmulticrop_maize"
MANIFEST = ML_ROOT / "data" / "prepared" / DATASET / "manifest.json"
SPLIT_DIR = ML_ROOT / "data" / "splits" / DATASET
cfg = load_train_config(ML_ROOT / "configs/train/baseline_yolo.yaml", name=f"{DATASET}_yolo11n")
print(yaml.safe_dump(cfg, sort_keys=False))
problems = preflight(MANIFEST, SPLIT_DIR, ML_ROOT / cfg["weights"])
print("pemeriksaan awal:", problems or "lulus")"""),
        ("md", "## Training (opsional dari notebook — lama; lebih aman lewat CLI di terminal)"),
        ("code", """\
RUN_TRAINING = False   # ubah ke True untuk menjalankan; sama dengan:
# .venv\\Scripts\\python -m wallacea_ml train data\\prepared\\<DATASET>\\manifest.json --split-dir data\\splits\\<DATASET> --name <nama>
if RUN_TRAINING:
    from wallacea_ml.train import train
    assert train(cfg, MANIFEST, SPLIT_DIR) == 0"""),
        ("md", "## Kurva training (dari run Ultralytics)"),
        ("code", """\
import csv
card_path = ML_ROOT / "artifacts" / "models" / cfg["name"] / "model_card.json"
if not card_path.is_file():
    print("Belum ada model card untuk", cfg["name"], "— training belum dijalankan.")
else:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(Path(card["ultralytics_run_dir"]) / "results.csv", encoding="utf-8")))
    rows = [{k.strip(): float(v) for k, v in r.items()} for r in rows]
    ep = [r["epoch"] for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(13, 3.5))
    for k in ("train/box_loss", "val/box_loss"): ax[0].plot(ep, [r[k] for r in rows], label=k)
    for k in ("metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)"): ax[1].plot(ep, [r[k] for r in rows], label=k)
    ax[0].legend(); ax[1].legend(); ax[1].set_title("metrik split VAL (dipakai memilih best.pt)"); plt.show()"""),
        ("md", "## Model card (metadata bobot)"),
        ("code", """\
if card_path.is_file():
    card = json.loads(card_path.read_text(encoding="utf-8"))
    print(json.dumps({k: card[k] for k in ("model_id", "model_version", "classes", "api_env", "preprocessing",
                                          "base_weights", "environment", "ultralytics_metrics_val")}, indent=1))
    print("split:", card["dataset"]["counts"], "| group_by:", card["dataset"]["split_report"]["group_by"])"""),
    ],
    "training/04_k919_evaluation.ipynb": [
        ("md", """\
# 04 — Evaluasi (publik) dan foto K919

1. Threshold confidence dipilih di split **val** → diterapkan ke split **test** (evaluasi akhir dataset publik).
2. Prediksi dibuat lewat **adapter API** (`app.inference.UltralyticsDetector`) — keluaran sama dengan `/analyze`.
3. Foto K919: statistik domain (ukuran, orientasi, ketajaman) vs dataset publik, dan — **hanya bila ada label
   manusia** — evaluasi terpisah dengan domain `k919`.

Hasil dataset publik **bukan** kinerja pada foto K919. Confidence model bukan ukuran akurasi survei."""),
        ("code", SETUP),
        ("code", """\
from wallacea_ml.evaluate import evaluate, sweep, choose_threshold
DATASET = "uavmulticrop_maize"
MODEL = f"{DATASET}_yolo11n"
EVAL_DIR = ML_ROOT / "artifacts" / "eval" / MODEL
card_path = ML_ROOT / "artifacts" / "models" / MODEL / "model_card.json"
pred_val = json.loads((EVAL_DIR / "pred_val.json").read_text(encoding="utf-8"))
pred_test = json.loads((EVAL_DIR / "pred_test.json").read_text(encoding="utf-8"))
rows = sweep(pred_val)
best = choose_threshold(rows, "count_mae")
print("threshold dipilih di VAL:", best)
fig, ax = plt.subplots(1, 2, figsize=(13, 3.5))
c = [r["conf"] for r in rows]
ax[0].plot(c, [r["precision"] for r in rows], label="precision"); ax[0].plot(c, [r["recall"] for r in rows], label="recall")
ax[0].plot(c, [r["f1"] for r in rows], label="F1"); ax[0].axvline(best["conf"], ls="--", c="k"); ax[0].legend(); ax[0].set_xlabel("confidence")
ax[1].plot(c, [r["count_mae_per_image"] for r in rows]); ax[1].axvline(best["conf"], ls="--", c="k"); ax[1].set_title("MAE hitungan per foto (VAL)")
plt.show()"""),
        ("md", "## Evaluasi akhir pada split TEST (threshold dari VAL, tidak diubah)"),
        ("code", """\
r = evaluate(pred_test, leaks=[], conf_threshold=best["conf"])
print({k: getattr(r, k) for k in ("domain", "images", "gt_total", "tp", "fp", "fn", "precision", "recall", "f1", "ap",
                                  "count_mae_per_image", "count_mean_error_per_image", "count_relative_error")})
for cv in r.caveats: print("•", cv)
gt = [row["gt"] for row in r.per_image]; pr = [row["pred"] for row in r.per_image]
plt.figure(figsize=(4.5, 4.5)); plt.scatter(gt, pr); m_ = max(gt + pr) * 1.05
plt.plot([0, m_], [0, m_], "k--"); plt.xlabel("hitungan label manusia"); plt.ylabel("hitungan model"); plt.title("per foto — TEST"); plt.show()"""),
        ("md", "## Visual: prediksi (biru) vs label (hijau) pada foto test"),
        ("code", """\
from wallacea_ml import backend
from wallacea_ml.viz import draw_boxes
ROOT = ML_ROOT / "data" / "prepared" / DATASET
im = max(pred_test["images"], key=lambda i: len(i["gt"]))
boxes = [("plant", g["bbox"]) for g in im["gt"]] + [("pred", p["bbox"]) for p in im["pred"] if p["confidence"] >= best["conf"]]
plt.figure(figsize=(14, 8)); plt.imshow(draw_boxes(backend.load_oriented(ROOT / im["image"]), boxes, max_side=2400)); plt.axis("off"); plt.show()"""),
        ("md", """\
## Foto K919

Salin foto ASLI dari kartu/aplikasi drone (bukan screenshot) ke `ml/data/k919/raw/` (tidak masuk Git).
Bila tim sudah melabeli sebagian (CVAT → COCO, label `plant`), buat config prepare dengan `domain: k919`
dan grup per lahan/penerbangan, lalu jalankan `prepare` → `split` → `predict` → `evaluate`."""),
        ("code", """\
from wallacea_ml.inspection import photo_folder_stats
K919 = ML_ROOT / "data" / "k919" / "raw"
k_rows = photo_folder_stats(K919) if K919.is_dir() else []
print(len(k_rows), "foto K919 ditemukan" if k_rows else "— belum ada foto K919 di data/k919/raw (status: BELUM DIUJI)")
if k_rows:
    display(_df(k_rows[:20]))
    print("orientasi EXIF:", Counter(r["exif_orientation"] for r in k_rows))"""),
        ("md", "## Perbandingan domain: dataset publik vs K919"),
        ("code", """\
from wallacea_ml.manifest import load_manifest
from wallacea_ml.inspection import inspect_manifest, compare_domains
pub = inspect_manifest(load_manifest(ROOT / "manifest.json"), ROOT, open_images=False).summary()
doms = {"public:" + DATASET: pub}
if k_rows:
    doms["k919 (tanpa label)"] = {"images": len(k_rows), "boxes": None,
                                  "image_sizes": dict(Counter(f"{r['width']}x{r['height']}" for r in k_rows))}
display(_df(compare_domains(doms)))
print("Ukuran objek tanaman pada foto K919 bergantung ketinggian terbang; bandingkan lebar box (px) setelah ada label K919.")"""),
        ("md", "## Prediksi pada foto K919 (tanpa label = BUKAN akurasi)"),
        ("code", """\
if k_rows and card_path.is_file():
    card = json.loads(card_path.read_text(encoding="utf-8"))
    env = card["api_env"]
    det = backend.build_api_detector(env["WALLACEA_MODEL_PATH"], json.loads(env["WALLACEA_LABEL_MAP_JSON"]),
                                     confidence=env["WALLACEA_CONFIDENCE"] or best["conf"], imgsz=env["WALLACEA_IMGSZ"])
    for r_ in k_rows[:3]:
        img = backend.load_oriented(K919 / r_["image"])
        out = det.detect(img)
        plt.figure(figsize=(12, 7)); plt.imshow(draw_boxes(img, [("pred", d.bbox) for d in out.detections], max_side=2400))
        plt.title(f"{r_['image']}: {len(out.detections)} kandidat (pending — perlu tinjauan manusia)"); plt.axis("off"); plt.show()
else:
    print("Lewati: butuh foto K919 dan model card.")"""),
    ],
    "01_data_inspection.ipynb": [
        ("md", """\
# 01 — Inspeksi data: foto contoh, orientasi, anotasi

Foto contoh berlisensi dari `samples/catalog.json` (katalog yang sama dengan `GET /api/v1/samples`). Setiap
berkas dicek sha256-nya. Gambar ditampilkan **setelah orientasi EXIF** lewat `app.imaging` — sama dengan editor
web dan input model. Anotasi manusia (Pascal VOC) hanya untuk evaluasi di notebook 03.

Kernel: **Python (wallacea-ml)**. Tidak butuh model/bobot."""),
        ("code", SETUP),
        ("md", "## 1. Katalog: sumber, lisensi, checksum"),
        ("code", """\
from wallacea_ml.samples import load_samples, samples_dir
samples = load_samples()          # gagal keras bila sha256 tidak cocok dengan katalog
print("folder:", samples_dir())
display(_df([{"id": s.id, "berkas": s.path.name, "sha256": s.sha256[:16] + "…", "lisensi": s.license_name,
              "anotasi": s.annotation_labels} for s in samples]))
print("Sumber:", samples[0].source_url)
print("Atribusi:", samples[0].attribution)
print("Citra:", samples[0].imagery)"""),
        ("md", "## 2. Dimensi mentah vs terorientasi, EXIF, kecerahan & ketajaman relatif"),
        ("code", """\
from wallacea_ml import backend
from wallacea_ml.inspection import photo_folder_stats
rows = []
for s in samples:
    img = backend.load_oriented(s.path)
    raw = backend.raw_size(s.path)
    rows.append({"id": s.id, "mentah": f"{raw[0]}×{raw[1]}", "terorientasi": f"{img.width}×{img.height}",
                 "exif_orientation": backend.exif_orientation(s.path), "mode": img.mode, "byte": s.path.stat().st_size})
display(_df(rows))
display(_df([{k: r[k] for k in ("image", "brightness", "sharpness_lapvar_1024")}
             for r in photo_folder_stats(samples[0].path.parent)]))"""),
        ("md", "## 3. Foto + anotasi manusia (hijau). Label asli dipetakan eksplisit."),
        ("code", """\
from wallacea_ml.viz import draw_boxes
from wallacea_ml.voc import load_voc
# OSBS & YELL memakai label "Tree"; SOAP_061 memakai "Alive"/"Dead". Semuanya tajuk pohon → plant (eksplisit).
VOC_LABELS = {"Tree": "plant", "Alive": "plant", "Dead": "plant"}
fig, axes = plt.subplots(1, len(samples), figsize=(6 * len(samples), 6))
size_rows = []
for ax, s in zip(axes, samples):
    img = backend.load_oriented(s.path)
    voc = load_voc(s.annotations, VOC_LABELS)
    assert (voc.width, voc.height) == img.size, "dimensi anotasi ≠ gambar terorientasi"
    ax.imshow(draw_boxes(img, voc.boxes)); ax.set_title(f"{s.id}: {len(voc.boxes)} kotak manusia"); ax.axis("off")
    w_px = sorted(b[2] * img.width for _, b in voc.boxes)
    size_rows.append({"id": s.id, "kotak": len(voc.boxes), "label_asli": voc.raw_labels,
                      "lebar_px_min": round(w_px[0], 1), "lebar_px_median": round(w_px[len(w_px) // 2], 1),
                      "lebar_px_max": round(w_px[-1], 1), "dilewati_clip": voc.skipped})
plt.tight_layout(); plt.show()
display(_df(size_rows))"""),
        ("md", """\
## 4. Foto K919 (bila ada)

Salin foto ASLI K919 MAX ke `ml/data/k919/raw/` (tidak masuk Git). Sel ini hanya statistik — tanpa label,
tanpa klaim akurasi."""),
        ("code", """\
K919 = ML_ROOT / "data" / "k919" / "raw"
k_rows = photo_folder_stats(K919) if K919.is_dir() else []
if k_rows:
    display(_df(k_rows))
    print("orientasi EXIF:", Counter(r["exif_orientation"] for r in k_rows))
else:
    print("Belum ada foto K919 di", K919, "— inspeksi hanya pada foto contoh NEON.")"""),
    ],
    "02_pretrained_inference.ipynb": [
        ("md", """\
# 02 — Inferensi pretrained (DeepForest) lewat adapter API

Model: `weecology/deepforest-tree` — **kandidat tajuk pohon**, dilatih pada citra pesawat NEON ±10 cm/px.
Bukan model tanaman pertanian; belum diuji pada K919. Notebook memanggil `app.inference.DeepForestDetector`
(adapter yang sama dengan `POST /photos/{id}/analyze`), memuat model SEKALI dari folder lokal tanpa unduhan,
dan mengukur waktu sebenarnya di mesin ini.

Prasyarat (sekali): `apps\\api\\scripts\\download_deepforest.py`. Lokasi bobot: env `WALLACEA_DEEPFOREST_DIR`
atau default `apps/api/var/models/deepforest-tree`."""),
        ("code", SETUP),
        ("md", "## 1. Identitas model & bobot"),
        ("code", """\
from wallacea_ml import backend
model_dir = backend.default_deepforest_dir()
manifest = json.loads((model_dir / "wallacea_model.json").read_text(encoding="utf-8"))
print(json.dumps({k: manifest[k] for k in ("repo_id", "revision", "license", "model_version", "source")}, indent=1))
print({n: f["sha256"][:16] + "…" for n, f in {**manifest["files"], **manifest["aux_files"]}.items()})"""),
        ("md", "## 2. Jalankan pada semua foto contoh (CPU). Waktu = median 3 pengulangan per foto."),
        ("code", """\
import platform, torch
from wallacea_ml.samples import load_samples
from wallacea_ml import pretrained
PARAMS = dict(confidence=0.35, device="cpu", patch_size=400, patch_overlap=0.05)   # = default API
det = backend.build_api_deepforest(model_dir, **PARAMS)
samples = load_samples()
result = pretrained.run_on_samples(det, samples, repeats=3)
out_path = pretrained.save(result)
print(f"mesin: {platform.processor() or platform.machine()} | torch {torch.__version__} | device: {PARAMS['device']}")
print(f"muat model: {result['load_seconds']} s (sekali)  →  {out_path.relative_to(ML_ROOT)}")
display(_df([{"foto": i["image"], "px": f"{i['width']}×{i['height']}", "mode": i["mode"],
              "detik (median)": i["seconds_median"], "detik (semua)": i["seconds"], "kandidat": len(i["pred"])}
             for i in result["images"]]))
print("parameter adapter:", result["parameters"])"""),
        ("md", "## 3. Kandidat model (biru) — belum dibandingkan dengan anotasi manusia"),
        ("code", """\
from wallacea_ml.viz import draw_boxes
fig, axes = plt.subplots(1, len(samples), figsize=(6 * len(samples), 6))
for ax, s, rec in zip(axes, samples, result["images"]):
    ax.imshow(draw_boxes(backend.load_oriented(s.path), [("pred", p["bbox"]) for p in rec["pred"]]))
    ax.set_title(f"{s.id}: {len(rec['pred'])} kandidat (pending)"); ax.axis("off")
plt.tight_layout(); plt.show()
conf = [p["confidence"] for r in result["images"] for p in r["pred"]]
plt.figure(figsize=(6, 3)); plt.hist(conf, bins=20); plt.xlabel("confidence (skor model, BUKAN akurasi)"); plt.show()
print("label asli model:", Counter(p["model_label"] for r in result["images"] for p in r["pred"]),
      "→ kind", Counter(p["label"] for r in result["images"] for p in r["pred"]))"""),
        ("md", """\
## 4. Foto K919 — kualitatif saja

Tanpa anotasi manusia, yang dilaporkan hanya kandidat + waktu. Tidak ada angka akurasi."""),
        ("code", """\
import time
K919 = ML_ROOT / "data" / "k919" / "raw"
ks = sorted(p for p in K919.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}) if K919.is_dir() else []
if not ks:
    print("Belum ada foto K919 — hasil notebook ini hanya untuk foto contoh NEON.")
for p in ks[:3]:
    img = backend.load_oriented(p)
    t = time.perf_counter(); out = det.detect(img); secs = time.perf_counter() - t
    plt.figure(figsize=(12, 8)); plt.imshow(draw_boxes(img, [("pred", d.bbox) for d in out.detections], max_side=2400))
    plt.title(f"{p.name} {img.size}: {len(out.detections)} kandidat tajuk pohon, {secs:.1f} s — TANPA ground truth")
    plt.axis("off"); plt.show()"""),
    ],
    "03_evaluation.ipynb": [
        ("md", """\
# 03 — Evaluasi terhadap anotasi manusia

Membandingkan kandidat DeepForest (hasil notebook 02, atau dijalankan ulang bila belum ada) dengan anotasi
manusia pada foto contoh yang **punya ground truth**. Pencocokan greedy per confidence, IoU ≥ 0.5.

Batas tafsir: hanya 3 foto hutan NEON yang berasal dari ekosistem/sensor yang sama dengan data pengembang
model → **tidak independen**; bukan akurasi untuk lahan pertanian atau foto K919. Foto tanpa anotasi tidak
dihitung metriknya."""),
        ("code", SETUP),
        ("md", "## 1. Prediksi + ground truth"),
        ("code", """\
from wallacea_ml import backend, pretrained
from wallacea_ml.samples import load_samples
from wallacea_ml.voc import load_voc
samples = {s.id: s for s in load_samples()}
if pretrained.DEFAULT_OUT.is_file():
    result = pretrained.load()
    print("memakai hasil notebook 02:", result["created_at"], result["model_version"])
else:
    det = backend.build_api_deepforest(backend.default_deepforest_dir(), confidence=0.35, device="cpu")
    pretrained.save(pretrained.run_on_samples(det, list(samples.values())))
    result = pretrained.load()
    print("notebook 02 belum dijalankan — inferensi dijalankan di sini")
VOC_LABELS = {"Tree": "plant", "Alive": "plant", "Dead": "plant"}   # eksplisit; lihat notebook 01
CONF = result["parameters"]["conf"]
data = {**{k: result[k] for k in ("model_id", "model_version", "split", "domain", "iou_threshold")}, "images": []}
for rec in result["images"]:
    s = samples[rec["image"]]
    if s.annotations is None:
        print("tanpa ground truth (dilewati dari metrik):", s.id)
        continue
    voc = load_voc(s.annotations, VOC_LABELS)
    data["images"].append({"image": s.id, "gt": [{"label": l, "bbox": b} for l, b in voc.boxes], "pred": rec["pred"]})
print(len(data["images"]), "foto dengan ground truth; threshold confidence =", CONF)"""),
        ("md", "## 2. Metrik per foto & gabungan (IoU ≥ 0.5)"),
        ("code", """\
from wallacea_ml.evaluate import evaluate, sweep
r = evaluate(data, leaks=[], conf_threshold=CONF)
display(_df([{k: row[k] for k in ("image", "gt", "pred", "tp", "fp", "fn", "count_error")} for row in r.per_image]))
print({k: (round(getattr(r, k), 3) if isinstance(getattr(r, k), float) else getattr(r, k))
       for k in ("gt_total", "tp", "fp", "fn", "precision", "recall", "f1", "ap", "count_mae_per_image")})
for c in r.caveats + ["Hanya 3 foto NEON, tidak independen dari data pengembang model. Bukan akurasi K919/pertanian."]:
    print("•", c)"""),
        ("md", "## 3. Pengaruh threshold confidence (ilustrasi pada 3 foto — jangan dipakai memilih threshold produk)"),
        ("code", """\
rows = sweep(data, [round(0.05 * i, 2) for i in range(7, 19)])
c = [x["conf"] for x in rows]
plt.figure(figsize=(7, 3.5))
for k in ("precision", "recall", "f1"):
    plt.plot(c, [x[k] for x in rows], label=k)
plt.axvline(CONF, ls="--", c="k"); plt.xlabel("threshold confidence"); plt.legend(); plt.show()
display(_df(rows))"""),
        ("md", "## 4. False positive (merah) & objek terlewat (kuning); cocok = hijau"),
        ("code", """\
from wallacea_ml.evaluate import match_details
from wallacea_ml.viz import draw_boxes
for im in data["images"]:
    m = match_details(im["gt"], [p for p in im["pred"] if p["confidence"] >= CONF], 0.5, "plant")
    boxes = [("plant", d["bbox"]) for d, _ in m["tp"]] + [("gap", d["bbox"]) for d in m["fp"]] + [("check", g["bbox"]) for g in m["fn"]]
    fp_conf = sorted(round(d["confidence"], 2) for d in m["fp"])
    print(f"{im['image']}: {len(m['tp'])} cocok, {len(m['fp'])} false positive, {len(m['fn'])} terlewat; "
          f"confidence FP median {fp_conf[len(fp_conf) // 2] if fp_conf else '-'}")
    plt.figure(figsize=(9, 9))
    plt.imshow(draw_boxes(backend.load_oriented(samples[im["image"]].path), boxes, max_side=1600))
    plt.title(f"{im['image']} — hijau=cocok, merah=FP, kuning=terlewat"); plt.axis("off"); plt.show()"""),
    ],
}


def build(only: list[str] | None = None) -> None:
    """Tulis notebook dari NB. `only` = nama berkas; default semua. Pakai `--only` agar notebook yang sedang
    diubah/dijalankan pengguna tidak tertimpa."""
    for name, cells in NB.items():
        if only and name not in only and Path(name).name not in only:
            continue
        nb = nbf.v4.new_notebook()
        nb.metadata["kernelspec"] = KERNEL
        nb.metadata["language_info"] = {"name": "python"}
        nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in cells]
        (HERE / name).parent.mkdir(parents=True, exist_ok=True)
        nbf.write(nb, HERE / name)
        print("ditulis", name)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="nama notebook, mis. 02_pretrained_inference.ipynb")
    build(ap.parse_args().only)
