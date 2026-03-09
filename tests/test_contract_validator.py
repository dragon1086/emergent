"""Tests for rolemesh/contract_validator.py [RB106]"""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rolemesh.contract_validator import validate_manifest, validate_manifest_file, ManifestError


# --- Valid manifests ---

def _valid_manifest():
    return {
        "id": "525ff9fd-622a-4974-8749-0036dc35b6de",
        "title": "Test Contract",
        "version": "1.0.0",
        "created_at": "2026-03-07T12:00:00",
        "assignee": "cokac",
        "status": "active",
        "features": [
            {
                "name": "Feature A",
                "description": "Does something",
                "acceptance_criteria": ["It works"],
                "deliverables": ["output.py"],
            }
        ],
    }


def test_valid_manifest():
    result = validate_manifest(_valid_manifest(), "test-001")
    assert result.valid, f"Expected valid, got errors: {result}"
    assert len(result.errors) == 0


def test_valid_with_constraints():
    m = _valid_manifest()
    m["constraints"] = {"timeout_seconds": 300, "max_retries": 2}
    result = validate_manifest(m, "test-002")
    assert result.valid


# --- Missing required fields ---

def test_missing_id():
    m = _valid_manifest()
    del m["id"]
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("missing required field 'id'" in e.message for e in result.errors)


def test_missing_title():
    m = _valid_manifest()
    del m["title"]
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("'title'" in e.message for e in result.errors)


def test_missing_features():
    m = _valid_manifest()
    del m["features"]
    result = validate_manifest(m, "test")
    assert not result.valid


def test_empty_features():
    m = _valid_manifest()
    m["features"] = []
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("empty" in e.message for e in result.errors)


# --- Invalid field values ---

def test_invalid_uuid():
    m = _valid_manifest()
    m["id"] = "not-a-uuid"
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("UUID" in e.message for e in result.errors)


def test_invalid_semver():
    m = _valid_manifest()
    m["version"] = "v1"
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("semver" in e.message for e in result.errors)


def test_invalid_status():
    m = _valid_manifest()
    m["status"] = "unknown_status"
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("unknown status" in e.message for e in result.errors)


def test_invalid_created_at():
    m = _valid_manifest()
    m["created_at"] = "not-a-date"
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("ISO 8601" in e.message for e in result.errors)


# --- Feature validation ---

def test_feature_missing_acceptance_criteria():
    m = _valid_manifest()
    del m["features"][0]["acceptance_criteria"]
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("acceptance_criteria" in e.path for e in result.errors)


def test_feature_empty_acceptance_criteria():
    m = _valid_manifest()
    m["features"][0]["acceptance_criteria"] = []
    result = validate_manifest(m, "test")
    assert not result.valid


def test_feature_missing_deliverables():
    m = _valid_manifest()
    del m["features"][0]["deliverables"]
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("deliverables" in e.path for e in result.errors)


def test_feature_not_object():
    m = _valid_manifest()
    m["features"] = ["not an object"]
    result = validate_manifest(m, "test")
    assert not result.valid


def test_feature_empty_criterion_string():
    m = _valid_manifest()
    m["features"][0]["acceptance_criteria"] = ["valid", ""]
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("non-empty string" in e.message for e in result.errors)


# --- Constraints validation ---

def test_invalid_constraint_type():
    m = _valid_manifest()
    m["constraints"] = {"timeout_seconds": -1}
    result = validate_manifest(m, "test")
    assert not result.valid
    assert any("non-negative" in e.message for e in result.errors)


def test_constraints_not_object():
    m = _valid_manifest()
    m["constraints"] = "bad"
    result = validate_manifest(m, "test")
    assert not result.valid


# --- File-level validation ---

def test_file_not_found():
    result = validate_manifest_file(Path("/nonexistent/feature_manifest.json"))
    assert not result.valid
    assert any("not found" in e.message for e in result.errors)


def test_invalid_json_file():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=tempfile.gettempdir()
    ) as f:
        f.write("{invalid json")
        tmp = Path(f.name)
    try:
        result = validate_manifest_file(tmp)
        assert not result.valid
        assert any("invalid JSON" in e.message for e in result.errors)
    finally:
        tmp.unlink()


def test_valid_file():
    with tempfile.TemporaryDirectory() as td:
        contract_dir = Path(td) / "test-contract"
        contract_dir.mkdir()
        manifest = contract_dir / "feature_manifest.json"
        manifest.write_text(json.dumps(_valid_manifest()))
        result = validate_manifest_file(manifest)
        assert result.valid, f"Expected valid, got: {result}"


# --- Error output quality ---

def test_error_has_fix_suggestion():
    m = _valid_manifest()
    del m["id"]
    del m["version"]
    result = validate_manifest(m, "test")
    for err in result.errors:
        assert err.fix, f"Error at {err.path} missing fix suggestion"


def test_to_dict():
    m = _valid_manifest()
    del m["id"]
    result = validate_manifest(m, "test")
    d = result.to_dict()
    assert d["contract_id"] == "test"
    assert d["valid"] is False
    assert d["error_count"] > 0
    assert all("fix" in e for e in d["errors"])


def test_multiple_errors_reported():
    """All errors should be reported, not just the first one."""
    m = {"status": "bogus"}  # missing almost everything
    result = validate_manifest(m, "test")
    assert len(result.errors) >= 4  # id, title, version, assignee, features at minimum


# --- Run ---

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
