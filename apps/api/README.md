# WALLACEA API (`apps/api`)

FastAPI + Pydantic, SQLAlchemy 2 + Alembic, SQLite. Python ≥ 3.11 (diuji 3.12.10 di Windows).
Kontrak: `../../packages/contracts/openapi.yaml`. Arsitektur: `../../docs/architecture/ARCHITECTURE.md`.

## Setup (sekali)

Windows PowerShell, dari root repo:

```powershell
cd apps\api
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
```

macOS/Linux: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.lock.txt`.

Semua perintah di bawah dijalankan **dari folder `apps\api`**. Web: terminal kedua di root repo → `pnpm dev:web`
→ <http://127.0.0.1:5173> (proxy `/api` → `127.0.0.1:8000`).

## Tiga cara menjalankan

| | Kapan | Tombol "Analisis foto" | `GET /api/v1/health` → `model` |
|---|---|---|---|
| **A. Manual** (default) | Belum punya bobot model | 503 `MODEL_NOT_CONFIGURED`; tandai manual | `mode=manual`, `state=not_configured` |
| **B. Simulasi** | Menguji alur UI tanpa model | kotak buatan **SIMULASI — BUKAN AI** | `mode=simulation`, `state=loaded` |
| **C. Model asli** | Ada `best.pt` hasil training | kandidat dari model | `mode=model`, `state=loaded` |

Pesan "Model tanaman belum dikonfigurasi" di skenario A **bukan error**. Itu tanda aplikasi jujur bahwa belum ada
model. Survei, unggah foto, penandaan manual, review, dan laporan tetap berjalan penuh.

### A. Manual tanpa model

```powershell
.venv\Scripts\python -m app            # http://127.0.0.1:8000, Swagger: /api/v1/docs
```

### B. Simulasi development (SIMULASI — BUKAN AI)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-simulation.ps1
```

Analisis membuat 3–8 kotak buatan per foto, **deterministik** (foto sama → kotak sama), berstatus `pending`,
`confidence` kosong, `model_id=simulation-not-ai`, label "SIMULASI — BUKAN AI". Laporan survei yang memuat kandidat
simulasi mendapat disclaimer khusus. Gunanya hanya menguji alur analisis → review → simpan → laporan. **Jangan dipakai
untuk keputusan lapangan.** Simulasi hanya aktif lewat `WALLACEA_DETECTOR=simulation`; tidak pernah menjadi
fallback otomatis (bobot hilang/rusak → `state=error`, bukan simulasi).

### C. Model AI tanaman asli (`best.pt`)

`best.pt` adalah **berkas bobot** hasil training YOLO detection pada foto drone berlabel (`ml\README.md`), atau
diberikan tim ML. Belum ada model tanaman terlatih di repo ini, dan API maupun skrip tidak pernah mengunduh bobot.

> ⚠️ Path `.pt` bukan perintah. Mengetik `models\best.pt` atau `C:\Model\best.pt` sendirian di PowerShell
> menghasilkan error `The term '…best.pt' is not recognized as the name of a cmdlet…`. Path itu diberikan sebagai
> **nilai** parameter `-ModelPath`, seperti di bawah.

```powershell
# 1) Dependensi model (sekali, berat ±1 GB). Tidak dipasang otomatis oleh skrip mana pun.
.venv\Scripts\python -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements-ai.txt

# 2) Letakkan bobot, mis. apps\api\models\best.pt (folder di-ignore Git), lalu periksa:
powershell -ExecutionPolicy Bypass -File .\scripts\check-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant'

# 3) Jalankan API dengan model (memeriksa ulang dulu; env hanya berlaku untuk proses ini):
powershell -ExecutionPolicy Bypass -File .\scripts\run-with-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant'
```

Path dengan spasi: bungkus dengan tanda kutip, mis. `-ModelPath "C:\Model Tanaman\best.pt"`.

`check-model.ps1` memeriksa: berkas ada, ekstensi `.pt`, paket `ultralytics` terpasang, bobot bisa dibuka, model
bertipe deteksi, isi `model.names`, dan kecocokan label map. Opsional `-Image foto.jpg` untuk satu inferensi uji.
Di akhir, skrip mencetak perintah `run-with-model.ps1` yang siap disalin. Exit code: 0 siap, 1 model bermasalah,
2 argumen/berkas.

