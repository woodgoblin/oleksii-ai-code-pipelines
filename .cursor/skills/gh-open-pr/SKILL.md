---
name: gh-open-pr
description: Opens a pull request against main with gh after an explicit auth check. Use when the user asks for a PR on main, to merge via pull request, or to publish a branch for review.
---

# Open a PR on main

Depends on skill `gh-github`. If that auth gate fails, stop. Do not create the PR locally-only and pretend it was filed.

## Steps

1. Follow `gh-github`: `gh auth status` must succeed. If not, ask the user to authorize and wait.
2. `git status`, `git diff`, `git log` / `git diff main...HEAD` as in the repo’s PR rules.
3. Commit only if the user asked for a commit or a PR that requires one. No secrets.
4. Push: `git push -u origin HEAD` (after auth).
5. Create the PR:

```bash
gh pr create --base main --title "title" --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...

EOF
)"
```

6. Return the PR URL. If `gh pr create` fails for auth, stop and ask to authorize again — do not assume access was denied forever.

Do not file a PR against a fork or a different base unless the user said so.
