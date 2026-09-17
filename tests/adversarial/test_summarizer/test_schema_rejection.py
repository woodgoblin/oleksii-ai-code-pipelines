"""Phase 1 attacks: extra JSON fields and missing schema_version must be rejected."""

import json

import pytest
from pydantic import ValidationError

from test_summarizer.models import (
    SCHEMA_VERSION,
    Delta,
    Finding,
    Snapshot,
)
from test_summarizer.models import TestRecord as InventoryRecord

SNAPSHOT_KEYS = (
    "schema_version",
    "analyzed_repo",
    "git_commit",
    "generated_at",
    "package_path",
    "product_narrative",
    "records",
    "findings",
    "capabilities",
    "shipped",
    "gaps",
    "contradictions",
    "delta",
)


def _minimal_snapshot_dict() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "analyzed_repo": "/tmp/empty",
        "git_commit": "",
        "generated_at": "2026-09-17T00:00:00+00:00",
        "package_path": ".",
        "product_narrative": "",
        "records": [],
        "findings": [],
        "capabilities": [],
        "shipped": [],
        "gaps": [],
        "contradictions": [],
        "delta": None,
    }


def _minimal_record_dict() -> dict:
    return {
        "id": "tests/test_foo.py::test_bar",
        "path": "tests/test_foo.py",
        "name": "test_bar",
        "suite": "",
        "layer": "unit",
        "oracles": [],
        "doubles": [],
        "status": "unknown",
        "source_present": True,
        "report_present": False,
        "needs_llm": [],
    }


def _minimal_finding_dict() -> dict:
    return {
        "id": "no_oracle:tests/test_foo.py::test_bar",
        "rule_id": "no_oracle",
        "severity": "error",
        "record_id": "tests/test_foo.py::test_bar",
        "evidence": "body has no assert",
        "message": "Test has no oracle.",
    }


def _minimal_delta_dict() -> dict:
    return {
        "findings_opened": [],
        "findings_closed": [],
        "capabilities_gained": [],
        "capabilities_lost": [],
        "shipped_without_evidence": [],
    }


class TestExtraJsonFieldsRejected:
    def test_given_legacy_score_field_when_validating_snapshot_then_it_is_rejected(self):
        """Given a banned extra field, when validating a snapshot, then extra keys are rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        payload["meaningfulness_score"] = 0.9

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)

    def test_given_extra_field_on_disk_when_loaded_then_snapshot_is_rejected(self, tmp_path):
        """Given extra snapshot keys on disk, when loaded, then validation fails."""
        # Arrange
        payload = _minimal_snapshot_dict()
        payload["unexpected"] = "not-in-schema"
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def test_given_extra_field_on_record_when_validating_then_it_is_rejected(self):
        """Given an extra TestRecord field, when validating, then the record is rejected."""
        # Arrange
        payload = _minimal_record_dict()
        payload["coverage_xml_hits"] = 12

        # Act / Assert
        with pytest.raises(ValidationError):
            InventoryRecord.model_validate(payload)

    def test_given_nested_record_with_extra_key_when_validating_snapshot_then_it_is_rejected(self):
        """Given extra keys inside records[], when loading a snapshot, then it is rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        record = _minimal_record_dict()
        record["not_a_schema_field"] = True
        payload["records"] = [record]

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)

    def test_given_extra_field_on_finding_when_validating_then_it_is_rejected(self):
        """Given an extra Finding field, when validating, then the finding is rejected."""
        # Arrange
        payload = _minimal_finding_dict()
        payload["severity_prose"] = "high"

        # Act / Assert
        with pytest.raises(ValidationError):
            Finding.model_validate(payload)

    def test_given_extra_field_on_delta_when_validating_then_it_is_rejected(self):
        """Given an extra Delta field, when validating, then the delta is rejected."""
        # Arrange
        payload = _minimal_delta_dict()
        payload["copied_from_previous"] = True

        # Act / Assert
        with pytest.raises(ValidationError):
            Delta.model_validate(payload)


class TestMissingSchemaVersionRejected:
    def test_given_on_disk_json_without_schema_version_when_loaded_then_it_is_rejected(
        self, tmp_path
    ):
        """Given a snapshot file missing schema_version, when loaded, then it is rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        del payload["schema_version"]
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def test_given_null_schema_version_when_validating_then_it_is_rejected(self):
        """Given schema_version set to null, when validating, then the snapshot is rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        payload["schema_version"] = None

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)

    def test_given_wrong_schema_version_when_validating_then_it_is_rejected(self):
        """Given schema_version other than 1, when validating, then the snapshot is rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        payload["schema_version"] = 2

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)

    def test_given_zero_schema_version_when_validating_then_it_is_rejected(self):
        """Given schema_version 0, when validating, then the snapshot is rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        payload["schema_version"] = 0

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)


class TestSnapshotKeyContract:
    def test_given_valid_payload_when_dumped_then_only_schema_keys_are_present(self):
        """Given a valid snapshot, when serialized, then JSON keys match SCHEMA.md exactly."""
        # Arrange
        snapshot = Snapshot.model_validate(_minimal_snapshot_dict())

        # Act
        data = json.loads(snapshot.model_dump_json())

        # Assert
        assert tuple(data.keys()) == SNAPSHOT_KEYS
        assert data["schema_version"] == SCHEMA_VERSION
        assert data["delta"] is None
