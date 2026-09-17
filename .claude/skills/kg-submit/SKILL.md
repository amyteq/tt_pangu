---
name: kg-submit
description: Use to decide whether a result deserves a submission slot and then to spend it safely: pre-push validation, the fail-closed pre-submit gate, the persisted submission-intent record, dispatch, and score reconciliation.
---

# kg-submit — spend the slot deliberately, and record it before you spend it

Use this on entry to `SUBMISSION_ELIGIBILITY`: a run has a result and the question is whether it should consume a submission slot. This skill carries `SUBMISSION_ELIGIBILITY` → `SKIP_SUBMISSION` **or** `PRE_SUBMIT_GATE` → `SUBMIT` → `WAIT_SCORE`.

Two facts shape everything below.

**A dispatched submission cannot be recalled, and the slot it spent does not come back.** That asymmetry is why the budget is reserved and the intent recorded *before* dispatch rather than reconciled after it: reconciliation can explain an overspend, it cannot undo one.

**A kernel or notebook push is not a leaderboard submission** (issue #77). In `kernel` and `notebook` modes `SUBMIT` is not complete until the competition's own submit call has been acknowledged. `competitions/arc-agi3/submissions.md` is the worked example: four kernels reached COMPLETE, two were submitted, two were scored.

Absorbs the submission-gate half of the retired `kaggle-tooling-integration` skill and the `kernel-prepush-validate` candidate from `competitions/_shared/skill-candidates.md` (issue #192).

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | The candidate run and its artifact, the `Experiment` record and its reproducibility fields, `competition.yaml` (`submission_mode`, `best`, `deadline`, `closing_window_days`, the whole `budget.submissions` block with its provenance fields), `rules.md`, and the `kg-audit` verdict on this artifact. |
| **Output schema** | A **submission-intent record**, written and flushed **before** the external call, at `competitions/<slug>/submissions/<utc-timestamp>-<intent-id>.yaml` — the shape is ADR-0022 §5's, reproduced below. Then, after dispatch, `submitted_at`; after reconciliation, `external_id` and the score, plus `competition.yaml:best` where the score is a genuine in-deadline improvement. On the skip path, a `SKIP_SUBMISSION` record with the reason. |
| **State transition** | `EVALUATE` → `SUBMISSION_ELIGIBILITY` → `SKIP_SUBMISSION` (recorded, with the reason) or `PRE_SUBMIT_GATE` → `SUBMIT` → `WAIT_SCORE` → `RESULT_ANALYSIS`. |
| **Allowed tools** | Read, Write, Glob, Grep, Bash, `kca kaggle push` / `kca kaggle submit`, `kca nb to-ipynb` via `kg-nb`. Reaches `remote-write` for a push and `submission` for a submit — the two highest levels in `docs/tooling/kca-side-effect-levels.md`, and the only place in the `kg-*` set that touches either. |
| **Budget** | Spends `budget.submissions` — the **verified** daily limit for this competition and team, never an assumed 5, minus `reserve_for_human`. Also spends the shared team scope. Reserve atomically in **every** scope that caps the dimension before dispatch (ADR-0022 §6's all-or-none rule), and record every reservation id in the intent's `budget_reservations` map. An unverified or expired limit blocks **submission** and nothing else: the competition sits in `PAUSED_BUDGET` for that dimension while other work continues. |
| **Prerequisite approvals** | See *Who approves what* below — it is the substance of this skill, not a footnote. |
| **Idempotency** | **Single-shot.** A dispatched submission is an external side effect and a second dispatch is a second submission. Resuming or reconciling the *same* action keeps its `ref` and must not dispatch again. An unknown outcome never authorizes a second dispatch: query the platform, match the record, and only then act. A genuinely new submission after reconciliation proved the previous action absent gets a **new** `ref` and records its predecessor. |
| **Failure classes** | Request sent, response lost → `NEEDS_RECONCILIATION` with the intent's `ref` as `external_ref`; query the platform, never blind-retry. Rate limit or transient platform error before dispatch → `RETRY_AT`. Daily limit reached, or unverified, or `null` → `PAUSED_BUDGET`, `resume_state: PRE_SUBMIT_GATE`. Inside the closing window, or rules ambiguous, or an approval expired → `WAIT_HUMAN`. Format or rules check failed → back to `IMPLEMENT`; the gate did its job. |
| **Acceptance tests** | An intent file exists for every dispatch, written before it, with a unique `ref`, a `budget_reservations` entry per capping scope, and `screen.require_repro` / `screen.rules_check` both `pass`. No dispatch exists without one. `submitted_at` is filled after dispatch and `external_id` after reconciliation. A skip is recorded with its reason rather than left silent. `competition.yaml:best` moves only on a verified in-deadline score. |

## Who approves what

This section is the reason the skill exists in this shape. Two different agents run this loop, and a rule written for one is not a rule for the other — conflating them is issue #65:

- **The harness (you, here — Claude Code or Codex).** A push or a submission spends the human's own Kaggle credentials and their daily quota on their own account, so it needs human approval: present the facts below and ask, then dispatch. That is the same rule as "the Claude Code harness still asks for paid-API/credential use", and it binds a Codex session identically.
- **The KCA product agent.** Governed by its competition's `autonomy` block — the file `competition.yaml:autonomy_config` names, conventionally `kca-<slug>.yaml` but the field is the lookup — and that block is configuration, not permission. ADR-0022 §5 opens the approval-free path only for a competition meeting activation conditions **A1-A7**; no competition meets them, ADR-0021 §2's earlier screened grant is unimplemented, and no code reads the block, so KCA's pushes and submissions are asked for too. Where the grant is open, the record is the intent file persisted before dispatch — never an audit log, which is driver-specific, gitignored and not competition-owned (`CLAUDE.md` principle 6).

**So, today, on every competition in this repo: ask before every Kaggle submission or kernel push.** Nothing will stop you if you do not — ADR-0022 §5's condition **A5** names the three gaps that make this a written rule rather than an enforced one: `.kca/permissions/*.yaml` resolves `kaggle_submit` / `kaggle_push` to `ask` but only `tools/kca/skill.py:15` reads any of them and the installed `kca` CLI does not; `kg.py`'s own gate defaults to allow (`tools/kca/kg.py:21-22`, and `_gate()` at `:53-59` has no call sites); and the harness allow-lists the direct forms (`.claude/settings.json:91-92`, with `guard_tool.py` matching no submit form).

Either way the same facts are required before a submission — in the approval request if you are the harness, in the persisted intent record if you are KCA:

- competition slug, and the exact artifact path plus its SHA-256;
- experiment id and run id;
- local validation score, the metric, and its direction;
- how many slots of the **verified** daily limit are already spent, and against which reset boundary;
- expected leaderboard behaviour and the risk or uncertainty in that expectation;
- one line on why this candidate rather than another.

`CLAUDE.md` principle 6 also holds the floor of things that stay human-gated for both agents however the rest is configured — seven items, not configurable down, including **choosing the competition's final submissions whenever that choice is made**. Read that floor there rather than from a copy here.

## Should this result spend a slot?

Decide in this order. **The closing window is checked first, before the candidate count** — reading by count first is how an exactly-one-winner day inside the window matches an autonomous row and dispatches something the floor reserves for the human.

| # | Condition | Action |
|---|---|---|
| **0** | Inside the closing window (`closing_window_days`; default `competition_period × 0.1` rounded up to whole days) — *any* number of candidates, including one, including zero | `WAIT_HUMAN`. The human chooses what is promoted. Scenarios 1-3 do not apply |
| 1 | Outside the window, exactly one candidate beats the current best | Submit it; use the remaining effective slots for exploration near the baseline |
| 2 | Outside the window, no candidate beats the current best | Do not bank the balance — an unused slot does not roll over. Spend the effective slots on exploration near the baseline |
| 3 | Outside the window, several candidates beat the current best | Submit the best N up to the effective limit; queue the rest for the next competition day |
| 4 | Inside the window, several candidates beat the current best | Ask the human which to promote — the case row 0 generalises |

"Effective limit" is `verified_daily_limit − reserve_for_human`, and held-back slots are held back from exploration first. "Per competition day" means a day delimited by `verified_reset_boundary`, read from this competition's own rules — Kaggle sets it per competition, and a scheduler assuming UTC submits into the wrong day and miscounts the current one. **Missing or stale timing fails to the human, never to row 3**: absent `launch` or `deadline`, or a `timing_verified_at` older than `timing_verified_ttl`, sends the competition to `WAIT_HUMAN`.

Screening orders candidates; it does not authorise them. `require_repro` (seed, artifact path and exact command recorded) and `rules_check` are **hard gates** and block. `beats_best` and `min_margin` are **ordering only** — they decide which candidate goes first, not whether a slot that would otherwise expire may be spent.

Not submitting is a real outcome: record `SKIP_SUBMISSION` with the reason rather than leaving the result unresolved.

## Pre-push validation — never waste a multi-hour run on a typo

For `kernel` and `notebook` modes, run this before the push. The evidence is three nemotron run-time errors — an F821 undefined name, a `.shape` on the wrong object, a ptxas path — each of which surfaced only at run time and cost roughly two GPU-hours. `docs/tooling/kaggle-kernel-ops.md` §5 is the full checklist:

1. **Static lint** — the `kca kaggle push` gate, or the competition's own checker (`competitions/nvidia-nemotron/kernels/validate_kernel.py` is the worked one). `ruff` F821 catches undefined-name typos in seconds.
2. **Fail-fast preflight inside the kernel** — exercise the generate/eval path on one example immediately after model load, before the long train. Runtime type errors then surface in minutes.
3. **Isolate non-essential steps** in their own `try/except`, so a failure in held-out eval cannot mislabel a successful train or lose the saved adapter.
4. **Resolve mounts with a glob**, never a literal path (`docs/tooling/kaggle-kernel-ops.md` §6).
5. **One kernel per candidate**, variant in the slug. The API exposes only a kernel's latest run, so an older version's artifact cannot be retrieved — submit the just-pushed latest and omit `--version`, or give the candidate its own kernel (§1-2).

## The pre-submit gate, and the record

`PRE_SUBMIT_GATE` is fail-closed: it refuses rather than proceeding when it cannot answer a question.

1. **Format and inference validation** — the artifact is in the exact shape `submission_mode` requires, and for `kernel` mode the kernel has actually reached COMPLETE and emitted the file.
2. **Rules check** — `rules_check` against `rules.md`, as a hard gate.
3. **Reproducibility** — `require_repro`, as a hard gate.
4. **Budget reservation** — atomically, in every scope that caps submissions, before anything is sent.
5. **Write the intent record and flush it.** **A submission whose intent record could not be persisted does not dispatch** — that is ADR-0022 §5's condition A6.

```yaml
# competitions/<slug>/submissions/<utc-timestamp>-<intent-id>.yaml
competition: <slug>
experiment_id: EXP-027
run_id: <run>
artifact: <path>            # the exact file dispatched
artifact_sha256: <hash>
code_commit: <git-sha>
expected_score: 0.86        # and the metric it is on
reason: <why this candidate, in one line>
scenario: 1                 # 1 | 2 | 3 only -- rows 0 and 4 are human-gated, so no
                            #   autonomous intent record ever carries them
screen: {require_repro: pass, rules_check: pass}
ref: INT-20260915-215804-7c92  # unique per intended external action, across competitions and
                            #   runs; NEVER the experiment id. Two submissions of one experiment
                            #   need different refs. Resume/reconciliation of the SAME action
                            #   retains its ref and must not dispatch again
budget_reservations:        # "<scope>/<dimension>" -> reservation id, one per capping scope
  competition:<slug>/submissions: RES-0007
  team:<competition-slug>:<team>/submissions: RES-0008
driver: claude-code         # claude-code | codex
submitted_at: null          # filled after dispatch
external_id: null           # filled at reconciliation
```

6. **Dispatch**, then fill `submitted_at`. `SUBMIT` is not complete until the competition's submit call is acknowledged — a push alone is not a submission.
7. **`WAIT_SCORE`** — bounded-backoff polling, not a spin. Keep kernel versions and submission ids so a human can see exactly what was sent and supersede it with a later submission.
8. **Reconcile**: write `external_id` and the score, attribute them to the experiment and run, and update `competition.yaml:best` only when the score is a verified in-deadline improvement. Update the mirrors in the same change.

## Safety

- **A timeout is not a failure.** Query the platform before ever retrying, or duplicate submissions follow. That is what `NEEDS_RECONCILIATION` is for.
- Follow the competition's rules, data rules, team rules and submission limits. Do not try to bypass a submission limit, scrape private data, misuse notebooks, or automate anything the competition prohibits — none of that is affected by how wide autonomy is.
- Kaggle credentials are **read-for-use, not read-to-share**: read `~/.kaggle/kaggle.json`, or the per-account files the dev-phase policy names (`.vscode/.env.harry`, `.vscode/.env.may` — that list, not a pattern), to authenticate a call, and never echo one into the session, a log, a web fetch, a PR or a comment. `.env.production` and `.env.test` are protected and must never be read. Never commit an API token.
- Choosing the competition's final submissions is always the human's, whenever that choice is made.
