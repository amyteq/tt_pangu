# ADR-0021: KCA autonomy model and the Claude-Code-vs-KCA agent boundary

## Status

Accepted (2026-06-17). Directed by the project owner. Supersedes the blanket "ask before any external submission" reading of `CLAUDE.md` Operating-principle #6 **for the KCA product agent** (the Claude Code harness default is unchanged — see "Two agents" below). Runtime enforcement is a tracked follow-up (see "Consequences").

## Context

- Real Kaggle competitions are now run from Claude Code under `competitions/` (e.g. `competitions/nvidia-nemotron/`) to accumulate concrete cases that inform the future KCA platform.
- The owner's intent for the KCA platform is a **highly autonomous** agent: routine `kaggle kernels push` and leaderboard `submit` should happen automatically once screening criteria pass. Humans contribute ideas, unblock progress, and provide course-correction — they should **rarely** need to approve an individual push/submit.
- Two distinct agents keep getting conflated in tasks/docs (root cause of issue #65): the **Claude Code harness** and the **KCA product**. Their governance, audit trails, and autonomy levels are different and must not be cross-applied.
- The eval regression framework and audit sentinel (ADR-0019, `eval.yml`) exist but the owner wants them **clarified now, not activated** as blocking gates.

## Decision

### 1. Two agents — distinct governance and audit

| | Claude Code harness | KCA product agent |
|---|---|---|
| What it is | The dev tool running these sessions | The product being built (KCA is itself an agent) |
| Governed by | `CLAUDE.md` + `.claude/hooks/guard_tool.py` + dev-phase policy | KCA's own `.kca/permissions/*.yaml` + `permission_policy.py` + per-comp `kca-<slug>.yaml` + decision/approval gates |
| Audit log | `.agent/audit/tool-events.jsonl` (`.claude/hooks/audit_event.py`; local, gitignored, dev telemetry) | `.agent/kca/audit.jsonl` (`tools/kca/agent/audit.py`; product policy-decision audit; read by eval/CI/tests) |
| Autonomy | Bounded by dev guardrails; the harness still asks for the human's own machine/account safety | **High** — screened-autonomous per §2 |

Rule of thumb: a `CLAUDE.md` clause governs **Claude Code sessions**; it is not automatically a KCA-product runtime policy, and vice versa. When a doc/task refers to an audit log, it must name the owner and the exact path.

### 2. KCA autonomy = screened-autonomy, configured per competition (default ON)

Autonomy is a per-competition setting in the file that `competitions/<slug>/competition.yaml:autonomy_config` names — conventionally `kca-<slug>.yaml`, but the field is the lookup and the convention is not (nemo's is `kca-nemo.yaml`). ADR-0022 §5's **A1** reads that file and no other. **Default: enabled.** A competition that needs strict human-in-the-loop must set `autonomy.enabled: false` explicitly.

When enabled, the KCA agent performs `kaggle kernels push` and leaderboard `submit` **without per-action human approval**, provided ALL screening criteria pass. **Not yet in effect:** nothing in the tree evaluates those criteria — no file under `tools/` / `src/` / `scripts/` reads the `autonomy:` block — and `.kca/permissions/*.yaml` sets both to `default_decision: ask` — declared in three of the four profiles, with `hackathon-runner.yaml` inheriting them from `default.yaml` via the resolver's fallback chain rather than declaring them (`competition-runner.yaml` allows them only in `competition-finalization` / `human-approved` modes) — but that file is read only by `tools/kca/skill.py:15`, not by the installed `kca` CLI, whose own gate defaults to *allow* (`tools/kca/kg.py:21-22`). An unevaluable precondition is a failed one, so submissions are human-gated until the screen is implemented (ADR-0022 §5). Instead of being posed as a question, the intended-submission summary (file, experiment id, expected score, reason) is **persisted before dispatch** in the phase-appropriate authority: a `competitions/<slug>/submissions/<timestamp>-<intent-id>.yaml` file for phase 1, or a transactional Supabase intent record for phase-2 KCA (§1). A submission whose record cannot be written does not dispatch — ADR-0022 §5's activation condition **A6**, which supersedes this paragraph's earlier wording. `.agent/kca/audit.jsonl` still receives the action, as supplementary evidence of what ran; it is not the record, because it is driver-specific, gitignored, and not owned by the competition.

`autonomy:` schema. It lives **either** at the top level of the config file **or** under its `_base:` key (the per-variant defaults convention `kca-nemo.yaml` uses) — exactly one of the two, because two would be ambiguous and ADR-0022 §5's **A1** fails on ambiguity as it does on absence. A section may override individual keys on top of `_base.autonomy`; A1 evaluates the merged result for the section the action runs under, and a `false` anywhere in the merge is an absolute veto that survives it (ADR-0022 §5 A1). Until the runtime reads it, it is an inert annotation key like `lb`/`note`:

```yaml
_base:
  autonomy:
    enabled: true            # default true; false = strict human-in-the-loop
    auto_push: true          # kernel push without per-action approval
    auto_submit: true        # leaderboard submit without per-action approval
                             # ^ both RETAINED by ADR-0022 §5: an explicit `false` is an
                             #   action-level veto, checked as part of activation condition
                             #   A1, so §5 can be active for pushes and inactive for submits.
    daily_submit_budget: 5   # SUPERSEDED by ADR-0022 §6 once §5 is active for the
                             # competition: use the VERIFIED per-team limit from
                             # competition.yaml:budget.submissions.verified_daily_limit.
                             # 5 is never assumed, and an unverified limit blocks.
    screen:                  # ALL must pass for an autonomous SUBMIT
      beats_best: true       # must beat current best on trusted local validation
      min_margin: 0.0        # ...by at least this margin
                             # ^ both SUPERSEDED by ADR-0022 §5 once active: they order
                             #   candidates, they do not gate the submission
      require_repro: true    # seed + artifact path + exact command recorded  (hard gate)
      rules_check: true      # competition-rules / submission-limit / no-leakage  (hard gate)
    human_gated:             # still require a human even when enabled. ADDITIVE to the
                             #   floor: ADR-0022 §5's seven items apply whether or not they
                             #   are repeated here, and config cannot shorten them.
      - final_promotion_near_deadline   # = scenario 4 (ADR-0022 §5)
      - irreversible_delete
      - over_budget_spend
      - ambiguous_rule
      - new_terms_or_team_change        # added by ADR-0022 §5
      - final_submission_selection      # added by ADR-0022 §5 (ADR-0006's own gate), and
                                        #   NOT only near the deadline
      - external_data_or_data_policy    # added by ADR-0022 §5 (ADR-0006's own gate)
```

**Which model is live for a competition.** This block is the schema for both models; the *semantics* of `screen` and `daily_submit_budget` depend on whether ADR-0022 §5 has been activated for that competition (ADR-0022 §5 lists the checkable conditions A1-A7). Where §5 is not active — which is every competition until a fail-closed pre-submit gate exists — the narrower reading on this page governs: all four `screen` criteria gate, and `daily_submit_budget` caps. Since nothing evaluates `screen` yet, "the narrower reading governs" currently resolves to the human-approval gate, not to approval-free screened submission. Where it is active, the annotations above apply. There is one schema and one live model per competition at any time, never two.

**Always human-gated, regardless of `autonomy.enabled`:** irreversible/permanent deletions, real-money spend beyond the configured budget, ambiguous competition rules, accepting new terms / joining a competition / any team change (added by ADR-0022 §5), final candidate promotion when the competition is closing soon (scenario 4, ADR-0022 §5), **choosing the competition's final submissions whenever that choice is made** and **adopting external data or expanding training data beyond the competition's own data** (the last two added by ADR-0022 §5, carrying ADR-0006's "final submission selection" and "data policy decisions" forward). These are exactly the points where the human "provides direction / unblocks", not routine ops. Per ADR-0022 §5 this set is a **floor**: ADR-0006's per-project / per-competition gate configuration may only tighten it, never remove or weaken an entry.

**Human role under autonomy:** contribute ideas, unblock, course-correct, and decide the human-gated points above. Everything else (screened push/submit, exploration within budget) runs autonomously and is reconstructable from `.agent/kca/audit.jsonl` + the run artifact. Autonomous actions must stay **auditable and supersedable** (kernel versioning, recorded submissions) so a human can see exactly what was sent and replace it with a later submission.

> **Amended by ADR-0022** (§5 "Recording an autonomous submission", and its "Relationship to ADR-0021" table). This paragraph said "auditable and **reversible** … roll back after the fact". That was wrong about the action it governs: a dispatched submission cannot be recalled and the quota slot it consumed does not come back, so nothing rolls back. The requirement is unchanged in substance — a human must be able to see and override — but the word mattered, because "reversible" made the mitigation for irreversible, quota-consuming actions look stronger than it is. The protection that actually binds is ADR-0022 §6's reserve-before-dispatch budget, applied *before* the submission, not the audit record written after it.

### 3. eval / audit — clarified, not activated

- The KCA audit log is now namespaced to `.agent/kca/audit.jsonl` (done as a follow-up to this ADR), removing the `.agent/audit.jsonl`-vs-`.agent/audit/` stem collision that caused #65. The harness hook log stays at `.agent/audit/tool-events.jsonl`. Forward-facing docs reference the new path; dated milestone/task-spec history is left as a point-in-time record. That rename is implemented and stands; KCA's *durable* audit location and format are deferred to phase 2 (`CLAUDE.md` §"Two agents", PR #200, #203).
- The eval regression framework stays as-is: the nightly + rolling-diff run, but the cv-drift delta gate is **not** armed (baseline records no `cv_score`) and the PR delta-check is **not** promoted to a hard release blocker yet. Activate later when the case library is richer.
- The rolling-diff tracking issue (#47) is now **optional**: if it is absent, `eval.yml` records the flip in the job summary and warns instead of failing — so the issue can be closed without breaking the nightly.

### 4. Daily submission strategy — the four scenarios

**Moved to ADR-0022 §5.** #188 lifted this table out of `CLAUDE.md` into this ADR; ADR-0022 (#190) then became the single source for how wide autonomy actually is, and it amends the table's reading (scenario 2's unused slots are *spent* on exploration, not banked; scenario 3's N is bounded by the competition's **verified** daily limit, never an assumed 5). Keeping a second copy here would re-create exactly the drift #188 was removing, so the table lives in `docs/adr/0022-long-run-competition-operating-model.md` §5 — one copy, there. Scenario 4 remains the `final_promotion_near_deadline` entry in the `human_gated` list above.

## Consequences

- **Policy of record now**; this ADR + the `CLAUDE.md` "Two agents" section + the per-comp `autonomy:` schema are the source of truth.
- **Follow-ups (tracked, not in this ADR's PR):**
  1. Runtime enforcement: `permission_policy.py` / the KCA runner resolves `competition.yaml:autonomy_config`, reads its `autonomy:` block (top level or under `_base:`), evaluates the `screen` criteria, and auto-allows screened push/submit while still gating the `human_gated` set; `guard_tool.py` made aware of competition autonomy so Claude-Code-driven `kca kaggle push/submit` for an autonomy-enabled comp does not pose a redundant `ask`.
  2. Per-comp `autonomy:` added to each active competition — in the file its `competition.yaml:autonomy_config` names (conventionally `kca-<slug>.yaml`, but `nvidia-nemotron`'s is `kca-nemo.yaml`, which is why the field is the lookup), and set in that file's `competition.yaml` at the same time.
  3. Optional: eval-gate activation. (Audit namespace separation — done.)
- **Risk & mitigation:** auto-submit/push are outward-facing. Mitigations: the budget cap **reserved before dispatch** (ADR-0022 §6 — the one that actually binds, because it is applied before the spend), mandatory screening, a full audit trail, **supersedability** (kernel versions retained and submission ids recorded, so a human can see what was sent and replace it with a later submission), and the always-human-gated set above. Not *reversibility*: a dispatched submission cannot be recalled and its quota slot does not come back — see the amendment note in §2 and ADR-0022's "Relationship to ADR-0021". A competition can opt out with one line (`autonomy.enabled: false`).
