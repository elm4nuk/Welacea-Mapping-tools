# Changelog kontrak API WALLACEA

Pemilik: Claude (backend). Setiap perubahan kontrak: naikkan `CONTRACT_REVISION` di
`apps/api/app/__init__.py`, regenerasi snapshot (`scripts/export_contract.py`), catat di sini
dengan kompatibilitas dan fixture yang berubah, commit, lalu sampaikan SHA ke frontend.
Usulan perubahan dari frontend: `docs/requests/codex-*.md`.

## Revisi 4 — 2026-10-20 (`info.version` 1.4.0) — diagnostik model + mode simulasi development

**Kompatibel mundur (aditif).** Tidak ada field yang dihapus atau diubah tipenya; `ModelStatus.state` tetap
`not_configured | configured | loaded | error`; kode error HTTP sama. Ada nilai enum **baru** yang harus ditangani UI.

`ModelStatus` (`GET /health` → `model`):

| Field | Tipe | Arti |
|---|---|---|
| `mode` (baru) | `"manual" \| "model" \| "simulation"` | `manual` = tanpa model (`state=not_configured`, atau `WALLACEA_DETECTOR` salah → `state=error`); `model` = detector sungguhan, siap/tidaknya dari `state`; `simulation` = `WALLACEA_DETECTOR=simulation`, **SIMULASI — BUKAN AI** |
| `diagnostic_code` (baru) | enum, nullable | Alasan status yang bisa dibaca mesin, lihat tabel bawah. `null` = siap tanpa catatan |
| `adapter` | + nilai `"simulation"` | |
| `target` | + nilai `"simulation"` | Kandidat adalah kotak buatan, bukan tanaman |

`diagnostic_code`:

| Kode | `state` | Arti / tindakan pengguna |
|---|---|---|
| `MODEL_PATH_NOT_SET` | `not_configured` | Mode manual (default). Bukan error |
| `DETECTOR_CONFIG_INVALID` | `error` | `WALLACEA_DETECTOR` tak dikenal, `ultralytics/deepforest` tanpa `MODEL_PATH`, confidence/device/patch salah |
| `MODEL_FILE_NOT_FOUND` | `error` | Path bobot/folder tidak ada (`message` berisi path lengkap) |
| `MODEL_FILE_NOT_PT` | `error` | Ultralytics: bukan berkas `.pt` (mis. folder run, `.onnx`) |
| `MODEL_FILES_INCOMPLETE` | `error` | DeepForest: folder bobot tidak lengkap |
| `DEPENDENCY_MISSING` | `error` | `ultralytics`/`deepforest` belum terpasang di venv API |
| `LABEL_MAP_INVALID` | `error` | `WALLACEA_LABEL_MAP_JSON` tidak bisa dibaca / nilai bukan `plant\|check\|gap` |
| `LABEL_MAP_MISMATCH` | `error` | Bobot terbuka tetapi tidak ada kelas model di label map (`message` menyebut kelas model) |
| `NOT_DETECTION_MODEL` | `error` | Bobot `task` ≠ `detect` (seg/cls/pose) |
| `MODEL_LOAD_FAILED` | `error` | Berkas ada tetapi gagal dibuka (rusak/versi) |
| `GENERIC_COCO_MODEL` | `loaded` | Model COCO umum: analisis jalan, tetapi `target_label` = "Kandidat dari model COCO umum (BUKAN model tanaman)" |
| `SIMULATION_ACTIVE` | `loaded` | Mode simulasi aktif |

Perilaku baru (tanpa perubahan skema):
- Kegagalan **memuat** model (`LABEL_MAP_MISMATCH`, `NOT_DETECTION_MODEL`, `MODEL_LOAD_FAILED`) kini diingat: setelah
  analisis pertama gagal, `/health` menunjukkan `state=error` + kode tersebut (dulu tetap `configured`). Berkas bobot
  yang diganti (ukuran/mtime berubah) dicoba lagi.
- 503 `MODEL_NOT_CONFIGURED` / `MODEL_UNAVAILABLE` dari `/analyze`: `details` = `{model_state, diagnostic_code}`
  (+ `run_id` bila run sudah dibuat). `message` 503 MODEL_NOT_CONFIGURED tidak lagi diberi akhiran " Mode manual tetap
  dapat dipakai." (kalimat itu kini sudah ada di `health.model.message`).
- **Simulasi** (`WALLACEA_DETECTOR=simulation`, tidak pernah otomatis): `state=loaded`, `model_id="simulation-not-ai"`,
  `model_version="simulation-v1"`, `target_label="SIMULASI — BUKAN AI"`. Kandidat: `source=model`,
  `review_status=pending`, `kind=plant`, `confidence=null`, `model_label="SIMULASI — BUKAN AI"`; kotak deterministik
  per gambar. `AnalysisRun.target="simulation"`, `parameters.not_ai=true`. `AnalysisResult.notice` diawali
  "SIMULASI — BUKAN AI". `SurveyReport.disclaimers` mendapat butir "SIMULASI — BUKAN AI: …" bila survei memuat kandidat
  simulasi (diterima atau tidak).

Fixture: **baru** `health.simulation.json`, `health.model-file-not-found.json`, `error.model-unavailable.json`,
`analyze.simulation.response.json`. `health.*.json` lain mendapat `mode` + `diagnostic_code`;
`error.model-not-configured.json` mendapat `details`. Fixture lain hanya berubah ID/timestamp.

