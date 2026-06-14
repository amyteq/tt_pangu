# M11-T002: New approval operations + reviewer-gate wiring

## Milestone
M11: authorized CTF / lab workflow. **`arch:` tagged** — introduces three
new approval-policy operations (`challenge_run`, `flag_submit`,
`network_egress`) and wires them through the reviewer-gate path. Discovery
/ Debate Gate evidence (T000, specifically `design-red-team.md`) is the
source of truth for the operation shape and defaults.

## Goal
Add the three new operations to `.kca/permissions/*.yaml`, extend
`src/worker/reviewer.py::should_consult_reviewer`, extend
`src/worker/worker.py::_tool_call` to emit the new `target_op` strings,
add the relevant entries to `.claude/settings.json` and
`.claude/hooks/guard_tool.py`, and document the contract in
`docs/adr/0017-ctf-approval-gates.md`.

## Read first

1. `PROJECT_STATE.md`
2. M11-T000 closeout + `docs/evidence/m11/discovery/design-red-team.md`
3. M11-T001 closeout
4. `docs/adr/0006-configurable-approval-gates.md` — operation data shape
5. `.kca/permissions/default.yaml`, `permissive-dev.yaml`,
   `competition-runner.yaml`
6. `src/worker/reviewer.py` — `should_consult_reviewer`, `run_review`,
   `target_op` shape
7. `src/worker/worker.py` — `_tool_call`, `target_op` extraction
8. `.claude/settings.json` — ask-list pattern for `Bash(kaggle …)` and
   `Bash(gh …)` entries
9. `.claude/hooks/guard_tool.py` — secret denylist pattern
10. `docs/tasks/m9/M9-T003-reviewer-approval-gate.md` (`kaggle_submit`
    precedent)
11. `docs/tasks/m10/M10-T003-kernel-push-reviewer-gate.md` (`kernel_push`
    precedent)

## Scope

1. **Permission policy entries.** Add to each profile:

   ```yaml
   - operation: challenge_run
     default_decision: ask
     reason: Executing a solver against an authorized CTF target — gate by default.
     audit_required: true
   - operation: flag_submit
     default_decision: ask
     reason: Submitting a flag to a CTF event API — external side effect.
     audit_required: true
   - operation: network_egress
     default_decision: deny
     reason: Egress outside ctf_scopes.target_urls is denied; widen scope row to allow.
     audit_required: true
     conditional_allow:
       when_in_scope: ask   # if request URL ∈ ctf_scopes.target_urls
   ```
   In `permissive-dev.yaml`, `challenge_run` and `flag_submit` stay on
   `ask` (no auto-allow for the live submission path). In
   `competition-runner.yaml`, `challenge_run` may move to
   `conditional_allow: allow when_in_scope` but `flag_submit` stays on
   `ask` regardless — flag submission is the highest-blast-radius op.

2. **`src/worker/reviewer.py`.** Extend `should_consult_reviewer` to
   return `True` for the three new ops; extend `run_review` to render
   the right context for each (target URL for `challenge_run` /
   `network_egress`; event slug + challenge slug for `flag_submit`;
   NEVER the flag value).

3. **`src/worker/worker.py`.** Extend `_tool_call` to emit `target_op`
   for the new operations. `challenge_run` fires when a solver tool is
   about to invoke against a target whose URL is in a `ctf_scopes`
   row or is a local in-scope service; `flag_submit` fires when
   `tools/kca/ctf.py::cmd_flag_submit` is invoked with `--dry-run=False`;
   `network_egress` fires when any worker-issued HTTP call's host is
   NOT in the union of `ctf_scopes.target_urls` rows for the current
   project AND NOT on the global allowlist.

4. **`.claude/settings.json`.** Add to the ask-list:
   - `Bash(kca ctf flag submit*)` — ask
   - `Bash(kca ctf solver run*)` — ask (only when `--dry-run=False`)
   - Do NOT add `kca ctf event/challenge/scope` — those are LOCAL_WRITE
     and run under `allow`.

