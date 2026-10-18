"""Generator notebook 01–04 (sumber kebenaran isi sel). Jalankan ulang setelah mengubah sel:

    .venv\\Scripts\\python notebooks\\_build_notebooks.py

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
    "01_dataset_inspection.ipynb": [
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
    "02_annotation_validation.ipynb": [
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
    "03_model_experiments.ipynb": [
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
    "04_k919_evaluation.ipynb": [
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
    "05_deepforest_pretrained.ipynb": [
        ("md", """\
# 05 — DeepForest pretrained: inspeksi, inferensi, perbandingan dengan anotasi manusia

Baseline prototype: **kandidat tajuk pohon** dari `weecology/deepforest-tree` (citra pesawat NEON ±10 cm/px).
Bukan model tanaman pertanian. Inferensi memakai **adapter API yang sama** (`app.inference.DeepForestDetector`)
dan gambar terorientasi dari `app.imaging` — hasil di sini = hasil `/analyze`.

Prasyarat: `apps/api/scripts/download_deepforest.py` sudah dijalankan; `pip install deepforest==2.1.0 pandas==3.0.5`
di venv ini. Foto contoh: `samples/deepforest-neon/` (atribusi di `ATTRIBUTION.md`).

Metrik hanya dihitung bila ada **anotasi manusia** (XML). Angkanya berlaku untuk 3 foto contoh NEON ini saja —
**bukan** akurasi pada lahan pertanian atau foto K919."""),
        ("code", SETUP),
        ("md", "## 1. Foto & anotasi manusia"),
        ("code", """\
from wallacea_ml import backend
from wallacea_ml.viz import draw_boxes
from wallacea_ml.voc import load_voc
SAMPLES = ML_ROOT.parent / "samples" / "deepforest-neon"
# Label XML: "Tree" (OSBS, YELL) dan "Alive"/"Dead" (SOAP_061: 9 hidup, 28 mati). Semuanya tajuk pohon → plant (eksplisit).
VOC_LABELS = {"Tree": "plant", "Alive": "plant", "Dead": "plant"}
photos = sorted(SAMPLES.glob("*.png"))
gts = {}
for p in photos:
    img = backend.load_oriented(p)
    voc = load_voc(p.with_suffix(".xml"), VOC_LABELS)
    assert (voc.width, voc.height) == img.size, "dimensi XML ≠ gambar terorientasi"
    gts[p.name] = voc
    print(f"{p.name}: {img.size[0]}×{img.size[1]} px, {len(voc.boxes)} kotak manusia {voc.raw_labels}")
fig, axes = plt.subplots(1, len(photos), figsize=(6 * len(photos), 6))
for ax, p in zip(axes, photos):
    ax.imshow(draw_boxes(backend.load_oriented(p), gts[p.name].boxes)); ax.set_title(f"{p.name} — anotasi manusia"); ax.axis("off")
plt.tight_layout(); plt.show()"""),
        ("md", "## 2. Inferensi pretrained (adapter API, CPU) — waktu benar-benar diukur"),
        ("code", """\
import time
PARAMS = dict(confidence=0.35, device="cpu", patch_size=400, patch_overlap=0.05)   # = default API
det = backend.build_api_deepforest(backend.default_deepforest_dir(), **PARAMS)
print("status:", det.info().state, "|", det.info().model_id, det.info().model_version)
t0 = time.perf_counter(); det.preload(); load_s = time.perf_counter() - t0
print(f"muat model: {load_s:.2f} s (sekali; tidak diulang per foto)")
preds, timing = {}, []
for p in photos:
    img = backend.load_oriented(p)
    t0 = time.perf_counter(); out = det.detect(img); dt_ = time.perf_counter() - t0
    preds[p.name] = out
    timing.append({"foto": p.name, "px": f"{img.size[0]}×{img.size[1]}", "mode": out.parameters["mode"],
                   "detik": round(dt_, 2), "kandidat": len(out.detections)})
