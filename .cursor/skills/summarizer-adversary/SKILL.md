---
name: summarizer-adversary
description: Adversarial tests for the test-summarizer rewrite. Use when fuzzing extractors, proving mocks-only is not coverage, empty deltas, changelog gaps, or glob/report confusion.
---

# Summarizer adversary

Read `docs/test-summarizer/PLAN.md` (current phase) and `SCHEMA.md`. Add tests under `tests/adversarial/test_summarizer/` with Arrange/Act/Assert and human-readable names.

## Attack list (use those in-phase)

| Attack | Phase |
|---|---|
| `coverage.xml` must not create `TestRecord`s | 2 |
| Broken `**/` globs miss Surefire-style paths | 2 |
| Empty test body → `empty_body` / `no_oracle` | 2 |
| Report-only name → `missing_source`; source-only ok | 2 |
| Mocks-only login is not non-discounted coverage | 3 |
| Extra JSON fields / missing `schema_version` rejected | 1 |
| Unchanged snapshot twice → empty `delta` lists | 5 |
| Feat in CHANGELOG, no tests → `gaps` | 4 |
| Theatrical evidence still appears in `findings` | 3 |

Prefer a failing test over patching production code. Do not weaken SCHEMA to make tests pass.

No live API keys. Fake the LLM client.
