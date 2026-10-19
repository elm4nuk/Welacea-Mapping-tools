# Handoff Claude (backend & integrasi) — 2026-10-18

## Commit

| | SHA | Branch |
|---|---|---|
| BASE_COMMIT (kontrak siap) | `15a7408312eff3fe03995c58de4dc46659fcc890` | `main`, titik awal kedua worktree |
| Pekerjaan backend setelah baseline | `e91fc82` | `agent/claude-backend` |
| Handoff ini | commit setelah `e91fc82` | `agent/claude-backend` |

Worktree: backend `D:\coding\wallacea-worktrees\claude-backend`, frontend `D:\coding\wallacea-worktrees\codex-frontend`.

## Status

- **CONTRACT_READY**: kontrak API v1 **revisi 1**, `packages/contracts/openapi.yaml` (`info.version` 1.1.0),
  37 fixtures dari respons API sungguhan. Tidak ada perubahan kontrak setelah baseline.
- Backend MVP selesai untuk mode manual + jalur model yang jujur. **Belum ada integrasi**: branch frontend
  belum menyatakan `FRONTEND_READY` (saat dicek 17:35, perubahan Codex masih belum di-commit).

## Scope selesai

- Survei CRUD + pagination + `If-Match` opsional; survei contoh `POST /demo/surveys` (PNG ilustrasi berlabel).
- Upload foto per berkas: validasi isi (JPEG/MPO/PNG/WebP), 20 MB, 60 MP, berkas terpotong/animasi ditolak,
  EXIF orientation → dimensi pasca-orientasi + `display` terorientasi, `captured_at`, `has_exif_gps`
  (tidak dipakai sebagai lokasi), sha256, nama storage acak, thumbnail ≤ 512 px, warning duplikat,
  cleanup berkas saat gagal, 413 sebelum body di-spool.
- Anotasi point/bbox ternormalisasi, validasi finite/0–1/bbox dalam gambar, maks 3000/foto,
  revision + `If-Match` wajib (update atomik bersyarat), 409 dengan `details.current`.
- Analisis: interface `Detector`, `UnconfiguredDetector` (503 `MODEL_NOT_CONFIGURED`, tanpa run palsu),
  `UltralyticsDetector` (bobot `.pt` lokal, label map eksplisit, `model_version` = sidik jari sha256 bobot),
  run persist, timeout → 504, run terputus restart → `failed/INTERRUPTED`, kontrol run berulang
  (`reject` / `replace_pending` / `append`), maksimal satu run `running` per foto (indeks unik DB).
- Impor deteksi (format starter) dengan cek dimensi terorientasi & sha256.
- Laporan per foto + temuan + disclaimer; CSV (BOM, anti formula injection).
- Impor backup starter `schemaVersion 1` sebagai salinan, atomik, label demo & catatan terjaga.
- Toolkit ML (`apps/api/ml`): manifest, split per lahan/penerbangan + cek kebocoran, evaluasi
  precision/recall/galat hitungan, wrapper training yang menolak tanpa data. **Tidak ada pelatihan dijalankan.**
- `docs/architecture/REPO_SELECTION.md`: lisensi & rilis dicek ke GitHub 2026-10-18.

## Endpoint (`/api/v1`)

`GET /health` · `GET|POST /surveys` · `GET|PATCH|DELETE /surveys/{id}` · `POST /demo/surveys` ·
`POST|GET /surveys/{id}/photos` · `GET|DELETE /photos/{id}` · `GET /photos/{id}/content|display|thumbnail` ·
`GET|POST /photos/{id}/annotations` · `PATCH|DELETE /annotations/{id}` · `POST /photos/{id}/analyze` ·
`POST /photos/{id}/detections/import` · `GET /photos/{id}/analysis-runs` · `GET /surveys/{id}/report` ·
`GET /surveys/{id}/export.csv` · `POST /imports/starter-backup`. Swagger: `/api/v1/docs`.

## Menjalankan

```powershell
cd apps/api
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
.venv\Scripts\python -m app                 # 127.0.0.1:8000
.venv\Scripts\python -m pytest              # tes
.venv\Scripts\python scripts\export_contract.py --check
# web (dari root): pnpm install; pnpm dev:web  → 127.0.0.1:5173, proxy /api
```

