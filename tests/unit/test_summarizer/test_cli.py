"""Tests for the phase-1 CLI: empty repo snapshot, ignored --previous."""

import json
import subprocess
import sys
from pathlib import Path

from test_summarizer.models import SCHEMA_VERSION, Snapshot


class TestRunCli:
    def test_given_empty_directory_when_run_then_exit_zero_and_snapshot_validates(self, tmp_path):
        """Given an empty dir, when running the CLI, then it exits 0 and writes a valid snapshot."""
        # Arrange
        repo = tmp_path / "repo"
        out = tmp_path / "out"
        repo.mkdir()

        # Act
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "test_summarizer",
                "run",
                "--repo",
                str(repo),
                "--out",
                str(out),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[3],
        )

        # Assert
        assert completed.returncode == 0, completed.stderr
        snapshot_path = out / "snapshot.json"
        assert snapshot_path.is_file()
        snapshot = Snapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
        assert snapshot.schema_version == SCHEMA_VERSION
        assert snapshot.records == []
        assert snapshot.delta is None
        assert snapshot.git_commit == ""
        assert Path(snapshot.analyzed_repo) == repo.resolve()

    def test_given_previous_flag_when_run_then_delta_stays_null(self, tmp_path):
        """Given --previous, when running phase 1, then the flag is accepted and delta stays null."""
        # Arrange
        repo = tmp_path / "repo"
        out = tmp_path / "out"
        previous = tmp_path / "old.json"
        repo.mkdir()
        previous.write_text("{}", encoding="utf-8")

        # Act
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "test_summarizer",
                "run",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--previous",
                str(previous),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[3],
        )

        # Assert
        assert completed.returncode == 0, completed.stderr
        data = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
        assert data["delta"] is None

    def test_given_missing_repo_when_run_then_exit_is_nonzero(self, tmp_path):
        """Given a missing --repo path, when running, then the CLI fails without writing a snapshot."""
        # Arrange
        missing = tmp_path / "no-such-repo"
        out = tmp_path / "out"

        # Act
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "test_summarizer",
                "run",
                "--repo",
                str(missing),
                "--out",
                str(out),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[3],
        )

        # Assert
        assert completed.returncode != 0
        assert not (out / "snapshot.json").exists()
