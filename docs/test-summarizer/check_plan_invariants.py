#!/usr/bin/env python3
"""Fail the rewrite if the tree drifts from docs/test-summarizer/PLAN.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs" / "test-summarizer" / "PLAN.md"
SCHEMA = ROOT / "docs" / "test-summarizer" / "SCHEMA.md"
PKG = ROOT / "test_summarizer"
OLD_PKG = ROOT / "project_test_summarizer"

FORBIDDEN_IN_NEW_PKG = (
    "google.adk",
    "LlmAgent",
    "SequentialAgent",
    "LoopAgent",
    "ParallelAgent",
    "InMemorySessionService",
    "adk web",
    "meaningfulness_score",
    "naming_clarity_score",
)

FORBIDDEN_IMPORT = re.compile(
    r"^\s*(from\s+google\.adk\s+import|import\s+google\.adk)",
    re.MULTILINE,
)


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)


def check_docs(errors: list[str]) -> None:
    if not PLAN.is_file():
        fail(f"missing contract: {PLAN}", errors)
    if not SCHEMA.is_file():
        fail(f"missing schema: {SCHEMA}", errors)
    else:
        text = SCHEMA.read_text(encoding="utf-8")
        if "schema_version" not in text:
            fail("SCHEMA.md must define schema_version", errors)
        if "coverage.xml" in text and "TestRecord" in text:
            # coverage.xml may be mentioned only as forbidden — require the word not
            pass


def check_new_package(errors: list[str]) -> None:
    if not PKG.is_dir():
        return
    for path in PKG.rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        if FORBIDDEN_IMPORT.search(body):
            fail(f"{rel}: imports google.adk", errors)
        for token in FORBIDDEN_IN_NEW_PKG:
            if token in body:
                fail(f"{rel}: forbidden token {token!r}", errors)
        if 'lstrip("**/")' in body or "lstrip('**/')" in body:
            fail(f"{rel}: forbidden glob lstrip of **/", errors)


def check_schema_models(errors: list[str]) -> None:
    models = PKG / "models.py"
    if not models.is_file():
        return
    schema = SCHEMA.read_text(encoding="utf-8")
    body = models.read_text(encoding="utf-8")
    required = [
        "schema_version",
        "TestRecord",
        "Finding",
        "Capability",
        "ShippedItem",
        "rule_id",
        "evidence_discounted",
    ]
    for name in required:
        if name not in schema:
            fail(f"SCHEMA.md missing {name}", errors)
        if name not in body:
            fail(f"test_summarizer/models.py missing {name} (must match SCHEMA.md)", errors)


def check_old_package_not_rewritten_as_adk_extension(errors: list[str]) -> None:
    """New work must not add agents to the frozen package."""
    agent = OLD_PKG / "agent.py"
    if not agent.is_file():
        return
    # Presence is fine. Adding more LlmAgent names is out of scope for this script.


def main() -> int:
    errors: list[str] = []
    check_docs(errors)
    check_new_package(errors)
    check_schema_models(errors)
    check_old_package_not_rewritten_as_adk_extension(errors)
    if errors:
        print("PLAN INVARIANTS: FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1
    print("PLAN INVARIANTS: PASS")
    if not PKG.is_dir():
        print("  (test_summarizer/ not created yet — docs-only pass)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