Dependency: `apps/api/requirements.lock.txt` (FastAPI 0.143.5, Starlette 1.8.0, Pydantic 2.14.1,
SQLAlchemy 2.0.55, Alembic 1.20.0, Pillow 13.0.0, uvicorn 0.54.0). Opsional: `requirements-ai.txt` (Ultralytics).
Web baseline: Node 24.18 LTS, pnpm 12.9.1, Vite 8.3.4, React 19.3.1, TypeScript 6.0.3.

## Tes yang benar-benar dijalankan

- `pytest`: **117 lulus** di worktree backend (107 di baseline + 10 toolkit ML), Windows 11, Python 3.12.10.
  Pipeline analisis memakai **detector test double** → contract test, **bukan** uji akurasi model.
  Adapter Ultralytics diuji dengan modul `ultralytics` palsu (paket asli tidak dipasang).
- Checkout bersih baseline: `pnpm install --frozen-lockfile`, `pnpm typecheck:web`, `pnpm build:web`,
  venv baru + `pip install -r requirements.lock.txt` + `pytest` + `export_contract.py --check` → lulus.
- Server nyata (`python -m app`, uvicorn): `GET /health` 200, buat survei 201, upload PNG 201,
  upload 25 MB → 413 sebelum diproses, `netstat` menunjukkan listen hanya di `127.0.0.1`.

## TIDAK dijalankan / belum terverifikasi

- Browser test / E2E UI (menunggu frontend Codex; fase integrasi).
- Inferensi model tanaman nyata (tidak ada bobot), paket Ultralytics/PyTorch asli.
- Foto K919 MAX nyata (format, EXIF, resolusi, orientasi belum dilihat).
- PostgreSQL (struktur siap, belum diuji). SQLAlchemy 2.1 belum diuji (dikunci `<2.1`).

## Limitasi

- Tanpa autentikasi; hanya untuk loopback. Satu proses, SQLite.
- Inferensi sinkron; thread yang melewati timeout tidak bisa dihentikan paksa (hasil dibuang, lock detector tertahan sampai selesai).
- Undo penghapusan kandidat model tidak bisa memulihkan `source=model` (POST manual selalu manual) — gunakan `rejected`.
- Belum ada ekspor backup format baru (hanya impor starter). Backup = salin `apps/api/var/` saat API mati.
- `captured_at` tanpa zona waktu (EXIF umumnya tidak menyimpannya). HEIC/RAW tidak didukung.
- Foto survei contoh dari backup starter (SVG) diganti placeholder PNG; posisi penanda contoh tidak lagi cocok dengan gambar ilustrasi asli.

## Blocker

- Dataset & bobot model tanaman belum ada → jalur AI hanya bisa diuji dengan test double.
- Kualitas/format foto K919 belum diketahui → batas 20 MB/60 MP dan dukungan format perlu dicek dengan foto nyata.

## Catatan untuk Codex

- Kontrak: `kind` = `plant | check | gap` (bukan `inspect`); bbox `[left, top, width, height]`; editor pakai `display_url`.
- Berkas editor yang sempat ada sebagai untracked di folder utama (`apps/web/src/features/editor/*`) tidak
  dimasukkan ke baseline. Saat dicek 17:35 berkas itu sudah tidak ada di folder utama dan ada `src/features/`
  (belum di-commit) di worktree Codex.
- Usulan perubahan kontrak → `docs/requests/codex-*.md` di branch frontend.

## Langkah berikut

1. Tunggu `FRONTEND_READY` + SHA dari Codex; baca `git show agent/codex-frontend:docs/handoff/codex.md`.
2. Integrasi di `integration/wallacea-mvp` dari baseline: merge `agent/claude-backend` + `agent/codex-frontend`,
   jalankan API + web, typecheck, build, pytest, E2E alur satu foto dengan API sungguhan + kondisi tanpa model.
3. Uji dengan beberapa foto K919 nyata (orientasi, ukuran, EXIF).
4. Tim AI/ML: mulai labeling satu tanaman sesuai `apps/api/ml/README.md`.
