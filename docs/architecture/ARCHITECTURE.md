# WALLACEA — Arsitektur

Pemilik: Claude. Kontrak API: revisi 2 (`packages/contracts/openapi.yaml`, `info.version` 1.2.0).

## Gambaran

```
 Browser (apps/web, React+Vite :5173)
   │  /api/*  ──proxy Vite──▶  FastAPI (apps/api, 127.0.0.1:8000, prefix /api/v1)
   │                              ├─ SQLAlchemy 2 + Alembic ─▶ SQLite  apps/api/var/wallacea.db
   │                              ├─ Storage lokal            ─▶ apps/api/var/uploads/xx/<uuid>.<ext>
   │                              └─ Detector (interface)
   │                                   ├─ UnconfiguredDetector  (default → 503 MODEL_NOT_CONFIGURED)
   │                                   ├─ UltralyticsDetector   (bobot YOLO .pt tim, opsional)
   │                                   └─ DeepForestDetector    (folder bobot weecology/deepforest-tree lokal,
   │                                                             kandidat TAJUK POHON, CPU, opsional)
   ▼
 Foto drone disalin manual dari kartu/aplikasi K919 → diunggah per berkas.
```

Tidak ada antrean (Redis/Celery). Analisis satu foto berjalan **sinkron** dengan batas waktu.

## Struktur repo

| Path | Isi | Pemilik |
|---|---|---|
| `apps/api/app/` | FastAPI: `main.py`, `schemas.py` (kontrak), `models.py` (ORM), `routers/`, `inference/`, `imaging.py`, `storage.py` | Claude |
| `apps/api/alembic/` | Migrasi skema | Claude |
| `apps/api/tests/` | pytest (kontrak, validasi, persistensi, pipeline) | Claude |
| `apps/api/scripts/export_contract.py` | Generate snapshot OpenAPI + fixtures dari API sungguhan | Claude |
| `ml/` | Workspace ML (Python + JupyterLab, venv terpisah): katalog dataset, validasi anotasi, prepare COCO→YOLO, split tanpa kebocoran, training, evaluasi via adapter API, notebook 01–04 | Claude |
| `packages/contracts/` | `openapi.yaml`, `fixtures/`, `CHANGELOG.md` | Claude |
| `apps/web/` | Frontend React | Codex |
| `legacy/starter-v01/` | Starter asli (referensi migrasi, jangan dihapus) | — |

## Model data

```
Survey 1─* Photo 1─* Annotation *─0..1 AnalysisRun
                 1─* AnalysisRun
```

- **Survey**: `name, crop_type, location_label, survey_date, notes, is_demo, revision, photo_count`.
- **Photo**: `width/height` **setelah orientasi EXIF**, `sha256` byte asli, `exif_orientation`,
  `has_exif_gps`, `captured_at` (jam lokal kamera, tanpa zona), `georef_status="none"`, `revision`,
  `duplicate_photo_ids`, `counts`, serta URL `content` (asli), `display` (terorientasi), `thumbnail`.
- **Annotation**: `kind plant|check|gap`, `geometry_type point|bbox`, `x,y` (untuk bbox = pusat kotak,
  dihitung server), `bbox [left, top, width, height]`, `source manual|model`, `review_status
  pending|accepted|rejected`, `confidence`, `model_label`, `analysis_run_id`, `revision`.
- **AnalysisRun**: `run_type inference|import`, `model_id`, `model_version`, `input_sha256`,
  `status running|succeeded|failed`, `candidate_count`, `parameters`, `error_code`.

Constraint DB: FK `ON DELETE CASCADE`, CHECK untuk enum & rentang 0–1, indeks unik parsial
"maksimal satu run `running` per foto".

## Konvensi koordinat dan orientasi

1. Server membaca tag EXIF Orientation, menerapkan `ImageOps.exif_transpose`, dan menyimpan dimensi hasilnya.
2. `GET /photos/{id}/display` mengembalikan gambar yang **sudah** terorientasi (turunan disimpan hanya bila
   orientasi ≠ 1). Editor harus memakai `display_url`, bukan `content_url`.
3. Semua `x, y, bbox` dinormalisasi terhadap `display` (= `Photo.width × Photo.height`).
4. Detector menerima gambar terorientasi yang sama. Impor deteksi wajib `image_width/height` = dimensi
   terorientasi; bila tertukar, API memberi petunjuk orientasi di pesan `DETECTION_MISMATCH`.
5. `content_url` = byte asli persis (sha256 cocok), untuk unduhan/arsip.

## Aturan hitungan

- Hitungan tanaman resmi foto = `kind=plant AND review_status=accepted` (`counts.plant_accepted`).
- Penanda manual default `accepted`; kandidat model selalu dibuat `pending` dan hanya bisa dibuat lewat
  `/analyze` atau `/detections/import` (endpoint manual menolak `source`, `confidence`).
