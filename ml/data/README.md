# ml/data — TIDAK masuk Git

| Folder | Isi | Dibuat oleh |
|---|---|---|
| `raw/<dataset>/` | Unduhan/sampel dari sumber asli | `python -m wallacea_ml datasets sample|download …` |
| `prepared/<nama>/` | `images/`, `labels/` (YOLO), `manifest.json`, `prepare_report.json` | `prepare <config>` |
| `splits/<nama>/` | `splits/*.txt`, `yolo/*.txt`, `dataset.yaml`, `split_report.json` | `split …` |
| `k919/raw/` | Foto ASLI K919 MAX dari kartu/aplikasi drone | tim (salin manual) |

Lisensi dataset publik ada di `configs/datasets.yaml` (CC-BY-4.0 → wajib atribusi bila dipublikasikan).
