# at-review-pr skill validation

Issue: [#207](https://github.com/amyteq/tt_pangu/issues/207). Validated 2026-09-15
against base `8f950823257aa2476fa356294d13448ab196ac60`, then re-checked on
2026-09-16 after the round-1 review of
[PR #208](https://github.com/amyteq/tt_pangu/pull/208) (the skill was named
`pr-review-loop` in the earlier revision; that live loop is still running).

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
| Four launch examples, executed with local stub CLIs | PASS: shell syntax, quoted model/config/MCP arguments, literal stdin, and process-local Claude effort | AC2 |
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

## Limits

This is an offline behavioral and syntax validation. It does not prove live model
access, the installed provider's runtime metadata schema, or GitHub review
permissions. The behavioral scenarios were simulated against the 2026-09-15
revision and were not re-run afterwards; the rejection cases above cover an
explicit zero/fractional value, not the now-defaulting absent `rounds`. A live
loop on PR #208 is in progress but not complete, so no finished
review/fix/approval cycle is recorded here. At invocation time the skill checks
actual profile metadata, final base/head, and permissions before accepting phase
output or approving. Actual model access failures must remain visible blockers.
