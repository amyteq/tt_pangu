# M8.5 / pre-M9 hardening — Loop Prompts

_CI repair + engineering practice + GitHub Issues/PR/labels collaboration interface._
_For sequential autonomous execution on Arch Linux._
_Prerequisite: M8 exit criteria confirmed met (see `docs/milestones/m8/final-review.md`)._
_Reference (source of truth): `docs/milestones/m8_5/references.md` (2026-05-23)._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md` (sequencing, no real Kaggle/Anthropic, DB DSN + sandbox bypass, worktree commit/push/PR at milestone end, secret denylist)._

---

## M8.5 at a glance

M8.5 is a **pre-M9 hardening milestone**. Direct entry into M9 is blocked
because (a) CI is currently red and (b) GitHub Issues/PR/labels are not yet
wired as a shared human ↔ Claude Code collaboration interface. M9's live
Kaggle regression should not start until both are in place.

M8.5 splits into three Claude Code work orders, executed in strict order:

1. **M8.5-T001 — CI repair.** Restore the M8/M8.5 baseline by fixing the
   Python no-db + live-db pytest failures (`nbformat`, `PyYAML`, `requests`,
   `kca skill` not registered) and the UI job failure
   (`pnpm -C ui install --frozen-lockfile` → `ERROR packages field missing
   or empty`). No new product features, no M9 work.
2. **M8.5-T002 — Engineering practice + GitHub interface.** Integrate the
   reusable, project-appropriate parts of
   `temp/engineering_practice_summary.md` and
   `temp/engineering_practice_details.md` into the repo. Add labels, issue
   forms, PR template, Claude Code agents/skills for GitHub collaboration,
   and concise routing rules in `AGENTS.md` / `CLAUDE.md`. Adjust
   `.claude/settings.json` so SSH/`gh` works for branch push and PR
   creation, while keeping explicit secret reads blocked at the hook
   level (`.env*`, `kaggle.json`, `id_rsa`, `id_ed25519`, AWS/GCP creds).
3. **M8.5-T003 — M9 planning only.** After T001 and T002 are merged and CI
   is green, draft `docs/milestones/m9/loop-prompts.md` + supporting planning docs
   for the live Spaceship Titanic Kaggle regression workflow. **No M9
   implementation.**

**M8.5 is not M9.** Do not run real Kaggle submissions, kernel push,
dataset uploads, or model uploads. Do not change production Supabase.
(See `docs/milestone-loop-protocol.md` §2 for the canonical list.)

Database / sandbox details are in `docs/milestone-loop-protocol.md` §3.

---

## M8.5 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M8.5-T001 | CI repair — Python deps, `kca skill` registration, pnpm workspace fix | Prompt 1 |
| M8.5-T002 | Engineering practice + GitHub Issues/PR/labels interface + agents/skills | Prompt 2 |
| M8.5-T003 | M9 planning only — draft `docs/milestones/m9/loop-prompts.md`, no implementation | Prompt 3 |

---

## Loop Prompt 1 — M8.5-T001 CI repair

```
/goal Execute M8.5-T001 CI repair for kaggle-code-agent until all CI-equivalent local checks pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec (full acceptance criteria): docs/tasks/m8_5/M8.5-T001-ci-repair.md

Read also (background context):
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones/README.md
- docs/milestones/m8/final-review.md
- .github/workflows/test.yml
- temp/ui-build-lint.log
- temp/no-db-pytest.log
- temp/live-db-pytest.log
- pyproject.toml
- tools/kca/, tools/legacy/, tests/, ui/

Mission (full version in task spec):
Repair the current CI failures before any M9 planning. Do not add new
product features except what is necessary to restore the M8/M8.5 baseline.

Known failures from CI logs (see task spec for root-cause + fix list):
1. no-db / live-db pytest: missing nbformat, yaml, requests; `kca skill`
   subcommand not registered.
2. UI job: `pnpm -C ui install --frozen-lockfile` →
   `ERROR packages field missing or empty`.

Acceptance criteria + closeout format: see task spec.
```

---

## Loop Prompt 2 — M8.5-T002 engineering practice + GitHub interface

```
/goal Execute M8.5-T002 engineering practice and GitHub interface baseline until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec (full scope + acceptance criteria + label list + agent rules):
  docs/tasks/m8_5/M8.5-T002-engineering-practice-github-interface.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md, docs/milestones/README.md
- temp/engineering_practice_summary.md
- temp/engineering_practice_details.md
- .github/workflows/claude.yml, claude-code-review.yml, test.yml
- .claude/settings.json
- .claude/hooks/guard_tool.py
- existing .claude/agents/ and .claude/skills/ directories

Mission (full version in task spec):
Integrate the reusable and project-appropriate parts of the engineering
practice docs into this repo, and add a GitHub Issues/PR/labels interface
for human ↔ Claude Code collaboration. Adjust .claude/settings.json so
SSH/gh work for branch push and PR creation, while keeping explicit
secret reads blocked at the hook layer.

Override note: `gh label create/edit/delete`, `gh issue edit/comment`,
`gh pr edit/comment` against existing repo issues/PRs remain on ASK
even after milestone end, per protocol §5. New labels and the PR
created by THIS milestone are in scope.
```

---

## Loop Prompt 3 — M8.5-T003 M9 planning only

```
/goal Execute M8.5-T003 M9 planning only until docs/milestones/m9/loop-prompts.md and related planning docs are ready for human review, or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec (full scope + acceptance criteria): docs/tasks/m8_5/M8.5-T003-m9-planning-only.md

