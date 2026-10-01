# Agentic team

Do not implement the rewrite from chat memory. Each role **re-reads** [PLAN.md](PLAN.md) and [SCHEMA.md](SCHEMA.md) at the start of its turn. Parent agents spawn **one role at a time**, wait, then spawn the next. One PLAN phase per implementation session.

## Roster

| Role | Cursor skill | Job | May change |
|---|---|---|---|
| Conductor | `summarizer-conductor` | Pick current phase, spawn others, refuse phase skip | Nothing except checklist status in the reply |
| Implementer | `summarizer-implement` | Code **only** the current PLAN phase | `test_summarizer/`, `tests/unit/test_summarizer/`, phase-allowed config |
| Plan auditor | `summarizer-plan-check` | Diff vs PLAN/SCHEMA; run invariants script | Nothing (report only) |
| Adversary | `summarizer-adversary` | Fixtures that should fail or stay empty-delta | `tests/adversarial/test_summarizer/` only |
| Senior reviewer | `summarizer-review` | Merge bar: correctness, scope, tests | Nothing (report only) |
| Schema steward | (no coding skill) | SCHEMA.md changes | SCHEMA.md + models, only in a `schema:` PR |

Do not add a “prompt engineer” that edits agent instructions instead of tests. Do not add an ADK/migration agent — the old package stays frozen.

## Sequence (every phase)

```
conductor  →  implementer  →  plan-check  →  (implementer fix if FAIL)
           →  adversary    →  plan-check (quick)  →  senior review  →  STOP
```

If plan-check fails, do **not** run adversary or review on a drifting tree. Loop implementer + plan-check until PASS or the user aborts.

If review says “scope creep / next phase leaked in,” revert that leak before merge. Do not “just finish it.”

## Spawn prompts (paste as the Task/agent prompt)

Replace `N` with the phase number. Always attach the two doc paths.

### Implementer

```
You are the test-summarizer implementer. Read and obey:
- docs/test-summarizer/PLAN.md (phase N only)
- docs/test-summarizer/SCHEMA.md
- .cursor/skills/summarizer-implement/SKILL.md

Do not start phase N+1. Do not import google.adk. Do not edit SCHEMA.md.
When done, run: python docs/test-summarizer/check_plan_invariants.py
and pytest for the unit tests you added. Report files changed and remaining TODOs.
```

### Plan auditor

```
You are the test-summarizer plan auditor. Read:
- docs/test-summarizer/PLAN.md
- docs/test-summarizer/SCHEMA.md
- .cursor/skills/summarizer-plan-check/SKILL.md

Inspect the git diff (uncommitted + this branch vs main). Run
python docs/test-summarizer/check_plan_invariants.py
Verdict: PASS or FAIL with a list of plan violations. Do not edit code.
```

### Adversary

```
You are the test-summarizer adversary. Read PLAN.md phase N, SCHEMA.md, and
.cursor/skills/summarizer-adversary/SKILL.md.
Add or run tests under tests/adversarial/test_summarizer/ that try to make
the CLI lie (coverage.xml as tests, mocks-only counted as coverage, empty
delta expected, glob miss, schema extra fields). Do not “fix” production
code unless a test cannot be expressed otherwise — prefer FAIL that the
implementer must fix.
```

### Senior reviewer

```
You are a senior engineer reviewing the test-summarizer rewrite.
Read PLAN.md, SCHEMA.md, .cursor/skills/summarizer-review/SKILL.md,
and the diff. Verdict: approve / request changes / reject (wrong phase).
Do not implement fixes.
```

## What the conductor must not do

- Implement production code itself “to save a round.”
- Summarize PLAN.md from memory instead of opening the file.
- Allow SCHEMA.md edits bundled with feature work.
- Run all four roles in one undifferentiated agent with no artifacts.

## GitHub

PRs and `git push` use `.cursor/skills/gh-github/SKILL.md`. Run `gh auth status` first. If not authorized, ask the user to authorize and **stop** — do not proceed and do not assume they refused.

## Human (you)

After each phase: glance at the auditor FAIL list and the review verdict. Merge only on auditor PASS + review approve. Then say “phase N+1” to start the next session.
