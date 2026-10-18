# WALLACEA — Project brief

Pemilik dokumen: Claude (backend & integrasi). Terakhir diperbarui 2026-10-18.

## Masalah dan produk

WALLACEA membantu tim survei pertanian mengolah **foto drone setelah drone mendarat**: unggah foto,
tandai tanaman / titik perlu diperiksa / dugaan titik kosong, tinjau kandidat model, lalu buat laporan
per foto. Domain produk: pertanian umum. Model pertama dibatasi **satu jenis tanaman dan satu dataset**.

## Kondisi nyata saat ini

| Hal | Status |
|---|---|
| Drone | K919 MAX (paket < Rp2 juta), diterbangkan dengan remote/aplikasi bawaan |
| Integrasi drone | Hanya unggah berkas setelah mendarat. SDK/API kontrol, live video **belum terverifikasi** |
| GPS per foto, resolusi asli, kualitas foto lahan | **Belum terverifikasi** dengan unit nyata |
| Model tanaman | **Belum dilatih**. Belum ada bobot, dataset, atau metrik |
| Starter v0.1 | HTML/CSS/JS + IndexedDB + bridge FastAPI; disimpan di `legacy/starter-v01/` |
| Tim | Founder (Sistem Informasi, kuat frontend/Figma), anggota AI/ML, operasi lapangan |

## Lingkup MVP

1. Survei (CRUD) yang persist di database lokal.
2. Foto asli JPG/PNG/WebP ≤ 20 MB, divalidasi isinya, orientasi EXIF konsisten.
3. Penanda titik & bounding box ternormalisasi; koreksi, catatan, status review.
4. Kandidat model selalu `pending`; hanya `plant` + `accepted` yang dihitung.
5. Laporan per foto, CSV, gambar beranotasi & cetak PDF (frontend).
6. Jalur AI jujur: tanpa bobot → `503 MODEL_NOT_CONFIGURED`; mode manual tetap penuh.
7. Impor backup starter `schemaVersion 1` sebagai salinan.

MVP harus berguna **secara manual** walaupun model belum ada.

## Di luar lingkup (jangan dibangun)

Blockchain · kontrol autopilot · sprayer · sensor tambahan · diagnosis penyakit · rekomendasi dosis
pupuk · estimasi hasil panen · luas lahan otomatis · orthomosaic dari foto biasa · koordinat GPS
tiruan · penjumlahan hitungan antar foto bertumpang tindih sebagai jumlah tanaman unik.

## Prinsip kejujuran data

- Koordinat penanda = koordinat gambar (0–1), **bukan** lintang/bujur.
- EXIF GPS (bila ada) = posisi kamera, bukan posisi tiap tanaman. API hanya melaporkan `has_exif_gps`.
- `confidence` = keluaran model, bukan akurasi survei.
- Data contoh selalu `is_demo=true` dan berlabel ilustrasi.
- Contract test dengan detector test double **bukan** uji akurasi model.

## Tahap berikut (tidak menghambat MVP)

1. AI satu tanaman: dataset, label, split berdasarkan lahan/penerbangan, evaluasi vs hitungan lapangan.
2. Kualitas: uji SAHI setelah baseline; DeepForest hanya pembanding kanopi pohon.
3. Pemetaan: uji ketajaman/overlap foto K919, engine fotogrametri terpisah, baru Leaflet.
4. Penggunaan bersama: PostgreSQL, object storage, autentikasi, backup, audit.
