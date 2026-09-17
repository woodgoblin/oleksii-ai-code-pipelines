---
name: summarizer-implement
description: Implements the next test-summarizer PLAN.md phase in test_summarizer/. Use when coding the rewrite, phase 1–5, CLI, extractors, lint rules, changelog align, or GitHub Action for the summarizer.
---

# Summarizer implementer

## Required reads (every turn)

1. `docs/test-summarizer/PLAN.md` — current phase only
2. `docs/test-summarizer/SCHEMA.md`
3. `AGENTS.md`

## Do

- Put code in `test_summarizer/` and unit tests in `tests/unit/test_summarizer/`.
- Match SCHEMA field names exactly.
- Run `python docs/test-summarizer/check_plan_invariants.py` before finishing.
- Run pytest on tests you added.

## Do not

- Import `google.adk` or edit `project_test_summarizer/` except a freeze comment if asked.
- Edit `docs/test-summarizer/SCHEMA.md`.
- Implement a later phase “while you are here.”
- Call live LLMs in phases 1–2.

If SCHEMA is insufficient, stop and request a `schema:` PR instead of inventing fields.
