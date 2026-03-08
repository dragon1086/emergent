"""
rolemesh/contract_validator.py - Contract Artifact Validator [RB106]

Validates contracts/<id>/feature_manifest.json against a strict schema.
Returns actionable errors with field paths and fix suggestions.
"""

import json
import re
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_DIR = ROOT / "contracts"

# --- Schema Definition ---

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[\w.]+)?$")
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

VALID_STATUSES = {"draft", "active", "completed", "failed", "delegated", "implemented", "verified"}


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


# --- Validation Errors ---

class ManifestError:
    """Single validation error with path and fix suggestion."""

    def __init__(self, path: str, message: str, fix: str):
        self.path = path
        self.message = message
        self.fix = fix

    def __str__(self):
        return f"  [{self.path}] {self.message}\n    → fix: {self.fix}"

    def to_dict(self) -> dict:
        return {"path": self.path, "message": self.message, "fix": self.fix}


class ValidationResult:
    """Aggregated validation outcome."""

    def __init__(self, contract_id: str, errors: list[ManifestError]):
        self.contract_id = contract_id
        self.errors = errors
        self.valid = len(errors) == 0

    def __str__(self):
        if self.valid:
            return f"✓ contracts/{self.contract_id}/feature_manifest.json — valid"
        header = (
            f"✗ contracts/{self.contract_id}/feature_manifest.json — "
            f"{len(self.errors)} error(s)"
        )
        details = "\n".join(str(e) for e in self.errors)
        return f"{header}\n{details}"

    def to_dict(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "valid": self.valid,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
        }


# --- Core Validator ---

def _require_field(data: dict, field: str, parent: str, expected_type: type) -> list[ManifestError]:
    """Check that a required field exists and has the correct type."""
    errors = []
    path = f"{parent}.{field}" if parent else field
    if field not in data:
        type_name = expected_type.__name__
        errors.append(ManifestError(
            path,
            f"missing required field '{field}'",
            f"add \"{field}\": <{type_name}> to the manifest",
        ))
    elif not isinstance(data[field], expected_type):
        errors.append(ManifestError(
            path,
            f"expected {expected_type.__name__}, got {type(data[field]).__name__}",
            f"change '{field}' value to a {expected_type.__name__}",
        ))
    return errors


def _validate_root(data: dict) -> list[ManifestError]:
    """Validate top-level required fields."""
    errors = []

    # required string fields
    for field in ("id", "title", "version", "assignee", "status"):
        errors.extend(_require_field(data, field, "", str))

    # id must be UUID
    if "id" in data and isinstance(data["id"], str) and not _is_uuid(data["id"]):
        errors.append(ManifestError(
            "id",
            f"invalid UUID format: '{data['id']}'",
            "use a valid UUID v4, e.g. uuid.uuid4()",
        ))

    # version must be semver
    if "version" in data and isinstance(data["version"], str):
        if not SEMVER_RE.match(data["version"]):
            errors.append(ManifestError(
                "version",
                f"invalid semver: '{data['version']}'",
                "use MAJOR.MINOR.PATCH format, e.g. '1.0.0'",
            ))

    # status must be valid enum
    if "status" in data and isinstance(data["status"], str):
        if data["status"] not in VALID_STATUSES:
            errors.append(ManifestError(
                "status",
                f"unknown status '{data['status']}'",
                f"use one of: {', '.join(sorted(VALID_STATUSES))}",
            ))

    # created_at (optional but must be ISO 8601 if present)
    if "created_at" in data:
        if not isinstance(data["created_at"], str) or not ISO8601_RE.match(data["created_at"]):
            errors.append(ManifestError(
                "created_at",
                "invalid ISO 8601 timestamp",
                "use format: 2026-03-07T12:00:00",
            ))

    # features must be a non-empty list
    errors.extend(_require_field(data, "features", "", list))
    if "features" in data and isinstance(data["features"], list):
        if len(data["features"]) == 0:
            errors.append(ManifestError(
                "features",
                "features array is empty",
                "add at least one feature object with name, description, acceptance_criteria, deliverables",
            ))

    return errors


