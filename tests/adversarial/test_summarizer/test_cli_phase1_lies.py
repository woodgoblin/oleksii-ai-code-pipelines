"""Phase 1 CLI lies: --previous must not invent delta; empty dir still writes a valid snapshot."""

import json
import subprocess
import sys
from pathlib import Path

from test_summarizer.models import SCHEMA_VERSION, Snapshot

REPO_ROOT = Path(__file__).resolve().parents[3]

SNAPSHOT_KEYS = frozenset(
    {
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
    }
)


def _run_cli(repo: Path, out: Path, previous: Path | None = None) -> subprocess.CompletedProcess:
    argv = [
        sys.executable,
        "-m",
        "test_summarizer",
        "run",
        "--repo",
        str(repo),
        "--out",
        str(out),
    ]
    if previous is not None:
        argv.extend(["--previous", str(previous)])
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _previous_snapshot_with_delta() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "analyzed_repo": "/tmp/old-repo",
        "git_commit": "abc123",
        "generated_at": "2026-09-01T00:00:00+00:00",
        "package_path": ".",
        "product_narrative": "should not be copied",
        "records": [],
        "findings": [],
        "capabilities": [],
        "shipped": [],
        "gaps": [],
        "contradictions": [],
        "delta": {
            "findings_opened": ["no_oracle:tests/test_foo.py::test_bar"],
            "findings_closed": [],
            "capabilities_gained": ["login"],
            "capabilities_lost": [],
            "shipped_without_evidence": ["1.0.0:feat-login"],
        },
    }


class TestCliPreviousStaysNullDelta:
    def test_given_previous_with_populated_delta_when_run_then_output_delta_is_null(self, tmp_path):
        """Given --previous with a filled delta, when phase 1 runs, then output delta stays null."""
        # Arrange
        repo = tmp_path / "repo"
        out = tmp_path / "out"
        previous = tmp_path / "previous.json"
        repo.mkdir()
        previous.write_text(json.dumps(_previous_snapshot_with_delta()), encoding="utf-8")

        # Act
        completed = _run_cli(repo, out, previous=previous)

        # Assert
        assert completed.returncode == 0, completed.stderr
        data = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
        assert data["delta"] is None
        snapshot = Snapshot.model_validate(data)
        assert snapshot.delta is None
        assert snapshot.product_narrative == ""
        assert snapshot.records == []
        assert snapshot.findings == []

    def test_given_missing_previous_file_when_run_then_exit_zero_and_delta_is_null(self, tmp_path):
        """Given --previous pointing at a missing file, when phase 1 runs, then it is ignored."""
        # Arrange
        repo = tmp_path / "repo"
        out = tmp_path / "out"
        missing = tmp_path / "no-such-previous.json"
        repo.mkdir()

        # Act
        completed = _run_cli(repo, out, previous=missing)

        # Assert
        assert completed.returncode == 0, completed.stderr
        data = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
        assert data["delta"] is None

    def test_given_previous_with_extra_keys_when_run_then_output_snapshot_still_validates(
        self, tmp_path
    ):
        """Given --previous with extra keys, when phase 1 runs, then the flag is ignored."""
        # Arrange
        repo = tmp_path / "repo"
        out = tmp_path / "out"
        previous = tmp_path / "previous.json"
        repo.mkdir()
        payload = _previous_snapshot_with_delta()
        payload["meaningfulness_score"] = 0.1
        previous.write_text(json.dumps(payload), encoding="utf-8")

        # Act
        completed = _run_cli(repo, out, previous=previous)

        # Assert
        assert completed.returncode == 0, completed.stderr
        snapshot = Snapshot.model_validate_json((out / "snapshot.json").read_text(encoding="utf-8"))
        assert snapshot.delta is None


class TestCliEmptyDirWritesValidSnapshot:
    def test_given_empty_dir_when_run_then_written_json_has_only_schema_keys(self, tmp_path):
        """Given an empty dir, when running the CLI, then the written snapshot matches SCHEMA keys."""
        # Arrange
        repo = tmp_path / "repo"
        out = tmp_path / "out"
        repo.mkdir()

        # Act
        completed = _run_cli(repo, out)

        # Assert
        assert completed.returncode == 0, completed.stderr
        path = out / "snapshot.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert set(data.keys()) == SNAPSHOT_KEYS
        snapshot = Snapshot.model_validate(data)
        assert snapshot.schema_version == SCHEMA_VERSION
        assert snapshot.package_path == "."
        assert snapshot.product_narrative == ""
        assert snapshot.records == []
        assert snapshot.findings == []
        assert snapshot.capabilities == []
        assert snapshot.shipped == []
        assert snapshot.gaps == []
        assert snapshot.contradictions == []
        assert snapshot.delta is None
        assert snapshot.git_commit == ""
        assert Path(snapshot.analyzed_repo) == repo.resolve()