**Label map** = nama kelas model → jenis penanda WALLACEA (`plant`, `check`, `gap`). Kunci harus sama persis
dengan `model.names` yang ditampilkan `check-model.ps1`; kelas yang tidak dipetakan diabaikan. Dua bentuk diterima:
- sederhana: `-LabelMap 'jagung=plant,gulma=check'` (disarankan; aman di semua shell)
- JSON: `-LabelMap '{"jagung":"plant"}'`. Catatan: `powershell -File …` di PowerShell 5.1 membuang tanda kutip ganda
  di dalam argumen, sehingga JSON tiba sebagai `{jagung:plant}`. API membaca bentuk itu juga, tetapi kunci yang
  mengandung `:` atau `,` hanya aman dalam bentuk JSON lewat `.env`.

Opsi `run-with-model.ps1`: `-Confidence 0.25` (default 0.35), `-Port 8000`, `-ModelId nama`, `-NoPreload`,
`-SkipCheck`. `-ExecutionPolicy Bypass` hanya berlaku untuk satu perintah itu; tidak mengubah kebijakan sistem.

Model COCO umum (`yolo11n.pt` dll.) bukan model tanaman. API tetap menjalankannya bila label map cocok (mis.
`potted plant=plant`), tetapi melabelinya `diagnostic_code=GENERIC_COCO_MODEL` dan "Kandidat dari model COCO umum
(BUKAN model tanaman)". Bobot DeepForest/Faster R-CNN tidak dimuat lewat adapter ini walau berekstensi `.pt`.
Lisensi Ultralytics (AGPL-3.0/Enterprise): `docs/architecture/REPO_SELECTION.md`.

### Konfigurasi lewat `.env` (opsional)

`python -m app` memuat `apps\api\.env` bila ada (`--env-file PATH` untuk berkas lain, `--no-env-file` untuk
mematikan). Salin `.env.example` → `.env`. Variabel yang sudah diset di terminal atau oleh skrip tidak ditimpa.
Path Windows ditulis apa adanya (`WALLACEA_MODEL_PATH=C:\Model Tanaman\best.pt`). Berkas `.env` tidak masuk Git.

## Diagnosis `health.model.diagnostic_code`

| Kode | Arti | Perbaikan |
|---|---|---|
| `MODEL_PATH_NOT_SET` | Mode manual (default) | Bukan error. Lihat skenario C bila ingin analisis otomatis |
| `MODEL_FILE_NOT_FOUND` | Path bobot tidak ada | Periksa path di `message`; kutip bila ada spasi |
| `MODEL_FILE_NOT_PT` | Bukan berkas `.pt` (folder/`.onnx`) | Tunjuk berkas `…\weights\best.pt` |
| `DEPENDENCY_MISSING` | `ultralytics` belum terpasang | `pip install -r requirements-ai.txt` |
| `LABEL_MAP_INVALID` | Label map tak terbaca / nilai salah | Bentuk `kelas=plant` |
| `LABEL_MAP_MISMATCH` | Tidak ada kelas model di label map | Salin nama kelas dari `check-model.ps1` |
| `NOT_DETECTION_MODEL` | Model seg/cls/pose | Latih model deteksi |
| `MODEL_LOAD_FAILED` | `.pt` rusak/versi tak cocok | Jalankan `check-model.ps1` untuk detail |
| `DETECTOR_CONFIG_INVALID` | `WALLACEA_DETECTOR`/confidence salah | Lihat tabel variabel |
| `GENERIC_COCO_MODEL` | Model COCO umum termuat | Hanya untuk uji integrasi |
| `SIMULATION_ACTIVE` | Mode simulasi | Jalankan tanpa `WALLACEA_DETECTOR=simulation` untuk keluar |

`POST /photos/{id}/analyze` yang gagal 503 membawa kode yang sama di `error.details.diagnostic_code`.

## Variabel model — `WALLACEA_DETECTOR`

| `WALLACEA_DETECTOR` | `WALLACEA_MODEL_PATH` | Hasil |
|---|---|---|
| kosong (default) | kosong | manual (`not_configured`) |
| kosong | berkas `.pt` | Ultralytics |
| `none` | apa saja | manual |
| `ultralytics` | bobot YOLO `.pt` tim | kandidat tanaman (`target=plant`) |
| `deepforest` | **folder** hasil `download_deepforest.py` | kandidat **tajuk pohon** (`target=tree_crown`) |
| `simulation` | diabaikan | **SIMULASI — BUKAN AI** (`target=simulation`) |
| nilai lain | — | `state=error`, analyze → 503 `MODEL_UNAVAILABLE` |