Override note: this is a planning-only task. At task end, Claude Code
MAY commit and push the planning docs and open a single PR with
`[planning]` in the title, but MUST NOT execute any M9 code yet.

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md, docs/milestones/README.md
- docs/milestones/m8/final-review.md
- docs/milestones/m8/handoff.md
- docs/engineering-practice.md (added by M8.5-T002)
- docs/github-collaboration.md (if added by M8.5-T002)
- .github/labels.yml, .github/ISSUE_TEMPLATE/
- latest docs/adr/
- tools/kca/, src/worker/, ui/

Mission (full version in task spec):
Plan M9 after CI is green and GitHub collaboration rules are in place.
Do not implement M9 code yet.

M9 baseline:
- M8 follow-up says first M9 task is live Kaggle regression test for
  Spaceship Titanic under approval.
- Current platform supports UI shell, worker, approval gates,
  research/browser workflow, model routing, and local Kaggle tooling.
- External side effects must require human approval.

Deliverables, M9 coverage topics, acceptance criteria, and closeout
format: see task spec.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
# DB DSN (M6/M7/M8-confirmed; refresh if the supabase-db container IP changed)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# UI tooling — install pnpm if not already present
corepack enable
corepack prepare pnpm@latest --activate

# Re-install Python deps (will pick up the new ones added by T001)
pip install -e ".[dev]"
```

### Settings additions for autonomous M8.5 loop

`.claude/settings.json` already covers most of the surface. T002 will:

- remove `~/.ssh` from sandbox `filesystem.denyRead` / `denyWrite`;
- keep `Read(~/.ssh/**)` blocked at the hook level (via
  `.claude/hooks/guard_tool.py`);
- keep `Bash(git push*)`, `Bash(gh pr create*)`, `Bash(gh pr merge*)`,
  `Bash(gh label create*)`, `Bash(gh label edit*)`,
  `Bash(gh label delete*)`, `Bash(gh issue edit*)`,
  `Bash(gh issue comment*)`, `Bash(gh pr comment*)`,
  `Bash(gh pr edit*)` on `ask`.

### Sandbox bypass

DB calls (`psql`, `pytest` against `SUPABASE_DB_URL`, any `kca` subcommand
that reaches Supabase) still need `dangerouslyDisableSandbox: true`
because the sandbox proxy excludes the local Docker bridge.

UI build/lint/test, GitHub `gh` reads, and Python tests do **not** need
sandbox bypass.

### Full autonomous run

Each Loop Prompt below assumes the shared rules in
`docs/milestone-loop-protocol.md` (sequencing, no real Kaggle/Anthropic,
DB DSN + sandbox bypass, worktree commit/push/PR at milestone end,
secret denylist).

Two reusable agents do the work; the loop prompt itself stays short.

| When | Invoke | Defined in |
|---|---|---|
| Running one Loop Prompt | `milestone-loop-runner` agent | `.claude/agents/milestone-loop-runner.md` |
| Milestone end (after every Loop Prompt PASSed) | `milestone-closeout` agent | `.claude/agents/milestone-closeout.md` |

The closeout agent in turn uses two skills:
`milestone-final-review` (writes `docs/milestones/m8_5/final-review.md`) and
`worktree-milestone-pr` (commit-per-Loop-Prompt + push + open PR per
protocol §5).

Recommended one-prompt-at-a-time invocation (T002 and T003 each get their
own worktree branched off the latest `main`):

```bash
# Inside a worktree branched off main, after M8.5-T001 is merged:
claude "Use the milestone-loop-runner agent to execute M8.5-T002 from docs/milestones/m8_5/loop-prompts.md. Assume M8.5-T001 is merged on main; do not re-run it."

# Inside a fresh worktree, after M8.5-T002 is merged:
claude "Use the milestone-loop-runner agent to execute M8.5-T003 from docs/milestones/m8_5/loop-prompts.md. Assume M8.5-T001 and M8.5-T002 are merged on main; do not re-run them."

# After every Loop Prompt for the milestone has PASSed (same worktree as the last runner):
claude "Use the milestone-closeout agent to finalize M8.5 — write docs/milestones/m8_5/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

Equivalent short form, if you'd rather drive Claude Code with `/goal`:

```bash
claude "/goal Execute M8.5 Loop Prompt 2 (delegate to milestone-loop-runner). Follow docs/milestone-loop-protocol.md."
```

If you prefer one-shot sequential execution (less recommended, since
T003 depends on artifacts created by T002):

```bash
claude "Use the milestone-loop-runner agent to execute M8.5-T001 then T002 then T003 from docs/milestones/m8_5/loop-prompts.md in sequence, then hand off to the milestone-closeout agent."
```

### Closeout

When M8.5-T001, M8.5-T002, and M8.5-T003 are all complete:

1. Update `PROJECT_STATE.md`, `README.md` (Current milestone), and `docs/milestones/README.md` to mark M8.5 done and generate a plan for M9.
2. Backfill `docs/milestones/m8_5/handoff.md` (mirror `docs/milestones/m8/handoff.md`).
3. Only after CI is green and M8.5 closeout is reviewed should M9 plan & implementation begin.
