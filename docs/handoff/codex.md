# Codex frontend handoff — 20 Oktober 2026

## Delivery

- Branch: `agent/codex-frontend`
- Worktree: `D:\coding\wallacea-worktrees\codex-frontend`
- Titik awal branch: `678ff41`
- Implementasi onboarding/status model: `be46aabb7807eb4efd42fa91aa7ef03c87049b25`
- Baseline frontend yang dibawa ke branch ini: `34b3572`, `b3fc2c0`, `2a0f7ff`,
  `fc505df`, dan `2afbf36` (cherry-pick dari pekerjaan Codex yang sudah ada).
- Sumber kebenaran backend/kontrak yang sudah **commit** dan dibaca:
  `agent/claude-backend` @ `e7f99cbeff82e7ad768ff2c64a958cbf2509e6b6`, OpenAPI revision 3.
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
bukan command; lokasi bobot server-side; dependency AI; contoh command
`check-model.ps1` dan `run-with-model.ps1` dengan tombol salin; keterbatasan model
COCO umum; dan kebutuhan training menggunakan dataset beranotasi. UI tidak menawarkan
unggah bobot melalui browser.

Tombol analisis mengikuti keadaan nyata: manual mengarahkan pengguna ke setup,
configured/loaded dapat menganalisis bila guard foto/draf/API terpenuhi, error
menampilkan alasan ramah pengguna dan aksi periksa ulang, dan simulation tetap aktif
namun tidak pernah disebut hasil AI. Pesan khusus mencakup bobot hilang, dependency
Ultralytics, label map, timeout, inference failed, dan API terputus.

Kandidat model/simulasi tetap `pending` sampai pengguna memilih Terima atau Tolak.
Koreksi kategori, catatan, dan koordinat tetap tersedia. Hanya tanaman `accepted`
masuk hitungan final. Confidence diberi label **Skor model**, bukan akurasi. Sumber
simulasi ditampilkan eksplisit. Aksi duplikat “Tolak” dihapus tanpa mengubah reducer,
transformasi koordinat, atau persistence.

## Kontrak dan request

Kontrak committed Claude revision 3 menyediakan empat state model, metadata adapter,
target, target label, device, limitations, serta target analysis run. Kontrak itu belum
memiliki discriminator simulasi atau kode diagnosis setup yang stabil. Frontend
sementara hanya mengenali field aditif eksplisit `simulation`, `adapter=simulation`,
atau `mode=simulation`; ia tidak menebak dari nama model atau teks bebas.

`docs/requests/codex-model-onboarding.md` mencatat CR-FE-004 untuk:

1. discriminator simulation pada health dan analysis run;
2. `ModelStatus.error_code` untuk penyebab setup;
3. interface final script PowerShell.

Pada saat handoff ini ditulis, worktree Claude masih memiliki perubahan backend,
simulation, fixture kontrak, dan script yang belum di-commit; SHA terbaru tetap
`e7f99cb`. Perubahan setengah jadi tersebut sengaja tidak dikonsumsi. Setelah Claude
membuat commit final, cocokkan nama field serta parameter script dengan CR-FE-004,
regenerasi tipe dari kontrak final, lalu hapus compatibility shim bila tidak diperlukan.

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
- API pengujian adalah FastAPI revision 3 yang bersih pada port terpisah. Simulation
  E2E menggunakan health fixture bernama QA, bukan hasil ML. Inferensi/simulation
  backend Claude yang sedang dikerjakan belum dapat diuji sebelum ada commit final.

Tipe frontend diregenerasi langsung dari snapshot revision 3 yang committed pada
integration/Claude, bukan dari OpenAPI lama yang masih ada pada branch frontend.

## Urutan integrasi ke `integration/wallacea-mvp`

1. Selesaikan dan commit pekerjaan Claude. Review SHA, `packages/contracts/CHANGELOG.md`,
   OpenAPI, fixture, serta interface `check-model.ps1`/`run-with-model.ps1`.
2. Integrasikan commit Claude lebih dahulu ke `integration/wallacea-mvp`.
3. Integrasikan commit Codex `be46aab` (dan commit dokumentasi setelahnya). Bila lima
   commit baseline frontend belum ada di integration, cherry-pick berurutan:
   `34b3572 b3fc2c0 2a0f7ff fc505df 2afbf36 be46aab`.
4. Regenerasi `apps/web/src/api/schema.d.ts` dari OpenAPI Claude final. Selaraskan
   discriminator simulation dan command setup dengan CR-FE-004; jangan mengubah
   kontrak diam-diam dari sisi frontend.
5. Jalankan export/check kontrak, seluruh pytest backend/ML yang relevan, lalu
   typecheck, Vitest, build, dan Playwright frontend termasuk real simulation serta
   real-model smoke bila bobot tersedia.

Commit Claude final perlu diintegrasikan **lebih dahulu** apabila ia mengubah kontrak
revision 3. Jangan merge ke `main` sebelum review dan izin eksplisit.
