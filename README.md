# WALLACEA — Survei pertanian dari foto drone

Aplikasi lokal untuk mengolah foto **setelah drone K919 MAX mendarat**: unggah foto, tandai tanaman,
tinjau kandidat model, dan buat laporan per foto. Model tanaman **belum dilatih**; aplikasi harus
dan bisa dipakai secara manual. Bukan alat kontrol drone, bukan peta GPS, bukan orthomosaic.

| Bagian | Path | Stack | Pemilik |
|---|---|---|---|
| API | `apps/api` | FastAPI, SQLAlchemy 2, Alembic, SQLite, Pillow | Claude |
| ML | `ml` | Python + JupyterLab, Ultralytics (opsional, venv terpisah) | Claude |
| Kontrak | `packages/contracts` | OpenAPI 3.1 (generated) + fixtures | Claude |
| Web | `apps/web` | React 19 + TypeScript 6 + Vite 8 (pnpm) | Codex |
| Starter lama | `legacy/starter-v01` | HTML/CSS/JS + IndexedDB (referensi) | — |
| Dokumen | `docs/architecture`, `docs/handoff`, `docs/requests` | | |

## Prasyarat (diverifikasi 2026-10-18)

- Node.js 24 LTS (`.node-version` = 24.18.0; Vite 8 butuh `^20.19 || >=22.12`), pnpm 12.9.1
- Python 3.12 (≥ 3.11)

## Menjalankan lokal

Terminal 1 — API (detail: `apps/api/README.md`). Setup sekali:

```powershell
cd apps\api
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
```

Lalu pilih **satu** dari tiga cara (tetap di folder `apps\api`):

```powershell
# A. Manual tanpa model (default). Pesan "Model tanaman belum dikonfigurasi" = normal, bukan error.
.venv\Scripts\python -m app

# B. Simulasi development: kotak kandidat buatan berlabel "SIMULASI — BUKAN AI". Hanya uji alur UI.
powershell -ExecutionPolicy Bypass -File .\scripts\run-simulation.ps1

# C. Model YOLO tanaman asli (berkas best.pt hasil training; pasang requirements-ai.txt dulu).
powershell -ExecutionPolicy Bypass -File .\scripts\check-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant'
powershell -ExecutionPolicy Bypass -File .\scripts\run-with-model.ps1 -ModelPath .\models\best.pt -LabelMap 'jagung=plant'
```

`models\best.pt` adalah **path berkas** untuk `-ModelPath`, bukan perintah. Mengetiknya sendirian di PowerShell
menghasilkan error "is not recognized". Belum ada model tanaman terlatih di repo ini. Cara membuatnya dari foto
drone berlabel: `apps/api/ml/README.md`. API: <http://127.0.0.1:8000/api/v1/docs>.

Terminal 2 — Web:

```powershell
pnpm install
pnpm dev:web                         # http://127.0.0.1:5173 (proxy /api → 127.0.0.1:8000)
```

Build/typecheck web: `pnpm build:web`, `pnpm typecheck:web`. Tes API: `cd apps/api; .venv\Scripts\python -m pytest`.
Tes ML: `cd ml; .venv\Scripts\python -m pytest` (setup & notebook: `ml/README.md`).

## Data dan backup

- Data runtime: `apps/api/var/` (SQLite + foto). Tidak masuk Git. Backup = salin folder ini saat API mati.
- Data starter lama ada di IndexedDB browser, **bukan** di Git. Ekspor dulu lewat UI starter
  (Pengaturan → Backup JSON) lalu impor ke API: `POST /api/v1/imports/starter-backup` (salinan baru).

## Kerja dua agen (Claude + Codex)

- Setiap agen bekerja di **worktree sendiri** dari `BASE_COMMIT` yang sama; jangan berbagi satu working tree.
  - `agent/claude-backend` → `D:\coding\wallacea-worktrees\claude-backend`
  - `agent/codex-frontend` → `D:\coding\wallacea-worktrees\codex-frontend`
- Handoff hanya lewat commit: `git show agent/codex-frontend:docs/handoff/codex.md`.
- Perubahan kontrak hanya oleh Claude (revisi + CHANGELOG); Codex mengajukan lewat `docs/requests/codex-*.md`.
- Integrasi di branch `integration/wallacea-mvp`. Tidak ada push, merge ke `main`, atau deploy otomatis.
- Dilarang: `reset --hard`, `git clean`, force push, stash perubahan orang lain.

## Batas produk

Tidak ada: blockchain, autopilot, sprayer, sensor tambahan, diagnosis penyakit, dosis pupuk, estimasi
panen, luas lahan otomatis. Koordinat foto bukan GPS. Hitungan antar foto bertumpang tindih bukan
jumlah tanaman unik. Detail: `docs/architecture/PROJECT_BRIEF.md`.
