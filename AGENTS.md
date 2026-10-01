# Agent notes

This repo is in a **test-summarizer rewrite**. Do not continue the Google ADK graph in `project_test_summarizer/`.

## Before any summarizer work

1. Read `docs/test-summarizer/PLAN.md` (contract; wins over chat and canvas).
2. Read `docs/test-summarizer/SCHEMA.md` (field names).
3. Read `docs/test-summarizer/TEAM.md` (roles). Follow the skill for your role under `.cursor/skills/`.

## Hard rules

- New code lives in `test_summarizer/`. No `google.adk` there.
- One PLAN phase per session. After coding: `python docs/test-summarizer/check_plan_invariants.py`.
- Do not edit `SCHEMA.md` unless the user asked for a `schema:` change.
- `cursor_prompt_preprocessor/` and `potato_decison_with_human_in_the_loop/` are out of scope unless the user names them.
- GitHub: `.cursor/skills/gh-github/SKILL.md`. `gh auth status` before push/PR. If unauthorized, ask the user to authorize and stop; do not assume they refused.

Canvas (briefing only): `test-summarizer-architecture.canvas.tsx` in the workspace canvases folder.
