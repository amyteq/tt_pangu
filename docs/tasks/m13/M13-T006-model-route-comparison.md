# M13-T006: Model-route comparison harness (Claude / GPT / local vLLM)

## Milestone
M13: evaluation, reliability, and regression suite.

## Tag
`policy:approval-required` — this is the only Loop Prompt in M13
that may make non-mocked, paid LLM calls. The closing issue MUST
carry `decision:confirmed` + an explicit human-approved budget cap
before this Loop Prompt runs.

## Goal
Wire the existing suites (T002 + T003 + T004 + T005) so each can be
invoked with `--route claude_sonnet_4_6 | claude_haiku_4_5 | gpt_4o |
local_vllm | mocked`. For T006's own report, run a single shared
sub-suite (a 5-case slice of `tool-smoke` + `reasoning`) across all
five routes and write one row per `(suite × route)` into
`eval_results`.

Hard cost cap (default $0.50 / run, env-tunable). Hard time cap
(default 600 s). `--dry-run` honoured. Refuse if
`KCA_ALLOW_REMOTE != 1` for any non-local / non-mocked route.

This task assumes **M13-T005 closeout is PASS** and the M13
proposal issue has the budget cap recorded in a
`decision:confirmed` comment.

## Read first

1. M13-T001 through M13-T005 closeouts.
2. `src/worker/routing.py` (per-job-type routing).
3. `src/worker/local_model.py` (vLLM / Ollama probe + fallback).
4. `docs/adr/0010-model-routing.md` (the precedent).
5. `docs/adr/0011-local-model-endpoints.md` (endpoint config).
6. The project auto-memory entries for local LLM endpoints
   (snorlax RTX 4090 / may RTX 3090).
7. `docs/architecture/eval-regression-suite.md` (route selector
   contract from ADR-0019).
8. `tools/kca/eval/suites/*/` (the five suites this task adapts).

## Scope

1. **Route enum** in `tools/kca/eval/routes.py`:
   - `mocked` — `litellm.mock_completion` with fixture text;
     allowed in any mode.
   - `local_vllm` — uses the existing `KCA_LOCAL_ENDPOINT_*` env
     vars via `src/worker/local_model.py`; needs the LAN-host
     sandbox bypass but no `KCA_ALLOW_REMOTE`.
   - `claude_haiku_4_5` — `anthropic/claude-haiku-4-5-20251001`
     via `litellm`; needs `KCA_ALLOW_REMOTE=1` AND
     `ANTHROPIC_API_KEY`.
   - `claude_sonnet_4_6` — `anthropic/claude-sonnet-4-6` via
     `litellm`; same gating.
   - `gpt_4o` — `openai/gpt-4o` via `litellm`; needs
     `KCA_ALLOW_REMOTE=1` AND `OPENAI_API_KEY`.

