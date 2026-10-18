# WALLACEA — Survei Pertanian

Versi awal yang bisa dijalankan untuk mengolah foto setelah drone K919 MAX mendarat.

## Yang sudah dibuat

- Dashboard responsif dengan data contoh yang diberi label ilustrasi.
- Buat/edit/hapus survei; simpan foto asli JPG, PNG, WebP.
- Penandaan titik tanaman, perlu pemeriksaan, dan dugaan titik kosong.
- Koreksi jenis penanda, catatan, hapus, undo, zoom foto.
- Penyimpanan lokal IndexedDB; backup/pulihkan JSON sebagai salinan.
- Ekspor penanda CSV, gambar beranotasi PNG, cetak laporan ke PDF.
- Impor kandidat AI JSON yang divalidasi terhadap dimensi foto aktif.
- Pengaturan endpoint backend AI dan alur review kandidat sebelum dihitung.
- Bridge FastAPI untuk model Ultralytics deteksi tanaman yang dilatih tim.

**Tidak disertakan:** model tanaman terlatih, kontrol penerbangan/SDK K919, live stream,
orthomosaic, pemetaan GPS otomatis, diagnosis penyakit, database multiuser, APK.
Data contoh bukan hasil penerbangan dan bukan hasil AI.

## Jalankan frontend (Windows, macOS, Linux)

Python 3.11 atau lebih baru disarankan untuk backend.

```bash
cd dist
python3 -m http.server 8080
```

Windows: gunakan `py -m http.server 8080` jika `python3` tidak tersedia.
Buka http://localhost:8080. Buka melalui server lokal; hindari membuka file HTML langsung.
Frontend memakai HTML/CSS/JavaScript tanpa build dan tanpa framework tambahan.
Font Google bersifat opsional: jika tidak tersedia, UI memakai font sistem.

## Alur penggunaan nyata

1. Buka **Survei baru**. Isi nama, tanaman, lokasi, tanggal.
2. Salin foto asli dari kartu/aplikasi drone ke komputer sesuai manual unit.
3. Unggah maksimal 40 foto per survei, 20 MB per foto, 60 megapiksel per foto.
4. Pilih alat **Tanaman**, **Periksa**, atau **Titik kosong**, kemudian klik foto.
5. Klik penanda untuk menulis catatan, koreksi kategori, atau menghapus.
6. Laporan menampilkan hitungan per foto. Pilih Cetak / PDF untuk menyimpan PDF lewat browser.
7. Ekspor backup JSON secara berkala. IndexedDB bukan penyimpanan bersama atau backup cloud.

Jangan menjumlahkan tanaman dari foto yang bertumpang tindih sebagai jumlah unik lahan.
Koordinat x/y adalah koordinat relatif gambar, bukan lintang/bujur.
Jika foto sudah diputar/crop, gunakan dimensi dan gambar yang sama saat menjalankan model.

## Backend opsional: API tanpa model

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell: `py -m venv .venv`, lalu `.venv\Scripts\Activate.ps1`.

http://127.0.0.1:8000/health memberikan status API. API bisa berjalan sebelum model tersedia;
`POST /analyze` sengaja mengembalikan 503 jika bobot belum diatur. Tidak ada hasil AI palsu.
Swagger API: http://127.0.0.1:8000/docs.

## Hubungkan model tanaman

1. Siapkan foto satu jenis tanaman dari kamera drone kalian.
2. Labeli bounding box dan pisahkan train/validation/test **berdasarkan lahan/penerbangan**,
   bukan acak foto berurutan yang bertumpang tindih.
3. Latih model deteksi. Simpan bobot terpercaya lokal, misalnya `best.pt`.
4. Di virtualenv backend, jalankan `pip install -r requirements-ai.txt`.
5. Atur environment sebelum menjalankan Uvicorn:

macOS/Linux:
```bash
export WALLACEA_MODEL_PATH="/absolute/path/best.pt"
export WALLACEA_LABEL_MAP_JSON='{"nama_kelas_tanaman_anda":"plant"}'
uvicorn main:app --host 127.0.0.1 --port 8000
```

PowerShell:
```powershell
$env:WALLACEA_MODEL_PATH="C:\models\best.pt"
$env:WALLACEA_LABEL_MAP_JSON='{"nama_kelas_tanaman_anda":"plant"}'
uvicorn main:app --host 127.0.0.1 --port 8000
```

6. Pada frontend lokal: Pengaturan → URL endpoint `http://127.0.0.1:8000/analyze`.
7. Buka foto asli → Jalankan deteksi → tinjau setiap kandidat → Terima & simpan.

