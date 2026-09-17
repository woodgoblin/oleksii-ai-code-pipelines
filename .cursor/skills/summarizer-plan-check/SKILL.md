---
name: summarizer-plan-check
description: Audits test-summarizer diffs against PLAN.md and SCHEMA.md. Use when checking plan alignment, invariants, rewrite drift, or after an implementer session.
---

# Summarizer plan auditor

Read `docs/test-summarizer/PLAN.md` and `SCHEMA.md` from disk. Do not use chat summaries of the plan.

## Procedure

1. `git diff` and `git diff main...HEAD` if on a branch (use the repo’s default base if not `main`).
2. Run `python docs/test-summarizer/check_plan_invariants.py`.
3. Manually check:
   - Only the current phase’s files/behavior landed.
   - No SCHEMA.md edits unless title/commit is `schema:`.
   - No ADK, no per-test LLM loop, no `coverage.xml` as tests, no `lstrip("**/")`.
   - New Pydantic fields ⊆ SCHEMA.md.

## Output

```
VERDICT: PASS | FAIL
INVARIANTS: PASS | FAIL
PHASE: N
VIOLATIONS:
- ...
SCOPE LEAK:
- ...
```

Do not edit the tree. FAIL must be explicit so the conductor can loop the implementer.
