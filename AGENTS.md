# AGENTS.md — Cross-Tool Project Instructions

This repository builds a hybrid human + AI coding agent for Kaggle-style competitions and authorized CTF/lab challenges.

## Two meanings of "code agent"

**Platform-development coding agents** are external AI tools — Claude Code (primary), ChatGPT, Cursor — used to build this repository. They write source code, update docs, run local tests, and open PRs under human supervision.

**Runtime competition code agents** are agents launched by the finished platform to help a human user compete. Initial runtime: Claude Agent SDK in an isolated Python worker. Future: model router for Claude, GPT-style, and local models.

Never confuse the two. A platform-development agent editing this repo is not the same as a runtime agent running a Kaggle experiment. See `docs/architecture/platform-vs-runtime-agents.md` for details.

## Read first
- PROJECT_STATE.md
- CLAUDE.md if present
- `docs/adr/0022-long-run-competition-operating-model.md` — the operating model for competition work (two loops, per-competition state machine, context pack, relaxed autonomy, budgets). **Where this file and ADR-0022 disagree, ADR-0022 wins**; issue #189 tracks the full alignment of this file.
- docs/milestones/README.md if present
- docs/milestones/*/handoff.md if present

## Source of truth
Use this repository as the durable project memory. Do not rely on hidden memory in any single AI product. Important decisions must be written to:
- `PROJECT_STATE.md`
- `docs/adr/` (start with ADR-0022, the competition operating model)
- `docs/architecture/`
- `docs/tooling/`
- `docs/testing/`
- `docs/meeting-notes/`

## Architecture
- Claude Code CLI/Desktop is used for interactive repository development.
- Claude Agent SDK is the intended core production worker.
- Worker execution is Python-first for Kaggle/ML/CTF tasks.
- Control plane and future UI are TypeScript/Supabase, developed in Claude Code (same repo, same migrations, same CI).
- Supabase stores metadata, messages, research notes, runs, results, artifacts, approvals, and audit events.
- Git stores code and agent instructions.
- Large datasets and generated artifacts should not be committed unless explicitly required.

## Branch and worktree rules
- Every AI task that modifies code should use a dedicated branch or worktree.
- `main` must remain stable and protected.
- Do not allow multiple AI sessions to edit the same branch or files simultaneously.
- Do not push branches or create PRs without explicit human approval.
- Do not force-push, reset --hard, or run destructive git operations without explicit human approval.

## Development rules
- Make small, reviewable changes. One meaningful change per task.
- Return a plan and wait for human approval before editing files.
- Update docs and ADRs when changing architecture or workflow assumptions.
- Prefer deterministic tests and local validation before external submissions.
- Never read, print, or commit secrets, `.env`, `kaggle.json`, API keys, or private keys.
- Do not submit to Kaggle or push remote kernels without explicit human approval — **unless** that competition has met ADR-0022 §5's activation conditions A1-A7, in which case it submits inside its budget and records the intent instead of asking — the record is `competitions/<slug>/submissions/<timestamp>-<intent-id>.yaml`, written before dispatch (ADR-0022 §5 **A6**); an audit-log line is supplementary evidence, not the record. That is not the case for anything today, and the ADR-0021 §2 fallback is unimplemented as well, so this line reads exactly as written. **Nothing enforces it:** `kg.py`'s approval gate defaults to *allow* (`tools/kca/kg.py:21-22`) and the harness allow-lists the direct submit forms (`.claude/settings.json:91-92`) — asking is a rule you follow, not a gate that stops you (ADR-0022 §5). `autonomy.auto_submit: false` / `auto_push: false` vetoes that action regardless — read from the file `competition.yaml:autonomy_config` names (ADR-0022 §5 **A1**).
- CTF support is restricted to explicitly authorized challenges, local labs, or sandboxed environments.

## Competition loop
Follow this loop unless a task says otherwise:
1. Understand rules, metric, data, limits, and submission format.
2. Create or verify validation strategy.
3. Establish a baseline.
4. Run one controlled experiment at a time.
5. Record config, metrics, artifacts, logs, and conclusions.
6. Decide whether to iterate, stop, or submit. Submission approval follows ADR-0022 §5, not a blanket per-submission gate: inside the approved budget, screened submissions are autonomous; the human decides priority across competitions and the always-gated set — a floor of seven that config may only tighten: irreversible deletion, over-budget real-money spend, ambiguous rules, new terms / team changes, choosing the competition's final submissions, promotion once the closing window opens, and adopting external data / expanding beyond the competition's own data.
7. Record state as an ADR-0022 §3 state token in `competitions/<slug>/competition.yaml:state` and mirror it into the tracking issue.

## Tooling
Existing Kaggle scripts should be wrapped behind stable commands or typed tools. Every tool must document:
- Purpose.
- Inputs and outputs.
- Side effects.
- Safety class: read-only, local-write, remote-write, or submission.
- Required approval policy.

## GitHub collaboration interface
GitHub Issues, labels, PR reviews, and comments are the shared interface
between humans and AI agents working on this repo. The full model lives
in `docs/engineering-practice.md`; the routing rules below are binding.

- **AI implementation is gated by labels.** An agent may pick up an issue
  only when all are true: open, has `ai:ready`, has clear acceptance
  criteria, has an owner/reviewer, and (if `type:decision` ever applied)
  the decision is `decision:confirmed`. If any of these is missing, the
  issue stays `ai:blocked` or `decision:needed`.
- **Triage is read-write on labels and comments only**, and only when the
  rule is deterministic. Triage agents must not infer decisions from
  ambiguous comments — file `decision:needed` instead.
- **Remote writes require explicit human approval.** This covers
  `gh issue edit/comment/close`, `gh pr edit/comment/merge/create`,
  `gh label create/edit/delete`, `gh release *`, `git push`, and any
  mass label/issue mutation. `scripts/sync_labels.py` defaults to
  dry-run; live writes need `--apply --i-mean-it` plus a human approval
  recorded on the originating issue.
- **PRs must use `.github/pull_request_template.md`.** Tests, docs,
  evidence, schema/secrets, and remote-side-effect checklist sections
  are load-bearing — PRs without them are sent back for revision.
- **Issue-comment writes from agents must cite evidence** (issue URL,
  doc anchor, file:line, test run) and the acceptance criterion they
  refer to.
- Labels are defined in `.github/labels.yml`. New labels need a PR; do
  not create labels directly on GitHub.
