"""CLI for the test summarizer (phase 1: empty-valid snapshot)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from test_summarizer.models import SCHEMA_VERSION, Snapshot

SNAPSHOT_FILENAME = "snapshot.json"


def _git_commit(repo: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def build_empty_snapshot(repo: Path) -> Snapshot:
    return Snapshot(
        schema_version=SCHEMA_VERSION,
        analyzed_repo=str(repo.resolve()),
        git_commit=_git_commit(repo),
        generated_at=datetime.now(timezone.utc).isoformat(),
        package_path=".",
        product_narrative="",
        records=[],
        findings=[],
        capabilities=[],
        shipped=[],
        gaps=[],
        contradictions=[],
        delta=None,
    )


def write_snapshot(snapshot: Snapshot, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / SNAPSHOT_FILENAME
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def run(repo: Path, out_dir: Path, previous: Path | None) -> Path:
    del previous  # accepted and ignored until phase 5
    snapshot = build_empty_snapshot(repo)
    return write_snapshot(snapshot, out_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="test_summarizer")
    sub = parser.add_subparsers(dest="command", required=True)
    run_cmd = sub.add_parser("run", help="Write a snapshot for --repo into --out")
    run_cmd.add_argument("--repo", required=True, type=Path, help="Repository root to analyze")
    run_cmd.add_argument("--out", required=True, type=Path, help="Directory for snapshot.json")
    run_cmd.add_argument(
        "--previous",
        type=Path,
        default=None,
        help="Previous snapshot (ignored until phase 5)",
    )
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.error(f"unknown command {args.command}")

    repo: Path = args.repo
    if not repo.is_dir():
        print(f"error: --repo is not a directory: {repo}", file=sys.stderr)
        return 2

    write_path = run(repo=repo, out_dir=args.out, previous=args.previous)
    print(write_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
