# requirements-skeptic report for M13-T000 (eval regression-suite framework)

Source: `docs/tasks/m13/M13-T000-eval-architecture.md`,
strawman `docs/adr/0019-eval-regression-suite.md`,
companion `docs/architecture/eval-regression-suite.md`,
parent `docs/milestones/README.md §M13`,
parent `docs/milestones/m13/loop-prompts.md §"M13 at a glance"`.

Upstream: legacy-archaeologist SKIPPED — see
`docs/evidence/m13/T000/discovery/SKIP-NOTE.md` (greenfield).

_Produced under the M9.4 Discovery / Debate Gate. The agent body
lives in `.claude/agents/requirements-skeptic.md`; this artefact is
a manual execution of that agent's protocol against the proposed M13
regression-suite framework, following the precedent set by
`docs/evidence/m9_4-kkr-replay/requirements-skeptic.md`._

Acceptance line (verbatim):

> Output MUST contain ≥5 questions spread across ≥3 categories, and
> an `explicit_unknowns:` section listing things the agent could not
> answer without human input.

## hidden_constraints

1. What is the hard upper bound (rows × suites) the platform commits
   to on `eval_results` before partitioning or rollups become
   mandatory? — consequence if unanswered: a year of nightly cron runs
   at 5 suites × 10 cases × 5 routes ≈ 91,250 rows; ten years ≈ 900k.
   Without an explicit retention policy, the table grows unboundedly
   and the report aggregator's `(eval_run_id, suite_id, route)` scan
   silently becomes slow.
2. Does ADR-0019 commit to a metric-schema versioning convention so
   the M13.1 / M13.2 / M14 suites can add `metrics_jsonb` keys
   without breaking the T007 report aggregator? — consequence: the
   first downstream suite that emits a new key either crashes the
   report or is silently dropped, depending on which side wins the
   race.
3. Is the `external_llm` gate's budget cap charged against the
   project (`projects.id`) or the run (`eval_runs.id`)? — consequence:
   project-level caps share across runs (nightly cron + manual runs
   compete for the same budget); run-level caps reset per invocation
   (a malicious or buggy caller can run the suite 100 times in a row
   each at the cap). ADR-0006's per-project / per-job hierarchy
   exists but ADR-0019 does not explicitly name which level wins.
4. What does "≤ ~5 MB per fixture" cumulatively mean across the
   ~5–7 suites M13 ships, plus the deferred M13.1 / M13.2 suites? —
   consequence: 5 MB × 10 fixtures = 50 MB in the repo, which is fine;
   5 MB × 30 fixtures (after CTF + Devpost land) = 150 MB, which
   begins to matter for shallow clones, Codespaces start-up time,
   and the GitHub UI's per-blob 10 MB rendering cap. ADR-0019
   §"Fixture posture" says ≤ ~5 MB *per fixture*; the total budget
   is not pinned.
5. Is the `git_sha` recorded on `eval_runs` the worktree SHA, the
   nearest `main` SHA, or the SHA of the task spec the harness was
   invoked under? — consequence: in worktree mode (the
   milestone-loop-protocol §5 default) the active branch SHA can
   drift far ahead of `main`; a row labelled with the worktree SHA
   is reproducible but a row labelled with the `main` SHA is
   comparable across runs. The two answer different questions and
   the architecture doc does not pick.
6. What is the policy for retaining `runs/m13-eval/<ts>/audit/` log
   directories on disk? — consequence: per-case audit logs accumulate
   under `runs/m13-eval/<ts>/audit/<suite>/<case>.log`; with a nightly
   cron that is 365 × 5 × 10 = 18,250 files per year and a
   per-worktree disk-cost. Is there a rotation rule? A retention
   window? ADR-0008's local-first artefact policy implies forever;
   M13's cron mode implies "until the next run, plus the previous
   one, plus the last green".

## personas_and_accounts

1. Who is the "owner" of an `eval_runs` row that was triggered by the
   nightly cron in `.github/workflows/eval.yml` (T008)? — consequence:
   `projects.id` is nullable per the architecture doc, but the row
   then has no human-attributable owner. If the cron stops being
   reliable, who in the team is paged? Without an owner field
   anchored to a GitHub identity or service account, the cron
   becomes a no-mans-land artefact.