2. **Per-suite route adapter.** Each suite module's `run(case,
   route)` learns to route its LLM-relevant cases through the
   selected route. Suites with no LLM-relevant cases
   (tool-smoke, kaggle-replay-*, kernel-dryrun) treat non-`mocked`
   routes as a no-op for the model-call portion of each case
   and emit a `route_no_op=True` metric. The reasoning suite is
   the primary consumer of the route comparison.

3. **Cost + time enforcement.**
   - Per-route cost ledger maintained in-memory; each case's
     `cost_usd` adds to the ledger. If the ledger would exceed
     `--budget` (default $0.50), the harness aborts the remaining
     cases on that route, marks them `status="skip"` with
     `error_text="BUDGET_EXCEEDED"`, and sets
     `eval_runs.aborted_on_budget=true`.
   - Per-run wall-clock cap (default 600 s); same abort behaviour
     with `error_text="TIME_EXCEEDED"`.

4. **`--route` refusal logic.**
   - If `--route` is non-mocked / non-local and
     `KCA_ALLOW_REMOTE != 1`: refuse with
     `{"ok": false, "error": "REMOTE_NOT_APPROVED"}` BEFORE
     any case starts (and BEFORE any API key is read).
   - If the corresponding API key env is missing for a paid
     route: refuse with `{"ok": false, "error":
     "MISSING_API_KEY:<KEY_NAME>"}`.
   - If `--route local_vllm` and `local_model.probe()` returns
     no live endpoint: refuse with `{"ok": false, "error":
     "NO_LIVE_LOCAL_ENDPOINT"}`.

5. **The T006 comparison run.** A dedicated `--route-compare`
   verb on `kca eval run` (or a `--all-routes` flag — design
   choice) that runs a fixed 5-case slice (3 tool-smoke + 2
   reasoning) across all five routes in sequence. Emits one
   row per `(case, route)`. The closing eval_runs row carries
   the total cost.

6. **Wire `external_llm` approval gate.** Per ADR-0006: the gate
   fires once per `eval run` invocation when any non-mocked /
   non-local route is selected. The gate consults the M13
   proposal issue's recorded budget cap. If the requested
   `--budget` exceeds the issue cap, refuse.

7. **Inherit M10-T007 audit-grep sentinel.** Even though T006
   calls real LLM APIs, it does NOT call real Kaggle. The
   sentinel still applies.

## Non-goals

- No real Kaggle calls. None.
- No new top-level CLI subcommands beyond a sub-verb of
  `kca eval run`.
- No new tables — emit into `eval_results.metrics_jsonb`.
- No LLM-quality gating — T006 baselines values; future
  milestones decide on score-delta gates between routes.
- No fine-tuning, no caching warm-up, no custom system prompts
  beyond what each suite already ships.

## Acceptance criteria

- `tools/kca/eval/routes.py` exports the five-route enum and a
  `resolve(route, *, allow_remote, env) -> RouteSpec` helper.
- `kca eval run --suite tool-smoke --route mocked --dry-run
  --json` continues to PASS unchanged from T002 (the route
  plumbing is additive).
- `kca eval run --suite reasoning --route mocked --dry-run
  --json` continues to PASS unchanged from T005.
- `kca eval run --route-compare --dry-run --json` (mocked only,
  no `KCA_ALLOW_REMOTE`) exits 0, produces 5 cases × 5 routes
  = 25 `eval_results` rows. Non-mocked routes report
  `status="skip"` with `error_text="REMOTE_NOT_APPROVED"` (or
  `MISSING_API_KEY:*`).
- `kca eval run --route-compare --route claude_haiku_4_5` without
  `KCA_ALLOW_REMOTE=1` refuses cleanly with the
  `REMOTE_NOT_APPROVED` payload BEFORE any case starts.
- Budget cap exceeded mid-run sets `aborted_on_budget=true` and
  marks remaining cases `skip`.
- Audit-grep guard PASSes: 0 lines matching the four forbidden
  Kaggle CLI commands.
- `ruff check .` + `ruff format --check .` clean.
- `pytest tests/ services/decision_api/tests` — 0 regressions.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- Real LLM calls — ALLOWED only via the `external_llm` gate AND
  with `KCA_ALLOW_REMOTE=1` AND with the M13 proposal issue
  carrying a `decision:confirmed` budget cap.
- Real Kaggle calls — NOT ALLOWED.
- LOCAL_WRITE Supabase — ALLOWED.

## Closeout format

```
M13-T006 closeout
  Routes wired: mocked, local_vllm, claude_haiku_4_5, claude_sonnet_4_6, gpt_4o
  --route-compare run (dry-run, mocked-only): <run_id>
    eval_results rows: <N> (5 cases × 5 routes; mocked PASS, others SKIP with REMOTE_NOT_APPROVED)
  --route-compare run (live, if approved): <run_id> | not run (decision not confirmed)
    cost_usd: <c> / budget_usd <b>
    aborted_on_budget: <true|false>
  Refusal verified: REMOTE_NOT_APPROVED, MISSING_API_KEY:*, NO_LIVE_LOCAL_ENDPOINT
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  pytest: <X> passed / <Y> skipped (0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS
  Next: M13-T007 (metrics aggregator + report)
```

## Related issues

- M13 proposal issue — carries the live-LLM budget cap.

## Stop condition

Stop after 80 turns. HALT and ask if:
- The budget cap on the proposal issue is missing or unclear.
  Do NOT run any non-mocked route until a human comment confirms
  the cap (default recommendation: $0.50 / run for the shared
  5-case slice).
- Any non-mocked route call reaches the network before the
  `REMOTE_NOT_APPROVED` / `MISSING_API_KEY` checks. That is a
  P0 leak — surface immediately.
- A local-vLLM endpoint is reachable but emits drift from the
  fixture text for the same input. Mark the route comparison
  row as informational (`status="pass"`, but record the drift).
