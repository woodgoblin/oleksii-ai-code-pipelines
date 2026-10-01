"""Tests for snapshot schema round-trip and extra-field rejection."""

import json

import pytest
from pydantic import ValidationError

from test_summarizer.models import SCHEMA_VERSION, Snapshot


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


class TestSnapshotSchema:
    def test_given_schema_v1_payload_when_round_tripped_then_models_match(self):
        """Given a schema v1 dict, when dumped and loaded, then field values are unchanged."""
        # Arrange
        original = Snapshot.model_validate(_minimal_snapshot_dict())

        # Act
        loaded = Snapshot.model_validate_json(original.model_dump_json())

        # Assert
        assert loaded == original
        assert loaded.schema_version == SCHEMA_VERSION
        assert loaded.delta is None
        assert loaded.records == []

    def test_given_unknown_field_when_validating_snapshot_then_validation_error_is_raised(self):
        """Given an extra JSON field, when validating, then extra fields are rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        payload["unexpected"] = True

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)

    def test_given_payload_missing_schema_version_when_validating_then_validation_error_is_raised(
        self,
    ):
        """Given JSON without schema_version, when validating, then the snapshot is rejected."""
        # Arrange
        payload = _minimal_snapshot_dict()
        del payload["schema_version"]

        # Act / Assert
        with pytest.raises(ValidationError):
            Snapshot.model_validate(payload)

    def test_given_empty_lists_when_dumping_json_then_keys_are_present(self):
        """Given an empty snapshot, when serialized, then inventory keys exist as empty arrays."""
        # Arrange
        snapshot = Snapshot.model_validate(_minimal_snapshot_dict())

        # Act
        data = json.loads(snapshot.model_dump_json())

        # Assert
        assert data["records"] == []
        assert data["findings"] == []
        assert data["capabilities"] == []
        assert data["shipped"] == []
        assert data["gaps"] == []
        assert data["contradictions"] == []
        assert data["delta"] is None
