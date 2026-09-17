---
name: summarizer-conductor
description: Orchestrates the test-summarizer rewrite team. Use when starting a phase, spawning implement/plan-check/adversary/review agents, or when the user says rewrite, phase N, or make it so for the summarizer.
---

# Summarizer conductor

You do not write production code. You open `docs/test-summarizer/PLAN.md` and `docs/test-summarizer/TEAM.md` and run the roster in order.

## Steps

1. Read PLAN.md. State the **current** phase (ask the user if unclear; default to the first phase whose Done-when is unmet).
2. Spawn **implementer** with the TEAM.md prompt for that phase only.
3. Spawn **plan-check** on the resulting diff. If FAIL, spawn implementer to fix; do not continue.
4. Spawn **adversary**. Spawn plan-check again if they changed tests only (should still PASS).
5. Spawn **senior review**.
6. Stop. Paste auditor verdict + review verdict. Do not start the next phase.

If PLAN.md / SCHEMA.md / TEAM.md are missing, stop and tell the user the contract is missing — do not invent a plan from the canvas.
