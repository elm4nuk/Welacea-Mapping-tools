# ml/artifacts — TIDAK masuk Git (bobot & hasil run)

| Folder | Isi |
|---|---|
| `pretrained/` | Bobot awal yang diunduh EKSPLISIT (mis. `yolo11n.pt`, AGPL-3.0/Enterprise Ultralytics) |
| `runs/<nama>/` | Run Ultralytics lengkap (kurva, `results.csv`, `weights/best.pt`) |
| `models/<nama>/` | `<nama>.pt` + `model_card.json` (dataset, kelas, preprocessing, config, seed, metrik, env API) |
| `eval/<nama>/` | `pred_val.json`, `pred_test.json`, `threshold.json`, `eval_test.json`, evaluasi eksternal |

Simpan `model_card.json` bersama bobot saat dipindahkan. `model_version` di card = `model_version` yang
dicatat API pada setiap AnalysisRun (sha256 16 hex pertama bobot).
