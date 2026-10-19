# Handoff Claude (backend, ML, kontrak) — 2026-10-19

## Commit

| | SHA | Branch |
|---|---|---|
| BASE_COMMIT | `15a7408` | `main` (titik awal worktree) |
| Backend MVP + toolkit ML awal | `e91fc82`, `9925e1e` | `agent/claude-backend` |
| Workspace `ml/` (dataset, training, evaluasi) | `1e1b6d4` | `agent/claude-backend` |
| Detector DeepForest + kontrak revisi 2 | `733f5d2`, `51ff249` | `agent/claude-backend` |
| **CONTRACT_READY revisi 3** (jawaban CR-FE-001/002/003) | **`3fe53c5`** (+ koreksi CHANGELOG `b35102f`) | `agent/claude-backend` |
| Notebook 01–03 + venv bersih | `b7fc097` | `agent/claude-backend` |
| **Integrasi** backend + frontend Codex (`codex-inference-integration`, lalu `codex-uiux-v2` @ `67aac04`) | `git rev-parse integration/wallacea-mvp` | `integration/wallacea-mvp` (worktree `D:\coding\wallacea-worktrees\integration`) |

Tidak ada push, merge ke `main`, atau deploy. Integrasi dibuat dari BASE `15a7408`: merge
`agent/codex-inference-integration` (`2e8a2d7`) lalu `agent/claude-backend`.

## CONTRACT_READY — revisi 3 (`info.version` 1.3.0) @ `3fe53c5`

Aditif, kompatibel mundur; detail & contoh di `packages/contracts/CHANGELOG.md`.

| Request Codex | Jawaban |
|---|---|
| CR-FE-001 nullable PATCH | `AnnotationUpdate`: `kind/note/review_status/geometry_type/x/y` tidak lagi nullable di OpenAPI (runtime sama: `null` → 422). `bbox: null` tetap = ubah ke titik. |
| CR-FE-002 foto contoh berlisensi | `GET /api/v1/samples` → `{items: SamplePhoto[], total}` (id, title, file_url, filename, media_type, size_bytes, sha256, width, height, source_name/url, license_name/url, attribution, imagery, has_human_annotations); `GET /api/v1/samples/{id}/file`. Unggah lewat endpoint upload biasa. Fixture `sample-page.json`. |
| CR-FE-003 semantik kandidat | `AnalysisRun.target` (`plant \| tree_crown \| null`) = `health.model.target` saat run dibuat (run gagal pun membawanya). Nama field `target`, bukan `candidate_semantics`, agar sama dengan revisi 2. |

Regex DeepForest frontend saat ini **memang cocok** dengan `weecology/deepforest-tree` (diverifikasi; koreksi atas
catatan awal di CHANGELOG). Tetap disarankan memakai `target` karena `model_id` dapat dikonfigurasi.

## Hasil integrasi (`integration/wallacea-mvp`, 2026-10-19)

| Uji | Hasil |
|---|---|
| Konflik merge | 4 dokumen milik Claude (cherry-pick lama di branch Codex) → versi `agent/claude-backend`. Merge juga menghidupkan kembali `apps/api/ml/` + `tests/test_ml_toolkit.py` lama (byte-identik `e91fc82`) → dihapus di commit terpisah. |
| `apps/api` pytest (+ bobot DeepForest) | **123 lulus** · `export_contract.py --check` cocok |
| `ml` pytest | **36 lulus** |
| Web: `pnpm install --frozen-lockfile`, typecheck, build, vitest | lulus · **18/18** unit test |
| **Playwright suite Codex** (desktop/tablet/mobile) vs API integrasi revisi 3 tanpa model | **18/18 lulus** (54.6 s) — perubahan kontrak tidak merusak UI |
| **Alur browser dengan ML nyata** (Chromium 1440×900, API + DeepForest CPU, skrip di luar `apps/web`) | unggah `OSBS_029.png` lewat UI → **Analisis foto** → 49 kandidat dalam 1.4 s, tampil "kandidat tajuk pohon / Menunggu review" → terima 1, tolak 1 → **Simpan** → **reload**: tetap 1 terkonfirmasi, API accepted=1 rejected=1 pending=47 → **Ekspor CSV foto** (49 baris), **Ekspor gambar anotasi** (PNG), `export.csv` survei 200 (49 baris). Run: `target=tree_crown`, `model_version=sha256:d37a7af0b5ba2754`. |

Port 18080/5174 sedang dipakai proses lain saat uji (dimulai 23:30, kemungkinan sesi Codex) — tidak disentuh;
uji integrasi memakai API 18090 + Vite 5180 (`API_PROXY_TARGET`). Screenshot ada di scratchpad sesi Claude (tidak di Git).

