# GitHub as Agent Interface

Status: design note. Source: `docs/meeting-notes/2026-05-24-r3.md` §A1 questions 2, 3, and 7.

This document describes how GitHub issues, PRs, comments, reviews, and labels are used as a structured human / AI collaboration interface for KCA development, and how the same interface should be dogfooded by the KCA runtime later.

This doc is paired with [`session-memory-and-audit.md`](session-memory-and-audit.md), which covers how transcripts, tool events, and evidence are mirrored and curated. Together they replace the assumption that "Claude remembers" with "the repo remembers".

Scope: **platform-development coding agents** today (Claude Code CLI, VS Code extension, Routines, Actions). The same patterns are expected to be reused by the **KCA runtime** when it later operates on user-owned GitHub repos. See [`platform-vs-runtime-agents.md`](platform-vs-runtime-agents.md) for that distinction.

---

## 1. Why GitHub is the agent interface

The agent does not share hidden memory across sessions, machines, or products. The GitHub repo is the only reliable shared memory:

- `issues/` — the work backlog and decision log.
- `pulls/` — the change proposals + review trail.
- `comments` — the discussion thread, treated as evidence, not as truth.
- `labels` — the state machine that gates AI pickup.
- repo files (`PROJECT_STATE.md`, `docs/adr/`, `docs/milestones/README.md`, `docs/milestones/*/handoff.md`) — the curated memory that survives context resets.