- Laporan memberi `plant_accepted_sum_across_photos` dengan `counts_are_unique_plants: false` dan
  disclaimer: jumlah antar foto bertumpang tindih bukan jumlah tanaman unik.

## Konkurensi dan revisi

- `Annotation.revision` mulai 1, naik setiap PATCH. `PATCH`/`DELETE /annotations/{id}` **wajib**
  `If-Match: "<revision>"` → 428 bila tidak ada, 409 `REVISION_CONFLICT` bila beda (body
  `details.current` = versi server). Pemeriksaan dilakukan dengan `UPDATE … WHERE revision = ?`.
- Respons tunggal membawa header `ETag: "<revision>"`.
- `Photo.revision` naik setiap kali kumpulan penandanya berubah (buat/ubah/hapus/analisis/impor) —
  pakai untuk invalidasi cache. `AnnotationPage.photo_revision` ikut dikembalikan.
- Survey/Photo: `If-Match` opsional untuk PATCH/DELETE.

## Alur analisis

```
POST /photos/{id}/analyze {on_existing}
  ├─ survei demo → 409 DEMO_SURVEY_READONLY
  ├─ detector not_configured → 503 MODEL_NOT_CONFIGURED   (tidak membuat run)
  ├─ detector error           → 503 MODEL_UNAVAILABLE      (tidak membuat run)
  ├─ ada run running          → 409 ANALYSIS_IN_PROGRESS
  ├─ run sukses model+versi+sha sama & on_existing=reject → 409 ANALYSIS_EXISTS
  ├─ buat run(status=running) → verifikasi sha256 berkas → detector.detect(gambar terorientasi)
  │     timeout (default 120 s) → run failed INFERENCE_TIMEOUT → 504
  │     gagal                    → run failed → 503/500
  └─ transaksi: (replace_pending: hapus kandidat pending lama) + kandidat pending baru + run succeeded
```

Saat startup, run yang masih `running` (server mati di tengah) ditandai `failed / INTERRUPTED`.
Catatan: thread inferensi yang melewati timeout tidak bisa dibunuh paksa; hasilnya dibuang.

`model_version` = `sha256:` 16 hex pertama berkas bobot (Ultralytics: `.pt`; DeepForest: `model.safetensors`),
jadi run berulang dengan bobot berbeda tidak dianggap sama.

Detector memuat model **sekali** (lazy saat analisis pertama, atau saat startup dengan `WALLACEA_MODEL_PRELOAD`) dan
tidak pernah mengunduh. DeepForest: konstruktor 2.1.0 akan mengunduh `config.model.name` dari Hub bila berupa
repo ID, jadi adapter selalu memberi folder lokal, menyalakan `HF_HUB_OFFLINE`, dan mengarahkan `TORCH_HOME` ke
folder model (backbone torchvision sudah diunduh skrip). Input = array RGB dari gambar terorientasi API (bukan
path — DeepForest membaca path tanpa EXIF transpose). Label asli `Tree` → `kind=plant` eksplisit, `model_label=Tree`;
`/health` menyebut `target=tree_crown` agar UI menamai hasil sebagai kandidat tajuk pohon.

## Error

Semua error (termasuk 404 route, 422 validasi, 413 middleware, 500):

```json
{"error": {"code": "REVISION_CONFLICT", "message": "…(Bahasa Indonesia)…", "details": {}, "request_id": "…"}}
```

Header `X-Request-ID` selalu ada (klien boleh mengirim sendiri). Daftar `code` adalah enum `ErrorCode`
di OpenAPI. Kode penting untuk UI: `VALIDATION_ERROR`(422, `details.issues[]`), `NOT_FOUND`(404),
`PRECONDITION_REQUIRED`(428), `REVISION_CONFLICT`(409), `PAYLOAD_TOO_LARGE`/`IMAGE_TOO_LARGE`(413),
`UNSUPPORTED_MEDIA_TYPE`(415), `INVALID_IMAGE`(400), `DEMO_SURVEY_READONLY`(409),
`ANALYSIS_EXISTS`/`ANALYSIS_IN_PROGRESS`(409), `DETECTION_MISMATCH`(422),
`ANNOTATION_LIMIT_EXCEEDED`(422), `MODEL_NOT_CONFIGURED`/`MODEL_UNAVAILABLE`(503),
`INFERENCE_TIMEOUT`(504), `INFERENCE_FAILED`(500), `INVALID_BACKUP`(400).

## Batas

