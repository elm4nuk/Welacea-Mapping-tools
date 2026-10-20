# Codex frontend handoff — workspace pemetaan, 20 Oktober 2026

## Delivery pemetaan revision 5

- Branch/worktree: `agent/codex-mapping` / `D:\coding\wallacea-worktrees\codex-mapping`.
- Base frontend: `1cb6d5183eebb458c4e341981503e0d70a164537`.
- Commit shell awal: `472fe7563ba18b4866f8255eeab396a07ae82aed`, disusul
  `0c327c2`, `e04ae04`, `834f411`, dan `a3c9a2c`.
- Sumber kebenaran Claude: backend `40ba48764e9107f3aafb253b8bf9a4431a4e9977`,
  OpenAPI revision 5 `f2e770f7f9a4b51b0923ccc49971c0c6c7ffc2c2`, dan docs
  `1d1d36ce858bbc2a1d2b1a468bdcd56e1ef910d2`. Handoff `CONTRACT_READY`
  terbaru dibaca pada `a911f30d4c620f2bd49881065884b824e3fa4c7c`; Claude juga mencatat
  baseline integrasi backend revision 5 di `integration/wallacea-mapping` @ `ca67ffe`.
- Commit integrasi revision 5: `e0c598d` (`feat(web): integrate revision 5 mapping
  API`). Commit dokumentasi/screenshot menyusul commit ini. Tidak ada push, merge
  `main`, deploy, perubahan backend/OpenAPI, model, atau dataset.

### Sebelum / sesudah

Sebelum revision 5, workspace hanya memiliki draf batas lokal: simpan dan GeoTIFF
dinonaktifkan karena kontrak belum tersedia. Sesudah integrasi, frontend memakai API
nyata untuk CRUD/impor batas, tautan `Survey.field_id`, metrik geodesik authoritative,
`If-Match` dan pemulihan konflik; upload/progress/tile GeoTIFF dengan bounds dan CRS;
serta run dan kandidat geografis pending/accepted/rejected.

Map tetap menjadi fokus. Panel desktop dapat diringkas; tablet/HP memakai Sheet. Terra
Draw menangani gambar/edit Polygon, Turf hanya memberi preview sebelum save, dan
MapLibre menampilkan tile raster serta kandidat berdasarkan geometri WGS84 dari API.
Foto biasa tidak diproyeksikan. Impor GeoTIFF tidak diklaim sebagai orthomosaic atau
georeferensi yang diverifikasi WALLACEA.

Simulasi memakai banner permanen **SIMULASI — BUKAN AI**, kandidat dimulai sebagai
pending, skor disebut skor model, dan hanya kandidat `kind=plant` yang accepted masuk
hitungan per-raster. Laporan menambahkan batas dan ringkasan tiap raster serta menolak
klaim bahwa hitungan lintas raster/penerbangan adalah tanaman unik.

Basemap memakai tile standar OpenStreetMap dengan atribusi terlihat dan penjelasan
bahwa layanan memerlukan internet serta bukan citra satelit. Kegagalan tile tidak
menyembunyikan boundary/raster lokal. CR-FE-005 kini ditandai dipenuhi; tidak ada
request kontrak baru.

### Verifikasi aktual

- `pnpm --filter @wallacea/web generate:api`: lulus dari OpenAPI revision 5.
- `pnpm install --frozen-lockfile`: lulus; lockfile supply-chain check lulus.
- `pnpm typecheck:web`: lulus.
- `pnpm --filter @wallacea/web test`: **26/26 lulus** dalam 5 file.
- `pnpm build:web`: lulus. Vite hanya memperingatkan chunk MapLibre/editor >500 kB;
  workspace GIS sudah lazy-loaded dan menjadi chunk terpisah.
- `pnpm peers check`: lulus tanpa masalah peer dependency.
- `git diff --check`: lulus.
- Backend revision 5 `python -m pytest`: **244 lulus, 2 skip**, dengan dua warning
  Rasterio yang memang berasal dari fixture raster tanpa georeferensi/GCP.
- Playwright status model: **3/3 lulus**; manual, configured, loaded, error, dan
  simulasi diperiksa jujur pada desktop/tablet/mobile.
- Playwright UI pemetaan terisolasi: **8 lulus, 1 skip**. Skip adalah emulasi gestur
  gambar sentuh mobile; impor GeoJSON, validasi, Sheet, dan responsivitas mobile lulus.
