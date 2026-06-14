# M9.2 — Loop Prompts

_`/save-log` skill: export a stopped or completed Claude Code background
session transcript to `docs/logs/<session-name>.md` via `claude-code-log`._
_For sequential, partly autonomous execution on Arch Linux._
_Prerequisite: M9 merged on main (see `docs/milestones/m9/final-review.md`)._
_Shared rules: every Loop Prompt below MUST follow `docs/milestone-loop-protocol.md`
(sequencing, no real Kaggle/Anthropic outside designated approval paths,
DB DSN + sandbox bypass where it applies, **per-milestone worktree by
default**, secret denylist)._

---

## M9.2 at a glance

M9.2 is a **focused operator-tooling milestone**, not a Kaggle regression.
It adds a `/save-log <name|id>` slash command (Claude Code project skill)
that exports a stopped or completed background-session transcript to
`docs/logs/<session-name>.md` via the `claude-code-log` package (run
through `uvx`). The motivation is recorded in
`docs/meeting-notes/2026-05-26-r1.md`: `claude logs <session-id>` only
emits terminal output with ANSI cursor/control sequences; clean Markdown
for handoff packs must come from the transcript JSONL under
`~/.claude/projects/`.

M9.2 sits **between M9 (done) and M10 (in planning)**. It does not
renumber anything downstream. M10 remains the next executable Kaggle
milestone.

Direct entry into M9.2 is blocked until **all** are true:

- M9 is merged on main (`docs/milestones/m9/final-review.md` exists and reports PASS).
- The dev box has `uvx` available on `PATH` (`uvx --version` exits 0).
- `claude agents --json` lists at least one session belonging to this
  repository (used by M9.2-T001 as the smoke target).

### What's in scope

| Capability | Owned by | M9.2 touches |
|---|---|---|
| Skill discovery + invocation | `.claude/skills/save-log/SKILL.md` | T000 — new skill, `disable-model-invocation: true` |
| Session selector + transcript locator | `scripts/save_claude_session_log.py` | T000 — name / short job id / session id matching with longest-prefix scoring |
| Terminal-state gate | same script | T000 — refuses to export non-`stopped`/`completed` sessions unless `--allow-any-state` |
| Clean Markdown export | `uvx claude-code-log@latest … --detail low --format md --compact` | T000 — script wraps the CLI |
| Secret-pattern scan | same script | T000 — nine patterns from meeting notes §3 |
| Atomic overwrite | same script | T000 — write `.tmp.md` → `replace` |
| Smoke verification | T001 — exercise a real stopped/completed session + 3 negative paths | |
| Final review + PR | `milestone-final-review` skill + `worktree-milestone-pr` skill | T002 |

### What's NOT in scope

- Schema changes (no migration; `docs/logs/<name>.md` files do not get a
  `submissions` / `agent_run_artifacts` row in M9.2).
- Network side effects beyond `uvx` fetching `claude-code-log` from PyPI
  on first use.
- A `.claude/commands/save-log.md` fallback — skills override commands of
  the same name, so a duplicate would just be ambiguity.
- Automatic git commit of `docs/logs/*.md`. Humans review each export
  and commit by hand. `docs/logs/` is **not** gitignored — see T001.
- A model-invokable variant of the skill. `disable-model-invocation: true`
  is load-bearing — only a human typing `/save-log` may trigger it.
- A `claude logs` ANSI-strip fallback. The script fails loudly if the
  transcript JSONL cannot be located.
- CI coverage. The skill is operator-local; no new CI job is created.
- Reading `.env`, `~/.kaggle/kaggle.json`, `~/.ssh`, `~/.aws`,
  `~/.config/gcloud`, `~/.config/gh`, or anything else outside
  `~/.claude/projects/` and `~/.claude/jobs/`. The dev-phase secret
  carve-out in CLAUDE.md (and `feedback_permissive_github_dev_phase`
  memory) does **not** apply here — this script has no need to read
  credentials.

DB / sandbox details: M9.2 does not require Supabase or a sandbox bypass.
The script makes no network call other than what `uvx` itself does to
install `claude-code-log` from PyPI on first use; PyPI is on the sandbox
allowlist, so no `dangerouslyDisableSandbox` should be needed.

---

## M9.2 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M9.2-T000 | Skill + script scaffold; full implementation per meeting-notes §3; `--help` parses; `ruff` clean | Prompt 0 |
| M9.2-T001 | Smoke against a real stopped/completed session + 3 negative paths; `docs/logs/` left un-gitignored | Prompt 1 |
| M9.2-T002 | `docs/milestones/m9_2/final-review.md`; update milestones / PROJECT_STATE / README; handoff; worktree PR | Prompt 2 |

Each task's full scope, acceptance criteria, allowed/forbidden paths, and
closeout format live in the matching `docs/tasks/m9_2/M9_2-T00N-*.md` spec.

---

## Loop Prompt 0 — M9.2-T000 Skill scaffold + script implementation

