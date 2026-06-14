# M9.2 → M10 Handoff Prompt

_Generated 2026-05-26 from `docs/milestones/m9_2/final-review.md` and
`docs/milestones/README.md` § M10._

Paste this into a fresh session that is starting **M10
(notebook-submission regression — Petals to the Metal)**. M9.2 was a
short, parallel operator-tooling track and did not displace M10; M10
remains the next executable Kaggle milestone.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M9 are complete; M9.2 (operator-tooling) ✓ done.** Your job is to
start **M10** (notebook-submission regression on Petals to the Metal,
`tpu-getting-started`) per `docs/milestones/m10/loop-prompts.md`.

M9.2 shipped a `/save-log <name|id>` Claude Code project skill that
exports stopped/completed background-session transcripts to
`logs/<name>.md` via `claude-code-log` (`uvx`). The skill is
operator-only (`disable-model-invocation: true`) and refuses to write
when any of ten secret-like patterns appear in the rendered output.
This is your tool for producing milestone-handoff artifacts going
forward — run `/save-log <session-name>` at the end of an M10 task to
capture the transcript before opening the milestone PR.

## Read these files first

1. `PROJECT_STATE.md` — current state at M9.2 exit.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions (especially the
   dev-phase secret carve-out; note that the `save-log` script does
   NOT use the carve-out).
4. `docs/milestones/README.md` — M10 section + the new M9.2 entry.
5. `docs/milestones/m9/final-review.md` — M9 ship summary + the five
   cross-cutting follow-ups (A–E) that landed as issues.
6. `docs/milestones/m9_2/final-review.md` — what landed in M9.2 (26-check
   matrix) including the `logs/` `.gitignore` carve-out and
   the secret-pattern refusal design.
7. `docs/milestones/m10/loop-prompts.md` — M10's full Loop Prompt set
   (T000–T008).
8. `docs/milestone-loop-protocol.md` — per-milestone worktree rules,
   secret denylist, sequencing rules.
9. `.claude/skills/save-log/SKILL.md` — the new skill (so you know
   how to invoke it).
10. `scripts/save_claude_session_log.py` — the backing implementation
    (relevant if you need to debug a `/save-log` invocation during
    M10 closeout).

## State at handoff

- M0–M9 done. M9.2 done. M10 is the next active milestone.
- The dev-phase secret carve-out (CLAUDE.md, 2026-05-24) is active.
  Non-destructive `gh` writes auto-allow; permanent deletions deny.
  Squash-merge defaults: drop `--delete-branch` so the GitHub branch
  remains for audit.
- `logs/` is now a tracked directory (post-M9.2). The existing
  `**/logs/*` rule is preserved; M9.2 added a `!logs/` +
  `!logs/**` carve-out after it.
- `claude-code-log v1.3.0` is the version `uvx` resolved at M9.2
  smoke time. The script doesn't pin a version; `uvx` picks the
  latest on each run.
- Active worktrees on disk (per `git worktree list` at M9.2 close):
  `docs-arch-github-session`, `m9_3-planning`, `m9_4-planning`. None
  block M10.

## Current task

Start M10. The full Loop Prompt set is in `docs/milestones/m10/loop-prompts.md`;
T000 (Kaggle credentials + competition registration for
`tpu-getting-started`) is the entry point. Hard pre-req for M10-T007:
issue #11 (dotenv-leak / Kaggle leaderboard pollution) must be merged
on main first. T000–T006 may proceed in parallel with #11 work.

When you finish M10, you can use `/save-log <session-name>` to capture
the M10 transcript before opening the milestone PR — see
`docs/milestones/m9_2/final-review.md` for the smoke evidence that the skill
works end-to-end.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs (especially the single approved real
  `kca kaggle push` in M10-T004).
- Patch or implementation.
- Suggested tests.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets. `save_claude_session_log.py` is the
  enforcement point for transcripts; humans review per-export before
  committing.
- Never submit to Kaggle, push kernels, or upload datasets without
  explicit human approval (M10-T004 is the only approved real push).
- Keep CTF work inside explicitly authorized local/sandbox challenge
  environments (M11 scope).
