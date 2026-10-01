#!/bin/sh
# Exit 0 if `gh` is logged in; exit 1 otherwise. No output except gh's own status.
set -e
if ! command -v gh >/dev/null 2>&1; then
  echo "gh is not installed" >&2
  exit 1
fi
gh auth status
