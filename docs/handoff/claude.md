# Handoff Claude (backend, ML, geospasial, kontrak) — 2026-10-20

## Commit

| | SHA | Branch |
|---|---|---|
| BASE_COMMIT | `15a7408` | `main` (titik awal worktree) |
| Backend MVP + toolkit ML awal | `e91fc82`, `9925e1e` | `agent/claude-backend` |
| Workspace `ml/` (dataset, training, evaluasi) | `1e1b6d4` | `agent/claude-backend` |
| Detector DeepForest + kontrak revisi 2 | `733f5d2`, `51ff249` | `agent/claude-backend` |
| **CONTRACT_READY revisi 3** (jawaban CR-FE-001/002/003) | **`3fe53c5`** (+ koreksi CHANGELOG `b35102f`) | `agent/claude-backend` |
| Notebook 01–03 + venv bersih | `b7fc097` | `agent/claude-backend` |
| **Integrasi** backend + frontend Codex (`codex-inference-integration`, lalu `codex-uiux-v2` @ `67aac04`) | `f15175b` | `integration/wallacea-mvp` (worktree `D:\coding\wallacea-worktrees\integration`) |
| **CONTRACT_READY revisi 4**: onboarding model Windows, mode simulasi, diagnostik | **`cfacdda`** (+ handoff `1ecda6c`) | `agent/claude-backend` |
| Mapping backend (A batas lahan, B raster GeoTIFF + tile, C AI → peta), migrasi `0002` | **`40ba487`** | `agent/claude-backend` |
| **CONTRACT_READY revisi 5** (snapshot OpenAPI 1.5.0, fixtures, CHANGELOG) — commit terpisah | **`f2e770f`** | `agent/claude-backend` |
| Dokumen scope mapping, panduan PowerShell, arsitektur | `1d1d36c` | `agent/claude-backend` |
| **Integrasi mapping**: `integration/wallacea-mvp` + `agent/codex-frontend` @ `1cb6d51` + backend revisi 5 | `ca67ffe` (+ merge handoff ini) | `integration/wallacea-mapping` (worktree `D:\coding\wallacea-worktrees\integration-mapping`) |

Tidak ada push, merge ke `main`, atau deploy.

## CONTRACT_READY — revisi 5 (`info.version` 1.5.0) @ `f2e770f` — mapping, 2026-10-20

Scope diperluas atas instruksi pengguna (lihat `docs/architecture/PROJECT_BRIEF.md` § Perubahan scope): **A** batas
lahan berkoordinat nyata, **B** impor raster GeoTIFF bergeoreferensi + tile, **C** hasil AI di peta. Pembuatan
orthomosaic dari foto K919 (ODM/NodeODM) **belum** — impor GeoTIFF tidak disebut fotogrametri. Detail kontrak:
`packages/contracts/CHANGELOG.md` § Revisi 5. Semua kompatibel mundur (aditif); endpoint lama tidak berubah makna.

### Migrasi

`apps/api/alembic/versions/0002_mapping.py` (head `0002`, otomatis saat start): tabel `fields`, `raster_assets`,
`raster_analysis_runs` (indeks unik parsial 1 run running/raster), `map_detections`; kolom `surveys.field_id`
(`REFERENCES fields ON DELETE SET NULL`) lewat `ALTER TABLE ADD COLUMN` **tanpa** batch-recreate — batch SQLite
melakukan `DROP TABLE surveys` yang, dengan `foreign_keys=ON`, memicu `ON DELETE CASCADE` ke photos/annotations.
Diverifikasi: test migrasi dengan data lama + **salinan DB nyata** `apps/api/var/wallacea.db` (3 survei, 4 foto, 773
penanda, 4 run → identik setelah upgrade); `alembic check` bersih; downgrade→upgrade aman. Backup `apps\api\var\`
tetap disarankan sebelum upgrade data penting.

### Contoh respons (fixture asli dari API)

`POST /api/v1/fields` → `FarmField` (`field.json`):
```json
{"name": "Petak contoh OSBS", "boundary_source": "digitized_from_raster",
 "measures": {"area_m2": 1021.31, "area_ha": 0.10213, "perimeter_m": 127.886, "exterior_perimeter_m": 127.886,
              "method": "geodesic_wgs84"},
 "bbox": [-81.99006, 29.69236, -81.98972, 29.69264], "label_point": [-81.98989, 29.6925], "revision": 1}
