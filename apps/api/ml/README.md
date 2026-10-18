# WALLACEA ML — dataset, labeling, split, evaluasi

Status 2026-10-18: **belum ada dataset, label, bobot, atau metrik.** Toolkit ini menyiapkan jalurnya;
tidak ada pelatihan yang dijalankan dan tidak ada angka akurasi yang boleh dikutip dari repo ini.

## 1. Batasi ruang lingkup

- **Satu jenis tanaman** dan satu sudut pandang kamera (K919 MAX, ketinggian & waktu terbang konsisten).
- Kelas awal cukup `plant`. `check`/`gap` adalah keputusan manusia di aplikasi, bukan target model awal.
- Model COCO umum (orang, mobil, dll.) **bukan** model tanaman. Bobot pretrained hanya titik awal fine-tune.

## 2. Kumpulkan data

- Salin foto asli dari kartu/aplikasi drone, jangan screenshot/kompresi ulang.
- Catat per foto: `field_id` (lahan), `flight_id` (penerbangan), `plot_id` (petak, opsional), urutan.
- Bila ada hitungan lapangan per petak, simpan terpisah sebagai ground truth hitungan.
- Data mentah & bobot **tidak masuk Git** (`.gitignore`: `*.pt`, `*.onnx`, `datasets/`, `apps/api/ml/data/`).

## 3. Labeling (CVAT dipilih; Label Studio tidak dipasang)

1. Buat project CVAT dengan label persis `plant` (huruf kecil).
2. Gambar bounding box per tanaman yang **terlihat**; jangan menebak tanaman yang tertutup penuh.
3. Tanaman terpotong di tepi foto tetap dilabeli bila ≥ ~50 % terlihat; tulis aturan ini di catatan tim.
4. Dua orang melabeli sampel yang sama (mis. 20 foto) untuk mengukur konsistensi antarlabeler.
5. Ekspor format **YOLO 1.1** (`<cls> <cx> <cy> <w> <h>` ternormalisasi). Pastikan orientasi EXIF
   diterapkan sama seperti di aplikasi (CVAT menampilkan gambar terorientasi; cek beberapa foto potret).

## 4. Manifest & split

Buat `data/manifest.json` mengikuti `dataset_manifest.example.json` (contoh berisi nilai fiktif).

```powershell
cd apps/api/ml
..\.venv\Scripts\python -m wallacea_ml validate data\manifest.json
..\.venv\Scripts\python -m wallacea_ml split data\manifest.json --root data --out data\split --group-by field
```

- Split **berdasarkan lahan** (`field`, disarankan) atau penerbangan (`flight`), tidak acak per foto.
- Tile/potongan (`parent_image`) selalu ikut split foto induknya.
- Foto identik (sha256) di dua split, atau grup yang terbelah → `leaks` dan exit code 1.
- Butuh ≥ 3 grup. Dengan 3 lahan, tiap split hanya satu lahan: hasil akan sangat bervariasi.

## 5. Pelatihan (setelah data siap)

```powershell
..\.venv\Scripts\python -m pip install -r ..\requirements-ai.txt     # PyTorch, berat
..\.venv\Scripts\python -m wallacea_ml train data\manifest.json --split-dir data\split --weights C:\models\yolo-base.pt --dry-run
```

`train` menolak berjalan bila: manifest error, < 50 gambar berlabel, split bocor, atau bobot awal lokal
tidak ada. Tidak ada unduhan otomatis. Lisensi Ultralytics: AGPL-3.0/Enterprise (lihat REPO_SELECTION.md).

## 6. Evaluasi

Siapkan `predictions.json` (format di docstring `wallacea_ml/evaluate.py`) untuk gambar split **test**:

```powershell
..\.venv\Scripts\python -m wallacea_ml evaluate predictions.json --manifest data\manifest.json --split-dir data\split --out eval.json
```

Keluaran: precision, recall (IoU ≥ 0.5, greedy per confidence), MAE & bias galat hitungan per foto,
MAE per petak, serta `validation_kind`:

| `validation_kind` | Arti |
|---|---|
| `group_held_out` | Split test berisi grup yang tidak dilihat saat pelatihan. Boleh disebut evaluasi held-out **untuk data ini**. |
| `leaky_not_product_validation` | Ada kebocoran. Jangan disebut validasi produk. |
| `unverified_split` | Manifest/split tidak diberikan. Jangan disebut validasi produk. |

Bandingkan juga hitungan model vs **hitungan lapangan** per petak. Galat per petak menjumlahkan foto;
bila foto bertumpang tindih, itu bukan hitungan tanaman unik.

## 7. SAHI dan DeepForest — hanya setelah baseline

- SAHI (tile inference) hanya bila evaluasi baseline menunjukkan objek kecil terlewat. Dedup antar tile
  dalam satu foto ≠ dedup tanaman antar foto/penerbangan. SAHI tidak memulihkan detail yang blur.
- DeepForest hanya pembanding untuk kanopi pohon RGB, bukan model semua tanaman atau diagnosis.

## 8. Menyambungkan ke API

Set `WALLACEA_MODEL_PATH` ke `best.pt` hasil pelatihan dan `WALLACEA_LABEL_MAP_JSON='{"plant":"plant"}'`.
Semua keluaran tetap `pending` dan harus ditinjau di aplikasi. `model_version` di API = sidik jari
sha256 bobot; catat versi ini bersama laporan evaluasinya.
