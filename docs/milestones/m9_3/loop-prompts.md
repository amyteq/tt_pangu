# M9.3 — Loop Prompts

_Memory-promotion + design-archaeology skills (replaces the broader M9.1 hardening plan)._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M9 exit confirmed (`docs/milestones/m9/final-review.md` reports PASS) and PR #18 (M10 planning) merged on main._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md` (sequencing, no real Kaggle/Anthropic outside designated approval paths, DB DSN + sandbox bypass, worktree commit/push/PR at milestone end, secret denylist)._

---

## M9.3 at a glance

M9.3 hardens two specific gaps that surfaced during M7–M9:

1. **Hidden-requirement loss in legacy migrations** — the earlier
   take-over of `tools/legacy/kkr.py` / `kkr.yaml` missed multi-Kaggle-
   account / multi-owner env mapping. M9.3 ships a `design-archaeology`
   skill so any future legacy migration starts with a structured
   10-section report whose §3 / §7 *cannot* miss multi-account
   behaviour.
2. **Silent / unaudited memory updates** — decisions made in GitHub
   issue/PR/review comments and meeting notes are promoted to canonical
   memory inconsistently. M9.3 ships a `memory-promotion` skill that
   distils evidence into propose-only patches against the four
   canonical memory files (`PROJECT_STATE.md`, `docs/milestones/README.md`,
   `docs/milestones/*/handoff.md`, `docs/adr/`). Human gate is load-bearing.

M9.3 **replaces** the unbuilt `docs/milestones/m9_1/loop-prompts.md` entirely;
the residual M9.1 scope (session-closeout skill, channels bridge,
agent-pack migration, bespoke agents) is deferred to a later milestone
(provisionally M9.4 — not scheduled by this doc). T003 retires the
M9.1 file with a retirement notice listing the deferred scope.

Direct entry into M9.3 is blocked until **all** are true:

- M9 is merged on main (`docs/milestones/m9/final-review.md` reports PASS).
- PR #18 (M10 planning) is merged on main — it is the canonical
  evidence source for T003's memory-promotion dogfood.
- `docs/milestone-loop-protocol.md` is current (no pending revisions).

### What's in scope

| Capability | Owned by | M9.3 touches |
|---|---|---|
| `design-archaeology` skill (10-section template + Must/Must-not rules) | `.claude/skills/design-archaeology/` | T001 |
| `memory-promotion` skill (4-phase workflow, propose-only) | `.claude/skills/memory-promotion/` | T002 |
| Canonical-memory model | `docs/adr/0015-memory-promotion-model.md` | T002 |
| Memory-promotion data flow | `docs/architecture/memory-promotion.md` | T002 |
| Proposals staging directory | `docs/proposals/` + README + .gitkeep | T002 |
| Real archaeology of legacy CLI | `docs/archaeology/kkr.md` | T003 |
| Real memory-promotion proposal | `docs/proposals/memory-2026-05-26-m10-pr18.md` | T003 |
| Design-archaeology architecture doc | `docs/architecture/design-archaeology.md` | T003 |
| M9.1 retirement | `docs/milestones/m9_1/loop-prompts.md` (body rewrite) | T003 |
| Milestone close (state / handoff / final-review) | `docs/milestones/README.md`, `PROJECT_STATE.md`, `README.md`, `docs/milestones/m9_3/final-review.md`, `docs/milestones/m9_3/handoff.md` | T003 + `worktree-milestone-pr` |

### What's NOT in scope

- Session-transcript mirroring / `session-closeout` skill.
- `scripts/claude_export_session.py`.
- GitHub webhook / Claude Code Channels bridge (research-preview only).
- Agent-pack migration packaging (`kca-agent-pack`).
- Bespoke agents: `requirements-skeptic`, `legacy-archaeologist`,
  `design-red-team`, `github-decision-extractor`. The two new
  *skills* are sufficient for M9.3; agents that wrap them can wait
  for M9.4+.
- Any edit to `.claude/hooks/audit_event.py`, `.claude/hooks/guard_tool.py`,
  or `.claude/settings.json`.