```
`POST /api/v1/surveys/{id}/rasters` → `RasterUploadResult.raster` (`raster-upload.response.json`, GeoTIFF NEON asli):
```json
{"product_type": "imported_georeferenced_raster", "is_verified_orthomosaic": false, "width": 400, "height": 400,
 "crs": {"epsg": 32617, "name": "WGS 84 / UTM zone 17N", "is_geographic": false},
 "bounds_wgs84": [-81.990099, 29.692322, -81.989683, 29.692686], "approx_gsd_m": 0.10003, "nodata": 255.0,
 "tilejson_url": "/api/v1/rasters/<id>/tilejson.json", "tile_url_template": "/api/v1/rasters/<id>/tiles/{z}/{x}/{y}.png",
 "minzoom": 18, "maxzoom": 21,
 "detection_counts": {"plant_accepted": 0, "plant_accepted_inside_field": 0, "pending_review": 0, "rejected": 0, "total": 0}}
```
`GET /api/v1/rasters/{id}/detections` → `MapDetectionPage.items[]` (`map-detection-page.json`, detector test double):
```json
{"kind": "gap", "source": "model", "review_status": "pending", "confidence": 0.42,
 "pixel_bbox": [240.0, 200.0, 60.0, 60.0], "center": [-81.989818, 29.692477], "center_native": [404238.9, 3285119.9],
 "geometry": {"type": "Polygon", "coordinates": [[[lon, lat], …5 titik]]}, "inside_field": true, "revision": 1}