- Playwright API revision 5: **6/6 lulus** pada Chromium 1440×900, 820×1180, dan
  390×844. Alur mencakup save/reload batas, metrik backend, konflik/reload, cancel,
  ekspor/hapus, upload GeoTIFF nyata, TileJSON/bounds, simulasi pending→accepted,
  laporan accepted-only, dan penghapusan raster.
- Regresi workspace foto terhadap API revision 5 mode manual: **18/18 lulus** pada
  ketiga viewport. Ini mencakup demo, multi-upload/EXIF/invalid, draf/undo/redo,
  save/reload, konflik, proteksi navigasi, API offline/retry, canvas zoom/pan,
  ekspor, backup, laporan, serta edit/delete survei.
- Inferensi model asli tidak dijalankan karena bobot tanaman terlatih tidak tersedia.
  Pengujian kandidat geografis memakai detector simulasi backend dan selalu diberi
  label data QA/bukan AI.

Screenshot baseline shell lokal: `docs/handoff/screenshots/mapping/desktop.png`,
`tablet.png`, `mobile.png`. Screenshot revision 5 dengan raster/kandidat dan keadaan
review setara: `rev5-desktop.png`, `rev5-tablet.png`, `rev5-mobile.png`. Semuanya telah
diperiksa pada ukuran viewport yang tepat; basemap sengaja digagalkan agar fallback,
raster lokal, atribusi, dan pesan offline dapat diverifikasi deterministik.

### Urutan integrasi yang aman

1. Cherry-pick Claude `40ba487`, lalu `f2e770f`, `1d1d36c`, dan handoff `a911f30` ke
   `integration/wallacea-mvp` jika commit itu belum ada.
2. Cherry-pick rangkaian Codex `472fe75`, `0c327c2`, `e04ae04`, `834f411`,
   `a3c9a2c`, lalu `e0c598d`, kemudian commit dokumentasi/screenshot sesudahnya.
3. Jalankan export/check kontrak, migrasi DB sementara, seluruh pytest backend,
   typecheck, Vitest, build, peer check, serta kedua suite Playwright API nyata.

Alternatif yang lebih pendek: bila `integration/wallacea-mapping` @ `ca67ffe` dipakai
sebagai baseline resmi, langsung cherry-pick rangkaian Codex pada langkah 2; jangan
mengulang commit Claude yang sudah terkandung di baseline itu.

---

## Handoff frontend AI sebelumnya

## Delivery

- Branch: `agent/codex-frontend`
- Worktree: `D:\coding\wallacea-worktrees\codex-frontend`
- Titik awal branch: `678ff41`
- Implementasi onboarding/status awal: `be46aabb7807eb4efd42fa91aa7ef03c87049b25`
- Integrasi kontrak revision 4 dan command final: `9e487376325e45d915477f63172dba0a329efb54`
- Baseline frontend yang dibawa ke branch ini: `34b3572`, `b3fc2c0`, `2a0f7ff`,
  `fc505df`, dan `2afbf36` (cherry-pick dari pekerjaan Codex yang sudah ada).
- Sumber kebenaran backend/kontrak yang sudah **commit** dan dibaca:
  `agent/claude-backend` @ `1ecda6c4eef476aaed84a212623c9ade9e696846`, OpenAPI revision 4
  (`cfacdda`).
- Tidak ada perubahan backend, OpenAPI, model, dataset, push, deploy, atau merge ke `main`.

## Perubahan UX

Status koneksi API tetap terpisah dari status model. Status model kini diturunkan dari
health response dan tampil sebagai salah satu dari:

- **Mode manual — model belum dikonfigurasi**;
- **Model ditemukan — siap dimuat**;
- **Model aktif**;
- **Konfigurasi model bermasalah**;
- **SIMULASI — BUKAN AI** sebagai banner permanen berkontras tinggi.

Panel responsif **Cara mengaktifkan AI** menjelaskan bahwa `best.pt` adalah file,
bukan command; lokasi `apps\api\models\best.pt`; dependency PyTorch CPU 2.11 /
torchvision 0.26 dan `requirements-ai.txt`; contoh command final
`check-model.ps1` dan `run-with-model.ps1` dengan tombol salin; keterbatasan model
COCO umum; dan kebutuhan training menggunakan dataset beranotasi. UI tidak menawarkan
unggah bobot melalui browser.

Tombol analisis mengikuti keadaan nyata: manual mengarahkan pengguna ke setup,
configured/loaded dapat menganalisis bila guard foto/draf/API terpenuhi, error
menampilkan alasan ramah pengguna dan aksi periksa ulang, dan simulation tetap aktif
namun tidak pernah disebut hasil AI. Pesan khusus mencakup bobot hilang, dependency
Ultralytics, label map, timeout, inference failed, dan API terputus.

