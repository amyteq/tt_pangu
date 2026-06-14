## Summary

- Dev-phase policy update: non-destructive GitHub writes auto-allow; permanent-deletion remote writes denied at the hook level; agent may read project dotenv files and ~/.kaggle/kaggle.json (SSH / AWS / gcloud / gh OAuth token / ./secrets/ remain off-limits).
- Three coordinated edits keep policy doc + harness settings + PreToolUse hook in sync.
- Behavior change for me: stop passing `--delete-branch` to `gh pr merge` (remote branches preserved); local worktree still cleaned up.

Closes # <!-- none — direct user request 2026-05-24 -->

## Tests run

- [x] `python -m json.tool .claude/settings.json` → valid JSON
- [x] `ruff check .claude/hooks/guard_tool.py` → All checks passed!
- [x] Guard-hook smoke tests (synthetic PreToolUse payloads piped through the worktree copy):
  - Read of project dotenv → pass (no decision)
  - Read of ~/.kaggle/kaggle.json → pass
  - Read of ~/.ssh/id_rsa → deny (Protected path)
  - Bash `gh issue delete 99` → deny (permanent GitHub deletion)
  - Bash `git push origin --delete some-branch` → deny (preserve branch history)
  - Bash `gh pr merge 19 --squash` → pass

## Docs / inventory impact

- [x] CLAUDE.md updated: operating principle #8 (secrets) and GitHub-collaboration section
- [x] No PROJECT_STATE.md / docs/milestones/README.md change (policy doc only)

## Evidence

- One file changed each: `.claude/settings.json` (allow / ask / deny lists), `.claude/hooks/guard_tool.py` (`path_is_protected` + `bash_decision`), `CLAUDE.md` (principle #8 + GitHub section).
- Memory: `feedback_permissive_github_dev_phase.md` written into the per-project memory index, with cross-links to the older `feedback_direct_edits` and `feedback_env_shadow_kaggle_ac` (both partially superseded).

## Schema / RLS / secrets impact

- [x] No DB migration
- [x] No new secret read / write surface — the change **narrows** what counts as a secret to-the-agent (drops dotenv + kaggle creds from the protected set during dev), but still denies SSH / AWS / gcloud / gh OAuth token / generic `./secrets/`.
- [x] `area:security` is appropriate; reviewer should sanity-check the path-protection regex and the new `gh <noun> delete` deny pattern.

## Remote side effects

- [x] None — local-only policy change. The new policy will affect *future* runs (auto-allowing merges, denying deletions); this PR itself doesn't fire any of those.

## Risks and follow-ups

- The hook regex assumes `gh <noun> delete` is the only verb spelling for permanent deletion. If `gh` adds e.g. `gh issue remove` later, the deny would not catch it; revisit if `gh` syntax evolves.
- Sandbox-level (not project-permission-level) reads of dotenv still go through `/dev/null` per [[feedback_env_shadow_kaggle_ac]] in some commands — that's a separate harness-level concern. Use the Read tool (which is the path this change actually opens), and `dangerouslyDisableSandbox: true` for the few subprocess paths that still hit the bind-mount shadow.
- A future hardening pass could add a periodic drift check that the three files (`settings.json`, `guard_tool.py`, `CLAUDE.md`) stay in lockstep.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
