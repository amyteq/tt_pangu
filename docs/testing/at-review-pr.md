# at-review-pr skill validation

Issue: [#207](https://github.com/amyteq/tt_pangu/issues/207). Validated 2026-09-15
against base `8f950823257aa2476fa356294d13448ab196ac60`, then re-checked on
2026-09-16 after rounds 1 and 2 of the live loop on
[PR #208](https://github.com/amyteq/tt_pangu/pull/208) (the skill was named
`pr-review-loop` in the earlier revision).

The deliverable is a Markdown development skill and two supporting references.
It adds no execution service, helper scripts, runtime configuration, or test code.
The [skill](../../.claude/skills/at-review-pr/SKILL.md) is canonical; the
[README](../../README.md#claude-code-project-skills) supplies discovery and invocation.

## Checks (2026-09-15, revision before the round-1 review)

| Check | Result | Acceptance criteria |
|---|---|---|
| Skill Creator `quick_validate.py` on the skill directory | PASS: frontmatter/name/body validation | AC1, AC7 |
| Relative Markdown references | PASS: all 3 skill-internal links resolve | AC1, AC7 |
| Installed CLI help | PASS: documented options exist in Codex 0.154.0 and Claude Code 2.1.272 | AC2 |
| Four launch examples, executed with local stub CLIs | PASS: shell syntax, quoted model/config/MCP arguments, literal stdin, and the then-present process-local Claude effort variable (since removed — see the round-2 probes) | AC2 |
| Independent behavioral simulation | PASS after the correction below; cases listed below | AC1–AC6 |
| `python -m pytest tests/ services/decision_api/tests -q --tb=short -p no:cacheprovider --basetemp=/tmp/issue207-pytest-clean` | 402 passed, 47 skipped in 39.22 s | AC7 |
| `ruff check --no-cache .` | PASS (Ruff 0.15.14) | AC7 |
| `ruff format --check --no-cache .` | Existing failure: 20 files would be reformatted, 371 already formatted; identical result in the original checkout and worktree | AC7 |
| `git diff --check` | PASS | AC7 |

The successful pytest run used the project-compatible interpreter already active
in that shell; resolve one against `requires-python` in `pyproject.toml` at run
time instead of pinning a patch version or an environment-manager path here.
Inherited service variables (`SUPABASE_*`, `KCA_*`, `KAGGLE_*`,
`ANTHROPIC_*`, `OPENAI_*`, `DEVPOST_*`, `CTFTIME_*`, `PG*`, `DATABASE_*`) were removed
from the child environment; `KCA_SKIP_DOTENV=1` and `PYTHONDONTWRITEBYTECODE=1`
were set. An earlier sandboxed attempt was stopped after inherited DB settings
selected unavailable DB tests; a diagnostic stopped at 1 failure / 50 passes.
The clean-environment rerun above is the completed local validation.

Formatting differences are all in unchanged competition/analysis files; this PR
does not format them. No UI, migration, or live-service tests were needed for the
Markdown-only change. The stub checks used prompt paths with spaces and literal
shell metacharacters; neither Codex nor Claude was actually invoked by those checks.

## Independent behavioral scenarios

A fresh evaluator received the skill, references, realistic requests, and mock PR
snapshots/agent outputs. It produced ordered role invocations, ledger transitions,
budget counts, and terminal actions without network access or repository writes.
Provider/model metadata and permission results in these cases were simulated.

| Case | Observed behavior |
|---|---|
| One round, fix at H2, author is signed-in user | Full → writer → final full; fix verified; eligible comment, no self-approval attempt |
| Four-round limit with `claude codex`, fixed P1 and deferred P2 | Full → writer → delta → closing full; stops after 2 rounds / 1 writer; formal approval eligible |
| Two rounds with `codex codex`, valid deferred P1 | Distinct sessions; last numbered review is full; accepted deferral stays blocking; no repeated writer |
| One round, final verification discovers a new P2 | Keeps P2 as residual work; no extra writer; proceeds to approval eligibility |
| Another session pushes after the full review | Detects head movement before approval and stops for reconciliation |
| Zero/fractional rounds, unknown provider, extra argument | Rejects before role launches or writes |
| Two candidate PRs with no explicit target | Requests target selection without guessing |
| Runtime metadata differs from generated signature | Rejects the claimed profile; stops rather than accepting the report |
| Publication timeout with inconclusive readback | Preserves the marker/body; stops without duplicating the write |

The first evaluation found an ambiguity when final verification discovered a P2:
the exhausted-budget branch could be read as skipping the otherwise eligible
approval. Step 6 now explicitly routes residual P2/P3 through the terminal approval
check and treats exhausted fix budget separately from actual approval status.
The evaluator rechecked that correction against the same case.

## Re-checks after the round-1 review (2026-09-16)

Round 1 of the live loop on PR #208 requested the rename to `at-review-pr`, the
`argument-hint` / `disable-model-invocation` frontmatter, a default of 10 rounds,
linked short-SHA comment headers, two-line signatures with defined fields, and
removal of the pinned interpreter version above. Those are documentation and
invocation-metadata changes, so only the checks below were re-run; the pytest and
Ruff results above stand as historical observations for this Markdown-only diff.

| Check | Result |
|---|---|
| Frontmatter parsed as YAML, including `argument-hint` (string) and `disable-model-invocation` (boolean `false`) | PASS |
| Skill Creator `quick_validate.py` on a temporary copy with those two keys removed | PASS: "Skill is valid!" |
| Skill Creator `quick_validate.py` on the skill as committed | Rejected: the portable validator allows only `name`, `description`, `license`, `allowed-tools`, `metadata` |
| Relative Markdown links across the skill, both references, the README entry, and this file | PASS: 7 links resolve; placeholders inside the report templates are not links |
| `bash -n` on the four launch examples, unchanged in this revision | PASS |
| `git diff --check` | PASS |

`argument-hint` and `disable-model-invocation` are supported Claude Code skill
frontmatter fields ([frontmatter reference](https://code.claude.com/docs/en/skills#frontmatter-reference));
the installed `quick_validate.py` accepts only the portable Agent Skills keys, so
its rejection is a validator limitation rather than a skill defect. No validator,
hook, or settings file was modified to obtain these results.

## CLI runtime-metadata probes (2026-09-16, round 2)

The round-1 loop stopped because Claude's effort setting could not be observed.
The author then decided that an unobservable effort may be published as the
requested value. These probes establish, per CLI, which signature fields are
actually retrievable, and are the evidence behind
[runtime metadata](../../.claude/skills/at-review-pr/references/agents.md#runtime-metadata).

| Probe | Observed |
|---|---|
| `codex exec --model gpt-5.6-sol --config model_reasoning_effort=xhigh --sandbox read-only --ephemeral` (default output) | stderr header block: `model: gpt-5.6-sol`, `provider: openai`, `approval: never`, `sandbox: read-only`, **`reasoning effort: xhigh`**, `session id:`; no context window |
| Same command with `--json` | only `thread.started`, `turn.started`, `item.completed`, `turn.completed` — the header, model and effort are absent |
| `claude -p --output-format stream-json --verbose` | `system`/`init` carries `model`, `tools`, `permissionMode`, `claude_code_version`; the final `result` carries `modelUsage[<model>].contextWindow`, `canonicalModel`, `terminal_reason`, `is_error`. **No effort field in any event** |
| `claude -p --effort bogus` | exit 0 with stderr `Warning: Unknown --effort value 'bogus' — ignoring it and using the default effort. Valid values: low, medium, high, xhigh, max.` — an invalid value is non-fatal, so stderr must be captured |
| `CLAUDE_CODE_EFFORT_LEVEL=bogus claude -p --effort high` | no warning and no behavior change: the variable is not recognized by Claude Code 2.1.273, so the earlier env-var prefix in the launch forms was unsupported and is removed |

Consequences applied to the skill: `codex exec` keeps its default output mode and
redirects stderr to the phase metadata file, because `--json` would discard the
only model/effort evidence; every launch form now captures stderr; effort that a
CLI never reports is published as `xhigh (requested)` and no longer blocks a
phase, while agent, model and timing stay verify-or-block. Codex CLI 0.154.0 and
Claude Code 2.1.273; probes used a cheap model where the field's presence, not
its value, was the question.

## Live loop on PR #208, run `pr208-20260916b` (2026-09-16)

The skill was exercised against its own PR. Round 1 reviewer: `codex exec`
`gpt-5.6-sol` at `xhigh`, read-only, full review of `8f95082..21d155e`; the
stderr header confirmed model and effort, so that phase is fully attested. It
raised two P1 findings and both were valid:

| ID | Finding | Outcome |
|---|---|---|
| F001 | "The writer must disposition every open finding, including P2/P3" contradicted the rule that a closing verification-only review grants no writer phase, so a cosmetic finding raised there could be read as blocking approval forever | Fixed: the disposition duty is scoped to findings routed to a writer phase; a P2/P3 first raised by the closing review is recorded as residual work, while a P0/P1 raised there still blocks |
| F002 | The metadata instructions told the coordinator to validate runtime fields from `phase_meta`, but Claude reports model, context, session and completion on **stdout** in the JSON result object, not on stderr | Fixed: the metadata table and the launch-form text name the stream per provider — `phase_meta` for Codex, `phase_output` for Claude, with Claude's stderr still captured for the effort warning |

The round-1 writer phase (`claude -p`, `claude-opus-5[1m]`, `--effort xhigh`)
ran and produced a complete, correct edit plan for both findings, but **every
write to `.claude/skills/**` was denied** by the harness protection on skill
files — via `Edit` and via `Bash(touch)` alike. It correctly refused to disable
hooks or broaden the sandbox, reported the exact denied action, and returned both
findings as `blocked` rather than claiming a fix. The coordinator then applied
the writer's specified edits verbatim under its own approval, which is the
"host's normal approval mechanism" the launch-form rules point to.

That is a real operating limitation worth stating plainly: **a Claude writer
phase cannot edit this skill's own files under the default harness permissions**,
so self-application of `at-review-pr` to a PR touching `.claude/skills/**`
requires coordinator escalation for the write step. A writer phase on any other
part of the repository is unaffected. The round-1 writer's JSON also confirmed
`modelUsage["claude-opus-5[1m]"].contextWindow == 1000000` and
`canonicalModel == "claude-opus-5"` on stdout — the direct evidence behind F002.

Round 2 was a full closing verification review of head `bddee5c` by the same
reviewer profile (`codex exec`, `gpt-5.6-sol`, `xhigh`, read-only). It did not
close clean: it found F001 and F002 resolved but raised one residual P2 — F003,
that this record's Limits section still asserted an offline boundary its own live
probes and live rounds had outgrown — alongside an approval-eligible verdict with
no unresolved P0/P1.

| Round | Phase | Outcome |
|---|---|---|
| 3 | writer (`claude -p`, `claude-opus-5[1m]`, `--effort xhigh`) | Edited this file and committed `09b214e` **itself, with no permission denial** — `docs/` is outside the protected skill path, so no coordinator escalation was needed |
| 4 | reviewer (same profile as rounds 1–2) | Full review of `09b214e`: F001/F002 still resolved, no new findings, no unresolved P0/P1, but **F003 reopened** — the round-3 writer described the loop while its own round was still running, so the record kept counting one writer phase and calling round 2 clean |

The round-4 writer phase fixes that staleness in this revision; the round-4
verification of the fix had not run when this paragraph was written.

## Limits

**Proven live, on this host.** The installed providers' runtime-metadata schema —
which signature fields exist, and on which stream — for Codex CLI 0.154.0 and
Claude Code 2.1.273. Live model access for both providers. Three real reviewer
phases (`codex exec`, `gpt-5.6-sol`, `xhigh`, read-only) — the round-1 full
review, the round-2 closing verification, and the round-4 verification — and two
real writer phases (`claude -p`, `claude-opus-5[1m]`, `--effort xhigh` requested,
1M context window confirmed in `modelUsage`). Two real review → fix →
verification cycles on PR #208; neither verification closed clean, since round 2
raised F003 and round 4 reopened it.

**Still not proven.** GitHub review permissions for a formal `APPROVE`: the
signed-in user authored PR #208, so self-approval is impossible and that path is
untested end to end. The 2026-09-15 behavioral scenarios were simulated against
that revision, were not re-run afterwards, and their rejection cases cover an
explicit zero/fractional `rounds` rather than the now-defaulting absent value.
Findings coverage rests on three reviewer phases against one small Markdown PR,
not on a broad or adversarial corpus. Results are pinned to those two CLI
versions. And the writer-phase block is specific to `.claude/skills/**`: the
round-3 writer edited this file and committed unaided, so the
writer-edits-then-commits path is proven outside that path, but no writer phase
has yet edited the skill's own files without coordinator escalation.

At invocation time the skill checks actual profile metadata, final base/head, and
permissions before accepting phase output or approving. Actual model access
failures must remain visible blockers.