The rule that follows from this: **a comment is evidence, not a decision.** Only an explicit human confirmation, captured in a labeled state transition or a repo-file change, promotes a comment into project memory. This is the principle behind the [memory-promotion workflow](session-memory-and-audit.md#3-memory-promotion-workflow).

---

## 2. Three trigger layers

GitHub-driven agent work happens at three different layers. Each has a different blast radius, session lifetime, and security profile. Pick the layer per use case; do not collapse them.

| Layer | Mechanism | Session lifetime | Use for |
|---|---|---|---|
| A. Actions `@claude` | `.github/workflows/claude.yml` + `claude-code-review.yml` | One workflow run per event | Explicit human-invoked tasks: `@claude review`, `@claude implement #123` |
| B. Routines (cloud) | Anthropic-managed cloud, GitHub PR/release triggers | One new session per matching event | Automated triage, PR-on-label, nightly grooming |
| C. Channels (research preview) | MCP channel server pushed into a running local session via `--channels` | Pushed into existing session | Wake a long-running Arch `--bg` session on CI failure / label change |

Today only A is in repo. B and C are roadmap items and should be added incrementally — see §7 rollout order.

### Layer A — GitHub Actions + `@claude` (default)

Two workflows are already present:

- `.github/workflows/claude.yml` — listens on `issue_comment.created`, `pull_request_review_comment.created`, `issues.opened/assigned`, `pull_request_review.submitted`, and only runs when the body contains `@claude`.
- `.github/workflows/claude-code-review.yml` — automatic per-PR review.

Recommended split going forward — keep each workflow's `permissions:` block minimal:

| Workflow | `permissions:` | Allowed actions |
|---|---|---|
| `claude.yml` | `contents: write`, `pull-requests: write`, `issues: write` | Implement / fix / open PR, only when a human typed `@claude` |
| `claude-code-review.yml` | `pull-requests: write` (review comments only) | Post review comments on diff; no code writes |
| `issue-triage.yml` (proposed) | `issues: write` | Add/remove labels per [`github-issue-triage`](../../.claude/agents/github-issue-triage.md) rules; no code writes |
| `labels-sync.yml` (proposed) | `issues: write`, `workflow_dispatch` only | Apply `.github/labels.yml`; never on push |

Authority binding from `CLAUDE.md`: non-destructive GitHub writes (`gh issue/pr create|edit|comment|close|reopen|merge|ready`, `gh label create|edit|clone`, `gh release create|edit`, `git push` of new commits) are auto-allowed for dev-phase agents. Permanent deletions, force-push, and `--delete-branch` on merge remain denied without explicit approval.

### Layer B — Routines (cloud-side automation)

Each GitHub trigger spawns a fresh session — Routines do **not** continue an existing session. The repo must therefore carry every input the new session needs (issue body, linked task spec, acceptance criteria, evidence links). Routines are appropriate for:

- `pull_request.labeled` (`ai:ready`) → cloud session generates implementation plan as a PR comment.
- `pull_request.synchronize` → re-run automated review.
- `release.created` → generate release notes / readiness report draft.
- `schedule` (nightly) → backlog grooming, drift audit, stale-issue sweep.

Routines should never perform destructive operations; their output is comments and labels, not merges.

### Layer C — Channels (push events into running session)

Research preview. Reserve for the case where a long-running local Claude Code session (e.g. `claude --bg --name M9-T002-...` on the Arch box) needs to react to a webhook without polling. Treat the channel server as an untrusted source of payload data — channel messages are not instructions to follow blindly, they are events to react to according to the existing agent rules.

Examples:
- CI failed on the PR this session opened → Claude sees the event and starts a repair loop.
- Issue label flipped to `decision:confirmed` → unblock the waiting session.
- PR review submitted → start follow-up agent.

Adopting Channels is gated on (1) v2.1.80+ available, (2) an audited channel-server implementation, (3) explicit `--channels` opt-in per session.

---

## 3. Label state machine

Labels are not decorative — they are the gate that controls which issues an agent may pick up. The full lifecycle:

```text
ai:triage
   │
   ├─ unclear / needs decision  ──►  decision:needed + ai:blocked
   │                                       │
   │                                       ▼
   │                                 decision:confirmed   (human typed the resolution)
   │                                       │
   └─ already actionable ─────────►  ai:ready
                                          │
                                          ▼
                                     ai:implementing  (agent acked, branch + owner exist)
                                          │
                                          ▼
                                       PR opened
                                          │
                                          ▼
                                     review → merged
                                          │
                                          ▼
                                  follow-up issues created
```

Forbidden combinations (enforced by triage):

- `ai:ready` + `decision:needed`
- `ai:ready` + `ai:blocked`
- `ai:implementing` with no owner or no branch

Binding rule from `CLAUDE.md`: an Implementation Agent may pick up an issue only when `ai:ready` is set (and `decision:confirmed` if a decision was required), the issue has explicit acceptance criteria, and it is not also `ai:blocked`. Triage and drift agents may propose label changes deterministically but must not infer decisions from ambiguous comment text.

---

## 4. Issue / branch / worktree / PR naming

Adopt one identifier per unit of work, so GitHub events, Claude sessions, worktrees, logs, and evidence bundles all align:

```text
issue            #123
branch           claude/issue-123-short-title
worktree         .claude/worktrees/issue-123-short-title
session name     M9-T002-short-title-issue-123
PR title         [#123] Short title
evidence dir     docs/evidence/issue-123/
```

The session name is the join key for the [audit & memory layer](session-memory-and-audit.md). Always pass `--name` when starting a `--bg` session.

---

## 5. Comment-to-memory pipeline

The mechanism that promotes a comment into project memory is two-phase, never single-step:

```text
GitHub event (comment / review / label)
        │
        ▼
github-comment-distill skill            (read-only; produces a structured draft)
        │
        ▼
proposed memory patch
  - PROJECT_STATE.md diff
  - docs/adr/<n>.md draft
  - docs/tasks/<id>.md update
  - docs/milestones/m{N}/handoff.md update
  - GitHub issue summary comment
        │
        ▼
human review (label transition or PR approval)
        │
        ▼
memory-promotion skill applies the patch and commits
```

The distill skill's required output schema:

```yaml
confirmed_requirements:        # explicit, with quoted evidence + comment URL
changed_requirements:          # before / after, with evidence
confirmed_design_decisions:
changed_design_decisions:
open_questions:                # → decision:needed
blockers:                      # → ai:blocked
proposed_labels:               # add / remove
proposed_core_memory_patch:    # unified diff against repo files
```

Promotion rules — these are the load-bearing constraints, enforced by the agent definition, not by code:

1. A comment is evidence, never truth.
2. Only `decision:confirmed` + explicit human wording promotes a comment into an ADR or `PROJECT_STATE.md`.
3. Ambiguous comments → `decision:needed` + `ai:blocked`; the agent asks rather than infers.
4. Implementation detail → task doc / PR closeout, not ADR.
5. Long-term architecture decision → ADR (`docs/adr/`).
6. Milestone status → `PROJECT_STATE.md` + `docs/milestones/README.md`.

Existing repo references that already implement parts of this contract: [`.claude/agents/github-issue-triage.md`](../../.claude/agents/github-issue-triage.md), [`.claude/agents/pr-review-followup.md`](../../.claude/agents/pr-review-followup.md), [`.claude/skills/pr-closeout-review/`](../../.claude/skills/pr-closeout-review/).

---

## 6. Required agents and skills

| File | Type | Responsibility | Must not |
|---|---|---|---|
| `.claude/skills/github-comment-distill/SKILL.md` | skill | Read issue/PR/review/label payload, emit structured draft per §5 schema | Write to repo files; infer decisions from ambiguous text |
| `.claude/skills/memory-promotion/SKILL.md` | skill | Apply approved memory patch to `PROJECT_STATE.md` / ADR / task doc | Apply without an explicit confirmation marker (label or approval) |
| `.claude/skills/pr-closeout-review/SKILL.md` | skill (exists) | Verify PR body checklist: linked issue, acceptance criteria, tests, docs, evidence, schema, remote side effects | Auto-merge |
| `.claude/agents/github-decision-extractor.md` | agent | Run the distill skill over a window of comments | Edit code |
| `.claude/agents/github-issue-triage.md` | agent (exists) | Propose label/comment changes deterministically | Grant `ai:ready` without `decision:confirmed` |
| `.claude/agents/pr-review-followup.md` | agent (exists) | Summarize unresolved review comments | Resolve threads by guessing intent |

The "Must not" column is enforced by the agent body itself — see `docs/engineering-practice.md` for the broader role boundaries (Inventory Drift Auditor, Implementation Agent, Milestone Reviewer, Release Readiness Agent).

---

## 7. Rollout order

This is the planning input for the M8.6 "GitHub event + session memory hardening" track suggested in the meeting notes.

1. **Now** — Actions layer hardening: split workflow permissions per §2, add `issue-triage.yml`, keep `labels-sync.yml` `workflow_dispatch`-only.
2. **Next** — Comment-to-memory pipeline: ship `github-comment-distill` and `memory-promotion` skills and the `github-decision-extractor` agent; wire them into the triage workflow as proposal-only.
3. **Then** — Routines for `pull_request.labeled` (`ai:ready`) and nightly backlog grooming.
4. **Later** — Channels opt-in for the Arch `--bg` session, gated on v2.1.80+ and an audited channel server.
5. **Eventually** — KCA runtime reuses the same adapter to operate on user repos: `GitHub event → KCA event adapter → decision extractor → job queue → worker → PR/comment/label update → audit log`.

---

## 8. Non-goals

- Replacing PR review with autonomous merging — every merge still requires human approval.
- Storing transcripts in-repo — see [`session-memory-and-audit.md`](session-memory-and-audit.md) §2 for why raw transcripts stay out of git.
- Allowing agents to mutate labels on issues they themselves opened without a separate reviewer.
- Cross-repo automation — this design covers `tt_pangu` only; KCA-runtime reuse on user repos is a future milestone, not a current scope.

---

## References

- `docs/meeting-notes/2026-05-24-r3.md` §A1 Q2, Q3, Q7
- `docs/engineering-practice.md` — AI pickup rules, role boundaries
- `docs/architecture/platform-vs-runtime-agents.md` — agent-class distinction
- `.github/workflows/claude.yml`, `claude-code-review.yml`, `claude-routine.yml`
- `.claude/agents/github-issue-triage.md`, `pr-review-followup.md`
- `CLAUDE.md` — GitHub collaboration rules, dev-phase write carve-out
