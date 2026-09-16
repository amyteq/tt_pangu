# at-review-pr skill validation

Issue: [#207](https://github.com/amyteq/tt_pangu/issues/207). Validated 2026-09-15 against base `8f950823257aa2476fa356294d13448ab196ac60`, then re-checked on 2026-09-16 across the live runs of the loop on [PR #208](https://github.com/amyteq/tt_pangu/pull/208) (the skill was named `pr-review-loop` in the earlier revision). Extended on 2026-09-17 by [#212](https://github.com/amyteq/tt_pangu/issues/212), which adds the `pr=<n>` first optional argument — see [that section](#prn-first-optional-argument-2026-09-17-issue-212).

The deliverable is a Markdown development skill and two supporting references. It adds no execution service, helper scripts, runtime configuration, or test code. The [skill](../../.claude/skills/at-review-pr/SKILL.md) is canonical; the [README](../../README.md#claude-code-project-skills) supplies discovery and invocation.

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

The successful pytest run used the project-compatible interpreter already active in that shell; resolve one against `requires-python` in `pyproject.toml` at run time instead of pinning a patch version or an environment-manager path here. Inherited service variables (`SUPABASE_*`, `KCA_*`, `KAGGLE_*`, `ANTHROPIC_*`, `OPENAI_*`, `DEVPOST_*`, `CTFTIME_*`, `PG*`, `DATABASE_*`) were removed from the child environment; `KCA_SKIP_DOTENV=1` and `PYTHONDONTWRITEBYTECODE=1` were set. An earlier sandboxed attempt was stopped after inherited DB settings selected unavailable DB tests; a diagnostic stopped at 1 failure / 50 passes. The clean-environment rerun above is the completed local validation.

Formatting differences are all in unchanged competition/analysis files; this PR does not format them. No UI, migration, or live-service tests were needed for the Markdown-only change. The stub checks used prompt paths with spaces and literal shell metacharacters; neither Codex nor Claude was actually invoked by those checks.

## Independent behavioral scenarios

A fresh evaluator received the skill, references, realistic requests, and mock PR snapshots/agent outputs. It produced ordered role invocations, ledger transitions, budget counts, and terminal actions without network access or repository writes. Provider/model metadata and permission results in these cases were simulated.

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

The first evaluation found an ambiguity when final verification discovered a P2: the exhausted-budget branch could be read as skipping the otherwise eligible approval. Step 6 now explicitly routes residual P2/P3 through the terminal approval check and treats exhausted fix budget separately from actual approval status. The evaluator rechecked that correction against the same case.

## Re-checks after the round-1 review (2026-09-16)

Round 1 of the live loop on PR #208 requested the rename to `at-review-pr`, the `argument-hint` / `disable-model-invocation` frontmatter, a default of 10 rounds, linked short-SHA comment headers, two-line signatures with defined fields, and removal of the pinned interpreter version above. Those are documentation and invocation-metadata changes, so only the checks below were re-run; the pytest and Ruff results above stand as historical observations for this Markdown-only diff.

| Check | Result |
|---|---|
| Frontmatter parsed as YAML, including `argument-hint` (string) and `disable-model-invocation` (boolean `false`) | PASS |
| Skill Creator `quick_validate.py` on a temporary copy with those two keys removed | PASS: "Skill is valid!" |
| Skill Creator `quick_validate.py` on the skill as committed | Rejected: the portable validator allows only `name`, `description`, `license`, `allowed-tools`, `metadata` |
| Relative Markdown links across the skill, both references, the README entry, and this file | PASS: 7 links resolve; placeholders inside the report templates are not links |
| `bash -n` on the four launch examples, unchanged in this revision | PASS |
| `git diff --check` | PASS |

`argument-hint` and `disable-model-invocation` are supported Claude Code skill frontmatter fields ([frontmatter reference](https://code.claude.com/docs/en/skills#frontmatter-reference)); the installed `quick_validate.py` accepts only the portable Agent Skills keys, so its rejection is a validator limitation rather than a skill defect. No validator, hook, or settings file was modified to obtain these results.

## CLI runtime-metadata probes (2026-09-16, round 2)

The round-1 loop stopped because Claude's effort setting could not be observed. The author then decided that an unobservable effort may be published as the requested value. These probes establish, per CLI, which signature fields are actually retrievable, and are the evidence behind [runtime metadata](../../.claude/skills/at-review-pr/references/agents.md#runtime-metadata).

| Probe | Observed |
|---|---|
| `codex exec --model gpt-5.6-sol --config model_reasoning_effort=xhigh --sandbox read-only --ephemeral` (default output) | stderr header block: `model: gpt-5.6-sol`, `provider: openai`, `approval: never`, `sandbox: read-only`, **`reasoning effort: xhigh`**, `session id:`; no context window |
| Same command with `--json` | only `thread.started`, `turn.started`, `item.completed`, `turn.completed` — the header, model and effort are absent |
| `claude -p --output-format stream-json --verbose` | `system`/`init` carries `model`, `tools`, `permissionMode`, `claude_code_version`; the final `result` carries `modelUsage[<model>].contextWindow`, `canonicalModel`, `terminal_reason`, `is_error`. **No effort field in any event** |
| `claude -p --effort bogus` | exit 0 with stderr `Warning: Unknown --effort value 'bogus' — ignoring it and using the default effort. Valid values: low, medium, high, xhigh, max.` — an invalid value is non-fatal, so stderr must be captured |
| `CLAUDE_CODE_EFFORT_LEVEL=bogus claude -p --effort high` | no warning and no behavior change: the variable is not recognized by Claude Code 2.1.273, so the earlier env-var prefix in the launch forms was unsupported and is removed |

Consequences applied to the skill: `codex exec` keeps its default output mode and redirects stderr to the phase metadata file, because `--json` would discard the only model/effort evidence; every launch form now captures stderr; effort that a CLI never reports is published as `xhigh (requested)` and no longer blocks a phase, while agent, model and timing stay verify-or-block. Codex CLI 0.154.0 and Claude Code 2.1.273; probes used a cheap model where the field's presence, not its value, was the question.

## Live loop on PR #208, run `pr208-20260916b` (2026-09-16)

The skill was exercised against its own PR. Round 1 reviewer: `codex exec` `gpt-5.6-sol` at `xhigh`, read-only, full review of `8f95082..21d155e`; the stderr header confirmed model and effort, so that phase is fully attested. It raised two P1 findings and both were valid:

| ID | Finding | Outcome |
|---|---|---|
| F001 | "The writer must disposition every open finding, including P2/P3" contradicted the rule that a closing verification-only review grants no writer phase, so a cosmetic finding raised there could be read as blocking approval forever | Fixed: the disposition duty is scoped to findings routed to a writer phase; a P2/P3 first raised by the closing review is recorded as residual work, while a P0/P1 raised there still blocks |
| F002 | The metadata instructions told the coordinator to validate runtime fields from `phase_meta`, but Claude reports model, context, session and completion on **stdout** in the JSON result object, not on stderr | Fixed: the metadata table and the launch-form text name the stream per provider — `phase_meta` for Codex, `phase_output` for Claude, with Claude's stderr still captured for the effort warning |

The round-1 writer phase (`claude -p`, `claude-opus-5[1m]`, `--effort xhigh`) ran and produced a complete, correct edit plan for both findings, but **every write to `.claude/skills/**` was denied** by the harness protection on skill files — via `Edit` and via `Bash(touch)` alike. It correctly refused to disable hooks or broaden the sandbox, reported the exact denied action, and returned both findings as `blocked` rather than claiming a fix. The coordinator then applied the writer's specified edits verbatim under its own approval, which is the "host's normal approval mechanism" the launch-form rules point to.

That is a real operating limitation worth stating plainly: **a Claude writer phase cannot edit this skill's own files under the default harness permissions**, so self-application of `at-review-pr` to a PR touching `.claude/skills/**` requires coordinator escalation for the write step. A writer phase on any other part of the repository is unaffected. The round-1 writer's JSON also confirmed `modelUsage["claude-opus-5[1m]"].contextWindow == 1000000` and `canonicalModel == "claude-opus-5"` on stdout — the direct evidence behind F002.

Round 2 was a full closing verification review of head `bddee5c` by the same reviewer profile (`codex exec`, `gpt-5.6-sol`, `xhigh`, read-only). It did not close clean: it found F001 and F002 resolved but raised one residual P2 — F003, that this record's Limits section still asserted an offline boundary its own live probes and live rounds had outgrown — alongside an approval-eligible verdict with no unresolved P0/P1.

The run then closed inside its budget. Its full phase ledger, with the head each phase saw and the wall-clock time it took:

| Round | Phase | Head | Elapsed | Outcome |
|---|---|---|---|---|
| 1 | review (full) | `21d155e` | 0:07 | F001 (P1) and F002 (P1) opened |
| 1 | writer | `bddee5c` | 0:03 | Every write under `.claude/skills/**` denied; the exact edits were specified and the coordinator applied them |
| 2 | review (full, closing) | `bddee5c` | 0:08 | F001 and F002 resolved; F003 (P2) opened |
| 3 | writer | `09b214e` | 0:02 | Edited this file and committed it **unaided, with no permission denial** — `docs/` is outside the protected skill path, so no coordinator escalation was needed |
| 4 | review (full) | `09b214e` | 0:06 | F001/F002 still resolved and no unresolved P0/P1, but **F003 reopened** — the round-3 writer described the loop while its own round was still running, so the record kept counting one writer phase and calling round 2 clean |
| 4 | writer | `66457d6` | 0:02 | Edited this file and committed unaided, same as round 3 |
| 5 | review (full) | `66457d6` | 0:08 | F003 resolved; F004 (P2) opened |
| 5 | writer | `012362a` | 0:01 | Denied under `.claude/skills/**` again; the edits were specified and the coordinator applied them |
| — | terminal verification (full) | `012362a` | 0:05 | F001–F004 all resolved, no new findings, AC1–AC7 met, verdict approval-eligible |

Measured totals: budget 10 rounds, 5 used; 5 reviewer phases (4 numbered plus the terminal verification) and 4 writer phases, of which 2 committed unaided under `docs/` and 2 were blocked under `.claude/skills/**`; 4 findings raised (2×P1, 2×P2), 4 fixed, 0 rebutted, 0 deferred, F003 reopened once; 0:56 wall clock, 19:44–20:40 AEST on 2026-09-16. Every review phase ran `codex`·`gpt-5.6-sol`·`xhigh`; every writer phase ran `claude`·`claude-opus-5`·`xhigh (requested)`, with `modelUsage["claude-opus-5[1m]"].contextWindow == 1000000` observed. The published ledger for this run is its [loop-closed summary](https://github.com/amyteq/tt_pangu/pull/208#issuecomment-5696170588).

## Second author review (2026-09-16)

The owner reviewed the completed loop and raised formatting, honesty and terminology defects that the loop itself had not caught, because none of them is visible from inside a single phase. The coordinator applied all of them directly, as commit `69b8184`; that is an ordinary edit answering review comments, not a loop phase, and it is not counted in the phase totals above.

| Request | Change |
|---|---|
| Soft-wrap Markdown everywhere, in files and in agent-written GitHub text | [ADR-0024](../adr/0024-markdown-soft-wrap.md) records the rule, `CLAUDE.md` carries it for every session, and the report templates bind published comments. This skill's four Markdown files were reflowed to one line per paragraph, list item and table row |
| Combine the reviewer's `Base:` and `[Scope / AC]` lines, and the writer's `Base:` and `[Review]` lines | Both report headers now open with a single line carrying base, heads and scope; secondary references moved to the second line |
| Leave a blank line before `---` | Codified in ADR-0024 and the report templates. Scanned all 12 published comments, the PR body and these four files: the only `---` without a preceding blank line is this skill's YAML frontmatter terminator, which is correct, so nothing currently renders bold |
| A reviewer phase cited a tool named `LoopX`, which this repo does not use | The reviewer handoff and the report template now require each phase's validation line to name only tools and commands it actually ran; a fabricated harness or wrapper name there is a report defect and the coordinator rejects the phase output rather than publishing it. **The premise of this request was wrong** — `loopx` is a real installed tool, see the correction below — but the rule it produced is sound and stands |
| Report per-round time and finding counts in the closing summary | The loop-closed summary now carries measured duration, findings raised, and fixed/rebutted/deferred counts per round |
| Explain `APPROVED` versus `APPROVAL ELIGIBLE` | Both are now stated to be the same code judgement, differing only in whether GitHub could store the verdict. `APPROVAL ELIGIBLE` is the terminal success state and the loop stops on it |

**Correction (2026-09-17, [#214](https://github.com/amyteq/tt_pangu/issues/214)): `loopx` is real, and the confabulation finding above was wrong.** This record previously stated that the reviewer "did not run any such tool" and that no such harness exists. That is false, and it was corrected only because a later run checked the claim instead of inheriting it.

`loopx` is installed at `/home/harry/.local/bin/loopx`, a symlink into `~/.local/share/loopx/releases/<timestamp>/scripts/loopx`. It is a general agent-loop harness — "keeps long-running agent work moving by preserving goals, todos, gates, quota, and evidence between agent turns" — belonging to the operating environment, not to this repository. `loopx pr-review` is a real subcommand whose own usage string is `loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]`, and it accepts `--limit` plus the global `--format markdown|json`. It shells out to `gh pr list`, so in a sandboxed agent session it fails with `"error": "Command '['gh', 'pr', 'list', …]' returned non-zero exit status 1."` — exactly the failure the cited phases described.

This surfaced during run `pr213-20260917a` on [PR #213](https://github.com/amyteq/tt_pangu/pull/213), when a fresh reviewer cited the same tool and the same failure. Under the rule above the coordinator was required to reject that phase; it checked first, found the tool, and published the report instead. The [coordinator note on that review](https://github.com/amyteq/tt_pangu/pull/213#issuecomment-5699485712) records the verification, and a [correction comment](https://github.com/amyteq/tt_pangu/pull/208#issuecomment-5703642872) links it from the original PR.

What remains unknown is narrower than the original claim: whether the specific 2026-09-16 phase actually executed the command was not re-verified and that session's transcript is not retained. The correction is that the tool exists and the citation was plausible on its face — not a positive finding that the earlier phase ran it.

The real lesson is the inverse of the one first recorded. A name that is unfamiliar from inside the repository tree is not thereby invented: host tooling is invisible to `git grep`, and "this repo does not use it" is not evidence of "it does not exist". Checking costs one `command -v`; skipping it cost a false finding that was then written into the rule, the PR record and this file, where it sat for a day instructing future coordinators to reject truthful reports. The validation-honesty rule itself is unaffected and stays in force — a genuinely invented tool name is still a report defect — but [agents.md](../../.claude/skills/at-review-pr/references/agents.md) now requires that verification step before a phase is rejected on those grounds.

### Writer permission: still blocked, and not self-fixable

The owner asked for the `.claude/skills/**` write restriction to be lifted so a writer phase can edit this skill's own files. The coordinator cannot do that. Launching a nested `claude -p` with a `--settings` file that grants `Edit(.claude/skills/**)` is itself refused by the harness permission layer with reason `[Self-Modification]`: an agent may not widen its own tool-configuration permissions, which is the correct guardrail and the same class of protection that blocked the writes.

Lifting it therefore requires a human-owned settings change, not an agent one. Until then the established fallback holds and is documented in the loop record: the writer reports the exact denied action together with its full intended edit, and the coordinator applies it verbatim. Both round-1 and round-5 writers did exactly that, and every edit they specified is present at this head.

## Second live run on PR #208, run `pr208-20260916c` (2026-09-16, in flight)

A second run started on head `69b8184`, the coordinator commit above. Its round-1 full review (`codex exec`, `gpt-5.6-sol`, `xhigh`, read-only) has completed and raised two findings: **F003 reopened** (P2), because this record's Limits section and its round table still described run `pr208-20260916b` as three reviewer phases stopping at round 4, contradicting that run's own published summary; and **F005** (P3), the `/at-review-pr` entry this PR adds to the README being hard-wrapped across eleven lines against [ADR-0024](../adr/0024-markdown-soft-wrap.md), which the same PR introduces.

This revision is that run's round-1 writer phase, fixing both. Its verification has not run, so this run's outcome is not yet recorded here — only that its round-1 review completed and what it found.

## `pr=<n>` first optional argument (2026-09-17, issue #212)

[#212](https://github.com/amyteq/tt_pangu/issues/212) adds `pr=<n>` as an optional first argument, so the loop can be pointed at a PR explicitly instead of only inferring one from conversation context or the current branch. The change is Markdown-only and touches `SKILL.md` (frontmatter `argument-hint`, usage line, input table, both validation paragraphs, and preflight steps 1 and 4), the README entry, and this record. No reference file, report format, signature field, round-sequencing rule, or approval rule changed, and the three positional arguments keep their order, meaning, and defaults.

| Check | Result | Acceptance criteria |
|---|---|---|
| `SKILL.md` frontmatter parsed as YAML: `argument-hint` is the string `[pr=<n>] [rounds=10] [reviewer=codex] [writer=claude]`, `disable-model-invocation` the boolean `false` | PASS | AC1 |
| Skill Creator `quick_validate.py` on a temporary copy with those two Claude-only keys removed | PASS: "Skill is valid!" | AC1 |
| Skill Creator `quick_validate.py` on the skill as committed | Rejected exactly as before: the portable validator allows only `allowed-tools`, `compatibility`, `description`, `license`, `metadata`, `name`. This is the same validator limitation recorded above, not a defect introduced here | AC1 |
| Relative Markdown links and anchors across the skill, both references, the README entry, and this file | PASS: 17 targets resolve, including the new intra-document anchor added in the header above; placeholders inside the report templates are excluded as before | AC1, AC6 |
| `bash -n` on the four launch examples in `agents.md`, unchanged by this revision | PASS | AC6 |
| `ruff check --no-cache .` (Ruff 0.15.14) | PASS | AC6 |
| `ruff format --check --no-cache .` | Unchanged baseline failure: 20 files would be reformatted, 372 already formatted — all in competition/analysis files this change does not touch | AC6 |
| `git diff --check` | PASS | AC6 |

No Python, test, schema, or configuration file changed, so the pytest and UI tiers do not apply; the 2026-09-15 suite results above stand as the historical baseline for this Markdown-only diff.

### Parsing scenarios walked against the revised text

Argument parsing here is specification text a coordinator executes, not code, so these cases were walked against the revised "Inputs and preflight" section rather than run. Each row states the answer the revised text gives.

| Invocation | Resolved behavior | Acceptance criteria |
|---|---|---|
| `/at-review-pr` | Unchanged: rounds 10, reviewer `codex`, writer `claude`; PR from context, else the branch's unique open PR | AC4 |
| `/at-review-pr 5 codex claude` | Unchanged: the three positional values parse exactly as before | AC4 |
| `/at-review-pr pr=208` | PR 208, rounds 10, `codex` / `claude` — positions 1-3 are all absent once `pr=` is consumed | AC1, AC4 |
| `/at-review-pr pr=208 5 claude codex` | PR 208, 5 rounds, Claude reviewer, Codex writer — positions counted after `pr=` | AC1, AC4 |
| `/at-review-pr 5 pr=208` | Rejected before writes or agent launches: `pr=` is recognized only as the first token | AC3 |
| `/at-review-pr pr=208 pr=209` | Rejected: repeated `pr=` token | AC3 |
| `/at-review-pr pr=`, `pr=0`, `pr=-3`, `pr=2.5`, `pr=abc` | Rejected: empty, zero, negative, fractional, and non-numeric values all fail the positive-integer rule | AC3 |
| `/at-review-pr pr=#208`, a `pr=<PR URL>` form, `pr=amyteq/tt_pangu#208` | Rejected with the accepted spelling named, never repaired by guessing; no cross-repository targeting | AC3 |
| `pr=<n>` names a PR that does not exist, or one that is closed, merged, or in another repository | Stops, the same way preflight step 1 already stopped for a context-resolved PR | AC2 |
| `pr=<n>` disagrees with the PR the branch or context would have chosen | The argument wins, and the override is stated in the pre-launch confirmation rather than applied silently | AC2 |
| `pr=<n>` targets a PR whose head is not the current branch | The dedicated worktree is checked out at that PR's head; preflight step 4 now says so explicitly | AC5 |
| Prose "review PR 208 for me" with no arguments | Resolves at the explicit-user-context step, one level below a `pr=<n>` argument | AC4 |

## Limits

**Proven live, on this host.** The installed providers' runtime-metadata schema — which signature fields exist, and on which stream — for Codex CLI 0.154.0 and Claude Code 2.1.273. Live model access for both providers. Run `pr208-20260916b` ran to completion: 5 real reviewer phases (`codex exec`, `gpt-5.6-sol`, `xhigh`, read-only) — 4 numbered reviews plus the terminal verification — and 4 real writer phases (`claude -p`, `claude-opus-5[1m]`, `--effort xhigh` requested, 1M context window confirmed in `modelUsage`). Four full review → fix → re-review cycles on PR #208: the first three verifications did not close clean (round 2 raised F003, round 4 reopened it, round 5 raised F004), and the terminal verification of `012362a` did close clean with all four findings resolved and no new ones. Run `pr208-20260916c` has so far added one more reviewer phase of the same profile, its round-1 review of `69b8184`.

**Still not proven.** GitHub review permissions for a formal `APPROVE`: the signed-in user authored PR #208, so self-approval is impossible and that path is untested end to end. The 2026-09-15 behavioral scenarios were simulated against that revision, were not re-run afterwards, and their rejection cases cover an explicit zero/fractional `rounds` rather than the now-defaulting absent value. Findings coverage rests on six reviewer phases across two runs against the same one small Markdown PR — still a single narrow corpus, not a broad or adversarial one. Results are pinned to those two CLI versions. The `pr=<n>` argument added by #212 is specification text: its parsing, precedence, and worktree-targeting rules were walked case by case, not executed, and no live loop has yet been launched with an explicit `pr=<n>`. And the writer-phase block is specific to `.claude/skills/**`: the round-3 and round-4 writers edited this file and committed unaided, so the writer-edits-then-commits path is proven outside that path, but no writer phase has yet edited the skill's own files without coordinator escalation.

At invocation time the skill checks actual profile metadata, final base/head, and permissions before accepting phase output or approving. Actual model access failures must remain visible blockers.