2. Does the route-comparison harness (T006) record the *Kaggle* /
   *GitHub* / *project owner* identity that approved the live-LLM
   budget cap on the M13 proposal issue? — consequence: the budget
   cap is approved by a human comment, but the `eval_runs` row only
   carries the cap value, not the approver. An audit "who approved
   $X on date Y" requires cross-referencing the issue comment by
   hand. ADR-0006's `human_decisions` row carries this; M13's
   `eval_runs` does not link to it.
3. The architecture doc §"Route secrets map" says secrets are read
   only via `src/worker/routing.py`. But the harness, when running
   `--route gpt_4o`, still needs `OPENAI_API_KEY` in its process
   environment. Is the eval harness one process or per-suite
   subprocesses, and where does the env-isolation boundary land? —
   consequence: a single-process harness inherits `os.environ`
   exactly as it was at `kca eval run` time, which means a stray
   `KAGGLE_USERNAME` or `OPENAI_API_KEY` from a sibling shell leaks
   into the run. ADR-0019 does not commit to the boundary.
4. Are M13's eval rows readable by Supabase RLS roles the platform
   already defines, or does the migration add a new role? —
   consequence: without an explicit policy, anonymous-role reads
   either return everything (privacy regression vs `agent_jobs`
   precedent) or nothing (UX regression: the platform UI cannot
   render the rolling diff M13-T008 promises).
5. Does the `mocked` route's fixture string carry any user data that
   would be sensitive if leaked? — consequence: if a fixture
   captured a real LLM completion that contained a real submission
   message or a leaked path, it goes into the repo. The team needs a
   scrub policy *before* the first fixture lands, not after.

## side_effects

1. The harness writes `eval_runs` / `eval_results` rows on every
   invocation. What reverses a bad run? — consequence: today there is
   no "rollback an eval run" CLI verb. If a flaky test polluted the
   table with `status=aborted_on_error`, those rows persist and the
   T007 report aggregates them. Is a manual SQL delete the intended
   recovery path, or does `kca eval delete --run-id <uuid>` need to
   land in T001?
2. The harness writes per-case audit logs under
   `runs/m13-eval/<ts>/audit/<suite>/<case>.log`. These files
   could capture suite-internal text (stdout / stderr) that
   incidentally contains credential-shaped substrings (a path with
   `/home/<user>/`, a process-list dump from a tool that ran in a
   misconfigured shell). What scrubs them? — consequence: a single
   accidental commit of `runs/m13-eval/<ts>/` to the M13 PR for
   posterity ships sensitive substrings to GitHub. The
   loop-prompts doc says `report.md` is committed; it does NOT say
   `audit/*.log` is committed. The intent is "no", but it is not in
   `.gitignore`.
3. T006's route-comparison run may make 5 routes × 5 cases = 25 live
   LLM calls in a single dispatch. What is the failure mode if the
   network drops mid-run? — consequence: the harness aborts cleanly
   per ADR-0019, but the `eval_runs` row is left in `status=running`
   forever unless a heartbeat or timeout exists. Does the harness
   have a "running for >N seconds → aborted_on_error" sweeper?
4. The nightly cron pushes a `gh issue comment` with the rolling
   diff against the previous nightly (per M13-T008). Which issue?
   Does it accumulate as noise on the M13 proposal issue, or does it
   target a dedicated long-lived "eval rollups" issue? —
   consequence: appending to the M13 proposal issue would, after a
   year, drown the original decision record under nightly diff
   comments and break GitHub's 65k-char per-comment cap.
5. The audit-grep guard triggers `aborted_on_error` on any violation
   and writes that to `eval_runs`. Does the same violation also page
   a human, or is it a silent abort visible only when someone reads
   the next morning's nightly report? — consequence: the M10-T007
   sentinel's whole point is that a leak is a P0. A row in a table
   nobody checks is not a page.

## edge_cases

1. What happens when `kca eval run --suite kaggle_replay_titanic
   --route mocked` is invoked against a Supabase that does not have
   migration 0010 applied (e.g. a stale local container)? —
   consequence: insert fails on missing table. Does the harness
   fail-fast with a friendly error, or does it crash mid-run with
   leftover state? ADR-0019 implies fail-fast; the architecture doc
   does not say.
