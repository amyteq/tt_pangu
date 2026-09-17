# Engineering Practice

Concise, project-specific operating model for the Kaggle / CTF Code Agent repository. Long-form rationale lives in the source docs linked at the bottom — do not duplicate them here.

## Model

```
GitHub                — canonical repo, source-of-truth docs, PRs, reviews, issues
Claude Code           — primary platform-development engineering loop, run from worktrees
Supabase (local + staging)
                      — migration-first schema management; no production dashboard edits
```

Out of scope here: a separate runtime competition agent runs *inside* the finished platform. It is product-internal and not the same as the platform-development agent that edits this repo.

> **Superseded in part (2026-09-15, issue #189).** An earlier version of this paragraph called that runtime agent a "Claude Agent SDK worker". `CLAUDE.md` → *Mission* is current: **KCA is not built on Claude Code or the Claude Agent SDK.** `CLAUDE.md` and `AGENTS.md` win over this document wherever they disagree.

## Five team rules

1. **GitHub is the canonical source of truth.** Code, docs, decisions, PRs, and evidence end up in the repo or linked GitHub records.
2. **Every inventory or drift finding produces an action.** Findings become issues, tests, docs, ADRs, deprecations, or an explicit no-action record — never a passive note.
3. **AI may implement only `ai:ready` issues with confirmed decisions.** Open questions stay `decision:needed` / `ai:blocked` until a human confirms.
4. **Every feature milestone updates tests, docs, and inventory.** Implementation without sync-back is incomplete.
5. **Summaries link to detail, never replace it.** A summary doc must not become a second source of truth.

## Execution loop

```
Inventory / drift audit
  → GitHub issue (with labels + acceptance criteria)
  → Human decision (decision:confirmed)
  → ai:ready
  → Feature worktree (branched off main)
  → Claude Code implementation (one meaningful change at a time)
  → Tests pass locally
  → PR with closeout checklist
  → Review (human + agent)
  → Docs + inventory updated in the same PR or follow-up
```

`/goal` drives most agent sessions and must have explicit stop conditions. `/loop` is reserved for bounded rechecking (CI status, PR comments, scheduled drift scans) — not for open-ended work.

## Agent lanes

See `.claude/agents/` for full definitions. Each agent has an explicit **Must not** section. Headline rules:

| Agent | Mode | Allowed write |
|---|---|---|
| `github-issue-triage` | Issues read/write | Labels + comments when rules are deterministic |
| `pr-review-followup` | PR comments read/write | Follow-up comments + label updates |
| `inventory-drift-auditor` | Read-only + issue create | Drift issues backed by evidence |
| `milestone-reviewer` | Read-only review | Review report; follow-up issues |
| `test-coverage-reviewer` | Read-only / test PRs | Test-gap issues; test PRs require approval |
| `release-readiness` | Read-only + issue create | Blocker / readiness reports — never grants READY |

## Label model

Source of truth: `.github/labels.yml`. Apply via `scripts/sync_labels.py` (dry-run is the default; remote write requires human approval).

Routing-critical labels:

- `ai:triage`, `ai:ready`, `ai:implementing`, `ai:blocked` — agent state.
- `decision:needed`, `decision:confirmed` — gate AI work.
- `type:bug | drift | test-gap | decision | docs | cleanup | feature` — what the issue is.
- `priority:P0 | P1 | P2` — scheduling.
- `area:*` — surface area for routing.
- `policy:approval-required` — remote-write / Kaggle / CTF / production surfaces; agents may plan but not execute without explicit human approval.

## AI implementation pickup rule

An implementation agent (or `/goal` session) may pick up an issue only when **all** are true:

- issue is open;
- issue has `ai:ready`;
- if any decision is involved, the label is `decision:confirmed`;
- the issue has clear acceptance criteria;
- the issue has an owner or reviewer;
- the issue does not have `ai:blocked`;
- scope does not include secrets, destructive migrations, production infra, Kaggle live submissions, real CTF targets, or customer-visible side effects unless the issue also has explicit human approval recorded on the issue.

Triage and planning are allowed before `ai:ready`; code edits and PRs are not.

## Issue forms

Use the forms under `.github/ISSUE_TEMPLATE/`. Each enforces the minimum fields needed for triage and decision gating:

- `bug.yml` → `type:bug`, `ai:triage`
- `drift.yml` → `type:drift`, `ai:triage`
- `decision.yml` → `type:decision`, `decision:needed`, `ai:blocked`
- `test-gap.yml` → `type:test-gap`, `ai:triage`
- `feature-work.yml` → `type:feature`, `ai:triage`

## Pull requests

Use `.github/pull_request_template.md`. The closeout checklist is load-bearing: a PR without tests run, docs/inventory impact, evidence links, and a schema/secrets/remote side-effect note should not be reviewed for merge.

**Phase-1 merge policy.** Merging your own feature-branch PR into `main` needs no separate human approval during phase 1 — once the required checks are green and that closeout checklist is filled in, squash-merge it (keep the remote branch: no `--delete-branch`). Unchanged: no direct pushes to `main`, no force-push, no merging on red or pending checks, someone else's PR stays theirs to approve, and permanent-deletion remote writes still require explicit human approval. §"Agent lanes" is also unchanged: `test-coverage-reviewer` still needs human approval to *open* a test PR, which this merge policy does not grant. Canonical wording: `CLAUDE.md` §"GitHub collaboration".

## Testing tiers (`docs/testing/`)

| Tier | Required use |
|---|---|
| Unit | Pure functions, validators, small components / hooks |
| Integration | Feature behavior across services, DB layer, permissions |
| Smoke | Critical paths that must not break (pytest `*_smoke.py`) |
| Regression | Any fixed bug likely to recur |
| E2E | P0 user-visible UI workflows (Playwright when set up) |

TDD applies to pure business logic and bug fixes when practical.

## Evidence and attachments

- Long-lived evidence: commit under `docs/evidence/` (do not commit bulk logs — summarize and link the artifact).
- CI artifacts: link the GitHub Actions artifact URL on the issue/PR.
- Human screenshots: paste into GitHub web UI on the issue/PR.
- Runtime proof: link the test run, audit log entry, or closeout doc.

## Anti-over-documentation

1. Keep summaries short; link to the source doc.
2. Don't add a new doc section when an ADR, issue, or status-map update would do.
3. Prefer action-linked docs (issue / PR / test / evidence / owner / decision) over standalone handbooks.
4. Pause expansion if documentation work begins to crowd out shipping.

## Sources

- `temp/engineering_practice_summary.md` — full team summary (external).
- `temp/engineering_practice_details.md` — full detailed handbook (external; not all sections apply to this repo — only the items above are adopted).
- `AGENTS.md` — cross-tool baseline for all agents working in this repo.
- `CLAUDE.md` — Claude Code project instructions.
- `docs/milestone-loop-protocol.md` — milestone-loop rules.
- `docs/milestones/README.md` — milestone roadmap and acceptance criteria.