Variabel lain: `WALLACEA_LABEL_MAP_JSON`, `WALLACEA_CONFIDENCE` (0.35), `WALLACEA_IMGSZ` (1280),
`WALLACEA_MODEL_ID`, `WALLACEA_DEVICE` (`cpu`|`cuda`|`auto`, DeepForest; default `cpu`), `WALLACEA_PATCH_SIZE` (400) /
`WALLACEA_PATCH_OVERLAP` (0.05) untuk tile DeepForest, `WALLACEA_MODEL_PRELOAD` (`true` = muat model di thread latar
saat startup), `WALLACEA_INFERENCE_TIMEOUT_S` (120).

### DeepForest pretrained (demo prototype, CPU)

Baseline **kandidat tajuk pohon** dari `weecology/deepforest-tree` (DeepForest 2.1.0, MIT; bobot MIT). Dilatih
pada citra pesawat NEON ±10 cm/px — **bukan** model tanaman pertanian dan belum diuji pada foto K919.

```powershell
# 1) PyTorch CPU (±200 MB) + DeepForest (versi teruji)
.venv\Scripts\python -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements-deepforest.txt
# 2) Unduh bobot SEKALI (Hugging Face weecology/deepforest-tree @ commit teruji + backbone torchvision ±230 MB)
.venv\Scripts\python scripts\download_deepforest.py
# 3) Jalankan
$env:WALLACEA_DETECTOR = "deepforest"
$env:WALLACEA_MODEL_PATH = "$PWD\var\models\deepforest-tree"
$env:WALLACEA_MODEL_PRELOAD = "true"
.venv\Scripts\python -m app
```

Cek: `GET /api/v1/health` → `model.state = "loaded"`, `adapter = "deepforest"`, `target = "tree_crown"`,
`model_version = "sha256:d37a7af0b5ba2754"`. Foto contoh untuk diunggah: `samples/deepforest-neon/*.png`.

Identitas: repo `weecology/deepforest-tree`, revisi `cc21436bc5d572dde8ff5f93c1e71a32f563cace`, `model.safetensors`
sha256 `d37a7af0b5ba2754282a80d41b4c7b66e8c7149234df5bf3f41bdaf57d329fc8` (dicatat di
`var/models/deepforest-tree/wallacea_model.json`). DeepForest 2.1.0 membangun RetinaNet lewat torchvision yang
mengambil backbone ImageNet `resnet50-0676ba61.pth` (lalu ditimpa bobot DeepForest); skrip unduh mengambilnya
ke `torch_home/` folder model dan adapter menolak memuat (503) bila berkas itu tidak ada.

## Catatan Windows

- `pandas` 3.0.6 diblokir **Smart App Control** pada mesin uji ("An Application Control policy has blocked this
  file") → `requirements-deepforest.txt` mengunci `pandas==3.0.5`.
- `pip install torch` gagal dengan `[Errno 2] No such file or directory … torch\include\…` bila path venv lebih dari
  260 karakter. Letakkan repo di path pendek (mis. `D:\coding\wallacea`) atau aktifkan Windows Long Paths.
- Desimal: skrip mengirim confidence dengan titik (`0.25`) walau Windows memakai format Indonesia (koma).

## Data, migrasi, keamanan

Migrasi Alembic berjalan otomatis saat startup (`WALLACEA_AUTO_MIGRATE=false` untuk mematikan; lalu jalankan manual:
`.venv\Scripts\alembic upgrade head`). Data runtime di `apps/api/var/` (di-ignore Git): `wallacea.db` + `uploads/`.
**Tidak ada autentikasi — jangan bind ke 0.0.0.0.**

## Tes

```powershell
.venv\Scripts\python -m pytest                           # semua test API
.venv\Scripts\python scripts\export_contract.py --check  # snapshot kontrak vs kode
.venv\Scripts\alembic check                              # model ORM vs migrasi (tanpa perubahan = lulus)
```

Test pipeline analisis memakai detector **test double** — itu contract test, bukan uji akurasi model.
`tests/test_model_onboarding.py` dan `tests/test_ultralytics_adapter.py` memakai modul `ultralytics` palsu;
`tests/test_deepforest_adapter.py` memakai modul `deepforest` palsu, dan satu test menjalankan **inferensi DeepForest
asli** bila bobot sudah diunduh (selain itu di-skip dengan alasan).

## Mengubah kontrak

1. Ubah `app/schemas.py` / router.
2. Naikkan `CONTRACT_REVISION` di `app/__init__.py`, catat di `packages/contracts/CHANGELOG.md`.
3. `.venv\Scripts\python scripts\export_contract.py` (menulis ulang `openapi.yaml` + fixtures).
4. Perubahan skema DB: `.venv\Scripts\alembic revision --autogenerate -m "..."`, tinjau berkasnya.
5. Commit, lalu sampaikan SHA ke pemilik frontend.
