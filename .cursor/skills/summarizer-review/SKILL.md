---
name: summarizer-review
description: Senior review of test-summarizer rewrite PRs. Use when reviewing summarizer diffs, merge bar, architecture drift, or phase scope.
---

# Summarizer senior review

Read `docs/test-summarizer/PLAN.md`, `SCHEMA.md`, and the diff. You do not implement.

## Merge bar

- Correct vs SCHEMA (names, types, omitted `delta` vs `null`).
- Phase scope: reject leaked later-phase features.
- Tests are meaningful (behavior), not factory-preamble asserts.
- CLI is deterministic without secrets in phases 1–2.
- No secrets in snapshots. Paths relative where possible.
- GHA (phase 5): least privilege, no `adk`, snapshot persistence is explicit.

## Output

```
VERDICT: approve | request changes | reject
PHASE FIT: ok | leaked
BLOCKERS:
- ...
NITS:
- ...
```

Reject if the PR teaches ADK agents to call new tools instead of adding `test_summarizer/`.
