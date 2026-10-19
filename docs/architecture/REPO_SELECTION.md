# Pemilihan repo & lisensi (backend / AI / GIS)

Dicek 2026-10-18 dari GitHub API (`license.spdx_id`, rilis terbaru) dan berkas LICENSE/README resmi.
Bukan nasihat hukum. Lisensi **model, bobot, dan dataset** terpisah dari lisensi kode dan harus dicek sendiri.
Frontend memilih repo-nya sendiri (lihat handoff Codex).

## Dipakai sekarang (dependency, tidak ada kode yang disalin)

| Repo | Peran | Lisensi | Versi dipakai / rilis terbaru |
|---|---|---|---|
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | HTTP API, OpenAPI | MIT | 0.143.5 / 0.143.5 |
| [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) | ORM | MIT | 2.0.55 / 2.1.5 — 2.1 belum diuji, sengaja `<2.1` |
| [sqlalchemy/alembic](https://github.com/sqlalchemy/alembic) | Migrasi | MIT | 1.20.0 / 1.20.0 |
| [python-pillow/Pillow](https://github.com/python-pillow/Pillow) | Validasi/dekode gambar, EXIF, thumbnail | MIT-CMU (HPND) | 13.0.0 / 13.0.0 |
| [Kludex/uvicorn](https://github.com/Kludex/uvicorn) (dulu encode/uvicorn) | Server ASGI | BSD-3-Clause | 0.54.0 |
| [Kludex/python-multipart](https://github.com/Kludex/python-multipart) | Parsing multipart | Apache-2.0 | 0.0.32 / 0.0.32 |
| pytest, httpx, PyYAML | Tes & export kontrak | MIT | lihat `requirements.lock.txt` |

## Opsional (detector model; dipasang terpisah)

| Repo | Peran | Lisensi | Catatan |
|---|---|---|---|
| [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) | Training/inferensi detektor (adapter `app/inference/ultralytics_adapter.py`) | **AGPL-3.0** atau Enterprise | Rilis v8.4.182. Adapter hanya `import` saat analisis; tidak dibundel. Menjalankan layanan jaringan dengan AGPL dapat memicu kewajiban membuka sumber — **putuskan lisensi sebelum produk komersial**. Bobot pretrained Ultralytics juga berlisensi AGPL/Enterprise. |
| [weecology/DeepForest](https://github.com/weecology/DeepForest) | Detector **kandidat tajuk pohon** pretrained (`app/inference/deepforest_adapter.py`) | MIT (kode); bobot `weecology/deepforest-tree` MIT (model card HF) | v2.1.0 (2026-02-26), diuji CPU. Opsional (`requirements-deepforest.txt`). Bukan model tanaman pertanian. Backbone torchvision `resnet50-0676ba61.pth` ikut diunduh skrip (BSD-3 kode torchvision; bobot ImageNet). |

## Kandidat setelah baseline diuji (belum dipasang)

| Repo | Peran | Lisensi | Kapan |
|---|---|---|---|
| [obss/sahi](https://github.com/obss/sahi) | Inferensi bertile untuk objek kecil | MIT | Hanya bila evaluasi baseline menunjukkan recall rendah karena objek kecil. Dedup antar tile ≠ dedup tanaman antar foto. |
| [opencv/opencv](https://github.com/opencv/opencv) | Pemrosesan citra (mis. ketajaman relatif) | Apache-2.0 | Bila ada kebutuhan konkret; Pillow cukup untuk MVP. |
| [cvat-ai/cvat](https://github.com/cvat-ai/cvat) | **Dipilih** untuk labeling dataset | MIT | Ekspor YOLO/COCO; lihat `ml/README.md`. |
| [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio) | Alternatif labeling | Apache-2.0 | Tidak dipasang (pilih satu: CVAT). |

## GIS — tahap berikut saja

| Repo | Peran | Lisensi | Catatan |
|---|---|---|---|
| [OpenDroneMap/ODM](https://github.com/OpenDroneMap/ODM) | Fotogrametri (orthomosaic, DEM) | AGPL-3.0 | v3.6.2. Butuh uji overlap & ketajaman foto K919 dahulu. |
| [OpenDroneMap/NodeODM](https://github.com/OpenDroneMap/NodeODM) | REST API untuk ODM | AGPL-3.0 | v3.6.2 |
| [WebODM/WebODM](https://github.com/WebODM/WebODM) | Aplikasi pemrosesan foto udara | AGPL-3.0 | v3.3.0. README (dicek): **sudah terpisah dari OpenDroneMap**, memproses dengan **ODX** (juga MicMac, LGT), bukan ODM. Jangan diasumsikan satu API dengan ODM/NodeODM. |
| [rasterio/rasterio](https://github.com/rasterio/rasterio) | Baca/tulis GeoTIFF | BSD-3-Clause | 1.5.2. Hanya setelah ada raster tergeoreferensi yang valid. |

## Provenance

Tidak ada kode dari repo di atas yang disalin ke repo ini. Pola yang diadaptasi dari starter v0.1
(`legacy/starter-v01/backend/main.py`, milik proyek ini): pemetaan label via `WALLACEA_LABEL_MAP_JSON`,
normalisasi kotak `xyxy` → `[left, top, width, height]`, dan penolakan 503 tanpa bobot.

## Dataset publik & bobot (ML)

Detail lengkap dan terverifikasi: `ml/configs/datasets.yaml` (dicek 2026-10-18 ke Zenodo/Mendeley/GitHub API
dan isi arsip via HTTP Range). Lisensi kode, dataset, dan bobot dibedakan:

| Dataset | Dataset | Kode | Bobot | Peran di WALLACEA |
|---|---|---|---|---|
| UAVmulticrop (Zenodo 4890370 v1) | CC-BY-4.0 | — | — | **Baseline jagung** (9 situs → split per situs) |
| MatchPlant (Zenodo 14856123) | CC-BY-4.0 | MIT ([repo](https://github.com/JacobWashburn-USDA/MatchPlant)) | Faster R-CNN `.pt`, CC-BY-4.0 — **bukan** checkpoint Ultralytics | Uji eksternal jagung |
| Sawit Ganoderma v2 (Mendeley s23jvbpnr3.2) | CC-BY-4.0 | — | — | Hanya bila tanaman = sawit; split geografis resmi |
| NeonTreeEvaluation (Zenodo 5914554 v0.2.2) | CC-BY-4.0 | CC0-1.0 | — | Opsional, pembanding tajuk pohon |
| Bobot awal `yolo11n.pt` (ultralytics/assets v8.3.0) | — | — | AGPL-3.0/Enterprise | Titik awal fine-tune baseline |

Bobot hasil fine-tune dari `yolo11n.pt` mewarisi pertimbangan lisensi Ultralytics (AGPL-3.0/Enterprise);
dataset CC-BY-4.0 mewajibkan atribusi. Putuskan lisensi sebelum produk komersial.