5. **`.claude/hooks/guard_tool.py`.** Extend the secret denylist to
   cover `~/.ctf/*.json`, `**/ctf-credentials.json`, and any path
   matching `CTF_*_TOKEN` env-var dumps. The hook denies direct file
   reads of these paths except when invoked from within
   `tools/kca/ctf.py::_load_event_credentials` (single allow-listed
   call-site).

6. **`docs/adr/0017-ctf-approval-gates.md`.** Document:
   - The three new operations + defaults + `audit_required` flag.
   - The `conditional_allow.when_in_scope` semantics (how the worker
     checks `ctf_scopes.target_urls` membership).
   - Why `network_egress` is deny-default while `challenge_run` and
     `flag_submit` are ask-default.
   - Audit row shape (`agent_reviews` + `human_decisions` + the new
     `agent_tool_audit` columns if any).
   - Cross-link to T000's `design-red-team.md` for alternatives /
     dropped capabilities.

7. **Tests.** Add `tests/test_reviewer_m11.py` covering:
   - `should_consult_reviewer('challenge_run')` → True
   - `should_consult_reviewer('flag_submit')` → True
   - `should_consult_reviewer('network_egress')` → True
   - Reviewer `run_review` for `flag_submit` does NOT include the flag
     value in the rendered context.
   - Permission policy resolution: `challenge_run` in `default.yaml`
     resolves to `ask`; in `competition-runner.yaml` with the worker
     in `when_in_scope` resolves to `allow`.

## Non-goals

- Do not add the `kca ctf` CLI commands. T003 owns those.
- Do not author or insert challenge / event fixtures. T004 owns them.
- Do not exercise the reviewer-gate end-to-end with a real worker
  run. T006 owns the round-trip.
- Do not change any existing operation's `default_decision` for
  `kaggle_submit` / `kernel_push` / `git_push` / etc.

## Acceptance criteria

- Each of `default.yaml`, `permissive-dev.yaml`, `competition-runner.yaml`
  contains the three new operations with the defaults named above.
- `src/worker/reviewer.py::should_consult_reviewer` returns True for
  `challenge_run`, `flag_submit`, `network_egress`.
- `python -m pytest tests/test_reviewer_m11.py -v` → all pass.
- `python -m pytest tests/ services/decision_api/tests -v` → 0
  regressions from M10/M9.
- `ruff check src/ tools/ tests/` clean.
- `.claude/settings.json` ask-list includes the two new `Bash(kca ctf …)`
  patterns.
- `.claude/hooks/guard_tool.py` denies a synthetic read of
  `~/.ctf/test.json` from outside the allow-listed call-site
  (smoke-test with a one-liner).
- `docs/adr/0017-ctf-approval-gates.md` exists with all five sections.

## Permissions

- Local file edits to `.kca/`, `.claude/`, `src/worker/`, `tests/`,
  `docs/adr/`.
- No DB writes in this Loop Prompt (reviewer-gate fires happen in T006).
- No real external network calls.

## Closeout format

```
M11-T002 closeout
  Permission policy entries: 3/3 in default; 3/3 in permissive-dev; 3/3 in competition-runner
  reviewer.py: should_consult_reviewer returns True for {challenge_run, flag_submit, network_egress}
  worker.py: target_op emitted for new ops at <file:line>
  settings.json: Bash(kca ctf flag submit*) on ask; Bash(kca ctf solver run*) on ask
  guard_tool.py: ~/.ctf/*.json deny verified via smoke
  tests/test_reviewer_m11.py: <n> passed
  ADR-0017: docs/adr/0017-ctf-approval-gates.md present (sections: 5/5)
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T003 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T002 closes the "approval gates" bullet.
- Cross-link M10 issue #15 (no `GET /decisions`) — work around the
  same way M10-T003 did; do NOT block M11-T002 on closing #15.
- Cross-link M10 issue #16 (reviewer_decision event_type drift) — same
  posture as M10.

## Stop condition

Stop after 80 turns. If `should_consult_reviewer` cannot be extended
without breaking an existing M9 / M10 test, halt and ask. If the
guard_tool deny-test passes accidentally for the wrong reason (e.g.
the file simply doesn't exist), construct a synthetic file in a
temp dir under `$TMPDIR` and re-run.