display(_df(timing))
print("parameter:", {k: v for k, v in out.parameters.items()})"""),
        ("md", "## 3. Perbandingan terhadap anotasi manusia (IoU ≥ 0.5)"),
        ("code", """\
from wallacea_ml.evaluate import evaluate, match_details
data = {"model_id": det.info().model_id, "model_version": det.info().model_version, "split": "sampel",
        "domain": "public:neon-deepforest-samples", "iou_threshold": 0.5,
        "images": [{"image": n, "gt": [{"label": l, "bbox": b} for l, b in gts[n].boxes],
                    "pred": [{"label": d.label, "confidence": d.confidence, "bbox": d.bbox} for d in preds[n].detections]}
                   for n in gts]}
r = evaluate(data, leaks=[], conf_threshold=PARAMS["confidence"])
display(_df([{k: row[k] for k in ("image", "gt", "pred", "tp", "fp", "fn", "count_error")} for row in r.per_image]))
print({k: (round(getattr(r, k), 3) if isinstance(getattr(r, k), float) else getattr(r, k))
       for k in ("tp", "fp", "fn", "precision", "recall", "f1", "ap", "count_mae_per_image")})
for c in r.caveats: print("•", c)
print("• Hanya 3 foto contoh NEON (hutan AS). Bukan validasi untuk lahan pertanian / K919.")"""),
        ("md", "## 4. False positive (merah) & objek terlewat (kuning) — dicatat per foto"),
        ("code", """\
COLORS = {"tp": "plant", "fp": "gap", "fn": "check"}   # hijau = cocok, merah = FP, kuning = terlewat
for img_ in data["images"]:
    m = match_details(img_["gt"], [x for x in img_["pred"] if x["confidence"] >= PARAMS["confidence"]], 0.5, "plant")
    boxes = [("plant", d["bbox"]) for d, _ in m["tp"]] + [("gap", d["bbox"]) for d in m["fp"]] + [("check", g["bbox"]) for g in m["fn"]]
    print(f"{img_['image']}: {len(m['fp'])} false positive, {len(m['fn'])} terlewat; "
          f"FP confidence: {sorted(round(d['confidence'], 2) for d in m['fp'])[:10]}")
    plt.figure(figsize=(9, 9)); plt.imshow(draw_boxes(backend.load_oriented(SAMPLES / img_["image"]), boxes, max_side=1600))
    plt.title(f"{img_['image']} — hijau=cocok, merah=FP, kuning=terlewat"); plt.axis("off"); plt.show()"""),
        ("md", """\
## 5. Foto K919

Belum ada foto K919 MAX di `ml/data/k919/raw/`. Tanpa foto dan anotasi manusia, **tidak ada** klaim kinerja
untuk K919. Bila ada foto, jalankan sel di bawah: hanya prediksi + waktu (tanpa metrik)."""),
        ("code", """\
K919 = ML_ROOT / "data" / "k919" / "raw"
ks = sorted(p for p in K919.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}) if K919.is_dir() else []
print(len(ks), "foto K919" if ks else "— belum ada foto K919 (hasil di atas hanya foto contoh NEON)")
for p in ks[:3]:
    img = backend.load_oriented(p)
    t0 = time.perf_counter(); out = det.detect(img); dt_ = time.perf_counter() - t0
    plt.figure(figsize=(12, 8)); plt.imshow(draw_boxes(img, [("pred", d.bbox) for d in out.detections], max_side=2400))
    plt.title(f"{p.name}: {len(out.detections)} kandidat tajuk pohon, {dt_:.1f} s — TANPA ground truth"); plt.axis("off"); plt.show()"""),
    ],
}


def build() -> None:
    for name, cells in NB.items():
        nb = nbf.v4.new_notebook()
        nb.metadata["kernelspec"] = KERNEL
        nb.metadata["language_info"] = {"name": "python"}
        nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in cells]
        nbf.write(nb, HERE / name)
        print("ditulis", name)


if __name__ == "__main__":
    build()
