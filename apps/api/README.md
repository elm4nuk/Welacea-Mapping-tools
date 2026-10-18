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

## Mengubah kontrak

1. Ubah `app/schemas.py` / router.
2. Naikkan `CONTRACT_REVISION` di `app/__init__.py`, catat di `packages/contracts/CHANGELOG.md`.
3. `.venv\Scripts\python scripts\export_contract.py` (menulis ulang `openapi.yaml` + fixtures).
4. Perubahan skema DB: `.venv\Scripts\alembic revision --autogenerate -m "..."`, tinjau berkasnya.
5. Commit, lalu sampaikan SHA ke pemilik frontend.

## Model tanaman (opsional)

Tanpa bobot, `POST /photos/{id}/analyze` → `503 MODEL_NOT_CONFIGURED`. Ini perilaku yang benar.
Bila tim sudah punya bobot deteksi Ultralytics `.pt` milik sendiri:

```powershell
.venv\Scripts\python -m pip install -r requirements-ai.txt   # berat: PyTorch
$env:WALLACEA_MODEL_PATH="C:\models\jagung-v0.pt"
$env:WALLACEA_LABEL_MAP_JSON='{"nama_kelas_model":"plant"}'
.venv\Scripts\python -m app
```

Tidak ada bobot yang diunduh otomatis. Model COCO umum bukan model tanaman.
Lisensi Ultralytics (AGPL-3.0/Enterprise): lihat `docs/architecture/REPO_SELECTION.md`.
