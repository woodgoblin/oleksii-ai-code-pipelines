"""Guard: rewrite contract files exist and the invariants script stays green."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.unit
class TestPlanInvariantsScript:
    def test_given_docs_only_tree_when_invariants_run_then_script_exits_zero(self):
        """Given the rewrite contract files, when the gate runs before test_summarizer exists, then it PASSes."""
        # Arrange
        script = ROOT / "docs" / "test-summarizer" / "check_plan_invariants.py"
        assert script.is_file()
        assert (ROOT / "docs" / "test-summarizer" / "PLAN.md").is_file()
        assert (ROOT / "docs" / "test-summarizer" / "SCHEMA.md").is_file()

        # Act
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        # Assert
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "PASS" in completed.stdout
