"""WALLACEA ML: dataset, validasi anotasi, split tanpa kebocoran, training & evaluasi detektor tanaman.

Modul:
- datasets:   katalog dataset publik + pengunduh eksplisit (metadata → sampel zip via HTTP Range → unduh penuh).
- coco:       validasi COCO & konversi eksplisit (category_id, piksel → ternormalisasi, class map).
- prepare:    COCO → layout YOLO + manifest, piksel terorientasi EXIF lewat kode API.
- manifest:   skema & validasi manifest dataset (satu tanaman, metadata lahan/penerbangan).
- inspection: statistik gambar/objek, isu label, duplikat, perbandingan domain (publik vs K919).
- split:      split train/val/test BERDASARKAN GRUP (lahan/penerbangan/split resmi) + pemeriksaan kebocoran.
- train:      training Ultralytics + model card; menolak berjalan bila data/split tidak valid.
- predict:    prediksi lewat adapter detektor API (jalur yang sama dengan /analyze).
- evaluate:   precision, recall, AP, galat hitungan per foto/petak; pemilihan threshold di split val.
- backend:    jembatan ke apps/api (orientasi gambar & adapter) — tidak ada logika ganda.
"""

__version__ = "0.2.0"
