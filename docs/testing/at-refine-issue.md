# at-refine-issue skill validation

Issue: [#209](https://github.com/amyteq/tt_pangu/issues/209). Task: [implementation work order, revision 1](https://github.com/amyteq/tt_pangu/issues/209#issuecomment-5697118933). Validated 2026-09-16 in worktree branch `worktree-issue-209-at-refine-issue`, based on `8f95082`.

The deliverable is a Markdown development skill plus two references. It adds no service, helper script, runtime configuration, test code, or dependency. The [skill](../../.claude/skills/at-refine-issue/SKILL.md) is canonical; the [README](../../README.md#claude-code-project-skills) supplies discovery and invocation. The mechanical checks C1–C8 ran offline, against fixtures and against read-only copies of #209's own artifacts. The scenario matrix mixes those executed checks with behavioral walkthroughs of the written rules; every row says which it is, and the split is repeated under [Limitations](#limitations). **No GitHub state was mutated by this validation** — the only remote calls were `GET` on #209 and its task comment, plus `--help` invocations of `gh`.

## Repository checks

| Check | Result | AC |
|---|---|---|
| `ruff check --no-cache .` | PASS, "All checks passed!" (Ruff 0.15.14) | AC8 |
| `ruff format --check --no-cache .` | Pre-existing failure: 20 files would be reformatted, 372 already formatted (371 before the `origin/main` merge) — identical on `main` and in this worktree, all 20 in untouched competition/analysis files | AC8 |
| `python -m pytest tests/ services/decision_api/tests -q` | 372 passed, 90 skipped in 32.88 s after merging `origin/main` at `1fc0355`. Before that merge, on base `8f95082`: 359 passed, 90 skipped in 33.91 s, identical to the same command run against the unmodified `main` checkout (359 passed, 90 skipped in 33.27 s). The rise from 359 to 372 comes from #201 and #208 landing on `main`, not from this diff | AC8 |
| `git diff --check` | PASS, no whitespace errors | AC8 |
| Skill registered by the harness from the worktree | PASS: listed as `at-refine-issue` with the frontmatter description after the file was written | AC1 |
| Documented `gh` forms exist in the installed CLI (2.100.0) | PASS: `gh issue comment -R/--repo -F/--body-file`, `gh issue edit -F/--body-file`, and `gh api -F key=@path` (documented file-reading form) all present in `--help` | AC1, AC3 |

The diff is Markdown-only, so pytest and Ruff are recorded as unchanged-baseline evidence rather than as coverage of new behavior. `git diff --stat origin/main HEAD` is the proof: 5 files, +557 lines, no Python touched. The `ruff format` failure is inherited and out of scope — this PR does not reformat unrelated competition files. The pytest runs used `~/micromamba/envs/v3.12.12/bin/python` with `SUPABASE_DB_URL` unset and `KCA_SKIP_DOTENV=1`, so the 90 skips are the DB-backed tests with no local Supabase to reach.

## Automated checks

Run from the worktree with an offline fixture set and read-only fetches of #209. Full output is in the PR; the harness itself is throwaway and not committed, per the task's "do not build a test framework" boundary.

| # | Check | Result |
|---|---|---|
| C1 | `SKILL.md` frontmatter parses as YAML with `name`, `description`, `argument-hint: "<issue-url\|number> [refinement instructions]"`, and `disable-model-invocation` as boolean `false` | PASS |
| C2 | Every relative Markdown link in `SKILL.md`, both references, this file, and the README entry resolves on disk (fenced blocks and inline code excluded — template placeholders there are not links) | PASS, 14 links |
| C3 | Byte-prefix append/rewrite test over four bodies: unchanged, appended, rewritten, truncated | PASS, `APPENDED / APPENDED / REWRITTEN / REWRITTEN` |
| C4 | The marker `jq` select over five mocked comment payloads: no prior comment, one prior comment, recovery-after-failed-body-update, accidental duplicate, and a body that only quotes the marker mid-text. The harness runs the bare `<!-- at-refine-issue:task` prefix; the repository/issue qualifier and the author check the skill requires around it are not exercised (see [Limitations](#limitations)) | PASS, `0 / 1 / 1 / 2 / 0` hits |
| C5 | Published launch-prompt blocks and Markdown link targets in #209's body and task comment carry no placeholder URL | PASS, 2 prompt blocks, 0 leaks |
| C6 | The AC list in #209's body is identical to the AC list in its task comment | PASS, 8 ACs, `AC1`–`AC8`, equal |
| C7 | Both launch prompt forms in #209's body carry the resolved permalink and a stop condition | PASS |
| C8 | #209's task comment has all nine required sections and none of the back-reference phrases ("see above", "as discussed", …) | PASS |

Two checks were wrong on first run and were corrected, not the artifacts:

- C2 initially flagged `[Linked issue / discussion / ADR](url)` and `[Implementation task, revision R](<real permalink>)` — placeholders inside the fenced templates and inline code spans, which are not links. The checker now strips fenced blocks and inline code before extracting links.
- C5 initially flagged five matches in #209's published bodies. All five are prose *describing* the prompt shape — AC4's own text contains `` `/goal Execute from <comment-url> ...` `` in backticks, and the verbatim quoted user request contains it too. The rule is that a published *launch prompt* or link target carries no placeholder, so the check was narrowed to fenced blocks that begin with `Execute from` / `/goal Execute from`, plus link targets. It passed with zero leaks.

C4–C8 exercise #209's own published artifacts, which a different session produced from the same contract before this skill file existed. That makes them an independent conformance fixture: the template in [task-comment.md](../../.claude/skills/at-refine-issue/references/task-comment.md) matches artifacts the skill did not generate.

## Scenario matrix

Each row gives the fixture input, the rule that decides it, and the observed outcome. A row that names a check was executed against fixtures. A row marked *walkthrough* was not: PASS there means the written rules decide that fixture as required on inspection, since a Markdown skill has no runtime to instrument and the task forbids demonstrating it on an unrelated live issue.

| # | Scenario | Fixture input | Observed result | Pass |
|---|---|---|---|---|
| S1 | Sparse issue | Title "add a refine skill", body "we should have something like #207", no labels, no AC | Preflight resolves the target, evidence gathering reads #207 and the repository instructions, and the refined body must carry goal, scope, non-goals, ordered plan, `AC1…ACn` with per-criterion evidence, owner, and authorization. Everything the drafter inferred is written as **Assumption**; no owner, priority, or approval is invented. Since AC and owner would be assumed rather than confirmed, the readiness rule denies `ai:ready` and applies `decision:needed` + `ai:blocked` | PASS (walkthrough) |
| S2 | Already-refined issue, repeat run | #209 as published, plus its revision-1 task comment | C4 fixture "repeat run" returns exactly one marker hit; the rule reuses that comment and edits it in place, so no second comment and the permalink is unchanged. Confirmed decisions, evidence links, and existing AC numbering survive: C6 shows `AC1`–`AC8` byte-identical across body and comment | PASS (C4, C6) |
| S3 | Missing or ambiguous target | (a) `/at-refine-issue` with two issues named earlier in the conversation; (b) bare `41` with no current repository; (c) a pull-request URL | All three fall to preflight step 2 or 3 and produce a question. Preflight step 4 forbids any state-changing remote call before the target verifies, so the observable result in all three is: one question, zero mutations | PASS (walkthrough) |
| S4 | Conflicting or unresolved decisions | Two comments propose different comment markers; neither is confirmed by the owner | The evidence-classification rule forbids promoting either to a confirmed decision. The open decision is recorded in the body with both options, the issue keeps `decision:needed` + `ai:blocked`, and the question is asked once while independent drafting continues | PASS (walkthrough) |
| S5 | Explicit existing authorization | "refine #209 with acceptance criteria and a task comment, open it this way" | The authority table maps that shape to: edit body, publish/update task comment, add Execution section, apply existing labels. It is recorded once and not re-asked. Implementation does not begin — the skill's own "Must not" forbids it, and the Execution section it writes states that creating the comment has not dispatched anything | PASS (walkthrough) |
| S6 | Concurrent human edit | Snapshot `updated_at=T0`; the owner edits the comment at `T1 > T0`; the run then tries to write | The re-read-before-write rule compares against the run's snapshot, sees the drift, and either reconciles the human's text into the new body or stops and reports the conflict. Stale text never overwrites the edit | PASS (walkthrough) |
| S7a | Active task, append | Revision 1 carrying a `--- dispatched 2026-09-16 ---` record, plus an extra instruction appended as `--- appended 2026-09-16 ---` | C3 "appended" → `APPENDED`; the dispatch continues | PASS (C3) |
| S7b | Active task, rewrite | Dispatched revision 1 with an earlier sentence corrected; and the truncated variant | C3 → `REWRITTEN` for both. The rule stops the dispatch, publishes revision 2 as a new comment, links both directions, repoints the issue's Execution section, and reports that explicit redispatch is required | PASS (C3) |
| S8 | Comment created, issue body update failed | One marker comment exists (id 7); the issue body has no Execution section | C4 fixture "recovery" returns exactly 1 hit. The recovery rule reuses that permalink and repairs only the body. A second comment is named as the failure mode | PASS (C4) |
| S9 | Completed publication | #209 as published | C6 AC lists equal; C7 both prompt forms carry the resolved permalink `…#issuecomment-5697118933` and the stop condition; C5 no placeholder survived; the permalink resolves via `GET /issues/comments/5697118933` (author `harrysun2006`, `updated_at 2026-09-16T12:04:48Z`) | PASS (C5, C6, C7) |
| S10 | Uncertain write | Publication call times out with no response body | The rule forbids a blind retry: query by marker first, adopt an existing candidate only when it passes the exact-marker and author checks, publish once if none exists. C4's "no prior comment" and "one prior comment" fixtures are the two branches that query resolves | PASS (C4) |

## Limitations

- S1, S3, S4, S5, S6 are behavioral walkthroughs against the written rules, not executed runs. A Markdown skill has no runtime to instrument, and the task's boundary forbids demonstrating it by refining an unrelated live issue. The decisive mechanical steps of S2, S7, S8, S9, S10 *are* executed (C3, C4, C5, C6, C7).
- The skill was not exercised end-to-end against a live issue. #209 itself is already refined and dispatched, so running it there would have rewritten an active task — exactly what the skill forbids.
- `argument-hint` and `disable-model-invocation` are Claude Code skill frontmatter fields. The portable Agent Skills validator accepts only `name`, `description`, `license`, `allowed-tools`, and `metadata`, so it rejects them; C1 parses the frontmatter directly instead. The same limitation was recorded for `at-review-pr`.
- The README entry and this file are the only integration points. `AGENTS.md`, `CLAUDE.md`, and `PROJECT_STATE.md` were read but not modified — the task scoped the deliverable to the skill, its references, the README entry, and this evidence.
- Round 1 of the [#211](https://github.com/amyteq/tt_pangu/pull/211) review loop changed four rules in the skill: the marker query is now qualified by repository and issue and a candidate is adopted only after an exact-marker, author, and required-section check; dispatch state is decided fail-closed with a `--- dispatched <date> ---` record in the comment; the Execution section carries a *Blocked* status sentence when the issue carries `ai:blocked`; and lock state is read from `gh api repos/<owner>/<repo>/issues/<n>` because `gh issue view --json` has no `locked` field. All four are inspected rules, not executed behaviour — C4 still runs the bare `<!-- at-refine-issue:task` prefix, and nothing exercises the author check, the dispatch record, or the lock query against a live locked issue. C2 was re-measured after the change: 14 links, unchanged, because every new cross-reference is an inline path rather than a Markdown link.
- [PR #208](https://github.com/amyteq/tt_pangu/pull/208) (`at-review-pr`) merged into `main` as `1fc0355` while this branch was in flight, adding an entry to the same README list and landing [ADR-0024](../adr/0024-markdown-soft-wrap.md). `origin/main` was merged into this branch and the one-hunk README conflict resolved by keeping both skill entries in alphabetical order; the two references now cite ADR-0024 for the soft-wrap rule they already followed. The checks in this file were re-run after that merge.