```
/goal Execute M9.2-T000 /save-log skill scaffold + script implementation until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_2/M9_2-T000-save-log-scaffold-and-impl.md

Read also (background context):
- docs/meeting-notes/2026-05-26-r1.md (the canonical spec — §2 for SKILL.md, §3 for the Python script)
- docs/milestones/README.md §M9.2
- CLAUDE.md (dev-phase secret carve-out — note it does NOT apply to this script)
- .claude/skills/worktree-milestone-pr/SKILL.md (skill frontmatter precedent)
- .claude/skills/kg-nb/SKILL.md (another skill precedent)
- scripts/README.md (script directory conventions)

Mission (full version in task spec):
Create .claude/skills/save-log/SKILL.md, scripts/save_claude_session_log.py,
and docs/logs/.gitkeep. Implement the Python script verbatim from the
meeting-notes §3 reference, honouring the read-list restrictions (only
~/.claude/projects/ and ~/.claude/jobs/). Confirm `python
scripts/save_claude_session_log.py --help` parses, `ruff check
scripts/save_claude_session_log.py` is clean, and `uvx --version` +
`uvx claude-code-log@latest --help` are reachable. Do NOT run a real
export against a session in this Loop Prompt — that is T001's job.
```

---

## Loop Prompt 1 — M9.2-T001 Smoke verification + doc note

```
/goal Execute M9.2-T001 /save-log smoke + negative paths until acceptance criteria pass or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_2/M9_2-T001-save-log-smoke-and-docs.md

Read also (background context):
- M9.2-T000 closeout
- docs/meeting-notes/2026-05-26-r1.md §5 (validation flow)
- README.md (where the new /save-log line goes)
- .gitignore (verify docs/logs/ is NOT ignored)

Mission (full version in task spec):
Find a real stopped/completed background session via
`claude agents --json`. Run `python
scripts/save_claude_session_log.py <name-or-id>` end-to-end. Confirm
the output file exists at docs/logs/<name>.md, contains the header
block, and the secret scanner did not trip on the real transcript.
Then exercise three negative paths: (a) a running session is refused;
(b) an ambiguous fuzzy selector is refused with the candidate list;
(c) a synthetic transcript containing `sk-ant-...` triggers the
secret-pattern refusal unless `--allow-secret-like`. Add a brief
`/save-log` mention to README.md. Verify `docs/logs/` stays
un-gitignored.
```

---

## Loop Prompt 2 — M9.2-T002 Exit criteria + final review

```
/goal Execute M9.2-T002 M9.2 exit criteria validation + final review until docs/milestones/m9_2/final-review.md PASSes or stop after 60 turns and summarize blockers.

Follow: docs/milestone-loop-protocol.md
Task spec: docs/tasks/m9_2/M9_2-T002-m9_2-exit-criteria.md

Read also (background context):
- all M9.2 closeouts (T000, T001)
- docs/milestones/m9/final-review.md (layout precedent)
- docs/milestones/m8_5/final-review.md (planning-milestone layout precedent)
- `milestone-final-review` skill
- `worktree-milestone-pr` skill

Mission (full version in task spec):
Run the milestone validation matrix, then call milestone-final-review
to write docs/milestones/m9_2/final-review.md mirroring the M9 / M8.5 layout.
Update docs/milestones/README.md (mark M9.2 done), PROJECT_STATE.md (set
current milestone to M10 again with M9.2 marked complete), and
README.md (current-milestone block). Write docs/milestones/m9_2/handoff.md.
After final review is written, call worktree-milestone-pr to commit
per-Loop-Prompt, push the worktree branch, and open the M9.2 PR
against main.

Override note: this is the only Loop Prompt in M9.2 that calls
worktree-milestone-pr.
```

---

## GitHub issue / label workflow for M9.2

Each M9.2 task is filed as a GitHub issue using the `feature-work.yml`
form, labelled per task type.

| Task | Issue labels at file time | Labels added by triage | Labels at merge |
|---|---|---|---|
| M9.2-T000 | `type:feature`, `ai:triage`, `area:tooling`, `area:claude-code` | `ai:ready` (after AC + owner) | `ai:implementing` → close |
| M9.2-T001 | `type:test-gap`, `ai:triage`, `area:tooling` | `ai:ready` | `ai:implementing` → close |
| M9.2-T002 | `type:feature`, `ai:triage`, `area:release`, `area:docs` | `ai:ready` after T000–T001 closed | `ai:implementing` → close |

No task in M9.2 carries `policy:approval-required` — there are no
remote-write side effects to gate. The PR for each task uses
`.github/pull_request_template.md`; the "Remote side effects" box stays
unchecked for all three.

---

## Approval gates (summary)

| Gate | When it fires | Where the approval is recorded | Who can approve |
|---|---|---|---|
| `kaggle_submit` | Not used in M9.2 | n/a | n/a |
| `kernel_push` | Not used in M9.2 | n/a | n/a |
| `dataset_upload` | Not used in M9.2 | n/a | n/a |
| `model_upload` | Not used in M9.2 | n/a | n/a |
| `external_fetch` | Triggered indirectly by `uvx` pulling `claude-code-log` from PyPI on first use | Sandbox allowlist already covers `pypi.org` and `files.pythonhosted.org`; no new approval required | n/a |