def _validate_feature(feat: Any, index: int) -> list[ManifestError]:
    """Validate a single feature entry."""
    errors = []
    path = f"features[{index}]"

    if not isinstance(feat, dict):
        errors.append(ManifestError(
            path,
            f"expected object, got {type(feat).__name__}",
            "each feature must be an object with name, description, acceptance_criteria, deliverables",
        ))
        return errors

    for field in ("name", "description"):
        errors.extend(_require_field(feat, field, path, str))

    # acceptance_criteria: required, non-empty list of strings
    ac_path = f"{path}.acceptance_criteria"
    if "acceptance_criteria" not in feat:
        errors.append(ManifestError(
            ac_path,
            "missing required field 'acceptance_criteria'",
            "add \"acceptance_criteria\": [\"criterion 1\", ...] — at least one",
        ))
    elif not isinstance(feat["acceptance_criteria"], list):
        errors.append(ManifestError(
            ac_path,
            f"expected list, got {type(feat['acceptance_criteria']).__name__}",
            "acceptance_criteria must be an array of strings",
        ))
    elif len(feat["acceptance_criteria"]) == 0:
        errors.append(ManifestError(
            ac_path,
            "acceptance_criteria is empty",
            "add at least one acceptance criterion string",
        ))
    else:
        for i, ac in enumerate(feat["acceptance_criteria"]):
            if not isinstance(ac, str) or not ac.strip():
                errors.append(ManifestError(
                    f"{ac_path}[{i}]",
                    "criterion must be a non-empty string",
                    "replace with a descriptive acceptance criterion",
                ))

    # deliverables: required, non-empty list of strings
    dl_path = f"{path}.deliverables"
    if "deliverables" not in feat:
        errors.append(ManifestError(
            dl_path,
            "missing required field 'deliverables'",
            "add \"deliverables\": [\"file_or_output_1\", ...] — at least one",
        ))
    elif not isinstance(feat["deliverables"], list):
        errors.append(ManifestError(
            dl_path,
            f"expected list, got {type(feat['deliverables']).__name__}",
            "deliverables must be an array of strings",
        ))
    elif len(feat["deliverables"]) == 0:
        errors.append(ManifestError(
            dl_path,
            "deliverables is empty",
            "add at least one deliverable (file path, artifact name, etc.)",
        ))

    return errors


def _validate_constraints(data: dict) -> list[ManifestError]:
    """Validate optional constraints block."""
    errors = []
    if "constraints" not in data:
        return errors

    constraints = data["constraints"]
    if not isinstance(constraints, dict):
        errors.append(ManifestError(
            "constraints",
            f"expected object, got {type(constraints).__name__}",
            "constraints must be an object with optional timeout_seconds, max_retries",
        ))
        return errors

    for field in ("timeout_seconds", "max_retries"):
        if field in constraints:
            val = constraints[field]
            if not isinstance(val, int) or val < 0:
                errors.append(ManifestError(
                    f"constraints.{field}",
                    f"must be a non-negative integer, got {val!r}",
                    f"set {field} to a positive integer",
                ))

    return errors


def validate_manifest(data: dict, contract_id: str = "unknown") -> ValidationResult:
    """Validate a parsed feature_manifest dict. Returns ValidationResult."""
    errors: list[ManifestError] = []
    errors.extend(_validate_root(data))

    if "features" in data and isinstance(data["features"], list):
        for i, feat in enumerate(data["features"]):
            errors.extend(_validate_feature(feat, i))

    errors.extend(_validate_constraints(data))

    return ValidationResult(contract_id, errors)


def validate_manifest_file(path: Path) -> ValidationResult:
    """Load and validate a feature_manifest.json file."""
    contract_id = path.parent.name

    if not path.exists():
        return ValidationResult(contract_id, [ManifestError(
            str(path),
            "file not found",
            f"create {path} with the required schema (see contracts/example/feature_manifest.json)",
        )])

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationResult(contract_id, [ManifestError(
            str(path), f"cannot read file: {exc}",
            "check file permissions",
        )])

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ValidationResult(contract_id, [ManifestError(
            str(path),
            f"invalid JSON at line {exc.lineno}, col {exc.colno}: {exc.msg}",
            "fix JSON syntax (check for trailing commas, missing quotes, etc.)",
        )])

    if not isinstance(data, dict):
        return ValidationResult(contract_id, [ManifestError(
            str(path),
            f"root must be an object, got {type(data).__name__}",
            "wrap content in {{ ... }}",
        )])

    return validate_manifest(data, contract_id)


def validate_all_contracts(contracts_dir: Path | None = None) -> list[ValidationResult]:
    """Validate all contracts/<id>/feature_manifest.json under the given dir."""
    cdir = contracts_dir or CONTRACTS_DIR
    if not cdir.exists():
        return []

    results = []
    for manifest in sorted(cdir.glob("*/feature_manifest.json")):
        results.append(validate_manifest_file(manifest))
    return results


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate contracts/<id>/feature_manifest.json files",
    )
    parser.add_argument(
        "path", nargs="?", default=None,
        help="specific manifest file or contracts dir (default: contracts/)",
    )
    parser.add_argument("--json", action="store_true", help="output as JSON")
    args = parser.parse_args()

    if args.path:
        p = Path(args.path)
        if p.is_file():
            results = [validate_manifest_file(p)]
        elif p.is_dir():
            results = validate_all_contracts(p)
        else:
            print(f"Error: {p} not found")
            raise SystemExit(1)
    else:
        results = validate_all_contracts()

    if not results:
        print("No contracts found.")
        raise SystemExit(0)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(r)
            print()

    if any(not r.valid for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
