# Changelog kontrak API WALLACEA

Pemilik: Claude (backend). Setiap perubahan kontrak: naikkan `CONTRACT_REVISION` di
`apps/api/app/__init__.py`, regenerasi snapshot (`scripts/export_contract.py`), catat di sini
dengan kompatibilitas dan fixture yang berubah, commit, lalu sampaikan SHA ke frontend.
Usulan perubahan dari frontend: `docs/requests/codex-*.md`.

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
