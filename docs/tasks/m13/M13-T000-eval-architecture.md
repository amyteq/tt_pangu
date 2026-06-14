# M13-T000: `arch:` Regression-suite architecture + ADR-0019 (Discovery / Debate Gate)

## Milestone
M13: evaluation, reliability, and regression suite.

## Tag
`arch:` — introduces a new architectural primitive (the eval
regression-suite framework). Triggers the **Discovery / Debate Gate**
per `docs/milestone-loop-protocol.md` §7.

## Goal
Write the canonical M13 design docs — `docs/adr/0019-eval-regression-suite.md`
(decision record) and `docs/architecture/eval-regression-suite.md`
(architecture and data-flow). Run the Discovery / Debate Gate
(`legacy-archaeologist` optional / skippable for greenfield;
`requirements-skeptic` mandatory; `design-red-team` mandatory) and
attach all three transcripts under `docs/evidence/m13/T000/discovery/`.

No code, no migration, no CLI changes in this Loop Prompt. Design
and discovery only.

## Read first

1. `docs/milestones/README.md` §M13
2. `docs/milestone-loop-protocol.md` §7 (Discovery / Debate Gate)
3. `docs/architecture/discovery-debate-gate.md` (canonical acceptance
   lines for the three agents)
4. `.claude/agents/requirements-skeptic.md`
5. `.claude/agents/legacy-archaeologist.md` (you will likely skip
   this one — document the skip in the closeout)
6. `.claude/agents/design-red-team.md`
7. `docs/adr/0010-model-routing.md` (route-routing precedent)
8. `docs/adr/0013-otel-console-sqlite-supabase.md` (multi-exporter
   precedent — eval reports may borrow this shape)
9. `docs/architecture/kca-cli-architecture.md` (existing four-layer
   CLI shape; `kca eval` will be a new top-level command)
10. `docs/adr/0006-approval-gate-policy.md` (approval gate posture
    for the new `external_llm` gate at T006)
