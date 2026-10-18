# Changelog kontrak API WALLACEA

Pemilik: Claude (backend). Setiap perubahan kontrak: naikkan `CONTRACT_REVISION` di
`apps/api/app/__init__.py`, regenerasi snapshot (`scripts/export_contract.py`), catat di sini
dengan kompatibilitas dan fixture yang berubah, commit, lalu sampaikan SHA ke frontend.
Usulan perubahan dari frontend: `docs/requests/codex-*.md`.

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
