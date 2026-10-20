# Contoh struktur dataset YOLO detection

Folder ini hanya contoh **struktur**. Tidak ada foto di Git; dataset asli disimpan di luar repo
(mis. `D:\dataset-jagung`).

```
D:\dataset-jagung\
  dataset.yaml                 ← salinan ml\dataset.yaml.example yang sudah disesuaikan
  images\
    train\  DJI_0001.JPG  DJI_0002.JPG  ...
    val\    DJI_0101.JPG  ...
    test\   DJI_0201.JPG  ...
  labels\
    train\  DJI_0001.txt  DJI_0002.txt  ...   ← nama sama dengan fotonya, ekstensi .txt
    val\    DJI_0101.txt  ...
    test\   DJI_0201.txt  ...
```

## Isi berkas label (`labels\train\DJI_0001.txt`)

Satu baris per tanaman (bounding box):

```
class_id x_tengah y_tengah lebar tinggi
0 0.512 0.334 0.041 0.038
0 0.770 0.402 0.044 0.040
```

- Semua angka dinormalisasi 0–1 terhadap lebar/tinggi foto, **bukan piksel**.
- `class_id` sesuai urutan `names` di `dataset.yaml` (0 = jagung).
- Foto tanpa tanaman boleh punya berkas `.txt` kosong (contoh latar belakang).
- Label dibuat dengan alat anotasi yang bisa ekspor "YOLO" (mis. CVAT, Label Studio). Periksa bahwa foto yang
  dilabeli sudah diputar sesuai EXIF yang sama dengan yang dilihat alat anotasi.

## Pembagian train / val / test

- Pisahkan **per lahan atau per penerbangan**. Foto bertumpang tindih dari satu penerbangan jangan dibagi ke
  train dan test sekaligus.
- Mulai dari setidaknya puluhan foto berlabel per split. Lebih sedikit dari itu, angka evaluasi tidak bermakna.
- Periksa sebelum training:

```powershell
cd apps\api
.venv\Scripts\python ml\train.py --data "D:\dataset-jagung\dataset.yaml" --check-only
```