| Batas | Nilai | Konfigurasi |
|---|---|---|
| Ukuran foto | 20 MB | `max_upload_bytes` |
| Piksel foto | 60 MP | `max_pixels` |
| Format | JPEG (termasuk MPO), PNG, WebP; animasi ditolak | — |
| Penanda per foto | 3000 | `max_annotations_per_photo` |
| Payload impor deteksi | 5 MB | `max_detection_payload_bytes` |
| Backup starter | 100 MB, ≤ 100 survei | `max_backup_bytes` |
| Body JSON lain | 1 MB | middleware |
| Pagination | `limit` 1–200 (default 50), `offset` ≥ 0; anotasi default/maks 3000 | — |

`GET /health` mengembalikan batas aktual di `limits`.

## Keamanan demo lokal

- `python -m app` bind ke `127.0.0.1`; peringatan bila host lain. **Tidak ada autentikasi** — jangan dibuka ke LAN/internet.
- CORS hanya untuk origin di `WALLACEA_ALLOWED_ORIGINS` (default `http://localhost:5173,http://127.0.0.1:5173`).
  Dengan proxy Vite, browser memakai satu origin dan CORS tidak terpakai.
- Nama berkas asli hanya metadata; berkas disimpan dengan nama acak di luar root publik; key storage
  divalidasi regex + `resolve()` agar tidak bisa keluar dari folder.
- Isi gambar didekode penuh (deteksi berkas terpotong, bomb dekompresi); MIME ditentukan dari isi.
- CSV: sel teks yang diawali `= + - @ tab CR LF` diberi prefiks `'`.
- Body terlalu besar ditolak sebelum di-spool (Content-Length) dan dihitung untuk chunked.

## Persistensi dan PostgreSQL

SQLite (WAL, `foreign_keys=ON`) untuk demo satu mesin. Semua tipe kolom portabel; datetime disimpan UTC
(`UTCDateTime`). Untuk PostgreSQL: set `WALLACEA_DATABASE_URL=postgresql+psycopg://…`, pasang driver,
jalankan `alembic upgrade head`. Belum diuji di PostgreSQL — perlu uji sebelum dipakai.

## Konfigurasi (environment)

| Variabel | Default |
|---|---|
| `WALLACEA_DATA_DIR` | `apps/api/var` |
| `WALLACEA_DATABASE_URL` | `sqlite:///<DATA_DIR>/wallacea.db` |
| `WALLACEA_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `WALLACEA_AUTO_MIGRATE` | `true` (migrasi saat startup) |
| `WALLACEA_DETECTOR` | kosong = otomatis (ultralytics bila MODEL_PATH ada) · `none` · `ultralytics` · `deepforest` |
| `WALLACEA_MODEL_PATH` | kosong → mode manual (DeepForest: folder hasil `scripts/download_deepforest.py`) |
| `WALLACEA_MODEL_ID` | stem nama berkas bobot |
| `WALLACEA_LABEL_MAP_JSON` | `{"plant":"plant","check":"check","gap":"gap"}` |
| `WALLACEA_CONFIDENCE` / `WALLACEA_IMGSZ` | `0.35` / `1280` |
| `WALLACEA_INFERENCE_TIMEOUT_S` | `120` |
| `WALLACEA_DEVICE` | `cpu` (DeepForest; `cuda`/`auto` opsional) |
| `WALLACEA_PATCH_SIZE` / `WALLACEA_PATCH_OVERLAP` | `400` / `0.05` (tile DeepForest) |
| `WALLACEA_MODEL_PRELOAD` | `false` (`true` = muat model di thread latar saat startup) |

## Catatan untuk frontend

- Satu request upload per berkas (progres per berkas). Tampilkan `warnings[]` (mis. duplikat).
- Gunakan `thumbnail_url` untuk daftar, `display_url` untuk kanvas. URL relatif terhadap base API.
- Simpan `revision` tiap penanda; kirim `If-Match`. Pada 409, tampilkan `details.current` dan biarkan
  pengguna memilih — jangan menimpa otomatis.
- Undo penghapusan kandidat model tidak bisa memulihkan `source=model` (POST manual selalu `manual`).
  Untuk kandidat model, gunakan `review_status=rejected` alih-alih hapus.
- `captured_at` tanpa zona waktu: tampilkan apa adanya sebagai jam kamera.
- Tidak ada endpoint backup format baru; impor hanya untuk backup starter.

## Perubahan yang sengaja melampaui kontrak minimum

`Survey.revision`, `Survey.photo_count`; `Photo.size_bytes`, `exif_orientation`, `has_exif_gps`,
`display_url`, `thumbnail_url`, `duplicate_photo_ids`, `counts`; `Annotation.analysis_run_id`,
`model_label`; `AnalysisRun.run_type`, `candidate_count`, `parameters`; endpoint
`DELETE /photos/{id}`, `GET /photos/{id}/display|thumbnail`, `GET /photos/{id}/analysis-runs`,
`POST /demo/surveys`, `POST /imports/starter-backup`.
