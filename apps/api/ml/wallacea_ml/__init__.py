"""Toolkit dataset & evaluasi WALLACEA. Tidak menjalankan pelatihan tanpa dataset nyata.

Modul:
- manifest: skema & validasi manifest dataset (satu tanaman, metadata lahan/penerbangan).
- split:    split train/val/test BERDASARKAN GRUP (lahan atau penerbangan) + pemeriksaan kebocoran.
- evaluate: precision, recall, galat hitungan per foto/petak terhadap ground truth.
- train:    wrapper Ultralytics yang menolak berjalan bila data/split tidak valid.
"""