M9.2 has no per-task approval gate. The only gates that apply are the
generic protocol §5 rules (no force-push, no `gh pr merge`, no push to
`main` directly, no edits to non-M9.2 issues).

---

## Required tests / evidence

- `python scripts/save_claude_session_log.py --help` exits 0 and prints
  the four flags (`--allow-any-state`, `--allow-secret-like`,
  `--detail`, `--output-dir`).
- `ruff check scripts/save_claude_session_log.py` clean.
- `ruff format --check scripts/save_claude_session_log.py` clean.
- `python -m pytest tests/` — 0 new failures (no new tests are required;
  M9.2 is operator tooling).
- A real `docs/logs/<name>.md` written in T001 contains the header
  block (`Session name`, `Job id`, `Session id`, `Status`, `Source
  transcript`, `Output`, `Exported at`) and the `claude-code-log
  --detail low --format md --compact` body.
- The three negative paths (running session, ambiguous selector,
  secret-pattern hit) exit non-zero with the expected error message.
- `docs/milestones/m9_2/final-review.md` exists and follows the M9 / M8.5 layout.

---

## Rollback / stop criteria

Stop the milestone — do **not** advance to the next Loop Prompt — if any
of these is true:

- `uvx` is unavailable on the dev box and cannot be installed without
  asking. Halt and ask; do not silently shell out to `pip install`.
- `claude-code-log` rejects the `--format md / --detail low / --compact`
  flag combination on the version `uvx` resolves to. Halt and ask
  before pinning a different version.
- The script reads any file outside `~/.claude/projects/` or
  `~/.claude/jobs/` (e.g. accidentally globs `.env` or `kaggle.json`).
  This is a security regression — halt and rewrite the locator.
- The secret-pattern scan trips on every real transcript (false-positive
  storm). Halt and ask — do not soften the patterns; the patterns are
  the safety net.
- The skill loader silently drops `save-log` (e.g. unknown frontmatter
  rejected, or directory layout mismatched). Halt and ask; do not
  switch to `.claude/commands/save-log.md` without confirmation.
- A real export of a session containing a known secret (e.g. a test
  transcript with a deliberate `sk-ant-…`) succeeds without
  `--allow-secret-like`. Halt and rotate the credential.

If M9.2 surfaces a follow-up that doesn't fit the milestone (e.g. a
`/save-log --all` mode, a Supabase artifact promotion, a transcript
post-processor), file it as a new issue and continue with M9.2 as
scoped — do not expand scope mid-milestone.

---

## Running on Arch Linux

```bash
# No DB required; M9.2 does not touch Supabase.
# uvx is the only new external dependency; verify it once:
uvx --version
uvx claude-code-log@latest --help | head -20

# Per-prompt invocation (each Loop Prompt runs inside its own worktree
# per the milestone-loop-protocol §5 default):
claude "Use the milestone-loop-runner agent to execute M9.2-T000 from docs/milestones/m9_2/loop-prompts.md."
# ...repeat for M9.2-T001, M9.2-T002.

# Milestone close:
claude "Use the milestone-closeout agent to finalize M9.2 — write docs/milestones/m9_2/final-review.md, update PROJECT_STATE/README/milestones/handoffs, and run worktree-milestone-pr to commit/push/open a PR."
```

The script makes no Supabase / Kaggle / GitHub network call; the only
outbound traffic is `uvx`'s PyPI fetch of `claude-code-log` on first
use. No `dangerouslyDisableSandbox` should be required.

---

## Human decisions needed before starting M9.2

Recorded here for the milestone-loop-runner's read list:

1. **Milestone slot.** M9.2 sits between M9 (done) and M10 (open).
   M10–M13 numbering stays. Confirmed in the M9.2 planning conversation
   on 2026-05-26.
2. **Logs in git.** `docs/logs/*.md` is **not** gitignored. Exports are
   repo-eligible after human review; the secret-pattern scan in the
   script is the safety net. Confirmed.
3. **Loop granularity.** Three Loop Prompts (scaffold+impl / smoke /
   closeout), matching M10's per-task cadence. Confirmed.
4. **Skill-only, not command.** No `.claude/commands/save-log.md` — skills
   override commands of the same name; a duplicate would just be
   ambiguity. Confirmed via meeting notes §2.
5. **No model-invokable variant.** `disable-model-invocation: true` is
   load-bearing; only a human typing `/save-log` may trigger the skill.
   Confirmed via meeting notes §2.
6. **Worktree.** Per-milestone worktree per
   `docs/milestone-loop-protocol.md` §5. Confirmed by repo default and
   the `feedback_direct_edits` memory.

The canonical decision record is the M9.2 planning conversation +
`docs/meeting-notes/2026-05-26-r1.md`.
