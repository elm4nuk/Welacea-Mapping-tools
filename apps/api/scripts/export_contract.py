"""Generate packages/contracts/openapi.yaml + fixtures dari aplikasi SUNGGUHAN.

    python scripts/export_contract.py          # tulis ulang snapshot & fixtures
    python scripts/export_contract.py --check  # gagal (exit 1) bila snapshot berbeda dari kode

Fixtures adalah respons nyata API (TestClient, data_dir sementara). Fixture analyze/import memakai
detector TEST DOUBLE berlabel "contract-test-double" — bukan model tanaman, bukan hasil akurasi.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import tempfile
from pathlib import Path

import yaml

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.inference import DetectionOutput, Detector, DetectorInfo, RawDetection  # noqa: E402
from app.inference.deepforest_adapter import DeepForestDetector  # noqa: E402
from app.inference.ultralytics_adapter import UltralyticsDetector  # noqa: E402
from app.main import create_app  # noqa: E402

CONTRACTS = API_ROOT.parents[1] / "packages" / "contracts"
FIXTURES = CONTRACTS / "fixtures"
V1 = "/api/v1"


class ContractTestDouble(Detector):
    def info(self):
        return DetectorInfo(state="loaded", message="TEST DOUBLE untuk fixture kontrak — bukan model tanaman.",
                            model_id="contract-test-double", model_version="sha256:0000000000000000")

    def detect(self, image):
        return DetectionOutput("contract-test-double", "sha256:0000000000000000", [
            RawDetection("plant", [0.10, 0.10, 0.20, 0.25], 0.91, "tanaman"),
            RawDetection("gap", [0.60, 0.50, 0.15, 0.15], 0.42, "titik_kosong"),
        ], {"adapter": "test-double"})


def openapi_dict() -> dict:
    with tempfile.TemporaryDirectory() as d:
        app = create_app(load_settings(data_dir=Path(d), auto_migrate=False))
        spec = app.openapi()
        app.state.engine.dispose()
        return json.loads(json.dumps(spec))


def openapi_yaml(spec: dict) -> str:
    header = ("# GENERATED — jangan edit manual. Sumber: apps/api/app (FastAPI/Pydantic).\n"
              "# Regenerasi: cd apps/api && .venv/Scripts/python scripts/export_contract.py\n")
    return header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120)


def jpeg_oriented() -> bytes:
    img = Image.new("RGB", (160, 90), (90, 140, 70))
    exif = Image.Exif()
    exif[0x0112] = 6
    exif.get_ifd(0x8769)[0x9003] = "2026:10:18 07:45:10"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def build_fixtures() -> dict[str, tuple[str, object]]:
    """Return {nama_berkas: (nama_skema | 'raw', isi)}."""
    out: dict[str, tuple[str, object]] = {}
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        def put(name, schema, resp_or_obj):
            body = resp_or_obj.json() if hasattr(resp_or_obj, "json") else resp_or_obj
            out[name] = (schema, body)
            return body

        with TestClient(create_app(load_settings(data_dir=base / "a"))) as c:
            put("health.not-configured.json", "Health", c.get(f"{V1}/health"))
            put("sample-page.json", "SamplePage", c.get(f"{V1}/samples"))   # katalog nyata <repo>/samples
            survey_req = {"name": "Kebun Jagung Blok A", "crop_type": "Jagung", "location_label": "Desa Contoh, petak 2",
                          "survey_date": "2026-10-18", "notes": "Penerbangan pagi, langit cerah."}
            put("survey-create.request.json", "SurveyCreate", survey_req)
            survey = put("survey.json", "Survey", c.post(f"{V1}/surveys", json=survey_req))
            put("survey-update.request.json", "SurveyUpdate", {"notes": "Tambahan: sisi timur tergenang."})
            put("survey-page.json", "SurveyPage", c.get(f"{V1}/surveys"))
            data = jpeg_oriented()
            up = put("photo-upload.response.json", "PhotoUploadResult",
                     c.post(f"{V1}/surveys/{survey['id']}/photos", files={"file": ("DJI_0001.JPG", data, "image/jpeg")}))
            photo = up["photo"]
            put("photo-upload.duplicate.response.json", "PhotoUploadResult",
                c.post(f"{V1}/surveys/{survey['id']}/photos", files={"file": ("DJI_0001 (1).JPG", data, "image/jpeg")}))
            point = {"kind": "plant", "geometry_type": "point", "x": 0.42, "y": 0.31, "note": ""}
            bbox = {"kind": "check", "geometry_type": "bbox", "bbox": [0.55, 0.6, 0.2, 0.15],
                    "note": "Daun menguning? Periksa di lapangan.", "review_status": "accepted"}
            put("annotation-create-point.request.json", "AnnotationCreate", point)
            put("annotation-create-bbox.request.json", "AnnotationCreate", bbox)
            ann = put("annotation.json", "Annotation", c.post(f"{V1}/photos/{photo['id']}/annotations", json=point))
            c.post(f"{V1}/photos/{photo['id']}/annotations", json=bbox)
            upd = {"kind": "gap", "note": "Ternyata titik kosong."}
            put("annotation-update.request.json", "AnnotationUpdate", upd)
            put("annotation-updated.json", "Annotation",
                c.patch(f"{V1}/annotations/{ann['id']}", json=upd, headers={"If-Match": '"1"'}))
            put("error.revision-conflict.json", "ErrorEnvelope",
                c.patch(f"{V1}/annotations/{ann['id']}", json={"note": "x"}, headers={"If-Match": '"1"'}))
            put("error.precondition-required.json", "ErrorEnvelope",
                c.patch(f"{V1}/annotations/{ann['id']}", json={"note": "x"}))
            put("error.validation.json", "ErrorEnvelope",
                c.post(f"{V1}/photos/{photo['id']}/annotations", json={"kind": "plant", "x": 1.4, "y": 0.2}))
            put("error.not-found.json", "ErrorEnvelope", c.get(f"{V1}/photos/00000000000000000000000000000000"))
            put("error.invalid-image.json", "ErrorEnvelope",
                c.post(f"{V1}/surveys/{survey['id']}/photos", files={"file": ("x.jpg", b"bukan gambar", "image/jpeg")}))
            put("error.model-not-configured.json", "ErrorEnvelope", c.post(f"{V1}/photos/{photo['id']}/analyze"))
            imp = {"image_width": photo["width"], "image_height": photo["height"], "model": "tim-ml-jagung-v0",
                   "model_version": "2026-10-01", "image_sha256": photo["sha256"], "on_existing": "reject",
                   "detections": [{"label": "plant", "confidence": 0.83, "bbox": [0.2, 0.1, 0.15, 0.12]},
                                  {"label": "plant", "confidence": 0.47, "bbox": [0.5, 0.4, 0.14, 0.1]}]}
            put("detections-import.request.json", "DetectionImportRequest", imp)
            put("detections-import.response.json", "AnalysisResult",
                c.post(f"{V1}/photos/{photo['id']}/detections/import", json=imp))
            put("error.analysis-exists.json", "ErrorEnvelope",
                c.post(f"{V1}/photos/{photo['id']}/detections/import", json=imp))
            put("error.detection-mismatch.json", "ErrorEnvelope",
                c.post(f"{V1}/photos/{photo['id']}/detections/import",
                       json={**imp, "image_width": photo["height"], "image_height": photo["width"], "on_existing": "append"}))
            put("photo.json", "Photo", c.get(f"{V1}/photos/{photo['id']}"))
            put("photo-page.json", "PhotoPage", c.get(f"{V1}/surveys/{survey['id']}/photos"))
            put("annotation-page.json", "AnnotationPage", c.get(f"{V1}/photos/{photo['id']}/annotations"))
            put("analysis-run-page.json", "AnalysisRunPage", c.get(f"{V1}/photos/{photo['id']}/analysis-runs"))
            put("report.json", "SurveyReport", c.get(f"{V1}/surveys/{survey['id']}/report"))
            out["export.csv"] = ("raw", c.get(f"{V1}/surveys/{survey['id']}/export.csv").content.decode("utf-8"))
            demo = put("demo-survey.json", "Survey", c.post(f"{V1}/demo/surveys"))
            demo_photo = c.get(f"{V1}/surveys/{demo['id']}/photos").json()["items"][0]
            put("error.demo-survey-readonly.json", "ErrorEnvelope",
                c.post(f"{V1}/surveys/{demo['id']}/photos", files={"file": ("a.jpg", data, "image/jpeg")}))
            assert demo_photo["counts"]["plant_accepted"] > 0

            small = io.BytesIO()
            Image.new("RGB", (40, 30), (60, 130, 60)).save(small, format="PNG")
            backup = {"schemaVersion": 1, "exportedAt": "2026-10-18T04:00:00.000Z", "surveys": [{
                "id": "lama-1", "name": "Kebun Sawit Muda", "crop": "Kelapa sawit", "location": "Blok 3",
                "date": "2026-10-17", "notes": "Catatan dari starter v0.1", "isDemo": False,
                "createdAt": "2026-10-17T04:00:00.000Z",
                "photos": [{"id": "f1", "name": "IMG_0001.png", "width": 40, "height": 30,
                            "dataUrl": "data:image/png;base64," + base64.b64encode(small.getvalue()).decode(),
                            "createdAt": "2026-10-17T04:00:00.000Z",
                            "annotations": [
                                {"id": "m1", "x": 0.5, "y": 0.5, "kind": "plant", "note": "", "source": "manual",
                                 "status": "confirmed"},
                                {"id": "m2", "x": 0.25, "y": 0.4, "kind": "plant", "note": "Model: tim-v0",
                                 "source": "ai", "status": "pending", "confidence": 0.7, "box": [0.1, 0.2, 0.3, 0.4]}]}]}]}
            out["starter-backup-v1.sample.json"] = ("raw", backup)
            put("starter-backup-import.response.json", "StarterBackupImportResult",
                c.post(f"{V1}/imports/starter-backup",
                       files={"file": ("wallacea-backup.json", json.dumps(backup).encode(), "application/json")}))

        # Adapter DeepForest ASLI dengan folder bobot yang belum diunduh: status jujur (error + metadata target).
        missing = DeepForestDetector(base / "c" / "models" / "deepforest-tree")
        with TestClient(create_app(load_settings(data_dir=base / "c"), detector=missing)) as c:
            put("health.deepforest-weights-missing.json", "Health", c.get(f"{V1}/health"))

        # Revisi 4. Adapter Ultralytics ASLI, berkas bobot tidak ada → state=error, diagnostic_code=MODEL_FILE_NOT_FOUND.
        absent = UltralyticsDetector(Path("C:/Model Tanaman/best.pt"), {"jagung": "plant"})
        with TestClient(create_app(load_settings(data_dir=base / "d"), detector=absent)) as c:
            put("health.model-file-not-found.json", "Health", c.get(f"{V1}/health"))
            s = c.post(f"{V1}/surveys", json=survey_req).json()
            p = c.post(f"{V1}/surveys/{s['id']}/photos",
                       files={"file": ("DJI_0003.JPG", jpeg_oriented(), "image/jpeg")}).json()["photo"]
            put("error.model-unavailable.json", "ErrorEnvelope", c.post(f"{V1}/photos/{p['id']}/analyze"))

        # Revisi 4. Detector SIMULASI development (WALLACEA_DETECTOR=simulation) — SIMULASI, BUKAN AI.
        with TestClient(create_app(load_settings(data_dir=base / "e", detector="simulation"))) as c:
            put("health.simulation.json", "Health", c.get(f"{V1}/health"))
            s = c.post(f"{V1}/surveys", json=survey_req).json()
            p = c.post(f"{V1}/surveys/{s['id']}/photos",
                       files={"file": ("DJI_0004.JPG", jpeg_oriented(), "image/jpeg")}).json()["photo"]
            put("analyze.simulation.response.json", "AnalysisResult", c.post(f"{V1}/photos/{p['id']}/analyze"))

        with TestClient(create_app(load_settings(data_dir=base / "b"), detector=ContractTestDouble())) as c:
            put("health.test-double-loaded.json", "Health", c.get(f"{V1}/health"))
            s = c.post(f"{V1}/surveys", json=survey_req).json()
            p = c.post(f"{V1}/surveys/{s['id']}/photos",
                       files={"file": ("DJI_0002.JPG", jpeg_oriented(), "image/jpeg")}).json()["photo"]
            put("analyze.request.json", "AnalyzeRequest", {"on_existing": "reject"})
            res = put("analyze.response.json", "AnalysisResult",
                      c.post(f"{V1}/photos/{p['id']}/analyze", json={"on_existing": "reject"}))
            acc = res["candidates"][0]
            put("annotation-accept.request.json", "AnnotationUpdate", {"review_status": "accepted"})
            put("annotation-accepted-candidate.json", "Annotation",
                c.patch(f"{V1}/annotations/{acc['id']}", json={"review_status": "accepted"}, headers={"If-Match": '"1"'}))

        build_mapping_fixtures(base / "f", put)
    return out


def build_mapping_fixtures(data_dir: Path, put) -> None:
    """Revisi 5. Raster = GeoTIFF NEON ASLI (samples/georeferenced/OSBS_029.tif, CC BY 4.0; bukan K919). Deteksi peta
    memakai detector TEST DOUBLE `contract-test-double` (kotak tetap per jendela) — bukan hasil model."""
    sample = API_ROOT.parents[1] / "samples" / "georeferenced" / "OSBS_029.tif"
    with TestClient(create_app(load_settings(data_dir=data_dir), detector=ContractTestDouble())) as c:
        ring = [[-81.99006, 29.69236], [-81.98972, 29.69236], [-81.98972, 29.69264], [-81.99006, 29.69264],
                [-81.99006, 29.69236]]
        field_req = {"name": "Petak contoh OSBS", "boundary_source": "digitized_from_raster",
                     "source_note": "Digambar di atas raster NEON OSBS_029 (contoh, bukan lahan WALLACEA)",
                     "notes": "", "geometry": {"type": "Polygon", "coordinates": [ring]}}
        put("field-create.request.json", "FieldCreate", field_req)
        field = put("field.json", "FarmField", c.post(f"{V1}/fields", json=field_req))
        put("field-page.json", "FieldPage", c.get(f"{V1}/fields"))
        put("field.geojson", "raw", c.get(f"{V1}/fields/{field['id']}/geojson"))
        bow = {"type": "Polygon", "coordinates": [[[106.8, -6.6], [106.81, -6.59], [106.81, -6.6], [106.8, -6.59],
                                                    [106.8, -6.6]]]}
        put("error.invalid-geometry.json", "ErrorEnvelope", c.post(f"{V1}/fields", json={**field_req, "geometry": bow}))
        survey = c.post(f"{V1}/surveys", json={"name": "Survei peta contoh", "crop_type": "Pohon (contoh NEON)",
                                               "survey_date": "2026-10-20", "field_id": field["id"]}).json()
        put("survey-with-field.json", "Survey", c.get(f"{V1}/surveys/{survey['id']}"))
        with open(sample, "rb") as fh:
            up = put("raster-upload.response.json", "RasterUploadResult",
                     c.post(f"{V1}/surveys/{survey['id']}/rasters",
                            files={"file": ("OSBS_029.tif", fh, "image/tiff")},
                            data={"source_description": "NEON AOP RGB mosaic via DeepForest 2.1.0 sample (CC BY 4.0)"}))
        raster = up["raster"]
        put("raster-page.json", "RasterPage", c.get(f"{V1}/surveys/{survey['id']}/rasters"))
        put("raster-tilejson.json", "TileJson", c.get(raster["tilejson_url"]))
        put("raster-analyze.request.json", "RasterAnalyzeRequest", {"tile_size": 1024, "overlap_px": 128})
        put("raster-analyze.response.json", "RasterAnalysisResult",
            c.post(f"{V1}/rasters/{raster['id']}/analyze", json={"tile_size": 1024, "overlap_px": 128}))
        page = put("map-detection-page.json", "MapDetectionPage", c.get(f"{V1}/rasters/{raster['id']}/detections"))
        put("map-detection-update.request.json", "MapDetectionUpdate", {"review_status": "accepted"})
        put("map-detection-accepted.json", "MapDetection",
            c.patch(f"{V1}/map-detections/{page['items'][0]['id']}", json={"review_status": "accepted"},
                    headers={"If-Match": '"1"'}))
        put("map-detections.geojson", "raw", c.get(f"{V1}/rasters/{raster['id']}/detections.geojson"))
        put("report-with-mapping.json", "SurveyReport", c.get(f"{V1}/surveys/{survey['id']}/report"))
        img = io.BytesIO()
        Image.new("RGB", (32, 32), (90, 140, 70)).save(img, format="TIFF")     # TIFF tanpa georeferensi
        put("error.raster-not-georeferenced.json", "ErrorEnvelope",
            c.post(f"{V1}/surveys/{survey['id']}/rasters", files={"file": ("tanpa-crs.tif", img.getvalue(), "image/tiff")}))
        put("health.mapping.json", "Health", c.get(f"{V1}/health"))


def write_all() -> None:
    CONTRACTS.mkdir(parents=True, exist_ok=True)
    (CONTRACTS / "openapi.yaml").write_text(openapi_yaml(openapi_dict()), encoding="utf-8", newline="\n")
    FIXTURES.mkdir(exist_ok=True)
    for old in FIXTURES.glob("*"):
        if old.is_file():
            old.unlink()
    fixtures = build_fixtures()
    index = {}
    for name, (schema, body) in sorted(fixtures.items()):
        path = FIXTURES / name
        if isinstance(body, str):
            path.write_text(body, encoding="utf-8", newline="")
        else:
            path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        index[name] = schema
    (FIXTURES / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"openapi.yaml + {len(fixtures)} fixtures ditulis ke {CONTRACTS}")


def check() -> int:
    snapshot = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
    if snapshot != openapi_dict():
        print("DRIFT: packages/contracts/openapi.yaml berbeda dari skema API. Jalankan export_contract.py "
              "dan catat perubahan di packages/contracts/CHANGELOG.md.")
        return 1
    print("openapi.yaml cocok dengan skema API.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    sys.exit(check() if ap.parse_args().check else write_all())