```
`POST /api/v1/rasters/{id}/analyze` → `run.parameters`: `tile_size, overlap_px, scale, window_count, raw_detections,
dropped_edge, dropped_masked, after_dedup, dedup{method: greedy_nms_per_kind, iou_threshold, ios_threshold, edge_rule}`.

Error baru: `error.invalid-geometry.json` (`Self-intersection[106.805 -6.595]`, `details.reason`),
`error.raster-not-georeferenced.json` (`details.reason = no_crs`).

### Untuk Codex (frontend) — revisi 5

1. Regenerasi tipe dari `packages/contracts/openapi.yaml`. Sudah diuji: web `1cb6d51` lolos `tsc` dengan tipe
   revisi 5 (tidak ada perubahan yang memecah).
2. **Batas lahan**: daftar/CRUD `/fields`, impor berkas `/fields/import` (multipart), ekspor `/fields/{id}/geojson`,
   `/fields-export.geojson`. Menggambar poligon di peta boleh memberi *preview* luas, tetapi tampilkan nilai tersimpan
   dari `measures` (backend). Tampilkan `boundary_source` + `source_note`. Tangani 422 `INVALID_GEOMETRY`
   (`message` menyebut alasan & lokasi; jangan "memperbaiki" geometri di klien). Koordinat **[lon, lat]**.
3. **Survei ↔ lahan**: `Survey.field_id`; `PATCH /surveys/{id}` `{"field_id": … | null}`.
4. **Peta udara**: unggah GeoTIFF per berkas (`/surveys/{id}/rasters`, field `file`, opsional `name`,
   `source_description`); progres upload seperti foto. Tampilkan dengan Leaflet/MapLibre dari `tilejson_url`/
   `tile_url_template` (relatif terhadap origin API; Vite proxy `/api`), `minzoom`/`maxzoom`, `bounds_wgs84`,
   `footprint`. Label wajib: "GeoTIFF impor — georeferensi dari berkas, bukan orthomosaic terverifikasi"
   (`is_verified_orthomosaic=false`). Tangani 415/422/413 (`UNSUPPORTED_RASTER`, `RASTER_NOT_GEOREFERENCED` +
   `details.reason`, `RASTER_TOO_LARGE`) dengan pesan dari API; raster ditolak tidak boleh muncul di peta.
   `preview_url` = gambar ruang piksel (bukan overlay peta).
5. **AI di peta**: `POST /rasters/{id}/analyze` (sinkron; bisa menit untuk raster besar; batas
   `limits.raster_analysis_timeout_s`). Error & `on_existing` sama dengan analisis foto. Gambar `MapDetection.geometry`
   sebagai poligon; status pending/accepted/rejected dibedakan seperti kandidat foto; `run.target`
   (`tree_crown`/`plant`/`simulation`) menentukan istilah; simulasi tetap "SIMULASI — BUKAN AI".
   Review `PATCH /map-detections/{id}` dengan **If-Match wajib**; 409 → `details.current`.
6. **Hitungan**: `RasterAsset.detection_counts` / `MapDetectionPage.counts` per raster; `plant_accepted_inside_field`
   bila survei punya lahan. **Jangan** menjumlahkan antar raster; `SurveyReport.mapping.counts_are_unique_plants =
   false`. Hitungan foto (`totals.plant_accepted_sum_across_photos`) tidak memuat deteksi peta.
7. **Capability**: tampilkan fitur mapping hanya bila `capabilities.field_boundaries` /
   `georeferenced_raster_import` / `map_ai_detections` true; `orthomosaic_generation` false → jangan tawarkan
   "buat orthomosaic". `georeferencing` (foto) tetap false: jangan menaruh penanda foto di peta, jangan memakai EXIF GPS
   foto sebagai lokasi tanaman.
8. **Laporan**: tampilkan `SurveyReport.mapping` dan `disclaimers` apa adanya (butir mapping kondisional).
9. Contoh raster nyata untuk demo/E2E: `samples/georeferenced/OSBS_029.tif` (NEON CC BY 4.0, atribusi di
   `ATTRIBUTION.md`; bukan K919). Untuk E2E multi-tile tanpa model gunakan API `WALLACEA_DETECTOR=simulation`.

### Tes yang benar-benar dijalankan (2026-10-20, Windows 11, Python 3.12.10)

| Tes | Hasil |
|---|---|
| `apps/api` pytest, venv backend (DeepForest + bobot) | **246 lulus**, 0 skip (57 test mapping baru + 18 validasi fixture kontrak baru) |
| `apps/api` pytest, **venv bersih** dari `requirements.lock.txt` (rasterio 1.5.2/GDAL 3.12.2, pyproj 3.8.0, shapely 2.2.0; tanpa DeepForest) | 244 lulus, 2 skip (DeepForest tidak terpasang); `pip check` bersih |
| `export_contract.py --check` · `alembic check` | cocok · tanpa operasi baru |
| `ml` pytest | 36 lulus |
| Luas referensi | sel 1°×1° ekuator = 12 308 778 361,469 m² (nilai GeographicLib); 1 ha UTM vs proyeksi equal-area EPSG:6933 rel < 1e-5; lubang, MultiPolygon, orientasi ring |
| Invalid | bowtie (lokasi self-intersection), ring terbuka, < 4 posisi, titik kembar, kosong, lon > 180, lat/lon tertukar, 3D, NaN, Point, antimeridian, lubang di luar, batas titik & payload 413, impor semua-atau-tidak, CRS GeoJSON non-WGS84 |
| Raster | UTM & EPSG:4326, piksel→dunia diketahui + urutan sumbu (dibanding pyproj tanpa `always_xy`), transform berotasi, tanpa CRS / identitas / hanya-GCP / 1 band / uint16 / PNG / TIFF rusak / band-4 non-alpha / footprint > 2500 km² / batas piksel & byte, alpha & nodata transparan, tile (zoom min/max, di luar = transparan, x di luar rentang 422), preview, PATCH revisi, hapus berkas, restart |
| AI → peta | GreenBoxDetector (melihat piksel) pada raster sintetis 3000×2000, 12 jendela 1024/128: **7/7 objek tepat sekali**, posisi piksel tepat, pusat & sudut = transform manual → pyproj; `scale 0.5` (model menerima 50%) posisi ±2 px; overlap 0 memecah objek di sambungan (didokumentasikan); dedup IoU/IoS; mask; review If-Match/409; replace_pending; inside_field; laporan; simulasi; persist restart |
| **DeepForest nyata pada GeoTIFF NEON** `OSBS_029.tif` | tile_size 400: **49 kandidat tajuk pohon** (= analisis PNG yang sama lewat alur foto), lokasi Florida benar; vs 61 anotasi manusia IoU 0,5: TP 38 FP 11 FN 23 (P 0,78 R 0,62). tile_size 256/overlap 64: P 0,33 R 0,33 → jendela harus ≥ patch latih model |
| Server uvicorn sungguhan (18095, DeepForest, data dir terpisah) | contoh PowerShell README (lahan 0,99 ha), impor NEON, analisis 49 kandidat 1,6 s, review, tile, laporan; **restart** → survei/lahan/raster/49 deteksi/ekspor GeoJSON utuh, sha256 asli cocok, tanpa model → 503 jujur |
| Performa (raster sintetis 12000×12000 = 144 MP JPEG) | impor 51 s, RSS proses +74 MB; tile z14–z22 38–126 ms; preview 218 ms |
| **Integrasi** `integration/wallacea-mapping` @ `ca67ffe` | API pytest lulus (2 skip: bobot DeepForest tidak ada di worktree integrasi); web install frozen, `tsc`, build, **vitest 23/23**; `tsc` dengan tipe revisi 5; **Playwright `workspace` + `model-status` 21/21** (API tanpa model, 18095/5185); **`simulation-smoke` 3/3** (API simulasi); endpoint mapping lewat proxy Vite 5185 (impor, TileJSON, tile ber-isi, analisis simulasi, GeoJSON) |

### Keterbatasan (jujur)

- **Belum ada UI peta** (bagian Codex); integrasi web baru dibuktikan lewat proxy Vite, bukan klik di browser.
- Tidak ada foto/peta K919. Satu-satunya raster nyata = NEON 40 m × 40 m (pesawat, hutan). Belum ada uji pada
  orthomosaic drone pertanian sungguhan, raster besar nyata, atau CRS kustom selain UTM/WGS84.
- Georeferensi raster dipercaya apa adanya; akurasi posisional tidak diverifikasi (tidak ada GCP/checkpoint).
- Validitas topologi batas = Shapely planar pada lon/lat (memadai untuk lahan, bukan untuk poligon benua/kutub);
  antimeridian ditolak. `inside_field` juga planar.
- Analisis raster sinkron dan memblokir satu worker; raster ratusan MP bisa mendekati batas waktu. Tidak ada antrean.
- Impor raster sinkron (144 MP ±51 s) dan menyimpan dua salinan (asli + turunan tampilan).
- Hanya RGB/RGBA 8-bit; multispektral/NIR, 16-bit, COG remote, GCP-only belum didukung.
- Dedup tidak menyatukan potongan berdampingan bila overlap lebih kecil dari objek; parameter dicatat per run.
- Tile dirender per request tanpa cache server (cukup untuk 1 pengguna lokal).
- Downgrade migrasi di SQLite tidak menghapus kolom `surveys.field_id` (dikosongkan; aman untuk upgrade ulang).

### Menjalankan (Windows PowerShell)

```powershell
cd D:\coding\wallacea-worktrees\claude-backend\apps\api
.venv\Scripts\python -m pip install -r requirements.lock.txt     # sekali: rasterio/pyproj/shapely/numpy
# (opsional) AI DeepForest — lihat README: $env:WALLACEA_DETECTOR="deepforest"; $env:WALLACEA_MODEL_PATH=...
.venv\Scripts\python -m app                                      # migrasi 0002 otomatis
# terminal 2, root repo: pnpm dev:web → http://127.0.0.1:5173
curl.exe -F "file=@..\..\samples\georeferenced\OSBS_029.tif" http://127.0.0.1:8000/api/v1/surveys/<id>/rasters
```

Panduan lengkap: `apps/api/README.md` § Mapping.

## CONTRACT_READY — revisi 4 (`info.version` 1.4.0) @ `cfacdda` — 2026-10-20

Masalah yang diperbaiki: pengguna Windows melihat "Model tanaman belum dikonfigurasi" tanpa tahu langkah berikutnya,
mengira `models\best.pt` adalah perintah, `.env` tidak dimuat, dan tidak ada cara aman menguji alur kandidat AI
tanpa bobot. Model tanaman terlatih **masih belum ada**; tidak ada yang diklaim lebih dari itu.

### Perubahan kontrak (aditif; detail di `packages/contracts/CHANGELOG.md`)

| Di mana | Perubahan |
|---|---|
| `ModelStatus.mode` (baru) | `manual \| model \| simulation` |
| `ModelStatus.diagnostic_code` (baru, nullable) | `MODEL_PATH_NOT_SET`, `DETECTOR_CONFIG_INVALID`, `MODEL_FILE_NOT_FOUND`, `MODEL_FILE_NOT_PT`, `MODEL_FILES_INCOMPLETE`, `DEPENDENCY_MISSING`, `LABEL_MAP_INVALID`, `LABEL_MAP_MISMATCH`, `NOT_DETECTION_MODEL`, `MODEL_LOAD_FAILED`, `GENERIC_COCO_MODEL`, `SIMULATION_ACTIVE` |
| `ModelStatus.adapter` | + `"simulation"` |
| `ModelStatus.target`, `AnalysisRun.target` | + `"simulation"` |
| 503 `/analyze` | `error.details = {model_state, diagnostic_code}` (+ `run_id` bila run dibuat). Pesan MODEL_NOT_CONFIGURED tanpa akhiran lama " Mode manual tetap dapat dipakai." |
| Perilaku | Gagal memuat (label map/task/berkas rusak) diingat → `/health` `state=error` + kode, bukan tetap `configured` |
| Simulasi | `state=loaded`, `model_id=simulation-not-ai`, `model_version=simulation-v1`, `target_label="SIMULASI — BUKAN AI"`; kandidat `pending`, `kind=plant`, `confidence=null`, `model_label="SIMULASI — BUKAN AI"`; `notice` diawali "SIMULASI — BUKAN AI"; disclaimer laporan |
| Model COCO umum | `state=loaded`, `diagnostic_code=GENERIC_COCO_MODEL`, `target_label="Kandidat dari model COCO umum (BUKAN model tanaman)"` |

`ModelStatus.state` **tidak** mendapat nilai baru. Tidak ada perubahan skema DB/migrasi.
Fixture baru: `health.simulation.json`, `health.model-file-not-found.json`, `error.model-unavailable.json`,
`analyze.simulation.response.json`.

### Berkas baru / berubah

| Berkas | Isi |
|---|---|
| `apps/api/app/inference/simulation.py` (baru) | `SimulationDetector`: kotak deterministik dari sidik jari piksel, hanya bila `WALLACEA_DETECTOR=simulation` |
| `apps/api/app/inference/base.py`, `ultralytics_adapter.py`, `deepforest_adapter.py`, `factory.py` | `DetectorInfo.mode/diagnostic_code`, `ModelUnavailable.diagnostic_code`, pesan spesifik (path lengkap, kelas model), kegagalan muat diingat, deteksi COCO |
| `apps/api/app/config.py` | `parse_label_map()`: JSON atau `kelas=plant,kelas2=check` / `{kelas:plant}` (JSON yang kutipnya dibuang PowerShell 5.1); pesan menyebut entri salah; `simulation` di `DETECTORS` |
| `apps/api/app/envfile.py` (baru), `__main__.py` | `python -m app` memuat `apps/api/.env` (tidak menimpa env; `--env-file`, `--no-env-file`); log mode model saat start |
| `apps/api/app/schemas.py`, `routers/health.py`, `routers/analysis.py`, `routers/reports.py`, `services.py` | kontrak revisi 4, `details.diagnostic_code`, notice & disclaimer simulasi |
| `apps/api/scripts/check-model.ps1` + `check_model.py` (baru) | ada? `.pt`? ultralytics? terbuka? `task=detect`? `model.names`, label map, COCO, `-Image` uji; cetak perintah run siap salin. Tanpa unduhan/instalasi |
| `apps/api/scripts/run-with-model.ps1`, `run-simulation.ps1` (baru) | env hanya untuk proses API (dipulihkan di `finally`), Python `.venv`, path berspasi, confidence culture-invariant |
| `apps/api/ml/` (baru) | `README.md`, `dataset.yaml.example`, `dataset-example/README.md`, `yolo_dataset.py`, `train.py`, `validate_model.py` |
| `apps/api/models/README.md`, `apps/api/.env.example` (baru), `.gitignore` | tempat `best.pt` lokal (di-ignore), templat `.env` |
| `README.md`, `apps/api/README.md`, `docs/architecture/ARCHITECTURE.md`, `packages/contracts/*` | tiga skenario A/B/C PowerShell, tabel diagnosis, revisi 4 |
| `apps/api/tests/test_model_onboarding.py` (33 test), `tests/test_ml_scaffold.py` (11 test) (baru) | lihat di bawah |

`apps/api/ml/` sengaja minimal (jalur "punya dataset YOLO → best.pt"). Toolkit lengkap tetap di `ml/` root.

### Tes yang benar-benar dijalankan (2026-10-20, Windows 11, Python 3.12.10)

| Tes | Hasil |
|---|---|
| `apps/api` pytest, venv API (DeepForest + bobot) | **171 lulus**, 0 skip |
| `apps/api` pytest, venv terpisah dengan **ultralytics 8.4.183 asli** + torch 2.11 CPU (tanpa DeepForest) | 170 lulus, 1 skip (DeepForest tidak terpasang) |
| `export_contract.py --check` | cocok (`info.version` 1.4.0) |
| `alembic upgrade head` + `alembic check` (DB sementara) | "No new upgrade operations detected" |
| `ml` pytest (root toolkit memakai adapter API) | **36 lulus** |
| `check-model.ps1` vs bobot **nyata**: model jagung tim (path berspasi), `yolo11n.pt` COCO + foto uji, path tidak ada, folder run, `.onnx`, `.pt` rusak, venv tanpa ultralytics, label map salah | pesan & exit code sesuai (0/1/2); COCO → PERINGATAN; folder → saran `weights\best.pt` |
| `run-with-model.ps1` (via `powershell -File`, port 18095, data dir sementara) + model jagung | health `loaded`, `sha256:9c2e20232a359fd5`; unggah foto NEON → analyze 201, 50 kandidat semua `pending` (2.4 s CPU). Uji jalan, **bukan akurasi** (model jagung pada foto hutan) |
| `run-with-model.ps1` label map salah | check gagal → API tidak dijalankan; env sesi tidak berubah |
| `run-simulation.ps1` (port 18096) | health `mode=simulation`; dua analisis → kotak identik; notice & disclaimer laporan "SIMULASI — BUKAN AI"; env pulih setelah server dihentikan |
| `ml/train.py` → `validate_model.py` → `check-model.ps1` | dataset **sintetis** 14 gambar, 1 epoch CPU dari `yolo11n.pt` lokal: lulus tanpa unduhan; metrik 0 (wajar), bukan model tanaman |

Temuan selama uji (sudah ditangani):
- `powershell -File … -LabelMapJson '{"jagung":"plant"}'` di PowerShell 5.1 tiba sebagai `{jagung:plant}` → parser
  menerima bentuk itu dan dokumentasi menyarankan `-LabelMap 'jagung=plant'`. `check_model.py` menerima label map
  lewat env, bukan argumen.
- Ultralytics mengartikan `path:` relatif di `dataset.yaml` terhadap folder kerja, bukan berkas yaml → `train.py` /
  `validate_model.py` memakai salinan yaml beralamat absolut, dan key `download` dibuang.
- `pip install torch` gagal di folder berpath panjang (>260 karakter, Long Path Windows) → dicatat di README.

Skrip & tes tidak mengunduh bobot atau memasang paket. Venv uji ultralytics, data dir, dan dataset sintetis ada
di scratchpad sesi Claude, bukan di Git.

### Untuk Codex (frontend) — revisi 4

1. Regenerasi tipe dari `packages/contracts/openapi.yaml` (revisi 4). Tidak ada field dihapus.
2. **Wajib**: tangani `health.model.mode === "simulation"` (atau `run.target === "simulation"`). Tampilkan
   `target_label` / "SIMULASI — BUKAN AI" secara mencolok di status model, tombol/hasil analisis, kartu kandidat, dan
   hitungan. Jangan menyebut kandidat simulasi sebagai "tanaman" atau "AI". `confidence` simulasi = `null`.
3. `adapter`/`target` kini bisa `"simulation"`; pastikan switch/regex lama tidak jatuh ke wording "kandidat tanaman".
4. Status model: pakai `mode` + `state` + `message`. `diagnostic_code` boleh dipakai untuk petunjuk singkat (mis.
   `MODEL_FILE_NOT_FOUND` → "periksa path bobot"). `MODEL_PATH_NOT_SET` = mode manual normal, bukan error merah.
5. Error 503 `/analyze`: `error.details.diagnostic_code` sama dengan health. Teks MODEL_NOT_CONFIGURED berubah
   (akhiran lama hilang; jangan cocokkan string).
6. `GENERIC_COCO_MODEL`: `target_label` sudah "Kandidat dari model COCO umum (BUKAN model tanaman)"; tampilkan
   `limitations[0]`.
7. `SurveyReport.disclaimers` dapat diawali butir "SIMULASI — BUKAN AI: …"; tampilkan di laporan/PDF.
8. E2E: `run-simulation.ps1` atau `WALLACEA_DETECTOR=simulation` memberi alur analisis nyata yang deterministik
   tanpa bobot (pengganti impor deteksi sintetis bila diinginkan). Suite yang butuh `MODEL_NOT_CONFIGURED` harus
   tetap memakai API tanpa variabel ini.

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
- Kontrak **revisi 5** (`info.version` 1.5.0, aditif): revisi 2 `health.model.{adapter,target,target_label,device,limitations}`, revisi 3 (`/samples`, `run.target`), revisi 4 `health.model.{mode,diagnostic_code}` + target `simulation`, revisi 5 mapping (`/fields`, `/rasters`, `/map-detections`, `Survey.field_id`, `SurveyReport.mapping`, capability mapping).
- Onboarding Windows: `apps/api/scripts/check-model.ps1`, `run-with-model.ps1`, `run-simulation.ps1`; training minimal `apps/api/ml/`. Model tanaman terlatih tetap belum ada.

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