11. `src/worker/routing.py` (per-job-type routing this milestone
    will reuse for T006's `--route` selector)
12. `tools/kca/run.py` (existing run-artifact layout — `runs/<comp>/<id>/`)
13. `tests/test_m9_e2e.py`, `tests/test_m10_e2e.py` (the closest
    "offline replay" precedents)

## Scope

1. **Run the Discovery / Debate Gate.**
   - Decide whether `legacy-archaeologist` applies. Greenfield is the
     default here: M13 introduces a new subsystem with no direct
     legacy artefact. The skip is acceptable IF you document it
     explicitly in the closeout AND the M13 proposal issue has a
     `decision:confirmed` comment naming the skip.
   - Invoke `requirements-skeptic` against the M13 description in
     `docs/milestones/README.md`. Expect ≥5 questions across ≥3 categories
     (scope, schema, routing, secrets, replay-stability, …) plus a
     non-empty `explicit_unknowns` list. Save the transcript under
     `docs/evidence/m13/T000/discovery/requirements-skeptic.md`.
   - Invoke `design-red-team` against a strawman draft of ADR-0019
     (write the strawman first, then red-team it). Expect ≥3
     alternatives, ≥1 dropped capability with file:line evidence
     from the current repo, 4 cost axes, actionable
     `open_disagreements`. Save under
     `docs/evidence/m13/T000/discovery/design-red-team.md`.
   - Verify all canonical acceptance lines byte-for-byte against
     `docs/architecture/discovery-debate-gate.md`. A missing
     acceptance line is a task FAIL.

2. **Write `docs/adr/0019-eval-regression-suite.md`.** Decisions
   covered (non-exhaustive):
   - Schema choice: three new tables (`eval_suites`, `eval_runs`,
     `eval_results`) vs single wide table. Argue for three.
   - Driver shape: per-suite Python module under
     `tools/kca/eval/suites/<name>/` exposing a `register()` +
     `run(case, route) -> EvalResult` contract. Argue why.
   - Route selector: reuse `src/worker/routing.py`'s job-type
     routing as the source of truth for `--route` values, plus a
     `mocked` route that returns `litellm.mock_completion`.
   - Cost gate: `external_llm` gate fires per route invocation
     (not per case) to avoid N×cost runaway; hard cap honoured by
     the harness, not by `litellm`.
   - Fixture posture: every Kaggle replay reads frozen sub-samples
     under `tests/fixtures/<comp>/` (≤ ~5 MB total per fixture);
     real Kaggle network is never reachable from any suite.
   - Replay determinism: every suite seeds `random.seed(0)` +
     `numpy.random.seed(0)` and pins the route-emitted text via
     `litellm.mock_completion`'s fixture string when `--route
     mocked` is selected.

3. **Write `docs/architecture/eval-regression-suite.md`.**
   Include:
   - ASCII data-flow: `kca eval run` → suite driver → cases →
     `eval_results` row → `kca eval report` → JSON + Markdown.
   - Table layout for each of the three new tables (column,
     type, nullable, FK).
   - Per-suite metric definitions (which suite emits which
     metric key into `eval_results.metrics_jsonb`).
   - Where each route's secrets are read (`ANTHROPIC_API_KEY`,
     `OPENAI_API_KEY`, `KCA_LOCAL_ENDPOINT_*` env vars) and
     which routes need `KCA_ALLOW_REMOTE=1`.
   - The "audit-grep sentinel" — every M13 suite must inherit
     the M10-T007 guard (0 lines for `kaggle competitions submit`
     / `kaggle kernels push` / `kaggle datasets create` etc.
     reach the kaggle CLI from any suite process).

4. **File the M13 proposal issue** using
   `.github/ISSUE_TEMPLATE/feature-work.yml`. Body links ADR-0019,
   the architecture doc, and the three discovery transcripts.
   Labels at file: `arch:`, `type:feature`, `area:eval`,
   `area:docs`, `decision:needed`, `ai:triage`. Promote to
   `decision:confirmed` + `ai:ready` only after a human confirms
   the gate skip (if any) and the live-LLM budget cap for T006.

## Non-goals

- Do not write any migration SQL. Migration 0010 lands in T001.
- Do not write any Python under `tools/kca/eval/` or new CLI
  subcommand registration. T001 owns the scaffold.
- Do not modify `src/worker/`, `tools/kca/db.py`, `tools/kca/kca.py`,
  or `supabase/migrations/`.
- Do not skip `requirements-skeptic` or `design-red-team`. They are
  mandatory under M9.4.

## Acceptance criteria

- `docs/adr/0019-eval-regression-suite.md` exists; covers all
  decisions in scope step 2; cross-links the architecture doc.
- `docs/architecture/eval-regression-suite.md` exists; covers all
  items in scope step 3; ASCII data-flow renders.
- `docs/evidence/m13/T000/discovery/requirements-skeptic.md`,
  `design-red-team.md`, and (if not skipped)
  `legacy-archaeologist.md` exist. If `legacy-archaeologist` is
  skipped, a `SKIP-NOTE.md` in the same directory states why and
  cites the greenfield argument.
- All three canonical acceptance lines from
  `docs/architecture/discovery-debate-gate.md` appear verbatim in
  the corresponding transcripts.
- The M13 proposal GitHub issue exists, links the four docs above,
  and carries `arch:`, `decision:needed`, `ai:triage` at file time.
- `ruff check .` and `ruff format --check .` — clean (no Python
  changed but verify the worktree).
- No source code (`src/`, `tools/`, `tests/`, `ui/`,
  `supabase/migrations/`) modified.

## Permissions

- `git add` / `git commit` deferred to milestone closeout (T009).
- `gh issue create` for the M13 proposal issue — ALLOWED (non-
  destructive write per `docs/engineering-practice.md`).
- No real Kaggle / Anthropic / OpenAI calls.

## Closeout format

```
M13-T000 closeout
  ADR: docs/adr/0019-eval-regression-suite.md (written; <n> decisions)
  Architecture: docs/architecture/eval-regression-suite.md (written; ASCII data-flow + 3 table layouts)
  Discovery / Debate Gate:
    legacy-archaeologist: SKIP (greenfield; see SKIP-NOTE.md) | RAN (see <path>)
    requirements-skeptic: RAN — <n> questions across <c> categories; explicit_unknowns: <list>
    design-red-team: RAN — <n> alternatives; <m> dropped capabilities; open_disagreements: <list>
  Canonical acceptance lines: 3/3 verified byte-for-byte
  Proposal issue: <url> — labelled arch:, decision:needed, ai:triage
  Acceptance: PASS — design + gate complete; no code changed
  Next: M13-T001 (migration 0010 + kca eval CLI scaffold) — BLOCKED until proposal issue reaches decision:confirmed + ai:ready
```

## Related issues

- M13 proposal issue (filed in this Loop Prompt) — canonical
  decision record for the milestone.
- M9.4 (Discovery / Debate Gate) — the gate this task exercises.

## Stop condition

Stop after 80 turns. HALT and ask if:
- Any of the three canonical acceptance lines cannot be produced
  byte-for-byte. The agent definitions in `.claude/agents/` are
  the source of truth — don't paraphrase.
- The strawman ADR-0019 lands more than one major schema decision
  that the `design-red-team` agent flags as load-bearing without
  evidence. Add evidence or split into a follow-up ADR.
- The M13 proposal issue cannot reach `decision:confirmed` because
  a load-bearing question lacks a human answer (e.g. T006 budget
  cap). Leave the issue at `decision:needed` and surface the
  unanswered questions in the closeout.
