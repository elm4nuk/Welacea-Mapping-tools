# CR: katalog foto contoh berlisensi dan semantik keluaran model

- Diajukan oleh / tanggal / branch: Codex / 2026-10-19 / `agent/codex-inference-integration`
- Status: kebutuhan kontrak dipenuhi pada revisi 2–3; integrasi picker katalog foto contoh tetap pekerjaan frontend terpisah.

## CR-FE-002 — katalog foto contoh berlisensi (kontrak terpenuhi)

Status 2026-10-19: kontrak revisi 3 pada `agent/claude-backend` menambahkan
`GET /api/v1/samples`, endpoint berkas, metadata sumber/lisensi, dan fixture.
Frontend redesign ini tidak menambahkan picker katalog; integrasi UI dapat dilakukan
terpisah tanpa mengubah alur unggah atau kontrak.

Alasan: endpoint `POST /demo/surveys` saat ini benar dan aman, tetapi hanya membuat ilustrasi internal.
Frontend tidak mempunyai foto udara contoh dengan sumber serta lisensi yang dapat ditampilkan. Karena itu UI
hanya menawarkan “contoh ilustrasi” dan tidak menyebutnya foto drone atau hasil ML.

Usulan: sediakan aset atau katalog stabil berisi minimal `id`, `title`, `file_url`, `source_name`,
`source_url`, `license_name`, dan `license_url`. Jika contoh perlu masuk melalui alur unggah normal,
berkas harus dapat diambil sebagai `File` tanpa melewati aturan validasi upload yang ada.

Kompatibilitas: endpoint/aset baru; tidak mengubah kontrak lama.

Acceptance: sumber dan lisensi tampil sebelum pengguna memilih contoh; foto diunggah melalui endpoint upload
biasa; hasil analisis hanya muncul setelah endpoint `/analyze` sungguhan berhasil.

## CR-FE-003 — semantik kandidat model (terpenuhi)

Status 2026-10-19: terpenuhi oleh kontrak revisi 2 dan dipertegas pada revisi 3
di branch `agent/claude-backend`. Frontend memakai `target_label` dan `target`
secara langsung, serta menampilkan `adapter`, `device`, dan `limitations` bila
tersedia. Respons revisi 1 tetap didukung sebagai fallback tanpa mengarang
semantik model.

Alasan: kontrak menyediakan `model_id`, tetapi belum menyatakan apakah bbox berarti tanaman, tajuk pohon,
atau objek lain. Frontend sementara memakai istilah “kandidat tajuk pohon” hanya bila `model_id` dari API
mengandung `DeepForest`; model lain tetap memakai “kandidat tanaman”.

Usulan field opsional pada `ModelStatus` dan `AnalysisRun`:

```json
{"candidate_semantics":"tree_crown"}
```

Nilai awal yang diusulkan: `plant`, `tree_crown`, atau `null`. `null` berarti UI memakai istilah generik.

Kompatibilitas: field response opsional, non-breaking.

Acceptance: health dan run mengembalikan nilai yang sama untuk adaptor aktif; DeepForest mengembalikan
`tree_crown`; frontend tidak perlu menebak semantik dari nama model.
