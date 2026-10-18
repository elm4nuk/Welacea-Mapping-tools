"""Snapshot kontrak harus sama dengan skema yang di-generate, dan fixtures valid terhadap skema."""
import json
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import TypeAdapter

from app import CONTRACT_REVISION
from app import schemas

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))
import export_contract  # noqa: E402

CONTRACTS = API_ROOT.parents[1] / "packages" / "contracts"
INDEX = json.loads((CONTRACTS / "fixtures" / "index.json").read_text(encoding="utf-8"))


def test_openapi_snapshot_matches_code():
    snapshot = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
    assert snapshot == export_contract.openapi_dict(), \
        "Kontrak berubah: jalankan scripts/export_contract.py, naikkan CONTRACT_REVISION, catat CHANGELOG."
    assert snapshot["info"]["version"] == f"1.{CONTRACT_REVISION}.0"


def test_changelog_mentions_current_revision():
    text = (CONTRACTS / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"Revisi {CONTRACT_REVISION}" in text


@pytest.mark.parametrize("name,schema", sorted(INDEX.items()))
def test_fixture_matches_schema(name, schema):
    path = CONTRACTS / "fixtures" / name
    assert path.is_file()
    if schema == "raw":
        return
    body = json.loads(path.read_text(encoding="utf-8"))
    TypeAdapter(getattr(schemas, schema)).validate_python(body)


def test_required_endpoints_present():
    paths = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))["paths"]
    required = {
        ("/api/v1/health", "get"), ("/api/v1/surveys", "get"), ("/api/v1/surveys", "post"),
        ("/api/v1/surveys/{survey_id}", "get"), ("/api/v1/surveys/{survey_id}", "patch"),
        ("/api/v1/surveys/{survey_id}", "delete"), ("/api/v1/surveys/{survey_id}/photos", "post"),
        ("/api/v1/surveys/{survey_id}/photos", "get"), ("/api/v1/photos/{photo_id}", "get"),
        ("/api/v1/photos/{photo_id}/content", "get"), ("/api/v1/photos/{photo_id}/annotations", "get"),
        ("/api/v1/photos/{photo_id}/annotations", "post"), ("/api/v1/annotations/{annotation_id}", "patch"),
        ("/api/v1/annotations/{annotation_id}", "delete"), ("/api/v1/photos/{photo_id}/analyze", "post"),
        ("/api/v1/photos/{photo_id}/detections/import", "post"), ("/api/v1/surveys/{survey_id}/report", "get"),
        ("/api/v1/surveys/{survey_id}/export.csv", "get"),
    }
    present = {(p, m) for p, ops in paths.items() for m in ops}
    assert required <= present, required - present