2. Two `kca eval run` invocations launched concurrently against the
   same project — are they serialised by `eval_runs.status=running`,
   or do they cooperate? — consequence: two cron-style runs in a row
   could double-charge the budget cap if it is project-scoped (see
   §hidden_constraints #3) and could write interleaved audit logs
   if the `runs/m13-eval/<ts>/` timestamps collide at second
   resolution.
3. What happens when the route's mock fixture is updated but the
   suite forgot to bump its `case_slug`? — consequence: the report
   aggregator silently joins old and new metrics under the same
   `(suite, case)` pair, producing a misleading delta. Is there a
   fixture-content hash recorded in `context_jsonb` to detect this?
4. The `local_vllm` route probes the LAN endpoint at run-start. What
   happens when the endpoint is down (the auto-memory note
   `reference_local_llm_endpoints.md` says snorlax is RTX 4090 and
   may is often off)? — consequence: per ADR-0010's existing
   fallback model logic, the route resolves to the fallback. Is the
   `eval_results.route` column then the requested route, the
   resolved route, or both? Without recording both, the metrics
   diff between routes loses meaning.
5. What is the suite's behaviour when a fixture file is missing or
   has a wrong SHA? — consequence: a flaky `git lfs` pull or a
   corrupt clone makes the suite either silently skip
   (false-negative cause) or hard-fail (CI red but unactionable).
   The choice should be explicit.
6. The `requires_db: true` suites SKIP without `SUPABASE_DB_URL`.
   But does the harness ALSO skip writing `eval_runs` / `eval_results`?
   — consequence: a skip that does not write a row is invisible to
   the report aggregator (which only sees the rows that exist); the
   nightly cron then under-reports coverage and the rolling diff
   spuriously regresses.

## rollback

1. What proves a `kca eval` deployment can be reverted? — consequence:
   migration 0010 adds three new tables; a revert needs `DROP TABLE
   IF EXISTS eval_results, eval_runs, eval_suites CASCADE`. There is
   no `0008_revert.sql` convention in the repo today. Is the answer
   "revert via PR + rerun the prior migration head", or is a
   separately-shipped revert SQL part of T001's scope?
2. What state would block a clean revert? — consequence: a foreign
   key from a future migration (say M14 adds an
   `eval_run_attribution` table that points at `eval_runs.id`)
   would make the cascade harder. Today no such FK exists; ADR-0019
   does not commit to "no inbound FKs to eval_* until T008
   stabilises".
3. If T008's nightly cron starts spuriously failing CI on a known-
   good `main`, can the cron be disabled without a code change? —
   consequence: a `KCA_DISABLE_EVAL_CRON=1` env var on the workflow
   is the standard escape hatch; without it the only revert is a
   PR that touches `.github/workflows/eval.yml`, which is slow when
   the CI is failing red.
4. If a suite is found to leak a credential pattern (audit-grep
   violation, dotenv read, kaggle CLI call), what is the
   `kca eval disable --suite <slug>` story? — consequence: the
   architecture doc has no such verb. Today the only mitigation is
   "delete the suite directory and re-run the migration to drop the
   `eval_suites` row" — which is a code change at 3am, exactly the
   ops-burden ADR-0006 was meant to avoid.

## explicit_unknowns

- Budget-cap scoping: project-level vs run-level. ADR-0006's
  hierarchy exists but ADR-0019 must name which level the
  `external_llm` gate consults.
- `eval_results` retention / partition policy. Indefinite growth is
  the implicit default; M13 should either accept it explicitly or
  pick a windowed-retention rule.
- Metric-schema versioning convention for `metrics_jsonb` keys.
  M13.1 / M13.2 / M14 will add keys; the T007 aggregator needs a
  forward-compatible parsing rule.
- Where the rolling-diff cron comment lands (M13 proposal issue vs
  dedicated "eval rollups" issue).
- Audit-log retention under `runs/m13-eval/<ts>/audit/`. The
  loop-prompts doc commits to checking in `report.md`; the audit log
  directory's commit posture is unspecified.
- Cap on per-fixture and total-fixture sizes. Per-fixture ≤5 MB is
  named; total budget across all suites (M13 + M13.1 + M13.2) is
  not.
- Env-isolation boundary for paid-route invocations (single-process
  harness vs per-suite subprocess).
- `git_sha` recorded on `eval_runs`: worktree HEAD vs nearest
  `main` ancestor.
- Reverse / disable / delete CLI verbs for a bad `eval_run` or a
  leaky suite (`kca eval delete`, `kca eval disable`).
- Whether the `local_vllm` route's fallback resolution is recorded
  in `eval_results.route` (requested vs resolved).
- Approver-identity capture for the `external_llm` gate (link
  `eval_runs.id` to a `human_decisions.id`).
- RLS policy posture on the three new tables under the platform's
  anon / authenticated roles.
