# WALLACEA ML — dataset, validasi anotasi, training, evaluasi

Workspace Python + JupyterLab untuk detektor **satu jenis tanaman per foto** yang dipakai API
(`apps/api/app/inference/ultralytics_adapter.py`). Python = implementasi (`src/wallacea_ml`, CLI + import);
Jupyter = eksperimen & visualisasi (`notebooks/`); FastAPI = inferensi aplikasi dengan bobot yang sudah dievaluasi.

**Satu sumber logika.** Orientasi gambar memakai `app.imaging.oriented_from_bytes` dan prediksi evaluasi
memakai `app.inference.UltralyticsDetector` — kode API yang sama (`wallacea_ml/backend.py`). Notebook hanya
memanggil modul; tidak ada preprocessing/metrik yang ditulis ulang di notebook.

Status hasil nyata: lihat [§ Status](#status-2026-10-18).

## Struktur

```
ml/
  pyproject.toml          paket wallacea-ml (src layout); extras: notebook, dev, train
  requirements.txt        env eksperimen: lock API + paket ini [notebook,dev] — TANPA PyTorch
  requirements-pretrained.txt  + torch CPU + DeepForest 2.1.0 (notebook 01–03; versi teruji)
  requirements-train.txt  + Ultralytics (PyTorch; pasang torch CUDA dulu)
  configs/
    datasets.yaml         katalog dataset (URL, versi, lisensi, format, ukuran, status)
    class_maps/*.yaml     pemetaan kategori COCO → plant/check/gap/drop (eksplisit)
    prepare/*.yaml        resep COCO → YOLO per dataset (grup lahan/penerbangan)
    train/baseline_yolo.yaml
    manifest.example.json
  notebooks/
    01_data_inspection.ipynb       foto contoh (katalog samples/), EXIF/orientasi, anotasi manusia
    02_pretrained_inference.ipynb  DeepForest lewat adapter API, waktu terukur, kandidat
    03_evaluation.ipynb            banding dengan anotasi manusia (P/R/AP, FP & terlewat)
    training/01..04_*.ipynb        alur training model tim (dataset publik → YOLO → evaluasi)
    _build_notebooks.py            generator isi sel (sumber kebenaran)
  src/wallacea_ml/        samples, pretrained, datasets, coco, voc, prepare, manifest, inspection, split, train,
                          predict, evaluate, viz, backend
  tests/                  pytest (fixture sintetis: pipeline & konvensi, bukan akurasi)
  data/      (tidak di Git) raw/ prepared/ splits/ k919/
  artifacts/ (tidak di Git) pretrained/ runs/ models/ eval/
```

## Setup (Windows PowerShell)

Venv **sendiri** di `ml/.venv` — tidak menyentuh Python global atau venv API.

```powershell
cd ml
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt          # API lock + jupyterlab, matplotlib, pytest
.venv\Scripts\python -m pytest                                    # 36 tes pipeline
```

Notebook 01–03 (DeepForest pretrained, CPU) — tambahan ±1 GB paket + bobot ±230 MB sekali:

```powershell
.venv\Scripts\python -m pip install -r requirements-pretrained.txt     # torch CPU 2.11.0 + deepforest 2.1.0
cd ..\apps\api; .\.venv\Scripts\python scripts\download_deepforest.py; cd ..\..\ml   # atau pakai python venv ML
```

`download_deepforest.py` bisa dijalankan dengan Python venv mana pun yang punya `huggingface_hub` + `torchvision`
(mis. `.venv\Scripts\python ..\apps\api\scripts\download_deepforest.py`). Bobot tersimpan di
`apps\api\var\models\deepforest-tree` (default yang dibaca notebook; ubah lewat env `WALLACEA_DEEPFOREST_DIR`).

**Windows: batas panjang path.** Bila `pip install` gagal dengan `[Errno 2] No such file or directory … .pyi` dan
petunjuk *Long Path support*, venv berada di folder yang terlalu dalam (berkas stub `jedi` melewati 260 karakter).
Letakkan repo/venv di path pendek (mis. `D:\coding\…\ml\.venv`) atau aktifkan Long Paths Windows.

Training (berat, opsional). GPU NVIDIA: pasang PyTorch CUDA dulu, lalu Ultralytics:

```powershell
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python -m pip install -r requirements-train.txt
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"
```

### Kernel Jupyter

Kernel didaftarkan **di dalam venv** (`--sys-prefix`), bukan di profil pengguna:

```powershell
.venv\Scripts\python -m ipykernel install --sys-prefix --name wallacea-ml --display-name "Python (wallacea-ml)"
.venv\Scripts\jupyter lab notebooks                                # pilih kernel "Python (wallacea-ml)"
```

VS Code: buka `.ipynb` → *Select Kernel* → *Python Environments* → `ml\.venv\Scripts\python.exe`.
Cek kernel benar: sel pertama mencetak `ML_ROOT = ...\ml`. Bila `ModuleNotFoundError: wallacea_ml`,
kernel yang dipilih bukan venv ini.

## Alur kerja

Semua perintah dari folder `ml/` dengan `.venv\Scripts\python -m wallacea_ml …` (atau `wallacea-ml …`).

| Langkah | Perintah | Notebook |
|---|---|---|
| 1. Katalog & metadata | `datasets list` · `datasets info <id>` · `datasets remote <id>` | 01 |
| 2. Lihat isi arsip tanpa unduh | `datasets ls-zip <id> "<berkas.zip>"` (HTTP Range) | — |
| 3. Sampel kecil / subset | `datasets sample <id> "<berkas.zip>" --pattern "<glob>" --max-mb 400` | — |
| 4. Unduh penuh (eksplisit) | `datasets download <id> "<berkas>" --yes` (tanpa `--yes` = dry-run; checksum diverifikasi) | — |
| 5. Validasi COCO | `coco-check <coco.json>` | 02 |
| 6. COCO → YOLO + manifest | `prepare configs\prepare\<x>.yaml` | 02 |
| 7. Inspeksi | `inspect data\prepared\<x>\manifest.json --duplicates` | 01, 02 |
| 8. Split | `split <manifest> --root data\prepared\<x> --out data\splits\<x> --group-by field` | 02 |
| 9. Training | `train <manifest> --split-dir data\splits\<x> --name <model>` | 03 |
| 10. Prediksi (adapter API) | `predict <manifest> --split-dir … --split val|test --weights <pt> --out …` | 04 |
| 11. Threshold (VAL) | `threshold pred_val.json --model-card <card>` | 04 |
| 12. Evaluasi akhir (TEST) | `evaluate pred_test.json --manifest … --split-dir … --model-card <card>` | 04 |
| DeepForest pretrained | `samples.load_samples`, `pretrained.run_on_samples`, `voc.load_voc` | 01, 02, 03 |

Contoh lengkap baseline jagung (perintah yang benar-benar dijalankan untuk § Status):

```powershell
.venv\Scripts\python -m wallacea_ml datasets sample uavmulticrop UAVmulticrop.zip --pattern "*/maize/*" --limit 200 --max-mb 400
.venv\Scripts\python -m wallacea_ml prepare configs\prepare\uavmulticrop_maize.yaml
.venv\Scripts\python -m wallacea_ml split data\prepared\uavmulticrop_maize\manifest.json --root data\prepared\uavmulticrop_maize `
    --out data\splits\uavmulticrop_maize --group-by field --ratios 0.6,0.2,0.2
curl.exe -L -o artifacts\pretrained\yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
.venv\Scripts\python -m wallacea_ml train data\prepared\uavmulticrop_maize\manifest.json --split-dir data\splits\uavmulticrop_maize `
    --name uavmulticrop_maize_yolo11n
$M = "artifacts\models\uavmulticrop_maize_yolo11n"
foreach ($s in "val","test") { .venv\Scripts\python -m wallacea_ml predict data\prepared\uavmulticrop_maize\manifest.json `
    --split-dir data\splits\uavmulticrop_maize --split $s --weights $M\uavmulticrop_maize_yolo11n.pt `
    --out artifacts\eval\uavmulticrop_maize_yolo11n\pred_$s.json }
.venv\Scripts\python -m wallacea_ml threshold artifacts\eval\uavmulticrop_maize_yolo11n\pred_val.json --model-card $M\model_card.json
.venv\Scripts\python -m wallacea_ml evaluate artifacts\eval\uavmulticrop_maize_yolo11n\pred_test.json `
    --manifest data\prepared\uavmulticrop_maize\manifest.json --split-dir data\splits\uavmulticrop_maize --model-card $M\model_card.json
```

## Aturan evaluasi (ditegakkan oleh kode)

- **Split per grup**, bukan acak per foto: `field` (lahan/situs, disarankan), `flight`, `official` (split resmi
  penerbit, mis. split geografis sawit — tidak diacak ulang), `external` (seluruh dataset = test, untuk uji
  lintas dataset). Tile/potongan (`parent_image`) ikut foto induknya. `split` gagal (exit 1) bila grup,
  penerbangan, foto induk, atau berkas identik (sha256) muncul di > 1 split. `inspect --duplicates`
  menambah deteksi **hampir identik** (dHash) dan menandai yang lintas grup.
- Untuk data sendiri: tentukan split per lahan/penerbangan **sebelum** tiling/augmentasi. Augmentasi
  Ultralytics hanya diterapkan pada split train.
- **Val** untuk memilih `best.pt` & threshold (`threshold` menolak split selain `val`); **test** hanya untuk
  evaluasi akhir dengan threshold dari val. `evaluate` memberi `validation_kind = leaky_not_product_validation`
  bila gambar evaluasi bukan dari split yang diklaim.
- Laporan: precision, recall, F1, AP@0.5 (dari semua prediksi), MAE & bias hitungan per foto, galat relatif
  hitungan, MAE per petak (bila `plot_id`). Hasil memuat `domain` — dataset publik ≠ K919.
- Confidence model **bukan** ukuran akurasi survei. Fixture sintetis di `tests/` hanya menguji pipeline.

## Konvensi koordinat & orientasi (training = API = editor)

1. Piksel = gambar **setelah** EXIF Orientation (`app.imaging`). `prepare` menulis piksel terorientasi
   (byte asli disalin bila orientasi 1 dan JPEG/PNG; selain itu PNG lossless tanpa EXIF).
2. Dimensi COCO harus = dimensi terorientasi. Bila = dimensi mentah dan EXIF memutar 90°, gambar dilewati
   (`ORIENTATION_MISMATCH`) — tidak diputar diam-diam. Diuji: `test_prepare_skips_annotations_made_on_unrotated_pixels`.
3. COCO `bbox` piksel `[x,y,w,h]` → `[left, top, width, height]` 0–1 (API/editor) → YOLO `cx cy w h` 0–1.
   `category_id` dipetakan lewat `categories[].id`/nama dan `class_map` eksplisit; kategori dipakai tetapi
   tidak dipetakan = error.
4. API memprediksi **foto penuh** di-letterbox ke `WALLACEA_IMGSZ`; baseline dilatih pada imgsz yang sama
   (1280) tanpa tiling. Bila nanti memakai tiling/SAHI, API butuh jalur inferensi yang sama.
5. Gambar tanpa anotasi **bukan** contoh negatif kecuali config `empty_images_are_negative: true` (hanya bila
   dokumentasi dataset menyatakannya).

## Dataset

Ringkasan (detail & sumber: `configs/datasets.yaml`). Semua dataset CC-BY-4.0 → wajib atribusi.

| ID | Tanaman | Format | Split | Status | Peran |
|---|---|---|---|---|---|
| `uavmulticrop` | jagung, sugar beet, bunga matahari | COCO per sesi, kelas `plant` | tidak ada → per **situs** | diunduh-sebagian (JSON + PNG jagung) | **baseline jagung** |
| `matchplant` | jagung | COCO per gambar, kelas `maize`; TIFF 5472×3648 | tidak ada | diperiksa (+3 TIFF sampel) | uji eksternal |
| `oilpalm-ganoderma-v2` | sawit | COCO, 2 kelas status lapangan | **resmi geografis** | diperiksa | hanya bila tanaman = sawit; sensus via `class_maps/oilpalm_census.yaml` (penggabungan kelas terdokumentasi) |
| `neon-tree-evaluation` | tajuk pohon (hutan) | Pascal VOC XML | train/eval resmi | diperiksa | opsional, pembanding; konverter XML belum dibuat |

**Bobot MatchPlant** (`Pre-trained model_Faster R-CNN.pt`) adalah Faster R-CNN, bukan checkpoint
Ultralytics — tidak dapat dimuat adapter API meski berekstensi `.pt`. Memakainya butuh `Detector` baru
(belum dibuat); anotasinya dipakai untuk training/evaluasi YOLO.

## Labeling data sendiri (K919)

- **Satu jenis tanaman**, satu ketinggian/sudut. Kelas awal cukup `plant`; `check`/`gap` = keputusan manusia di aplikasi.
- Salin foto asli dari kartu/aplikasi drone (jangan screenshot). Catat per foto `field_id`, `flight_id`, `plot_id` (opsional).
- CVAT (dipilih): label persis `plant`; box per tanaman **terlihat**; tanaman terpotong di tepi dilabeli bila ≥ ~50 % terlihat.
  Dua pelabel pada ~20 foto yang sama untuk konsistensi. Ekspor **COCO 1.0**, lalu buat config `prepare`
  dengan `domain: k919` dan grup per lahan/penerbangan; `prepare` memeriksa orientasi terhadap EXIF.
- Bila ada hitungan lapangan per petak, simpan terpisah sebagai ground truth hitungan.

## Menyambungkan ke API

`model_card.json` → `api_env` berisi nilai siap pakai:

```powershell
$env:WALLACEA_MODEL_PATH = "D:\...\ml\artifacts\models\<nama>\<nama>.pt"
$env:WALLACEA_MODEL_ID = "<nama>"
$env:WALLACEA_LABEL_MAP_JSON = '{"plant":"plant"}'
$env:WALLACEA_IMGSZ = "1280"
$env:WALLACEA_CONFIDENCE = "<dipilih di val>"
cd ..\apps\api; .venv\Scripts\python -m pip install -r requirements-ai.txt; .venv\Scripts\python -m app
```

Tanpa `WALLACEA_MODEL_PATH`, API tetap mode manual dan `/analyze` → 503 `MODEL_NOT_CONFIGURED`.
Semua kandidat model dibuat `pending` dan harus ditinjau di aplikasi. `model_version` pada AnalysisRun =
`model_version` di model card (sha256 16 hex pertama bobot) — simpan card bersama bobot.

## Batas

Tidak ada kontrol drone/live video/SDK K919, GPS tanaman dari koordinat gambar, diagnosis penyakit, atau
rekomendasi pupuk. Tidak terdeteksi ≠ tanaman mati/hilang. Hitungan foto bertumpang tindih tidak boleh
dijumlahkan sebagai tanaman unik lahan. Tidak ada endpoint training di API.

## Status 2026-10-19

Semua angka di bawah berasal dari run nyata di mesin dev (Windows 11, RTX 4060 Laptop 8 GB untuk training,
CPU untuk DeepForest). Bukan hasil foto K919: **belum ada foto K919 MAX** di repo/mesin ini.

### A. Baseline jagung (YOLO11n fine-tune, adapter Ultralytics) — dataset publik UAVmulticrop

- Data: 51 crop plot jagung, 9 situs Prancis, 5.257 box (`prepare` 0 isu, 0 duplikat lintas grup).
- Split **per situs** (`--ratios 0.6,0.2,0.2`, seed `wallacea`, 0 kebocoran): train 5 situs/31 foto,
  val 2 situs (hermine, nerac)/12 foto, test 2 situs (pleinefougeres, villedieu)/8 foto/1.220 tanaman.
- Training: `yolo11n.pt` (ultralytics/assets v8.3.0, sha256 `0ebbc80d…`), imgsz 1280, 150 epoch, seed 20261018,
  6,5 menit (23:56:26–00:02:53). Bobot `uavmulticrop_maize_yolo11n.pt`, `model_version` **sha256:9c2e20232a359fd5**.
- Metrik Ultralytics di **val** (dipakai memilih best.pt — bukan evaluasi akhir): P 0.797, R 0.734, mAP50 0.762.
- Threshold dipilih di **val** (kriteria MAE hitungan): conf **0.25** (val: P 0.735, R 0.790, MAE 11.6/foto).
- **Evaluasi akhir TEST** (situs tak terlihat, lewat adapter API, IoU 0.5):
  precision **0.455**, recall **0.470**, AP50 **0.399**, MAE hitungan **15.0/foto** (rata-rata ±152 tanaman/foto),
  galat relatif hitungan **9.8 %**, bias +5.25. `validation_kind = group_held_out`.
  → Hitungan per foto cukup dekat, tetapi lokalisasi kotak pada situs baru lemah (generalisasi turun tajam dari val).
- Inferensi lewat API (TestClient, `WALLACEA_DETECTOR` otomatis): 144 & 288 kandidat `pending`, sama dengan
  evaluasi offline; `model_version` = model card.
- Belum dijalankan: uji eksternal MatchPlant (3 TIFF sampel sudah diunduh, `configs/prepare/matchplant.yaml` siap),
  uji pada foto K919.

### B. DeepForest pretrained (kandidat tajuk pohon) — notebook `02_pretrained_inference` & `03_evaluation`

Bobot `weecology/deepforest-tree` @ `cc21436b…`, `model_version` sha256:d37a7af0b5ba2754, CPU, conf 0.35,
patch 400. Dijalankan lewat adapter API yang sama dengan `/analyze`:

| Foto contoh NEON | Ukuran | Mode | Waktu (diukur) | Manusia | Model | Cocok | FP | Terlewat |
|---|---|---|---|---|---|---|---|---|
| 2019_YELL_…_crop.png | 1249×1035 | tile | 11.7 s | 279 | 293 | 186 | 107 | 93 |
| OSBS_029.png | 400×400 | image | 1.0 s | 61 | 49 | 38 | 11 | 23 |
| SOAP_061.png | 400×400 | image | 1.2 s | 37 (9 Alive, 28 Dead) | 30 | 21 | 9 | 16 |

Gabungan (IoU 0.5): precision 0.659, recall 0.650, AP 0.537; muat model 8–20 s sekali (20.5 s pada venv baru).
Dieksekusi ulang 2026-10-19 dari venv BERSIH (`requirements-pretrained.txt`, kernel baru per notebook): 01 (8 s),
02 (80 s; median 3× per foto: 1.1 s / 1.2 s / 15.0 s), 03 (8 s) — 0 error, angka identik.
`notebooks/05_deepforest_pretrained.ipynb` adalah versi gabungan lama (digantikan 02 + 03). Sebagian besar FP
berconfidence 0.35–0.45. Foto ini berasal dari ekosistem/sensor yang sama dengan data pengembang model
(hutan NEON, citra pesawat) — **tidak independen**, dan **bukan** ukuran kinerja pada lahan pertanian/K919.
