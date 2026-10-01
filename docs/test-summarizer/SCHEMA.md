# Snapshot schema v1

Canonical field names for `test_summarizer`. Pydantic models must match this file. Bump `schema_version` and this document together (`schema:` PR).

## Snapshot

```json
{
  "schema_version": 1,
  "analyzed_repo": "/abs/or/rel/path",
  "git_commit": "sha or empty if not a git repo",
  "generated_at": "ISO-8601 UTC",
  "package_path": "." ,
  "product_narrative": "",
  "records": [],
  "findings": [],
  "capabilities": [],
  "shipped": [],
  "gaps": [],
  "contradictions": [],
  "delta": null
}
```

- `package_path`: `.` or a path from `.release-please-manifest.json`.
- `product_narrative`: optional prose generated **last** from `capabilities`. Never the thing that is diffed.
- `delta`: `null` when no previous snapshot was provided.

## TestRecord

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable: `{path}::{name}` (pytest node-id style). |
| `path` | string | Repo-relative file path. |
| `name` | string | Function, method, or `it()` title. |
| `suite` | string | Class / describe block, else `""`. |
| `layer` | `unit` \| `integration` \| `e2e` \| `unknown` | Heuristic from path (`e2e`, `integration`, default `unit`). |
| `oracles` | list[string] | Assert/expect/fail snippets or normalized labels. Empty → `no_oracle`. |
| `doubles` | list[string] | Mock/stub/spy/fake names. |
| `status` | `passed` \| `failed` \| `skipped` \| `error` \| `unknown` | `unknown` if no report overlay. |
| `source_present` | bool | False if only seen in a report. |
| `report_present` | bool | False if only seen in source. |
| `needs_llm` | list[string] | Rule ids deferred to phase 3. |

## Finding

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable: `{rule_id}:{record_id}`. |
| `rule_id` | see rules below | |
| `severity` | `error` \| `warning` \| `info` | |
| `record_id` | string | `TestRecord.id`. |
| `evidence` | string | Short quote or reason. |
| `message` | string | Human sentence. |

### rule_id (v1)

| rule_id | Phase | Default severity |
|---|---|---|
| `no_oracle` | 2 | error |
| `empty_body` | 2 | error |
| `orphan_report` | 2 | warning |
| `missing_source` | 2 | warning |
| `skip_or_flake` | 2 | info |
| `theatrical` | 3 | warning |
| `name_mismatch` | 3 | warning |
| `framework_not_product` | 3 | warning |

Do not add rules in code before they appear here.

## Capability

| Field | Type | Notes |
|---|---|---|
| `id` | string | Slug, stable across runs when title is similar (phase 3 defines matching). |
| `title` | string | Short name. |
| `behavior` | string | One sentence. |
| `evidence_record_ids` | list[string] | All supporting tests. |
| `evidence_discounted` | bool | True if every evidence record is theatrical or `no_oracle`. |
| `confidence` | `high` \| `medium` \| `low` | Allowed here (cluster quality), not on findings. |

## ShippedItem

| Field | Type | Notes |
|---|---|---|
| `id` | string | `{version}:{heading-slug}` |
| `version` | string | e.g. `1.4.0` |
| `kind` | `feat` \| `fix` \| `perf` \| `revert` \| `other` | |
| `title` | string | Changelog line. |
| `date` | string | ISO date or `""`. |

## Gap / Contradiction

```json
{ "shipped_id": "...", "capability_id": null, "reason": "..." }
```

```json
{ "shipped_id": "...", "capability_id": "...", "reason": "..." }
```

Gap: shipped, no non-discounted capability. Contradiction: both sides present but behavior disagrees.

## Delta

| Field | Type |
|---|---|
| `findings_opened` | list[string] (finding ids) |
| `findings_closed` | list[string] |
| `capabilities_gained` | list[string] |
| `capabilities_lost` | list[string] |
| `shipped_without_evidence` | list[string] (shipped ids new since previous) |

Empty lists, never omitted, when previous snapshot exists.
