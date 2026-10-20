# Codex frontend handoff — workspace pemetaan, 20 Oktober 2026

## Delivery pemetaan

- Branch/worktree: `agent/codex-mapping` / `D:\coding\wallacea-worktrees\codex-mapping`.
- Base frontend: `1cb6d5183eebb458c4e341981503e0d70a164537`.
- Commit implementasi shell peta: `472fe7563ba18b4866f8255eeab396a07ae82aed`.
- Sumber kontrak terakhir yang sudah committed dan dibaca: Claude
  `1ecda6c4eef476aaed84a212623c9ade9e696846`, OpenAPI revision 4.
- Pada saat handoff ini ditulis, perubahan geospasial Claude masih belum committed.
  Jangan mengintegrasikan file backend yang masih dirty; ambil SHA `CONTRACT_READY`
  baru dari Claude lebih dahulu.
- Tidak ada push, merge `main`, deploy, perubahan backend/OpenAPI, model, atau dataset.

### Yang sudah tersedia

- Navigasi survei eksplisit **Peta lahan / Foto & AI / Laporan**. Editor foto,
  persistence anotasi, transformasi koordinat normalized, dan laporan existing tidak
  diubah.
- Workspace MapLibre dominan dengan panel layer/detail yang dapat diringkas pada
  desktop dan Sheet pada tablet/HP.
- Terra Draw Polygon/select untuk menggambar dan mengedit draf; impor menerima tepat
  satu Polygon/MultiPolygon WGS84 dengan urutan longitude, latitude. GeoJSON invalid,
  range koordinat, ring terbuka, dan jumlah feature ditolak dengan pesan Indonesia.
- Turf menampilkan luas/keliling sebagai **Preview Turf**, bukan angka tersimpan.
  Ekspor GeoJSON mempertahankan geometry dan menambahkan nama/sumber draf.
- Basemap OpenStreetMap dikonfigurasi dengan atribusi terlihat dan label jelas bahwa
  ia membutuhkan internet serta bukan citra satelit. Bila tile gagal, boundary lokal
  tetap terlihat pada fallback netral.
- Draft map ikut proteksi navigasi dan `beforeunload`; hapus draf memakai konfirmasi.
- MapLibre/Terra Draw/Turf dimuat lewat lazy chunk sehingga editor foto tidak menarik
  bundle GIS ketika workspace peta belum dibuka.

### Batas kontrak yang sengaja tidak dipalsukan

Revision 4 belum memiliki boundary CRUD, raster GeoTIFF, tile/bounds/CRS, atau kandidat
AI geografis. Karena itu tombol **Simpan** dan **Unggah GeoTIFF** tetap disabled dengan
alasan yang terlihat; draf diberi label lokal dan dinyatakan hilang saat reload. Tidak
ada endpoint buatan, persistence palsu, proyeksi foto JPG/PNG, polygon otomatis, atau
hasil AI geografis. Kebutuhan lengkap tercatat di
`docs/requests/codex-mapping-contract.md` sebagai CR-FE-005.

Setelah Claude memberi kontrak committed, frontend masih harus menghubungkan:

1. boundary query/mutation + `If-Match`, backend metrics authoritative, conflict/reload;
2. upload/status/tile GeoTIFF, opacity, bounds, footprint, metadata CRS;
3. geographic findings, detail raster/run, filter pending/accepted/rejected, dan
   accepted-only summary;
4. capability/limit discovery granular, lalu tes API nyata untuk save/reload, edit,
   cancel, conflict, delete, raster placement, dan review kandidat.

### Verifikasi aktual pemetaan

- `pnpm install --frozen-lockfile`: lulus; lockfile supply-chain check lulus.
- Type generation dari OpenAPI committed Claude revision 4: lulus dan menghasilkan
  tidak ada diff pada `apps/web/src/api/schema.d.ts`.
- `pnpm typecheck:web`: lulus.
- `pnpm --filter @wallacea/web test`: **26/26 lulus** dalam 5 file.
- `pnpm build:web`: lulus; warning chunk MapLibre/editor >500 kB tetap tercatat.
- `pnpm peers check`: lulus, tidak ada masalah peer dependency.
- `git diff --check`: lulus.
- Focused Playwright mapping: **6/6 lulus** pada Chromium 1440×900, 820×1180,
  dan 390×844. Skenario menguji impor boundary QA sintetis, preview, UI responsif,
  Sheet, API capability tidak tersedia, tombol save disabled, GeoJSON invalid, dan
  tile OSM yang sengaja digagalkan. Ini tes UI/kontrak lokal, bukan integrasi backend.
- Screenshot viewport yang diperiksa: `docs/handoff/screenshots/mapping/desktop.png`,
  `tablet.png`, dan `mobile.png`. Desktop/tablet memperlihatkan boundary tetap terlihat
  pada fallback ketika tile gagal; mobile memverifikasi toolbar wrap dan kanvas tanpa
  panel permanen.
- Regresi Playwright workspace existing dijalankan terhadap snapshot API Claude
  revision 4 yang committed, pada DB QA terpisah: run pertama **15/18 lulus** dan tiga
  kegagalan identik hanya karena selector `/Laporan/` menjadi ambigu setelah navigasi
  baru. Selector dipersempit ke nav `Ruang kerja survei`; ketiga skenario gagal tadi
  kemudian **3/3 lulus** pada desktop/tablet/mobile. Alurnya mencakup demo, multi-upload,
  EXIF, anotasi manual, undo/redo, save/reload, konflik, API offline/retry, ekspor,
  laporan, backup, edit/delete survei, dan isolasi foto.
- Tes API nyata untuk persistence/raster/geographic findings **belum dapat dijalankan**
  karena kontrak/commit Claude belum tersedia. Tes regresi API existing tidak diklaim
  dijalankan ulang pada delivery pemetaan ini; hasil delivery frontend sebelumnya ada
  di bagian historis di bawah.

### Urutan integrasi yang aman

1. Minta SHA final Claude yang menyatakan `CONTRACT_READY` untuk mapping, lalu integrasikan
   commit backend/migrasi/OpenAPI itu ke `integration/wallacea-mvp`.
2. Regenerasi tipe dari snapshot tersebut dan selesaikan adapter API di branch Codex;
   jangan memakai nama endpoint dari CR-FE-005 sebagai fakta kontrak.
3. Cherry-pick `472fe75`, lalu commit integrasi API lanjutan dan commit handoff terbaru.
4. Jalankan export/check kontrak, migrasi DB sementara, seluruh pytest backend, typecheck,
   Vitest, build, peer check, dan Playwright API nyata pada tiga viewport.

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
