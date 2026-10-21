# Foto contoh udara (DeepForest / NEON) — untuk demo unggah & inferensi

Berkas di folder ini **disalin apa adanya** dari paket resmi DeepForest 2.1.0 (`src/deepforest/data/`,
tag [`v2.1.0`](https://github.com/weecology/DeepForest/tree/v2.1.0/src/deepforest/data)). sha256 tiap berkas
dicocokkan dengan berkas di tag GitHub tersebut pada 2026-10-19 (identik).

| Berkas | Ukuran | Situs NEON | Anotasi manusia (VOC XML) |
|---|---|---|---|
| `OSBS_029.png` | 400×400 px | OSBS — Ordway-Swisher Biological Station, Florida | `OSBS_029.xml` (61 kotak `Tree`) |
| `SOAP_061.png` | 400×400 px | SOAP — Soaproot Saddle, California | `SOAP_061.xml` (37 kotak: 9 `Alive`, 28 `Dead`) |
| `2019_YELL_2_541000_4977000_image_crop.png` | 1249×1035 px | YELL — Yellowstone, Wyoming | `…_image_crop.xml` (279 kotak) |

## Asal & lisensi

- **Citra**: NEON Airborne Observation Platform, mosaik kamera RGB ±10 cm/px (citra **pesawat**, bukan drone).
  NEON menyatakan produk data & sampel datanya berlisensi **CC BY 4.0**
  ([Data Use and Citation Policy](https://data.neonscience.org/data-api/data-use-policy/); sebelum 2026
  dirilis sebagai CC0). Diperlakukan sebagai CC BY 4.0 → atribusi wajib:
  > Citra: National Ecological Observatory Network (NEON), Battelle, disponsori NSF. Data NEON berlisensi CC BY 4.0.
- **Anotasi & distribusi**: repositori DeepForest (weecology), lisensi MIT; anotasi berasal dari
  NeonTreeEvaluation (Weinstein et al.).
- Sitasi model: Weinstein, B.G. et al. (2019) *Individual Tree-Crown Detection in RGB Imagery Using
  Semi-Supervised Deep Learning Neural Networks*. Remote Sensing 11(11):1309; Weinstein et al. (2020)
  *DeepForest*, Methods in Ecology and Evolution.

## Cara pakai

Unggah PNG lewat alur normal (web → survei baru → unggah foto), lalu tekan analisis. API harus berjalan dengan
`WALLACEA_DETECTOR=deepforest` (lihat `apps/api/README.md`). Hasil = **kandidat tajuk pohon, status pending**.
Berkas XML = anotasi manusia untuk perbandingan di notebook `ml/notebooks/05_deepforest_pretrained.ipynb`;
**tidak** diimpor sebagai hasil inferensi.

Ini hutan AS, bukan lahan pertanian dan bukan foto K919 MAX. Kinerja pada foto K919 belum diuji.