Catatan UI untuk Codex (dari screenshot alur nyata, tidak mengubah frontend):
- Judul kartu kandidat masih "Tanaman" dan metrik "Tanaman terkonfirmasi" walau `target=tree_crown`; subjudul
  sudah "Kandidat tajuk pohon". Pertimbangkan memakai `health.model.target_label` / `run.target` untuk judul & metrik.
- Header masih "API tersedia / Model tersedia" (sudah jujur) — `limitations` revisi 2 belum ditampilkan.
- Label "T KAND" padat pada foto berisi 49+ kandidat; tinjau kepadatan label pada zoom kecil.
- Katalog `/samples` (CR-FE-002) siap dipakai untuk tombol "Coba foto contoh".

## Integrasi `agent/codex-uiux-v2` @ `67aac04` (2026-10-20)

Merge ke `integration/wallacea-mvp` tanpa konflik. Cakupan Codex hanya `apps/web`, dokumen/screenshot Codex, dan
`pnpm-lock.yaml`. Setelah merge: `apps/web` identik dengan `67aac04`, backend identik dengan `agent/claude-backend`.

| Uji (diverifikasi Claude, server milik Claude) | Hasil |
|---|---|
| API pytest (+ DeepForest) · kontrak `--check` · ML pytest | 123 lulus · cocok · 36 lulus |
| install frozen · typecheck · build · vitest · `pnpm peers check` | lulus · lulus · lulus (chunk 526 kB, peringatan) · **21/21** · bersih |
| Regenerasi tipe dari `openapi.yaml` revisi 3 vs `schema.d.ts` yang di-commit | identik |
| Playwright `workspace.spec` (API integrasi tanpa model, 18080/5174) | **18/18 lulus**, `ml-smoke` 3 skip (benar: tanpa model) |
| `ml-smoke.spec` Codex apa adanya (API + DeepForest 18095, Vite integrasi 5185) | desktop **lulus** (5.5 s); tablet & mobile **gagal** (timeout 2 min) |
| Alur pengguna tablet/mobile (spec sementara Claude: buka Sheet "Pilih foto"/"Review"; dihapus setelah run) | desktop 4.9 s · tablet 6.1 s · mobile 6.4 s **lulus**: analisis nyata 49 kandidat → terima/tolak → simpan → reload → accepted=1/rejected=1 di API, `run.target=tree_crown`, `export.csv` 200 |

**Tabrakan port — hasil awal tidak sah.** Saat verifikasi, sesi Codex menjalankan API (venv backend Claude) dan Vite
`codex-uiux-v2` di **18090/5180** — port yang juga dipakai Claude. Run tahap-2 pertama Claude (00:35–00:38) ternyata
mengenai server Codex dengan perubahan `apps/web` yang **belum di-commit** (UI menampilkan "Tajuk pohon terkonfirmasi"
dan tombol "Foto contoh berlisensi"); hasil itu dibuang. Angka di tabel berasal dari ulang uji di 18095/5185 setelah PID
pemegang port diverifikasi milik Claude. Usul pembagian port: **Codex 18090/5180**, **Claude 18095/5185** (suite
`workspace.spec` tetap 18080/5174 bila bebas).

Temuan untuk Codex (pada `67aac04` yang di-commit; frontend tidak diubah Claude):
1. `e2e/ml-smoke.spec.ts` tablet/mobile: mengklik `.filmstrip-card__select` yang tersembunyi tanpa membuka Sheet
   "Pilih foto" (`.filmstrip__mobile-trigger`) → timeout; langkah reload sudah memakai `:visible`, langkah awal belum.
   Review di tablet/mobile juga perlu `.mobile-review-trigger`.
2. Cleanup `finally { request.delete(...) }` gagal setelah timeout (`Target page, context or browser has been closed`)
   → survei "QA ML UI …" tertinggal di DB uji. Gunakan `test.afterEach`/request context tersendiri.
3. Metrik masih "Tanaman terkonfirmasi" walau `health.model.target`/`run.target` = `tree_crown` (subjudul & status
   model sudah benar). Worktree Codex tampaknya sedang mengubah ini (belum di-commit) — akan diverifikasi setelah commit.
4. Pill status model di header hanya tampil di desktop; tablet/mobile hanya "API terhubung". Info lengkap (termasuk
   `limitations`) tetap ada di "Status model dan riwayat analisis foto" di bawah kanvas.
5. Panel temuan terpilih: tombol "Tolak" dan "Tolak kandidat" muncul bersamaan; daftar temuan menyusut sampai hampir
   tak terlihat saat satu temuan dipilih (desktop 1440×900).

Screenshot sah (desktop/tablet/mobile, setelah simpan): scratchpad sesi Claude `uiux-v2-verified/` (tidak di Git).

## Notebook Jupyter (terlacak di Git)

