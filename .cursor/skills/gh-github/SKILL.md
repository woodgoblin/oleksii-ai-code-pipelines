---
name: gh-github
description: Uses the GitHub CLI (gh) for PRs, issues, checks, and releases. Use when creating or updating pull requests, inspecting GitHub, or when git push/gh needs authorization. Enforces an auth gate — never assume GitHub access.
---

# GitHub via `gh`

Use `gh` for all GitHub manipulation (PRs, issues, checks, releases, repo metadata). Do not use the raw REST API, `hub`, or invented tokens.

## Auth gate (mandatory, before any `gh` write or `git push`)

Run:

```bash
gh auth status
```

**Logged in:** continue with the requested `gh`/`git push` work.

**Not logged in / not authorized:**

1. Tell the user GitHub CLI is not authorized.
2. Ask them to authorize. Do **not** proceed. Do **not** assume they will refuse. Do **not** assume they already granted access.
3. Offer, and wait:
   - `gh auth login` (user completes the browser/device flow), and/or
   - Cursor GitHub connect (`ConnectScm`) if the host supports it.
4. Re-run `gh auth status`. Only if it succeeds may you push or call `gh pr create`.
5. If they have not confirmed authorization in this turn, **stop** and wait for the next message.

Never print tokens, PATs, or cookie values. Never ask the user to paste a PAT into chat.

## After auth

- PRs: `gh pr create` (HEREDOC body). Target `main` unless the user named another base.
- Prefer `gh` over opening github.com URLs in a browser for write actions.
- `git push -u origin HEAD` only after the auth gate passes.
- Do not `--force` to `main`/`master`. Do not skip git hooks.

## Examples

```bash
gh auth status
gh pr view --json url,title
gh pr create --base main --title "..." --body "$(cat <<'EOF'
...
EOF
)"
```
