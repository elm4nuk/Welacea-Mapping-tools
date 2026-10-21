# Melatih model tanaman sendiri → `best.pt` (YOLO detection)

Pipeline minimal dan jujur untuk membuat bobot yang bisa dipakai WALLACEA API. Bahannya **foto drone milik
Anda yang sudah diberi bounding box**. Tanpa foto berlabel tidak ada model tanaman; aplikasi tetap bisa dipakai
secara manual.

| Berkas | Fungsi |
|---|---|
| `dataset.yaml.example` | Templat konfigurasi dataset Ultralytics (salin ke folder dataset Anda) |
| `dataset-example/README.md` | Struktur folder `images/` + `labels/` dan format baris label |
| `yolo_dataset.py` | Pemeriksaan dataset (tanpa PyTorch): split, pasangan foto–label, format, kelas |
| `train.py` | Periksa dataset → latih → salin `best.pt` + model card → evaluasi split test |
| `validate_model.py` | Evaluasi ulang `.pt` pada split berlabel → laporan JSON |

Toolkit yang lebih lengkap (katalog dataset publik, konversi COCO/VOC → YOLO, split tanpa kebocoran per lahan,
notebook) ada di `ml/` di root repo (`../../../ml/README.md`). Folder ini untuk jalur paling sederhana.

**Tidak masuk Git:** dataset, `runs/`, `*.pt`, dan isi `apps/api/models/` (lihat `.gitignore`).
**Tidak ada unduhan diam-diam:** bobot awal harus berkas lokal, key `download` di `dataset.yaml` diabaikan, AMP dan
plot (yang bisa memicu unduhan kecil di Ultralytics) mati kecuali diminta `--amp` / `--plots`.

## 1. Siapkan dataset

1. Kumpulkan foto drone dari beberapa lahan dan penerbangan.
2. Beri **bounding box** setiap tanaman target dengan alat anotasi (CVAT, Label Studio, dll.), lalu ekspor format
   **YOLO**. Satu kelas per jenis tanaman, mis. `jagung`.
3. Bagi menjadi **train / val / test** per lahan atau per penerbangan (mis. 70/15/15). Foto test tidak boleh
   berasal dari penerbangan yang juga dipakai train, karena foto yang bertumpang tindih membuat angka terlalu bagus.
4. Susun folder seperti `dataset-example/README.md` dan salin `dataset.yaml.example` → `D:\dataset-jagung\dataset.yaml`.

## 2. Pasang dependensi (sekali, berat)

```powershell
cd apps\api
# CPU (±1 GB). GPU NVIDIA: ganti URL index dengan versi CUDA dari https://pytorch.org/get-started/locally/
.venv\Scripts\python -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements-ai.txt
```

Bila `pip` gagal dengan `[Errno 2] No such file or directory … torch\include\…` dan petunjuk *Long Path support*,
folder venv terlalu dalam (lebih dari 260 karakter). Pindahkan repo ke path pendek (mis. `D:\coding\wallacea`) atau
aktifkan Windows Long Paths.

Bobot awal (fine-tune) diunduh **sendiri, sadar, sekali**, mis. `yolo11n.pt` dari rilis resmi Ultralytics
(<https://github.com/ultralytics/assets/releases>), lalu simpan di luar Git, mis. `D:\bobot\yolo11n.pt`. Lisensi
Ultralytics dan bobotnya: AGPL-3.0 atau Enterprise (lihat `docs/architecture/REPO_SELECTION.md`).

## 3. Periksa lalu latih

```powershell
cd apps\api
.venv\Scripts\python ml\train.py --data "D:\dataset-jagung\dataset.yaml" --check-only
.venv\Scripts\python ml\train.py --data "D:\dataset-jagung\dataset.yaml" --base-weights "D:\bobot\yolo11n.pt" `
    --name jagung-v1 --epochs 100 --imgsz 1280 --batch 8 --device 0      # --device cpu bila tanpa GPU
```

Hasil:
- `ml\runs\jagung-v1\weights\best.pt`: bobot terbaik menurut validasi (inilah "best.pt").
- `apps\api\models\jagung-v1.pt` + `jagung-v1.model_card.json`: salinan siap pakai, sha256, kelas, jumlah data,
  dan metrik split test.

`imgsz` sebaiknya sama dengan `WALLACEA_IMGSZ` API (default 1280).

## 4. Evaluasi

```powershell
.venv\Scripts\python ml\validate_model.py --model .\models\jagung-v1.pt --data "D:\dataset-jagung\dataset.yaml"
```

Precision, recall, dan mAP **hanya berlaku untuk split yang dievaluasi**. Tidak ada angka akurasi yang boleh
diklaim tanpa evaluasi seperti ini, dan angka dari satu lahan bukan jaminan untuk lahan, kamera, atau ketinggian
terbang lain. Di aplikasi, kandidat tetap `pending` sampai ditinjau manusia.

## 5. Pakai di API

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-model.ps1 -ModelPath .\models\jagung-v1.pt -LabelMap 'jagung=plant'
powershell -ExecutionPolicy Bypass -File .\scripts\run-with-model.ps1 -ModelPath .\models\jagung-v1.pt -LabelMap 'jagung=plant'
```

## Diverifikasi (2026-10-20)

Uji jalan pada dataset **sintetis** 14 gambar (lingkaran hijau), 1 epoch CPU dari `yolo11n.pt` lokal:
`--check-only` → train → `best.pt` + model card → `validate_model.py` → `check-model.ps1` lulus. Tidak ada unduhan.
Metrik = 0 (wajar untuk 1 epoch); ini uji pipeline, bukan model tanaman.
