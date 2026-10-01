# Test summarizer rewrite — contract

This file is the source of truth. The architecture canvas is a briefing, not a license to invent. If chat, canvas, and this plan disagree, **this plan wins**. Change it in a dedicated PR, not as a side effect of coding.

- Canvas: `.cursor/projects/.../canvases/test-summarizer-architecture.canvas.tsx` (IDE) or ask the user to open **Test summarizer** canvas
- Schema: [SCHEMA.md](SCHEMA.md)
- Team: [TEAM.md](TEAM.md)
- Invariants gate: `python docs/test-summarizer/check_plan_invariants.py`

## Product

Two primary goals, one snapshot:

1. **Quality lint** — findings with stable `rule_id`s (not high/medium/low prose).
2. **Intel** — product-from-tests (`capabilities[]`), coverage gap vs release-please changelog, real product vs tested, plus week-over-week delta.

A theatrical (mocks-only) test is a lint hit **and** must not count as coverage.

## Runtime (non-negotiable)

- New package: `test_summarizer/` (do not extend `project_test_summarizer/`).
- CLI: `python -m test_summarizer run ...` writing files on disk.
- GitHub Action (phase 5): reusable workflow. Not `adk web`.
- **No Google ADK** in the new package: no `LlmAgent`, `SequentialAgent`, `LoopAgent`, `InMemorySessionService`, session JSON tools.
- LLM only as batched structured calls behind a narrow client (Pydantic models in, Pydantic models out). Zero LLM in phases 1–2.
- One model id in config when LLM lands. One HTTP-client retry policy. No monkey-patches of `google.genai`.

Leave `project_test_summarizer/` frozen until a later cutover PR deletes or stubs it.

## Locked defaults

| Question | Default until the user overrides this table |
|---|---|
| Fail the Action? | Weekly cron never fails default branch. Release-please PR: comment. Optionally fail on `Feat` changelog entries with no non-theatrical evidence (flag, default off). |
| Corpus | Test **source** is primary. JUnit/Jest/HTML reports overlay `status`. Lint must work with source only. |
| Gap target | Changelog-only (Keep a Changelog / release-please). No public-API crawl in v1. |
| Monorepo | One snapshot per `.release-please-manifest.json` package path; single-package repos → one snapshot at repo root. |
| Persistence | Bot-commit `snapshots/YYYY-MM-DD.json` (+ `report.md`) on a `test-intel` branch. Artifacts are backup, not history. |
| AI rewrite prompts | Derived from `Finding[]` in a later export. Not a pipeline stage. |
| FAISS / embeddings | Forbidden until after phase 5 and a written bottleneck. |

## Pipeline

```
collect → inventory → lint (cheap rules) → [LLM hard cases] → [LLM capabilities]
        → parse changelog → align → diff previous snapshot → write snapshot + report
```

Phases 1–2 implement collect, inventory, cheap lint, snapshot write (intel fields empty). Later phases fill intel and diff.

## Phases (one phase per agent session)

### Phase 1 — schema + CLI skeleton

- Pydantic models matching [SCHEMA.md](SCHEMA.md) exactly (`schema_version: 1`).
- `python -m test_summarizer run --repo <path> --out <dir>` produces a valid empty-ish snapshot (inventory may be empty, but JSON validates).
- `--previous` accepted and ignored until phase 5.
- Fixture: snapshot round-trip test. No ADK. No network.

**Done when:** `pytest tests/unit/test_summarizer` validates schema + CLI exit 0 on an empty dir.

### Phase 2 — extractors + cheap lint

- `git ls-files` based collect (tracked files only). Depth-capped sketch is optional metadata, not LLM input yet.
- Test-source discovery via globs in config (fix `**/` glob joining; never `lstrip("**/")` then `os.path.join`).
- Extractors: pytest/unittest functions, JUnit XML `testcase`, Jest JSON `assertionResults`. Coverage XML is **not** a test extractor.
- Cheap rules (deterministic): `no_oracle`, `orphan_report`, `missing_source`, `skip_or_flake`, `empty_body`.
- `theatrical` and `name_mismatch` may be stubbed `needs_llm: true` without calling a model.
- Dogfood: run on this repo’s `tests/` and commit a golden snapshot fragment.

**Done when:** this repo’s tests produce `TestRecord[]` + some findings with no Gemini key.

### Phase 3 — batched LLM quality + capabilities

- Single client module. Structured output only. Batch tests, do not one-call-per-test.
- Fill `theatrical`, `name_mismatch`, `framework_not_product`.
- Cluster into `Capability[]`. Discount evidence that has `theatrical` (or `no_oracle`) — those tests stay in inventory and lint, they do not cover a capability.
- Offline tests: recorded fixtures / fake client. Live model tests marked `integration` and skipped in CI without a key.

**Done when:** a fixture suite with a mocks-only login test yields that finding and a login capability with `evidence_discounted: true`.

### Phase 4 — changelog alignment

- Parse `CHANGELOG.md` (Keep a Changelog / release-please sections) → `ShippedItem[]`.
- Optional `.release-please-manifest.json`.
- Align to capabilities → `gaps[]` and `contradictions[]`.
- Fixture: synthetic changelog Feat with no tests → gap.

**Done when:** alignment tests pass without network.

### Phase 5 — diff + GitHub Action

- Load previous snapshot, emit `delta` (new/closed findings, gained/lost capabilities, shipped-since-last-run with no evidence).
- Reusable workflow: after host tests (optional JUnit artifact), run CLI, write step summary, commit or upload snapshot.
- Triggers: `workflow_dispatch`, cron, and a note in docs for release-please PRs.
- Second run on unchanged repo → empty delta.

**Done when:** workflow file exists and is documented; delta tests pass.

## Forbidden (all phases)

- Importing `google.adk` from `test_summarizer/`.
- Scoring tests with free-text “high/medium/low” as the stored result (legacy field names are banned).
- Treating `coverage.xml` as extracted tests.
- `input()` / human-in-the-loop in the CLI path.
- Changing [SCHEMA.md](SCHEMA.md) in the same PR as feature work unless the PR title starts with `schema:`.
- Implementing phase N+1 in the same session as phase N.

## After each coding session

1. `python docs/test-summarizer/check_plan_invariants.py`
2. `pytest tests/unit/test_summarizer tests/adversarial/test_summarizer -q` (adversarial dir may not exist until phase 2)
3. Stop. Do not start the next phase unless the user said so.
