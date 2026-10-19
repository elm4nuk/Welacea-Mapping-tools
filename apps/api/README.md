# WALLACEA API (`apps/api`)

FastAPI + Pydantic, SQLAlchemy 2 + Alembic, SQLite. Python ≥ 3.11 (diuji 3.12.10 di Windows).
Kontrak: `../../packages/contracts/openapi.yaml`. Arsitektur: `../../docs/architecture/ARCHITECTURE.md`.

## Setup

Windows PowerShell:

```powershell
cd apps/api
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
```

macOS/Linux:

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
```

## Jalankan (demo lokal, loopback)

```powershell
.venv\Scripts\python -m app            # http://127.0.0.1:8000, Swagger: /api/v1/docs
```

Migrasi Alembic berjalan otomatis saat startup (`WALLACEA_AUTO_MIGRATE=false` untuk mematikan;
lalu jalankan manual: `.venv\Scripts\alembic upgrade head`). Data runtime di `apps/api/var/`
(di-ignore Git): `wallacea.db` + `uploads/`. **Tidak ada autentikasi — jangan bind ke 0.0.0.0.**

## Tes

```powershell
.venv\Scripts\python -m pytest                       # semua test API
.venv\Scripts\python scripts\export_contract.py --check  # snapshot kontrak vs kode
```

Test pipeline analisis memakai detector **test double** — itu contract test, bukan uji akurasi model.
`tests/test_deepforest_adapter.py` memakai modul `deepforest` palsu untuk kontrak adapter; satu test menjalankan
**inferensi DeepForest asli** bila bobot sudah diunduh (selain itu di-skip dengan alasan).

## Mengubah kontrak

1. Ubah `app/schemas.py` / router.
2. Naikkan `CONTRACT_REVISION` di `app/__init__.py`, catat di `packages/contracts/CHANGELOG.md`.
3. `.venv\Scripts\python scripts\export_contract.py` (menulis ulang `openapi.yaml` + fixtures).
4. Perubahan skema DB: `.venv\Scripts\alembic revision --autogenerate -m "..."`, tinjau berkasnya.
5. Commit, lalu sampaikan SHA ke pemilik frontend.

## Model (opsional) — pilih lewat `WALLACEA_DETECTOR`

Tanpa model, `POST /photos/{id}/analyze` → `503 MODEL_NOT_CONFIGURED` dan mode manual tetap berjalan.
Ini perilaku yang benar. API **tidak pernah mengunduh bobot** saat request; unduhan selalu perintah eksplisit.

| `WALLACEA_DETECTOR` | `WALLACEA_MODEL_PATH` | Hasil |
|---|---|---|
| kosong (default) | kosong | manual (`not_configured`) |
| kosong | berkas `.pt` | Ultralytics (perilaku lama) |
| `none` | apa saja | manual |
| `ultralytics` | bobot YOLO `.pt` tim | kandidat tanaman (`target=plant`) |
| `deepforest` | **folder** hasil `download_deepforest.py` | kandidat **tajuk pohon** (`target=tree_crown`) |
| nilai lain | — | `state=error`, analyze → 503 `MODEL_UNAVAILABLE` |

Variabel lain: `WALLACEA_CONFIDENCE` (0.35), `WALLACEA_DEVICE` (`cpu`|`cuda`|`auto`, DeepForest; default `cpu`),
`WALLACEA_PATCH_SIZE` (400) / `WALLACEA_PATCH_OVERLAP` (0.05) untuk tile DeepForest, `WALLACEA_MODEL_PRELOAD`
(`true` = muat model di thread latar saat startup), `WALLACEA_INFERENCE_TIMEOUT_S` (120),
`WALLACEA_LABEL_MAP_JSON` (DeepForest default eksplisit `{"Tree":"plant"}`).

### DeepForest pretrained (demo prototype, CPU)

Baseline **kandidat tajuk pohon** dari `weecology/deepforest-tree` (DeepForest 2.1.0, MIT; bobot MIT). Dilatih
pada citra pesawat NEON ±10 cm/px — **bukan** model tanaman pertanian dan belum diuji pada foto K919.

```powershell
cd apps/api
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

Catatan Windows: `pandas` 3.0.6 diblokir **Smart App Control** pada mesin uji ("An Application Control policy has
blocked this file") → `requirements-deepforest.txt` mengunci `pandas==3.0.5`.

### Ultralytics (bobot tim)

```powershell
.venv\Scripts\python -m pip install -r requirements-ai.txt   # berat: PyTorch
$env:WALLACEA_DETECTOR = "ultralytics"
$env:WALLACEA_MODEL_PATH = "C:\models\jagung-v0.pt"
$env:WALLACEA_LABEL_MAP_JSON = '{"nama_kelas_model":"plant"}'
.venv\Scripts\python -m app
```

Model COCO umum bukan model tanaman. Bobot DeepForest/Faster R-CNN **tidak** dimuat lewat adapter ini walau
berekstensi `.pt`. Lisensi Ultralytics (AGPL-3.0/Enterprise): lihat `docs/architecture/REPO_SELECTION.md`.
Training & evaluasi model tim: `ml/README.md`.
