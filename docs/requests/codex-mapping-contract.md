# CR-FE-005 — kontrak workspace pemetaan lahan

- Diajukan: Codex, 2026-10-20, branch `agent/codex-mapping`
- Sumber yang diperiksa: `agent/claude-backend` @ `f2e770f`, OpenAPI revision 5
- Status: **dipenuhi** oleh backend `40ba487`, kontrak `f2e770f`, dan dokumentasi
  `1d1d36c`; frontend mengonsumsi snapshot committed tersebut.

## Tujuan

Frontend memerlukan data geografis tersimpan untuk batas lahan, raster GeoTIFF, dan
kandidat AI tergeoreferensi. Koordinat harus GeoJSON `[longitude, latitude]`. Anotasi
foto normalized existing tetap terpisah dan tidak boleh diproyeksikan tanpa transformasi
backend yang sah.

## Kebutuhan minimum

### Batas lahan

- List/get/create/update/delete batas per survei.
- Geometry GeoJSON `Polygon | MultiPolygon` dalam WGS84/EPSG:4326.
- Metadata: `id`, `survey_id`, `name`, `source` (`drawn | geojson_import`),
  `geometry`, `area_m2`, `perimeter_m`, `revision`, `created_at`, `updated_at`.
- Nilai `area_m2` dan `perimeter_m` dihitung backend dan menjadi nilai authoritative.
- Update/delete memakai `If-Match`; 409 mengikuti envelope `REVISION_CONFLICT` existing.
- Validasi topology/range/ukuran dan error code stabil untuk GeoJSON invalid.
- Endpoint ekspor GeoJSON atau jaminan bahwa representasi GET boleh diekspor apa adanya.

### Raster GeoTIFF

- Upload multipart khusus per survei, terpisah dari upload JPG/PNG existing.
- Batas ukuran, media type, status pemrosesan, dan error terstruktur pada health/response.
- Record raster minimal: `id`, `filename`, `status`, `bounds`, `footprint`, `source_crs`,
  `display_crs`, resolusi/GSD bila benar-benar diketahui, `tile_url` atau TileJSON,
  `revision`, dan pesan kegagalan.
- Tile/preview dibuat backend; frontend tidak mengambil GeoTIFF penuh sebagai satu gambar.
- Delete memakai revisi. URL tile harus aman dipakai MapLibre dan menjelaskan cache/CORS.

### Kandidat geografis

- List kandidat per survei/raster dengan geometry WGS84, bukan koordinat piksel.
- Metadata: `id`, `raster_id`, `analysis_run_id`, `geometry`, `review_status`,
  `confidence`, `model_id/version/label`, `source`, `revision`.
- PATCH review/koreksi dan konflik memakai pola `If-Match` existing.
- Ringkasan accepted-only serta disclaimer bahwa observasi lintas penerbangan bukan
  tanaman unik kecuali backend menyediakan deduplikasi yang tervalidasi.
- Tautan stabil dari kandidat ke raster/run sumber.

### Capability discovery

- Health membedakan capability boundary CRUD, raster ingest/tiles, dan geographic
  findings. Boolean `georeferencing` tunggal tidak cukup untuk partial deployment.
- Sediakan batas upload raster dan format yang didukung pada `health.limits`.

## Acceptance kontrak

- OpenAPI, fixture sukses/error/conflict, CHANGELOG, dan handoff committed.
- Fixture memuat polygon/raster/kandidat berlabel QA sintetis, bukan data lapangan nyata.
- Backend menghitung metrik geometry dan membuktikan tile bounds pada tes integrasi.

## Penyelesaian revision 5

Kontrak final menggunakan boundary global di `/fields` lalu menautkannya melalui
`Survey.field_id`, bukan endpoint boundary yang bersarang langsung di bawah survei.
Ini memenuhi kebutuhan ownership tanpa frontend menebak endpoint. Impor mengembalikan
`FieldImportResult`; update/delete batas dan review kandidat memakai `If-Match`.

Raster tersedia melalui `/surveys/{survey_id}/rasters` dan `/rasters/{raster_id}`,
dengan TileJSON, bounds WGS84, CRS sumber, footprint, run analisis, dan kandidat peta.
Health menyediakan capability granular dan limit raster/batas. Laporan memuat ringkasan
batas serta per-raster dengan hitungan accepted-only. Kontrak juga menegaskan bahwa:

- impor GeoTIFF bukan pembuatan atau verifikasi orthomosaic;
- foto biasa tidak dianggap tergeoreferensi;
- kandidat simulasi bukan keluaran AI;
- hitungan antar-raster tidak membuktikan tanaman unik.

Tidak ada request kontrak lanjutan yang diperlukan untuk delivery frontend ini.