Model COCO bawaan tidak otomatis menjadi model sensus tanaman. Tidak ada bobot yang diunduh otomatis.
Nilai confidence adalah keluaran model, bukan akurasi survei atau kepastian diagnosis.
Evaluasi hitungan terhadap hitungan lapangan; ukur galat, missed detections, dan hitungan ganda.
Pelatihan dan validasi model belum dilakukan pada proyek ini.

Backend ini untuk demo lokal. Untuk penggunaan bersama, tambahkan autentikasi, pembatasan
permintaan, storage, database, dan deployment backend sebelum membuka layanan ke internet.
Jangan menjalankan server dengan `--host 0.0.0.0` hanya demi menghubungkan demo.
URL frontend HTTPS perlu backend HTTPS; paling sederhana gunakan keduanya secara lokal dahulu.
Set `WALLACEA_ALLOWED_ORIGINS` ke origin frontend yang benar jika berbeda dari localhost:8080.
Tidak ada file foto yang disimpan server oleh implementasi ini, tetapi foto dikirim ke backend yang dipilih pengguna.

## Format impor AI

```json
{
  "image_width": 1920,
  "image_height": 1080,
  "model": "nama-model",
  "detections": [{"label": "plant", "confidence": 0.86, "bbox": [0.1, 0.2, 0.08, 0.12]}]
}
```

`bbox = [kiri, atas, lebar, tinggi]`, semuanya relatif 0–1. Label: `plant`, `check`, `gap`.
Dimensi harus sesuai foto. Maksimal 3.000 penanda per foto, 5 MB file deteksi.
Semua kandidat harus diterima manual sebelum masuk hitungan tanaman.

## Stack yang direkomendasikan untuk versi tim

Prototipe frontend ini sengaja tidak perlu build. Untuk aplikasi yang dikembangkan bersama tim:

| Bagian | Pilihan | Repo / dokumentasi |
|---|---|---|
| Frontend | React + TypeScript + Vite | https://github.com/vitejs/vite |
| Dashboard | shadcn-admin sebagai referensi struktur/komponen | https://github.com/satnaing/shadcn-admin |
| Anotasi gambar | React Konva | https://github.com/konvajs/react-konva |
| Backend AI | FastAPI | https://github.com/fastapi/fastapi |
| Deteksi | Ultralytics, bobot tanaman milik tim | https://github.com/ultralytics/ultralytics |
| Pelabelan dataset | CVAT | https://github.com/cvat-ai/cvat |
| Peta web (tahap berikut) | Leaflet | https://github.com/Leaflet/Leaflet |
| Fotogrametri (tahap berikut) | ODM atau WebODM, pilih sesuai alur | https://github.com/OpenDroneMap/ODM dan https://github.com/WebODM/WebODM |

Leaflet menampilkan data peta; bukan mesin pembuat orthomosaic. React Konva untuk editor gambar,
bukan pemetaan GPS. Jangan memasukkan koordinat gambar ke peta sebagai koordinat geografis.
Pada saat pengecekan, WebODM sudah memisahkan diri dari OpenDroneMap dan memakai ODX,
bukan ODM. Perlakukan integrasi keduanya secara terpisah.

Lisensi yang perlu diperiksa sebelum produk komersial ditetapkan: Ultralytics memiliki
opsi AGPL dan Enterprise; WebODM/ODM menggunakan AGPL-3.0. File sumber proyek ini tidak
membundel kode atau bobot dari repo tersebut. Evaluasi kewajiban lisensi sesuai distribusi
dan integrasi aktual; menjalankan pustaka tidak otomatis menghapus kewajibannya.

## Pembagian kerja tim

- Firaz: UX, editor anotasi, dashboard, laporan, dan pengujian alur pengguna.
- Anggota AI/ML: dataset, anotasi, pelatihan, evaluasi terpisah berdasarkan lahan/penerbangan.
- Backend: API, penyimpanan survei bersama, autentikasi, kontrak hasil model.
- Operasi lapangan: prosedur pengambilan foto konsisten, hitungan pembanding, izin akses lahan.
- QA/bisnis: wawancara calon pengguna, uji manfaat laporan, dokumentasi dan penetapan layanan.

## Pengujian

`node --check dist/app.js` memeriksa sintaks frontend.
`node tests/frontend-contract.cjs` menguji kontrak impor, hitungan kandidat, escaping, dan ekspor CSV.
`python3 -m py_compile backend/main.py` memeriksa sintaks backend.
Tes inferensi aktual membutuhkan bobot tanaman, dependensi AI, dan foto uji nyata.
Browser QA belum dapat dijalankan pada lingkungan pembuatan ini karena infrastruktur preview menolak mount proc.
