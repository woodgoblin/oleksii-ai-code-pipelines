## Plan: Using Embeddings + FAISS in Test Analysis Pipeline

### 1. Repository Sketch & Detection Plan (First Step)

- Start from `git ls-files` to respect `.gitignore` and only include tracked files.
- Build a **Directory Sketch** capped at depth 5, containing:
  - Total files/dirs counts
  - All root-level file names
  - Top directories and their immediate children
  - File extension histogram (top N)
  - Basename patterns counts (e.g., *test*, *spec*, *report*)
  - A few sampled config/test/report files with only head/tail snippets (≤ 200–300 chars)

**Example Sketch (Input to LLM):**

```json
{
  "totals": {"files": 12873, "dirs": 1523},
  "max_depth": 5,
  "root_files": ["README.md","package.json","pom.xml","pyproject.toml","Makefile",".gitlab-ci.yml"],
  "root_dirs": ["src","tests","spec","e2e","lib","app","build","scripts","tools","docs"],
  "dir_tree_top": [["src", ["main","test","lib"]], ["tests", ["unit","integration","e2e"]]],
  "ext_hist_top": [[".java",6120],[".xml",830],[".md",210],[".kt",180]],
  "basename_patterns": [["*test*",905],["*spec*",240],["*report*",120]],
  "config_samples": [
    {"p":"ci/config.yml","head":"steps: - run: run-tests --report junit"},
    {"p":"project.conf","head":"reporter=junit-xml\ncoverage=lcov"}
  ]
}
```

**Detection Plan (Output from LLM):**

```json
{
  "version": "1.0",
  "summary": {
    "ecosystem_hypotheses": 3,
    "framework_hypotheses": 5,
    "confidence_overall": 0.76
  },
  "ecosystems": [
    {
      "name": "free-text (e.g., JVM-like, Node-like, Custom DSL)",
      "confidence": 0.0,
      "reason": "≤120 chars",
      "checks": [
        {"glob": "**/tests/**"},
        {"glob": "**/build/**"}
      ],
      "content_probes": [
        {"glob": "package.json", "regex": "\"test[s]?\":", "bytes": 512}
      ],
      "test_frameworks": [
        {
          "name": "free-text (e.g., junit-xml-like, jest, text-block reporter)",
          "confidence": 0.0,
          "reason": "≤120 chars",
          "checks": [
            {"glob": "**/reports/**"},
            {"glob": "**/test-results/**"}
          ],
          "content_probes": [
            {"glob": "**/*.xml", "regex": "<test(case|suite)\\b", "bytes": 512}
          ],
          "report_hints": [
            {
              "label": "free-text (e.g., junit-xml, json-cases, text-block)",
              "confidence": 0.0,
              "globs": ["**/reports/**/*.xml","**/test-results/**/*.xml"],
              "parse_kind_hint": "xml|json|text|html|other",
              "record_locator_hint": "e.g., //testcase, $.tests[*], block: ^TEST..blank line"
            }
          ]
        }
      ]
    }
  ],
  "report_hints_global": [
    {
      "label": "json-cases",
      "confidence": 0.5,
      "globs": ["**/*report*/*.json","**/coverage/**/*.json"],
      "parse_kind_hint": "json",
      "record_locator_hint": "$..[?(@.name && @.status)]"
    }
  ],
  "assumptions": [
    "short free-text bullets explaining inferences"
  ],
  "notes": [
    "execution hints or caveats for next stages"
  ]
}
```

### 2. LLM‑Driven Ecosystem & Framework Discovery

- Feed the Directory Sketch to the LLM with an instruction like:

**Agent Instruction:**

> You are an ecosystem-agnostic build/test detective. Given only a directory sketch, infer:
>
> 1. Languages/ecosystems that may be present.
> 2. For each ecosystem, plausible testing frameworks.
> 3. For each, propose **toolable detection steps**:
>    - Glob/path checks we can run locally.
>    - Optional content probes (regex on first N bytes of files).
>    - Expected report/coverage globs to scan next.
> 4. Return strict JSON with ecosystems, frameworks, confidence scores, and detection plans.

- The output is a **Detection Plan**: structured, stack‑agnostic, and actionable locally.

### 3. Report & Test Case Discovery

- Run the Detection Plan locally:
  - Execute glob checks and probes.
  - Gather candidate report files.
- For each candidate, read head/tail snippets and ask LLM:
  - “Is this a test/coverage artifact? If yes, emit an **extractor spec**.”
- Extractor specs are minimal DSLs (XPath/JSONPath/regex/sections) that your pipeline applies deterministically.
- From these, produce **per-test records** in a universal ontology (id, name, group, status, duration, purpose, evidence, free-text framework/language guess).

### 4. Chunking & Embeddings

- Each per-test record becomes an embedding chunk:
  - Compact description string: `[artifact:<label>] group::<group> name::<name> status::<status> dur::<ms> purpose::<short>`
  - Pointer to evidence for deeper inspection.
- Store vectors in FAISS indexes, separated by artifact type (reports, test code, prod code if analyzed).
- Later agents use FAISS to quickly retrieve relevant tests/snippets instead of scanning everything again.

### 5. Integration into Pipeline

- **New first stage**: Directory Sketch → LLM Detection Plan → Local detection execution → Candidate reports.
- **Next**: Report Discovery agent uses extractor specs to parse reports into test case records.
- **Then**: Test Extraction/Analysis agents proceed with embeddings + FAISS retrieval to trace call chains and assess test quality.
- **Context assembly** remains: budget tokens, but depth prioritized (line-by-line reads, regex call chain tracing acceptable).

### 6. Role of FAISS

FAISS makes sense in this schema:

- After initial discovery, we will accumulate many per-test records and code snippets.
- Embedding + FAISS retrieval lets later agents retrieve only the most relevant slices (tests under discussion, code under test) rather than re-reading huge report/code files.
- Supports hybrid retrieval (vector + BM25) to balance keyword precision and semantic matching.

### Notes

1. Not too frugal with token budget, but must avoid loading entire repo blindly.
2. Acceptable to read test report line-by-line via LLM if that aids precision.
3. Regex + step-by-step file reading to follow call chains is acceptable if it increases clarity.
4. Goal is to mimic a human’s deep manual test review, not a quick heuristic scan.
5. Pipeline is meant to *replace* human test quality review, and long runtimes (hours) are acceptable since it’s scheduled (nightly/weekly).

