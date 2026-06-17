# ADR-0021: KCA autonomy model and the Claude-Code-vs-KCA agent boundary

## Status

Accepted (2026-06-17). Directed by the project owner. Supersedes the blanket
"ask before any external submission" reading of `CLAUDE.md` Operating-principle
#6 **for the KCA product agent** (the Claude Code harness default is unchanged —
see "Two agents" below). Runtime enforcement is a tracked follow-up (see
"Consequences").

## Context

- Real Kaggle competitions are now run from Claude Code under `competitions/`
  (e.g. `competitions/nvidia-nemotron/`) to accumulate concrete cases that
  inform the future KCA platform.
- The owner's intent for the KCA platform is a **highly autonomous** agent:
  routine `kaggle kernels push` and leaderboard `submit` should happen
  automatically once screening criteria pass. Humans contribute ideas, unblock
  progress, and provide course-correction — they should **rarely** need to
  approve an individual push/submit.
- Two distinct agents keep getting conflated in tasks/docs (root cause of issue
  #65): the **Claude Code harness** and the **KCA product**. Their governance,
  audit trails, and autonomy levels are different and must not be cross-applied.
- The eval regression framework and audit sentinel (ADR-0019, `eval.yml`) exist
  but the owner wants them **clarified now, not activated** as blocking gates.

## Decision

### 1. Two agents — distinct governance and audit

| | Claude Code harness | KCA product agent |
|---|---|---|
| What it is | The dev tool running these sessions | The product being built (KCA is itself an agent) |
| Governed by | `CLAUDE.md` + `.claude/hooks/guard_tool.py` + dev-phase policy | KCA's own `.kca/permissions/*.yaml` + `permission_policy.py` + per-comp `kca-<slug>.yaml` + decision/approval gates |
| Audit log | `.agent/audit/tool-events.jsonl` (`.claude/hooks/audit_event.py`; local, gitignored, dev telemetry) | `.agent/kca/audit.jsonl` (`tools/kca/agent/audit.py`; product policy-decision audit; read by eval/CI/tests) |
| Autonomy | Bounded by dev guardrails; the harness still asks for the human's own machine/account safety | **High** — screened-autonomous per §2 |

Rule of thumb: a `CLAUDE.md` clause governs **Claude Code sessions**; it is not
automatically a KCA-product runtime policy, and vice versa. When a doc/task
refers to an audit log, it must name the owner and the exact path.

### 2. KCA autonomy = screened-autonomy, configured per competition (default ON)

Autonomy is a per-competition setting in `kca-<slug>.yaml` (`autonomy:` block).
**Default: enabled.** A competition that needs strict human-in-the-loop must set
`autonomy.enabled: false` explicitly.

When enabled, the KCA agent performs `kaggle kernels push` and leaderboard
`submit` **without per-action human approval**, provided ALL screening criteria
pass. The intended-submission summary (file, experiment id, expected score,
reason) is written to `.agent/kca/audit.jsonl` instead of being posed as a question.

`autonomy:` schema (lives under `_base`, overridable per section; until the
runtime reads it, it is an inert annotation key like `lb`/`note`):

```yaml
_base:
  autonomy:
    enabled: true            # default true; false = strict human-in-the-loop
    auto_push: true          # kernel push without per-action approval
    auto_submit: true        # leaderboard submit without per-action approval
    daily_submit_budget: 5   # never exceed the per-team quota
    screen:                  # ALL must pass for an autonomous SUBMIT
      beats_best: true       # must beat current best on trusted local validation
      min_margin: 0.0        # ...by at least this margin
      require_repro: true    # seed + artifact path + exact command recorded
      rules_check: true      # competition-rules / submission-limit / no-leakage check passed
    human_gated:             # still require a human even when enabled
      - final_promotion_near_deadline   # = autonomous-submission-strategy scenario 4
      - irreversible_delete
      - over_budget_spend
      - ambiguous_rule
```

**Always human-gated, regardless of `autonomy.enabled`:** irreversible/permanent
deletions, real-money spend beyond the configured budget, ambiguous competition
rules, and final candidate promotion when the competition is closing soon
(`CLAUDE.md` autonomous-submission-strategy scenario 4). These are exactly the
points where the human "provides direction / unblocks", not routine ops.

**Human role under autonomy:** contribute ideas, unblock, course-correct, and
decide the human-gated points above. Everything else (screened push/submit,
exploration within budget) runs autonomously and is reconstructable from
`.agent/kca/audit.jsonl` + the run artifact. Autonomous actions must stay
**auditable and reversible** (kernel versioning, recorded submissions) so a human
can override or roll back after the fact.

### 3. eval / audit — clarified, not activated

- The KCA audit log is now namespaced to `.agent/kca/audit.jsonl` (done as a
  follow-up to this ADR), removing the `.agent/audit.jsonl`-vs-`.agent/audit/`
  stem collision that caused #65. The harness hook log stays at
  `.agent/audit/tool-events.jsonl`. Forward-facing docs reference the new path;
  dated milestone/task-spec history is left as a point-in-time record.
- The eval regression framework stays as-is: the nightly + rolling-diff run, but
  the cv-drift delta gate is **not** armed (baseline records no `cv_score`) and
  the PR delta-check is **not** promoted to a hard release blocker yet. Activate
  later when the case library is richer.
- The rolling-diff tracking issue (#47) is now **optional**: if it is absent,
  `eval.yml` records the flip in the job summary and warns instead of failing —
  so the issue can be closed without breaking the nightly.

## Consequences

- **Policy of record now**; this ADR + the `CLAUDE.md` "Two agents" section +
  the per-comp `autonomy:` schema are the source of truth.
- **Follow-ups (tracked, not in this ADR's PR):**
  1. Runtime enforcement: `permission_policy.py` / the KCA runner reads
     `kca-<slug>.yaml:autonomy`, evaluates the `screen` criteria, and
     auto-allows screened push/submit while still gating the `human_gated` set;
     `guard_tool.py` made aware of competition autonomy so Claude-Code-driven
     `kca kaggle push/submit` for an autonomy-enabled comp does not pose a
     redundant `ask`.
  2. Per-comp `autonomy:` added to each active `kca-<slug>.yaml`.
  3. Optional: eval-gate activation. (Audit namespace separation — done.)
- **Risk & mitigation:** auto-submit/push are outward-facing. Mitigations:
  default budget cap, mandatory screening, full audit trail, reversibility
  (kernel versions), and the always-human-gated set above. A competition can
  opt out with one line (`autonomy.enabled: false`).