`ml/notebooks/01_data_inspection.ipynb`, `02_pretrained_inference.ipynb`, `03_evaluation.ipynb` (+ `training/01–04`,
`05_deepforest_pretrained.ipynb` versi gabungan lama). Dieksekusi dari **venv bersih** (`ml\.venv-clean`, dibuat dari
`requirements-pretrained.txt`, `pip check` bersih), kernel baru per notebook: 01 (8 s), 02 (80 s), 03 (8 s), 0 error,
nbformat valid. Output tidak di-commit (gambar berat).

## Status singkat

- **Inferensi ML nyata berjalan lewat `POST /photos/{id}/analyze`** dengan DeepForest pretrained
  (kandidat **tajuk pohon**, CPU) — diuji dengan server uvicorn sungguhan + 3 foto contoh NEON.
- Model jagung tim (YOLO11n fine-tune pada dataset publik UAVmulticrop) juga berjalan lewat adapter
  Ultralytics; dievaluasi pada situs yang tidak terlihat (lihat `ml/README.md` § Status).
- **Belum ada foto K919 MAX.** Semua hasil hanya pada foto contoh/dataset publik.
- Kontrak **revisi 3** (`info.version` 1.3.0, aditif): revisi 2 `health.model.{adapter,target,target_label,device,limitations}` + revisi 3 di atas.

## Untuk Codex (frontend)

1. Regenerasi tipe dari `packages/contracts/openapi.yaml` (revisi 3). Tidak ada field yang dihapus.
2. `health.model` kini punya: `adapter` (`ultralytics|deepforest|null`), `target` (`plant|tree_crown|null`),
   `target_label` (teks siap tampil), `device`, `limitations: string[]`. Contoh respons nyata (server uvicorn,
   DeepForest dimuat):

   ```json
   "model": {
     "state": "loaded", "available": true,
     "model_id": "weecology/deepforest-tree", "model_version": "sha256:d37a7af0b5ba2754",
     "message": "Model DeepForest termuat di memori.",
     "adapter": "deepforest", "target": "tree_crown",
     "target_label": "Kandidat tajuk pohon (DeepForest pretrained)", "device": "cpu",
     "limitations": [
       "Model pretrained tajuk pohon dari citra pesawat NEON ±10 cm/px (hutan AS), bukan model tanaman pertanian.",
       "Belum dievaluasi pada foto K919 MAX; ukuran objek bergantung ketinggian terbang dan resolusi.",
       "Tanaman semusim kecil (jagung muda, padi, sayuran) umumnya tidak cocok untuk model ini."]
   }
   ```
   Fixture: `health.not-configured.json`, `health.test-double-loaded.json`, **baru**
   `health.deepforest-weights-missing.json` (state `error`, metadata target tetap ada).
3. Saran UI (tanpa menebak):
   - Status pill `App.tsx` saat ini statis "API tersedia / Mode manual" — gunakan `model.state` +
     `model.target_label`; tampilkan `model.limitations` di dekat tombol analisis.
   - Kandidat DeepForest tersimpan `kind="plant"`, `model_label="Tree"`, `source="model"`, `pending`. Bila
     `health.model.target === "tree_crown"`, beri nama kandidat model sebagai `target_label` (bukan "tanaman").
     Setelah diterima pengguna, hitungan tetap `plant_accepted` per foto (bukan jumlah tanaman unik lahan).
   - `AnalysisRun.parameters` (objek bebas) berisi `adapter`, `target`, `mode` (`image|tile`), `conf`,
     `patch_size`, `device`, `hf_repo`, `hf_revision`, `deepforest_version` — boleh ditampilkan sebagai detail run.
   - Analisis sinkron di CPU: ±1 s untuk 400×400, ±12 s untuk 1249×1035 (diukur). Foto drone penuh bisa
     puluhan detik; 504 `INFERENCE_TIMEOUT` (batas `limits.inference_timeout_s`) mungkin muncul.
   - Survei demo tetap read-only: analyze → 409 `DEMO_SURVEY_READONLY` (tidak diubah).
4. Foto contoh untuk demo unggah: `samples/deepforest-neon/*.png` (atribusi & lisensi di `ATTRIBUTION.md`;
   NEON CC BY 4.0, distribusi DeepForest MIT). XML di folder itu = anotasi manusia untuk notebook, **bukan**
   untuk diimpor sebagai hasil inferensi.

## Menjalankan (Windows PowerShell)

API + DeepForest (CPU):

```powershell
cd apps/api
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
.venv\Scripts\python -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements-deepforest.txt
.venv\Scripts\python scripts\download_deepforest.py          # sekali; ±230 MB
$env:WALLACEA_DETECTOR = "deepforest"
$env:WALLACEA_MODEL_PATH = "$PWD\var\models\deepforest-tree"
$env:WALLACEA_MODEL_PRELOAD = "true"
.venv\Scripts\python -m app                                    # 127.0.0.1:8000
# web (root): pnpm dev:web → 127.0.0.1:5173
```

