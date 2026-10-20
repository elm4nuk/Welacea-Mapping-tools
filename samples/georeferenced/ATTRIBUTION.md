# Contoh raster bergeoreferensi — `OSBS_029.tif`

Satu-satunya contoh GeoTIFF **nyata** untuk demo impor peta. Ini **bukan** foto K919 MAX, bukan lahan pertanian,
dan bukan orthomosaic yang dibuat WALLACEA.

| | |
|---|---|
| Berkas | `OSBS_029.tif` — 400 × 400 px, 3 band RGB uint8, nodata 255 |
| CRS / resolusi | EPSG:32617 (WGS 84 / UTM 17N), 0,10 m/px (≈ 40 m × 40 m, ±1 600 m²) |
| Lokasi | NEON OSBS — Ordway-Swisher Biological Station, Florida, AS (≈ −81,990°, 29,693°) |
| Jenis citra | Mosaik kamera RGB **pesawat** NEON Airborne Observation Platform (bukan drone) |
| sha256 | `8521dbb5e8063d37d61895867dfcca7476491d1345103dc1b3fd96f71b186353` |
| Asal salinan | Disalin byte-per-byte dari paket `deepforest==2.1.0` (PyPI) `deepforest/data/OSBS_029.tif`, 2026-10-20 |

## Lisensi & atribusi

- **Citra**: National Ecological Observatory Network (NEON), Battelle, disponsori NSF. NEON menyatakan produk data &
  sampelnya berlisensi **CC BY 4.0** ([Data Use and Citation Policy](https://data.neonscience.org/data-api/data-use-policy/)).
  Atribusi wajib:
  > Citra: National Ecological Observatory Network (NEON), Battelle, disponsori NSF. Data NEON berlisensi CC BY 4.0.
- **Distribusi**: repositori/paket DeepForest (weecology), lisensi MIT.
- Anotasi manusia untuk citra yang sama (61 kotak `Tree`, koordinat piksel) ada di
  `../deepforest-neon/OSBS_029.xml` (NeonTreeEvaluation, Weinstein et al.). PNG dengan piksel yang sama:
  `../deepforest-neon/OSBS_029.png`.

## Cara pakai

Web → survei nyata → impor peta udara → pilih `OSBS_029.tif`, atau lewat API:

```powershell
curl.exe -F "file=@samples\georeferenced\OSBS_029.tif" -F "source_description=NEON AOP via DeepForest 2.1.0 (CC BY 4.0)" `
  http://127.0.0.1:8000/api/v1/surveys/<survey_id>/rasters
```

Hasil uji nyata (2026-10-20, DeepForest pretrained CPU, `tile_size` 400, overlap 0): 49 kandidat **tajuk pohon**
pending, identik dengan analisis PNG yang sama lewat alur foto. Terhadap 61 anotasi manusia (IoU ≥ 0,5): TP 38, FP 11,
FN 23 (precision 0,78, recall 0,62). Citra ini tidak independen dari data pengembang model → **bukan** akurasi produk.
