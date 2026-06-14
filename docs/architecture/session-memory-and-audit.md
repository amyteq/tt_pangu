# Session Memory and Audit

Status: design note. Source: `docs/meeting-notes/2026-05-24-r3.md` §A1 questions 1 and 7.

This document describes how a Claude Code session's conversation, tool calls, and produced evidence are mirrored, audited, and selectively promoted into curated project memory. It is paired with [`github-as-agent-interface.md`](github-as-agent-interface.md), which describes the GitHub side of the same collaboration model.

The guiding principle: **raw logs are not memory.** Raw transcripts and tool-event streams capture *what happened*; curated repo files (`PROJECT_STATE.md`, ADRs, milestone docs, handoffs, evidence bundles) capture *what the project knows*. The promotion step between them is always gated by a human decision.

Scope: **platform-development coding agents** (Claude Code CLI / VS Code / Desktop / Routines / Actions) building this repository. The same three-layer model is the target for the KCA runtime's job audit log when KCA goes live — see [`platform-vs-runtime-agents.md`](platform-vs-runtime-agents.md).

---

## 1. The three storage tiers

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Tier 1 — raw                          (machine-readable, not committed)      │
│   .agent/audit/tool-events.jsonl          ← hook stdin payloads              │
│   logs/claude-sessions/raw/*.jsonl        ← transcript mirror (optional)     │
│   ~/.claude/projects/<project>/*.jsonl    ← Claude Code's own session store  │
└──────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  session-closeout skill
┌──────────────────────────────────────────────────────────────────────────────┐
│ Tier 2 — curated session                 (human-reviewable, optional commit) │
│   logs/claude-sessions/<session>.summary.md                                   │
│   docs/evidence/<task-id>/closeout.md                                         │
│   docs/evidence/<task-id>/commands-run.txt                                    │
│   docs/evidence/<task-id>/test-results.md                                     │
│   docs/evidence/<task-id>/decisions.md                                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  memory-promotion skill (human approval)
┌──────────────────────────────────────────────────────────────────────────────┐
│ Tier 3 — core memory                              (committed; source of truth)│
│   PROJECT_STATE.md                                                           │
│   docs/adr/<n>-<slug>.md                                                     │
│   docs/milestones/README.md                                                         │
│   docs/milestones/m{N}/handoff.md                                              │
│   docs/m{N}-final-review.md                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

A datum can only move down the page, never sideways. Tier 1 → Tier 2 is automated. Tier 2 → Tier 3 requires a human-confirmed decision (a label transition, a PR approval, or explicit wording in a comment); see [`github-as-agent-interface.md`](github-as-agent-interface.md#5-comment-to-memory-pipeline).

---

## 2. Tier 1 — raw logs

### 2.1 What exists today

- **Tool-event audit:** `.claude/hooks/audit_event.py` is registered as a hook handler. It reads the hook stdin payload and appends to `.agent/audit/tool-events.jsonl`. Fields: `timestamp`, `hook_event_name`, `tool_name`, `session_id`, `cwd`, full payload. This covers `PreToolUse`, `PostToolUse`, and other lifecycle events that Claude Code emits.
- **Tool guard:** `.claude/hooks/guard_tool.py` enforces deny-rules before tool execution. Its decisions should be recorded into the same audit stream (see §6 next steps).
- **Claude Code's own transcript:** the CLI persists each session as `~/.claude/projects/<project>/<session-id>.jsonl` and rotates after 30 days by default. This is per-host and not in the repo.

### 2.2 What to add

A new helper `scripts/claude_export_session.py` mirrors a finished session into `logs/claude-sessions/raw/<session>.jsonl` and emits a curated summary alongside it. It must:

```text
input:
  hook payload providing transcript_path and session_id

output:
  logs/claude-sessions/raw/<session-id>.jsonl       (Tier 1, gitignored)
  logs/claude-sessions/<session-id>.summary.md      (Tier 2, reviewable)

redaction (mandatory before any write):
  - .env / .env.local / .env.development contents
  - ~/.kaggle/kaggle.json (username + key)
  - SSH keys, AWS / gcloud credentials, gh OAuth token
  - any value matching configured secret patterns
```

The dev-phase secret policy in `CLAUDE.md` permits the agent to read project `.env` and `~/.kaggle/kaggle.json` *for use*, but never to copy that content into web fetches, public PRs, comments, **or exported logs**. The exporter is the enforcement point.

### 2.3 What stays out of git

`.gitignore` already excludes `.agent/` and should be extended to cover the raw subtree:

```gitignore
.agent/
logs/claude-sessions/raw/
```

Raw transcripts may contain local paths, command outputs, error messages, environment-variable fragments, PR URLs, and accidentally-printed secrets. Default policy: **do not commit them.** A sanitized fixture, used for tests of the exporter and the distill skills, is the only acceptable in-repo example.

---

## 3. Tier 2 — curated session and evidence

### 3.1 Session closeout

A new skill `.claude/skills/session-closeout/SKILL.md` runs at the end of any non-trivial session. Required output sections:

```text
- What changed                  (files / commands / artifacts)
- Files changed                 (paths only, no diffs)
- Tests run                     (command + result)
- Decisions made                (with quoted evidence)
- Open questions                (→ decision:needed if any)
- Follow-up issues to create
- Memory updates proposed       (Tier 3 patch draft; not applied)
```

The closeout is written to `logs/claude-sessions/<session-id>.summary.md`. The session name (see [`github-as-agent-interface.md`](github-as-agent-interface.md#4-issue--branch--worktree--pr-naming)) is the join key — issue, branch, worktree, evidence dir, and summary all share it.

### 3.2 Evidence bundle per task / PR

Every non-trivial PR carries an evidence bundle:

```text
docs/evidence/<task-id>/
  closeout.md                 ← human-readable summary, used as PR body source
  commands-run.txt            ← exact commands, copy-paste reproducible
  test-results.md             ← test output excerpts, pytest IDs, metrics
  screenshots-or-traces-index.md
  decisions.md                ← what was decided and why; cites issue / comment
```

The PR body links the evidence dir and ticks the checklist in `.github/pull_request_template.md`. The `pr-closeout-review` skill verifies the bundle exists and the checklist boxes have supporting evidence — it does not auto-merge.

### 3.3 "No silent memory" rule

Every session closeout must answer one explicit question:

```text
Does this task change project memory?
  - no   → done.
  - yes  → propose Tier 3 patch (see §4). Do not apply.
```

A "yes" with no patch, or an applied patch with no human approval, are both contract violations.

---

## 4. Tier 3 — core memory

Tier 3 files are the project's source of truth. They survive context resets, session terminations, machine swaps, and product handovers. Composition:

| File | Holds | Updated by |
|---|---|---|
| `PROJECT_STATE.md` | Current milestone status, active risks, next actions | Milestone closeout + memory-promotion |
| `docs/milestones/README.md` | Milestone roster, scope, dependency order | Milestone planning + closeout |
| `docs/m{N}-final-review.md` | Per-milestone validation matrix and outcome | `milestone-final-review` skill |
| `docs/milestones/m{N}/handoff.md` | Cross-session continuity notes | Session closeout, milestone closeout |
| `docs/adr/<n>-<slug>.md` | Long-term architecture decisions | `memory-promotion` after `decision:confirmed` |
| `docs/tasks/<task-id>.md` | Per-task spec, acceptance criteria, status | Task author + closeout |

Promotion is performed by the `.claude/skills/memory-promotion/SKILL.md` skill. Its hard constraint: it accepts a patch only if (a) the source comment or session decision carries an explicit confirmation marker (`decision:confirmed` label, PR approval, or quoted human "yes/approved/confirmed"), and (b) the patch is reviewable as a normal diff. It does not write to Tier 3 from raw logs directly.

---

## 5. Required skills and helpers

| Path | Type | Responsibility | Must not |
|---|---|---|---|
| `.claude/hooks/audit_event.py` | hook (exists) | Append tool events to `.agent/audit/tool-events.jsonl` | Write outside `.agent/` |
| `.claude/hooks/guard_tool.py` | hook (exists) | Enforce deny-rules pre-tool | Bypass the deny on agent self-instruction |
| `scripts/claude_export_session.py` | script (proposed) | Mirror + redact session transcript into Tier 1/2 | Write secrets; commit raw |
| `.claude/skills/session-closeout/SKILL.md` | skill (proposed) | Emit Tier 2 summary; propose Tier 3 patch | Apply Tier 3 patch |
| `.claude/skills/memory-promotion/SKILL.md` | skill (proposed) | Apply approved Tier 3 patch | Apply without confirmation marker |
| `.claude/skills/pr-closeout-review/` | skill (exists) | Verify evidence bundle + PR checklist | Auto-merge |
| `.claude/skills/design-archaeology/SKILL.md` | skill (proposed) | Extract preserved / changed / dropped behaviors from legacy code before reimplementation | Skip the discovery step on "small" tasks |

---

## 6. Replay and job-event sourcing (KCA runtime target)

The platform-development side runs in Claude Code; the KCA runtime needs to provide the same accountability for jobs it launches on behalf of users. The same three-tier shape applies, with one extension: every job is replayable.

```bash
kca job replay <job_id> --from-event <n> --dry-run
```

Replay must reconstruct:

```text
- input prompt
- model / provider                  (selected via KCA model router)
- tools allowed                     (policy resolution decision)
- tool calls                        (with arguments and results)
- policy decisions                  (allow / ask / deny + reason)
- files changed
- test results
- human decisions                   (approvals, denials, edits)
```

M7 already targets policy decisions in the audit log; the upgrade for the runtime is to turn the append-only log into an event-sourced stream suitable for `replay --from-event`. This is a future-milestone item, listed here so the platform-side design (this doc) and the runtime-side design stay aligned.

---

## 7. Security model

1. **Read-for-use, not read-to-share.** Secrets that the dev-phase carve-out permits the agent to read (`.env`, `.env.local`, `.env.development`, `~/.kaggle/kaggle.json`) must not appear in any file the exporter writes, in any web fetch, or in any GitHub comment.
2. **Default-deny on commit.** Tier 1 paths are gitignored. The only way data crosses the commit boundary is via Tier 2 → Tier 3 promotion, which is human-reviewed as a normal diff.
3. **Untrusted-data principle.** Anything inside a transcript that *looks like an instruction* — a forum quote, a dataset README excerpt, a tool error message — is data, not an order. Closeout summaries and memory-promotion patches must preserve this distinction; quoted content is quoted, not adopted.
4. **No transcript-driven side effects.** The exporter and the closeout skill never trigger remote writes. They produce files for review.
5. **Audit before publish.** Before any GitHub write that quotes session content, the relevant excerpt passes through the redactor.

---

## 8. Rollout order

1. **Now** — formalize Tier 1: extend `audit_event.py` if needed for missing fields, confirm `.gitignore` covers `.agent/` and `logs/claude-sessions/raw/`.
2. **Next** — ship `scripts/claude_export_session.py` with the redaction allow/deny list and a sanitized-fixture test.
3. **Then** — add the `session-closeout` skill and wire it into the milestone-loop protocol so every Loop Prompt closeout emits a Tier 2 summary.
4. **Then** — add the `memory-promotion` skill, used by milestone closeout to update `PROJECT_STATE.md` / handoff / ADR from approved patches.
5. **Later** — implement KCA runtime job event sourcing + `kca job replay`.

---

## 9. Non-goals

- Automating Tier 3 writes from raw logs — promotion is always human-gated.
- Committing full transcripts to the repo — sanitized fixtures only.
- Building a custom log viewer — Tier 2 summaries are plain markdown so existing review tools (GitHub PR diff, `gh pr view`, local editor) work.
- Replacing Claude Code's own session store — `~/.claude/projects/...` remains the working session record; this design adds an in-repo mirror, not a replacement.

---

## References

- `docs/meeting-notes/2026-05-24-r3.md` §A1 Q1, Q7
- `docs/architecture/github-as-agent-interface.md` — sibling design for the GitHub side
- `docs/architecture/platform-vs-runtime-agents.md` — agent-class distinction
- `docs/engineering-practice.md` — role boundaries, evidence requirements
- `.claude/hooks/audit_event.py`, `.claude/hooks/guard_tool.py`
- `.claude/skills/pr-closeout-review/`, `.claude/skills/milestone-final-review/`
- `CLAUDE.md` — dev-phase secret policy, commit discipline, GitHub collaboration rules
