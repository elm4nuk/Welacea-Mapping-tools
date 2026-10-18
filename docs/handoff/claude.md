# Handoff Claude (backend, ML, kontrak) — 2026-10-19

## Commit

| | SHA | Branch |
|---|---|---|
| BASE_COMMIT | `15a7408` | `main` (titik awal worktree) |
| Backend MVP + toolkit ML awal | `e91fc82`, `9925e1e` | `agent/claude-backend` |
| Workspace `ml/` (dataset, training, evaluasi, notebook) | lihat `git log agent/claude-backend` | `agent/claude-backend` |
| Detector DeepForest + kontrak **revisi 2** | lihat `git log agent/claude-backend` | `agent/claude-backend` |

Ambil SHA terbaru: `git rev-parse agent/claude-backend`. Tidak ada push, merge ke `main`, atau deploy.
`origin/main` sudah berisi frontend Codex (PR #2); branch ini **belum** di-rebase/merge ke sana.

## Status singkat

- **Inferensi ML nyata berjalan lewat `POST /photos/{id}/analyze`** dengan DeepForest pretrained
  (kandidat **tajuk pohon**, CPU) — diuji dengan server uvicorn sungguhan + 3 foto contoh NEON.
- Model jagung tim (YOLO11n fine-tune pada dataset publik UAVmulticrop) juga berjalan lewat adapter
  Ultralytics; dievaluasi pada situs yang tidak terlihat (lihat `ml/README.md` § Status).
- **Belum ada foto K919 MAX.** Semua hasil hanya pada foto contoh/dataset publik.
- Kontrak **revisi 2** (`info.version` 1.2.0): **aditif** di `GET /health → model`.

## Untuk Codex (frontend)

1. Regenerasi tipe dari `packages/contracts/openapi.yaml` (revisi 2). Tidak ada field yang dihapus.
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
2. Codex: regenerasi tipe revisi 2, pakai `target_label`/`limitations` (lihat di atas).
3. Integrasi `integration/wallacea-mvp`: merge `agent/claude-backend` dengan `origin/main` (frontend).
4. Tentukan tanaman target nyata; latih model tim (`ml/`) bila DeepForest tidak cocok.