## Revisi 3 — 2026-10-19 (`info.version` 1.3.0) — jawaban CR-FE-001/002/003 Codex

**Kompatibel mundur.** Endpoint baru + field response opsional; perilaku runtime request lama tidak berubah.

- **CR-FE-003 — semantik kandidat**: `AnalysisRun.target` (`"plant" | "tree_crown" | null`). Nilainya sama
  dengan `health.model.target` saat run dibuat, dicatat sejak run dimulai (run `failed` pun membawanya).
  `null` = tidak diketahui (impor deteksi, run sebelum revisi 3) → pakai istilah generik. Nama field `target`
  dipakai (bukan `candidate_semantics` yang diusulkan) agar sama dengan `ModelStatus.target` revisi 2.
  Pakai field ini alih-alih menebak dari `model_id`. (Koreksi: regex frontend saat ini
  `/(^|[^a-z0-9])deep[\s_-]*forest([^a-z0-9]|$)/i` memang cocok dengan `model_id` DeepForest
  `"weecology/deepforest-tree"` — diverifikasi 2026-10-19 — tetapi nama model bisa berubah/dikonfigurasi lewat
  `WALLACEA_MODEL_ID`, sedangkan `target` berasal dari adapter.)
- **CR-FE-002 — katalog foto contoh berlisensi**: `GET /api/v1/samples` → `SamplePage {items: SamplePhoto[], total}`
  dengan `id, title, file_url, filename, media_type, size_bytes, sha256, width, height, source_name, source_url,
  license_name, license_url, attribution, imagery, has_human_annotations`. `GET /api/v1/samples/{id}/file` →
  byte asli (sha256 = katalog). Alur: tampilkan sumber/lisensi → ambil berkas sebagai `File` → unggah lewat
  `POST /surveys/{id}/photos` biasa → `/analyze`. Tidak ada anotasi yang ikut terunggah. Sumber katalog:
  `samples/catalog.json` (env `WALLACEA_SAMPLES_DIR`); berkas dengan sha256 tidak cocok/path keluar folder dilewati.
- **CR-FE-001 — `AnnotationUpdate`**: `kind, note, review_status, geometry_type, x, y` tidak lagi bertipe nullable
  di OpenAPI (dulu diiklankan nullable tetapi runtime menolak `null` → 422; runtime tidak berubah). Kirim hanya
  field yang berubah. `bbox: null` tetap sah (= ubah ke titik). Untuk bbox, jangan kirim `x`/`y`.

Fixture: **baru** `sample-page.json`. `analyze.response.json`, `analysis-run-page.json`, `detections-import.response.json`
mendapat `run.target` (`null` untuk test double/impor). Fixture lain hanya berubah ID/timestamp.

## Revisi 2 — 2026-10-19 (`info.version` 1.2.0) — detector DeepForest, status model lebih jujur

**Kompatibel mundur (aditif).** Tidak ada field yang dihapus/diubah tipe; endpoint & kode error sama.

`ModelStatus` (`GET /health` → `model`) mendapat field opsional:

| Field | Tipe | Arti |
|---|---|---|
| `adapter` | `"ultralytics" \| "deepforest" \| null` | Jenis detector aktif; `null` = manual / konfigurasi salah |
| `target` | `"plant" \| "tree_crown" \| null` | Apa yang dideteksi. `tree_crown` = **tajuk pohon** (DeepForest pretrained), bukan semua tanaman |
| `target_label` | `string \| null` | Teks siap tampil, mis. `"Kandidat tajuk pohon (DeepForest pretrained)"` |
| `device` | `string \| null` | `cpu \| cuda \| auto` |
| `limitations` | `string[]` (default `[]`) | Keterbatasan model untuk ditampilkan ke pengguna |

Tidak berubah tetapi perlu diketahui frontend:
- Kandidat DeepForest tetap `kind="plant"`, `source="model"`, `review_status="pending"`; `model_label="Tree"`.
  UI sebaiknya memakai `health.model.target_label` untuk menamai kandidat (jangan menebak dari `kind`).
- `AnalysisRun.parameters` (objek bebas) kini berisi `adapter`, `target`, dan untuk DeepForest:
  `mode` (`image|tile`), `conf`, `patch_size`, `patch_overlap`, `device`, `hf_repo`, `hf_revision`, `deepforest_version`.
- Inferensi CPU: foto 400×400 ±1 s, 1249×1035 ±12 s (diukur). Foto K919 penuh bisa mendekati
  `limits.inference_timeout_s` (120 s) → 504 `INFERENCE_TIMEOUT` mungkin terjadi; tampilkan apa adanya.

Fixture: **baru** `health.deepforest-weights-missing.json` (adapter DeepForest ASLI, bobot belum diunduh →
`state=error` + metadata target). `health.*.json` lain mendapat field baru (null/[]). Fixture lain hanya
berubah ID/timestamp karena dibuat ulang dari API sungguhan.

## Revisi 1 — 2026-10-18 (baseline v1, `info.version` 1.1.0)

Baseline pertama. Prefix `/api/v1`. Belum ada klien, jadi belum ada isu kompatibilitas.