Tanpa langkah DeepForest, API tetap mode manual (`MODEL_NOT_CONFIGURED`). ML/Jupyter: `ml/README.md`
(`ml\.venv`, kernel "Python (wallacea-ml)", notebook 01–05).

## Sumber & identitas bobot

| Model | Sumber | Versi / checksum | Lisensi |
|---|---|---|---|
| DeepForest tree | HF `weecology/deepforest-tree` @ `cc21436bc5d572dde8ff5f93c1e71a32f563cace` | `model.safetensors` sha256 `d37a7af0b5ba2754…` → `model_version` `sha256:d37a7af0b5ba2754` | MIT (model card); kode DeepForest 2.1.0 MIT |
| Backbone konstruksi | `https://download.pytorch.org/models/resnet50-0676ba61.pth` | sha256 `0676ba61b6795bbe…` | torchvision (BSD-3 kode; bobot ImageNet). Nilai ditimpa safetensors |
| Jagung YOLO11n (eksperimen) | dilatih lokal dari `yolo11n.pt` (ultralytics/assets v8.3.0) + UAVmulticrop CC-BY-4.0 | `sha256:9c2e20232a359fd5` | turunan bobot AGPL-3.0/Enterprise; tidak di Git |

Semua tercatat di `apps/api/var/models/deepforest-tree/wallacea_model.json` dan
`ml/artifacts/models/<nama>/model_card.json` (tidak di Git).

## Tes yang benar-benar dijalankan (2026-10-19, Windows 11, Python 3.12.10)

| Tes | Hasil | Jenis |
|---|---|---|
| `apps/api` pytest, venv lengkap (DeepForest + bobot) | **116 lulus** | kontrak + 1 inferensi nyata |
| `apps/api` pytest, venv minimum (tanpa numpy/torch/deepforest) | lulus, 3 skip beralasan | kontrak |
| `export_contract.py --check` | cocok | kontrak |
| `ml` pytest | **33 lulus** | pipeline (fixture sintetis), bukan akurasi |
| DeepForest muat + infer dengan **socket diblokir** | lulus (muat 1.5 s, 49 kandidat) | tanpa unduhan saat request |
| E2E HTTP uvicorn :8011 (DeepForest, preload) | health `loaded` dalam 7 s; 3 foto → 201, semua `pending`; review 0→1; analyze ulang 409 `ANALYSIS_EXISTS`; demo 409 `DEMO_SURVEY_READONLY` | integrasi nyata |
| Orientasi EXIF, model nyata | JPEG piksel diputar + EXIF 6 → 48/49 kotak IoU≥0.8 dengan PNG asli | konsistensi editor↔model |
| Notebook 05 dieksekusi (nbconvert, kernel wallacea-ml) | sukses; angka di `ml/README.md` § Status B | perbandingan vs anotasi manusia (3 foto) |
| Model jagung via API (TestClient) | 144 & 288 kandidat `pending`, `model_version` = model card | integrasi nyata |

Pembanding terhadap anotasi manusia (3 foto NEON, IoU 0.5, conf 0.35): precision 0.659, recall 0.650, AP 0.537,
FP 127, terlewat 132. Foto ini tidak independen dari data pengembang model → **bukan** akurasi produk.

## Keterbatasan (jujur)

- DeepForest = **tajuk pohon** dari citra pesawat NEON 10 cm. Untuk lahan pertanian (jagung, padi, sayuran)
  dan foto K919 pada ketinggian berbeda, hasilnya kemungkinan buruk; **belum diuji**. Untuk sawit/kebun pohon
  lebih masuk akal, tetap belum diuji pada K919.
- `patch_size` 400 disetel untuk ±10 cm/px; GSD K919 belum diketahui → perlu disetel ulang setelah ada foto.
- CPU lambat untuk foto penuh; thread inferensi yang melewati timeout tidak bisa dihentikan paksa.
- Windows Smart App Control memblokir `pandas` 3.0.6 di mesin uji → dikunci 3.0.5.
- Model jagung: P/R 0.46/0.47 pada situs baru; tidak dipakai sebagai default demo.

## Blocker / langkah berikut

1. Foto K919 MAX nyata (beberapa penerbangan, catat ketinggian) → uji orientasi/EXIF/ukuran + label ±20 foto.
2. Codex: regenerasi tipe revisi 3; pakai `run.target`/`target_label`/`limitations` dan katalog `/samples` (lihat di atas).
3. Integrasi sudah dibuat (`integration/wallacea-mvp`); ulangi merge bila Codex mengirim commit baru.
4. Tentukan tanaman target nyata; latih model tim (`ml/`) bila DeepForest tidak cocok.