- Any edit to `tools/legacy/kkr.py` or `kkr.yaml` (archaeology is
  read-only).
- Any new `kca` CLI subcommand.
- Auto-applying memory patches. T003's milestone-close edits to
  `PROJECT_STATE.md` / `docs/milestones/README.md` / `README.md` happen via
  the propose-only pathway but are explicitly authorised as the one
  closeout edit; all other canonical-memory edits remain gated on
  a human approving a proposal in `docs/proposals/`.

DB / sandbox details: see `docs/milestone-loop-protocol.md` §3 — the
local `supabase-db` container
(`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`) needs
`dangerouslyDisableSandbox=true`. M9.3 does not write to Supabase,
but baseline pytest may.

---

## M9.3 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M9.3-T001 | Ship `.claude/skills/design-archaeology/SKILL.md` (10-section template, Must/Must-not rules) | Prompt 1 |
| M9.3-T002 | Ship `.claude/skills/memory-promotion/SKILL.md` + ADR 0015 + `docs/architecture/memory-promotion.md` + `docs/proposals/` staging | Prompt 2 |
| M9.3-T003 | Dogfood: `docs/archaeology/kkr.md` (kkr.py / kkr.yaml) + `docs/proposals/memory-2026-05-26-m10-pr18.md` (PR #18) + `docs/architecture/design-archaeology.md`; retire `docs/milestones/m9_1/loop-prompts.md`; write final-review + handoff | Prompt 3 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m9_3/M9.3-T00N-*.md` spec.

---

## Loop Prompt 1 — M9.3-T001 design-archaeology skill

```
/goal Execute M9.3-T001 design-archaeology skill until acceptance criteria pass or stop after 40 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_3/M9.3-T001-design-archaeology-skill.md

Read also (background context):
- PROJECT_STATE.md, AGENTS.md, CLAUDE.md
- docs/milestones/m9_3/loop-prompts.md
- docs/meeting-notes/2026-05-24-r3.md §6
- docs/meeting-notes/2026-05-24-r2.md, 2026-05-25-r1.md
- .claude/skills/inventory-drift-audit/SKILL.md (pattern)
- .claude/skills/research-brief/SKILL.md (pattern)
- .claude/skills/github-issue-triage/SKILL.md (frontmatter + rule style)

Mission (full version in task spec):
Ship .claude/skills/design-archaeology/SKILL.md with all 10 numbered
section headings, ≥ 5 Must/Must-not rules, a worked-example pointer
to docs/archaeology/kkr.md (produced in T003), and YAML frontmatter
that parses. Body ≤ 200 lines. Diff scope: ONLY
.claude/skills/design-archaeology/. Do not touch tools/legacy/**,
hooks, or other skills.
```

---

## Loop Prompt 2 — M9.3-T002 memory-promotion skill + ADR 0015 + architecture

```
/goal Execute M9.3-T002 memory-promotion skill + ADR 0015 + architecture doc until acceptance criteria pass or stop after 50 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_3/M9.3-T002-memory-promotion-skill.md

Read also (background context):
- M9.3-T001 closeout
- PROJECT_STATE.md (section layout — the skill targets it)
- docs/milestones/README.md, docs/milestones/m9/handoff.md, docs/milestones/m8_5/handoff.md
- docs/adr/0014-ui-stack.md (latest ADR — numbering precedent)
- .claude/skills/github-issue-triage/SKILL.md + .claude/agents/github-issue-triage.md
- .claude/skills/inventory-drift-audit/SKILL.md, .claude/skills/pr-closeout-review/SKILL.md
- .github/labels.yml (ai:* and decision:* taxonomy)
- docs/meeting-notes/2026-05-24-r3.md §3
- memory/MEMORY.md (call out the boundary — NOT canonical memory)

Mission (full version in task spec):
Ship .claude/skills/memory-promotion/SKILL.md with all 4 phases and
≥ 6 Must/Must-not rules. Write docs/adr/0015-memory-promotion-model.md
naming the four canonical files. Write docs/architecture/memory-promotion.md
with ASCII data-flow diagram. Create docs/proposals/ staging
(README + .gitkeep). Do NOT edit any canonical memory file (that is
T003's milestone-close job). Diff scope: ONLY the four new paths.
```

---

## Loop Prompt 3 — M9.3-T003 dogfood + M9.1 retirement + milestone close

```
/goal Execute M9.3-T003 dogfood (kkr.py archaeology + PR #18 memory-promotion + M9.1 retirement + milestone close) until acceptance criteria pass or stop after 80 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_3/M9.3-T003-dogfood-kkr-and-recent-pr.md

Read also (background context):
- M9.3-T001, M9.3-T002 closeouts
- .claude/skills/design-archaeology/SKILL.md
- .claude/skills/memory-promotion/SKILL.md
- docs/adr/0015-memory-promotion-model.md, docs/architecture/memory-promotion.md
- tools/legacy/kkr.py (full file — argparse, RunManifest, _load_env_for_owner ~528–548, subcommands ~2193–2289)
- tools/legacy/kkr.yaml (full file — _base, _envs, owners harrysun2006 / firefly2006, blocks a09h..d09m)
- docs/milestones/m10/loop-prompts.md (what PR #18 landed)
- gh pr view 18 --json title,body,reviews,commits,labels
- gh api repos/<owner>/<repo>/issues/18/comments
- gh api repos/<owner>/<repo>/pulls/18/comments
- docs/milestones/m9_1/loop-prompts.md (to retire)
- `milestone-final-review` skill (for docs/milestones/m9_3/final-review.md)
- `worktree-milestone-pr` skill (for milestone close)

Mission (full version in task spec):
Produce docs/archaeology/kkr.md (≤ 250 lines, all 10 sections, must
cite harrysun2006 / firefly2006 / multi-account in §3 and §7).
Produce docs/proposals/memory-2026-05-26-m10-pr18.md (≤ 200 lines,
extraction matrix + ≥ 1 proposed patch + unchecked approval
checkbox). Write docs/architecture/design-archaeology.md (≤ 100
lines, cross-links kkr.md). Retire docs/milestones/m9_1/loop-prompts.md (body
≤ 30 lines, retirement notice + deferred-scope list). Insert M9.3
row in docs/milestones/README.md; append M9.3 to PROJECT_STATE.md Completed
milestones (only if T001 + T002 PASS); reflect M9.3 in README.md.
Write docs/milestones/m9_3/final-review.md (mirror M9 / M8.5 layout) and
docs/milestones/m9_3/handoff.md (mirror M9 handoff). Hand off to
`worktree-milestone-pr` for commit/push/PR.

Override note: this is the only Loop Prompt in M9.3 that calls
`milestone-final-review` and (via session handoff) `worktree-milestone-pr`.
```

---

## GitHub issue / label workflow for M9.3

Each M9.3 task is filed as a GitHub issue using the `feature-work.yml`
form, labelled per task type:

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M9.3-T001 | `type:feature`, `ai:triage`, `area:agents` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M9.3-T002 | `type:feature`, `ai:triage`, `area:agents`, `area:docs` | `ai:ready` | `ai:implementing` → close |
| M9.3-T003 | `type:feature`, `ai:triage`, `area:docs`, `area:agents` | `ai:ready` after T001 + T002 closed | `ai:implementing` → close |

No task in M9.3 is `policy:approval-required` — there are no live
Kaggle / GitHub-write side effects. The PR for the milestone uses
`.github/pull_request_template.md`; the "Remote side effects" section
should report "Reads only (gh pr view 18, gh api comments)."

---

## Required tests / evidence

- `python -m pytest tests/ services/decision_api/tests -v` — 0 failures
  (no behavior change expected in M9.3).
- `ruff check .` and `ruff format --check .` — clean.
- `pnpm -C ui install --frozen-lockfile`, `pnpm -C ui lint`,
  `pnpm -C ui typecheck`, `pnpm -C ui build`, `pnpm -C ui run test --run`
  — all clean (M9.3 makes no UI changes).
- Skill frontmatter parses for both new skills:
  `python -c "import yaml,pathlib; [yaml.safe_load(p.read_text().split('---')[1]) for p in pathlib.Path('.claude/skills').glob('*/SKILL.md')]"`.
- `grep -n "harrysun2006\|firefly2006\|multi.*account\|multi.*owner" docs/archaeology/kkr.md`
  returns hits in §3 and §7 — the "skill actually catches the known-
  missed requirement" gate.
- `docs/proposals/memory-2026-05-26-m10-pr18.md` exists and contains
  both `confirmed_design_decisions:` and `open_questions:` keys with
  ≥ 1 entry each.
- `docs/milestones/m9_1/loop-prompts.md` body ≤ 30 lines and references
  `docs/milestones/m9_3/loop-prompts.md`.
- `docs/milestones/m9_3/final-review.md` exists and follows the M9 / M8.5 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any
of these is true:

- The `design-archaeology` skill body grows past 200 lines or the
  `memory-promotion` skill body grows past 200 lines. Prune; do not
  expand.
- T003's archaeology report fails to surface `harrysun2006` /
  `firefly2006` / multi-account behaviour. This is the "did the new
  skill catch the thing earlier passes missed" check — a miss means
  T001 also needs revision.
- The memory-promotion proposal in T003 accidentally edits a canonical
  file directly instead of writing to `docs/proposals/`. Revert and
  re-run.
- Any test in the validation suite regresses from green to red.
- The PR body fails the `pr-closeout-review` checklist (tests, docs,
  evidence, remote side effects).

If M9.3 surfaces a need for a brand-new ADR beyond 0015 (e.g. on
session-transcript redaction, or on the channels bridge), **pause and
ask** — those are M9.4+ decisions, not M9.3 expansion. Open an ADR
draft in `docs/adr/` and stop the milestone there.

---

## Running on Arch Linux

```bash
# DB DSN (refresh container IP if `docker compose up` has rotated it)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local

# No Kaggle credentials needed for M9.3 (no Kaggle calls).

# Per-prompt invocation:
claude "Use the milestone-loop-runner agent to execute M9.3-T001 from docs/milestones/m9_3/loop-prompts.md."
# ...repeat for M9.3-T002, M9.3-T003.

# Milestone close (T003 already calls milestone-final-review internally;
# this command hands off to worktree-milestone-pr):
claude "Use the milestone-closeout agent to finalize M9.3 — verify docs/milestones/m9_3/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

`gh pr view 18` and `gh api .../comments` (READ-ONLY) need network out
to `api.github.com`. No `dangerouslyDisableSandbox` needed for M9.3
unless baseline pytest touches the local Supabase container (same as
prior milestones).

---

## Human decisions needed before starting M9.3

These decisions block M9.3-T001 / T003 specifically. Each should be
recorded as a `type:decision` issue with `decision:confirmed` BEFORE
the corresponding task is promoted to `ai:ready`:

1. **Canonical memory file list.** Confirm the four files named in
   ADR 0015 (`PROJECT_STATE.md`, `docs/milestones/README.md`,
   `docs/milestones/m{N}/handoff.md`, `docs/adr/NNNN-*.md`) are the
   complete set. If `README.md` or `AGENTS.md` should also be
   canonical, decide now — M9.3 ships with the four-file list and
   would need re-scoping otherwise.
2. **PR #18 as the memory-promotion dogfood input.** Confirm PR #18
   (M10 planning) is the right input. Alternatives: PR #10 (M9
   live regression) or PR #19 (CI repair). T003 assumes #18.
3. **Multi-account quota pooling — open question, not a decision.**
   The kkr.py archaeology in T003 will surface "should KCA M10+
   re-introduce multi-account quota pooling" as an explicit §8 open
   question. Do **not** decide this in M9.3; it is the *output* of
   the skill, not an input.
4. **M9.4 placeholder.** Confirm that the M9.1 retirement notice in
   T003 can point to a tentative M9.4 for the deferred residual
   scope (session-closeout, channels, agent-pack, bespoke agents),
   without committing to scheduling.