Kandidat model/simulasi tetap `pending` sampai pengguna memilih Terima atau Tolak.
Koreksi kategori, catatan, dan koordinat tetap tersedia. Hanya tanaman nyata/model
`accepted` masuk hitungan tanaman final; simulation yang diterima ditampilkan sebagai
hitungan simulasi terpisah. Confidence diberi label **Skor model**, bukan akurasi. Sumber
simulasi ditampilkan eksplisit. Aksi duplikat “Tolak” dihapus tanpa mengubah reducer,
transformasi koordinat, atau persistence.

## Kontrak dan request

Kontrak committed Claude revision 4 menyediakan empat state model, `mode`,
`diagnostic_code`, metadata adapter, target, target label, device, limitations, serta
target analysis run. Frontend memakai `mode=simulation` / target `simulation` secara
typed dan memakai kode diagnosis untuk pesan setup; ia tidak menebak dari nama model
atau teks bebas.

`docs/requests/codex-model-onboarding.md` menandai CR-FE-004 **dipenuhi** oleh revision 4:

1. discriminator simulation pada health dan analysis run;
2. `ModelStatus.diagnostic_code` untuk penyebab setup;
3. interface final script PowerShell.

Tipe frontend sudah diregenerasi dari OpenAPI revision 4. Command panel sama dengan
script committed Claude, termasuk `-ModelPath .\models\best.pt` dan
`-LabelMap 'plant=plant'`.

## Verifikasi aktual

Perintah yang lulus:

    pnpm typecheck:web
    pnpm --filter @wallacea/web test
    pnpm build:web
    pnpm peers check
    git diff --check

Hasil:

- TypeScript typecheck: lulus.
- Vitest: 23/23 lulus dalam 4 file.
- Production build: lulus; hanya peringatan chunk Vite >500 kB yang sudah ada.
- Peer dependency check: lulus.
- Playwright: 21 lulus, 3 dilewati pada desktop 1440×900, tablet 820×1180, dan
  mobile 390×844. Tiga yang dilewati adalah smoke test DeepForest nyata karena
  `WALLACEA_E2E_REAL_MODEL`/bobot tidak diaktifkan pada API QA.
- Status manual/configured/loaded/error/simulation dan panel setup diuji di ketiga
  viewport. Workspace nyata juga menguji upload, EXIF, draf, undo/redo, save/reload,
  candidate review, konflik revision, proteksi navigasi, API offline/retry,
  CSV/PNG/PDF, edit/delete survei, dan validasi upload.
- Focused E2E onboarding revision 4: 3/3 lulus pada ketiga viewport.
- Real simulation E2E terhadap FastAPI revision 4: 3/3 lulus pada ketiga viewport.
  Alur membuat survei, mengunggah foto QA, menjalankan simulation, memastikan kandidat
  pending tanpa confidence, menerima kandidat, menyimpan, dan memastikan hitungan
  tetap `0 Tanaman terkonfirmasi` + `1 simulasi diterima`.
- Simulation tersebut adalah kotak deterministik QA dari backend dan selalu dilabeli
  **SIMULASI — BUKAN AI**, bukan hasil deteksi atau bukti akurasi.

Tipe frontend diregenerasi langsung dari revision 4 committed pada branch Claude.

## Urutan integrasi ke `integration/wallacea-mvp`

1. Integrasikan commit Claude `1ecda6c` lebih dahulu ke `integration/wallacea-mvp`.
2. Integrasikan commit Codex `be46aab`, `9e48737`, dan commit dokumentasi setelahnya. Bila lima
   commit baseline frontend belum ada di integration, cherry-pick berurutan:
   `34b3572 b3fc2c0 2a0f7ff fc505df 2afbf36 be46aab 9e48737`.
3. Pastikan `apps/web/src/api/schema.d.ts` tetap identik dengan OpenAPI Claude final;
   jangan mengubah kontrak dari sisi frontend.
4. Jalankan export/check kontrak, seluruh pytest backend/ML yang relevan, lalu
   typecheck, Vitest, build, dan Playwright frontend termasuk real simulation serta
   real-model smoke bila bobot tersedia.

Commit Claude revision 4 perlu diintegrasikan **lebih dahulu**. Jangan merge ke `main`
sebelum review dan izin eksplisit.
