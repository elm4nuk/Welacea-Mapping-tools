# WALLACEA — Acceptance criteria MVP

Status dicatat jujur: **[otomatis]** = ada test yang dijalankan; **[manual]** = harus dicek manusia/browser;
**[belum]** = belum bisa diuji (butuh model/data/perangkat).

## A. Backend (pemilik: Claude)

| # | Kriteria | Bukti |
|---|---|---|
| A1 | Survei, foto, anotasi, review, laporan persist setelah server restart | [otomatis] `test_persistence.py` |
| A2 | Skema DB dibuat lewat migrasi Alembic dan sama dengan model ORM | [otomatis] `test_migrations_match_models` |
| A3 | Upload JPG/PNG/WebP; MIME dari isi; SVG/teks/GIF/terpotong ditolak | [otomatis] `test_photos.py` |
| A4 | > 20 MB → 413; > 60 MP → 413 `IMAGE_TOO_LARGE` | [otomatis] + live curl 25 MB → 413 |
| A5 | Orientasi EXIF: dimensi pasca-orientasi, `display` terorientasi, asli utuh | [otomatis] `test_exif_orientation_metadata_and_display` |
| A6 | Duplikat dalam survei → disimpan + warning `DUPLICATE_IN_SURVEY` | [otomatis] |
| A7 | Nama berkas tidak dipakai sebagai path; berkas dibersihkan saat gagal/hapus | [otomatis] |
| A8 | Koordinat/bbox/confidence invalid, NaN/Infinity → 422 | [otomatis] `test_annotations.py` |
| A9 | `If-Match` wajib untuk ubah/hapus penanda; konflik → 409 + versi server | [otomatis] |
| A10 | ID salah → 404 envelope; semua error berbentuk `{error:{code,message,details,request_id}}` | [otomatis] |
| A11 | Tanpa model: health jujur, analyze → 503 `MODEL_NOT_CONFIGURED`, tanpa run palsu, manual tetap jalan | [otomatis] |
| A12 | Test double: kandidat pending tidak dihitung; accept → hitungan naik; reject → tidak | [otomatis] **contract test, bukan akurasi** |
| A13 | Analisis berulang terkendali (`reject`/`replace_pending`/`append`), tiap run punya ID | [otomatis] |
| A14 | Run gagal/timeout/terputus restart → `failed` dengan `error_code` | [otomatis] |
| A15 | Impor deteksi: dimensi & sha256 dicek, label non-tanaman ditolak | [otomatis] |
| A16 | Impor backup starter `schemaVersion 1` sebagai salinan; demo tetap berlabel; catatan terjaga; atomik | [otomatis] `test_backup_import.py` |
| A17 | CSV: BOM UTF-8, satu baris per penanda, formula injection dinetralkan | [otomatis] |
| A18 | CORS hanya origin terdaftar; server bind loopback | [otomatis] CORS; [manual] `netstat` saat `python -m app` |
| A19 | Snapshot OpenAPI = skema yang di-generate; fixtures valid terhadap skema | [otomatis] `test_contract.py` |
| A20 | Inferensi model tanaman nyata | **[belum]** — tidak ada bobot/dataset |

## B. Frontend (pemilik: Codex) — ringkasan dari prompt Codex

- B1 Typecheck & production build lulus.
- B2 Transformasi koordinat ternormalisasi benar pada zoom/pan/resize/EXIF (memakai `display_url`).
- B3 Pending → accepted/rejected mengubah hitungan sesuai `counts` API.
- B4 Tambah → edit → undo/redo tidak memengaruhi foto lain; response basi diabaikan saat foto berganti.
- B5 Upload multi-berkas dengan progres & alasan penolakan per berkas.
- B6 API mati, model belum ada (503), konflik revisi (409), impor backup invalid → pesan jelas.
- B7 Tidak ada angka/hasil AI palsu; data contoh selalu berlabel.
- B8 CSV/PNG/PDF laporan dengan judul, survei, tanggal, legenda, status review, disclaimer.

## C. Integrasi (pemilik: Claude, branch `integration/wallacea-mvp`)

E2E dengan API sungguhan (bukan mock):

1. Buat survei → unggah foto nyata (termasuk JPEG ber-EXIF orientasi ≠ 1).
2. Tambah penanda, koreksi kategori/catatan, hapus, undo/redo.
3. Reload browser → data tetap ada.
4. Laporan & CSV sesuai hitungan.
5. Tanpa model: tombol deteksi menampilkan pesan 503 yang jelas, mode manual tetap jalan.
6. Laporkan eksplisit: apakah browser test dijalankan, apakah inferensi model nyata dijalankan
   (saat ini **tidak ada model**), apakah ada tes dengan foto K919 nyata (saat ini **belum**).
