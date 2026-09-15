# Review and disposition reports

Use these formats as Markdown comments. Replace placeholders with observed facts;
omit no-findings rows rather than inventing findings. Empty tables may be replaced
by "No new findings" / "No fixes required" plus the ledger summary. Escape pipes
inside table cells. Link exact file lines at the reviewed commit, tests, and prior
comments. Include the run/round/phase marker to reconcile uncertain publication.

Do not repeat the PR URL — the comment already lives on the PR. Write each SHA as
a short hash linked to its exact full-SHA commit URL, and carry every other
reference on descriptive link text; no bare URLs in comment prose. Both signatures
are defined in [Signature fields](#signature-fields).

## Reviewer

```markdown
<!-- at-review-pr: RUN_ID round=R phase=review|closing-review -->
## PR review — round R / LIMIT — full|delta|final-full

Base: [BASE_SHA_SHORT](BASE_COMMIT_URL) · Reviewed head: [HEAD_SHA_SHORT](HEAD_COMMIT_URL)
[Scope / AC](SCOPE_URL) · [Previous review](PREVIOUS_REVIEW_URL) · [Writer disposition](DISPOSITION_URL)
Delta range: [PREVIOUS_HEAD_SHORT..HEAD_SHA_SHORT](COMPARE_URL) (full reviews: complete PR diff)

| ID | Priority | Finding / concrete impact | Evidence at reviewed head | Ledger state / adjudication |
|---|---|---|---|---|
| F001 | P1 | Trigger and resulting defect | file:line + test/reproduction | open |

Ledger: resolved IDs; accepted rebuttals; accepted deferrals with residual severity;
pending/reopened IDs and new evidence. Do not restate accepted requests as new findings.
Validation: commands/results actually observed, skipped checks with reasons.
Verdict: continue / approval-eligible / blocked / budget-exhausted.
Unresolved P0/P1: IDs or none. Residual P2/P3: IDs or none.

---
🔎 ACTUAL_AGENT ACTUAL_MODEL, ACTUAL_EFFORT · read-only head: [HEAD_SHA_SHORT](HEAD_COMMIT_URL) · context: OBSERVED_CONTEXT_OR_NA · STARTED_TIMESTAMP..ENDED_TIMESTAMP TZ · MEASURED_ELAPSED
Requested profile: REQUESTED_PROFILE · metadata evidence: LOCAL_REFERENCE · VERDICT
```

In round 1 write `previous review: none` and `writer disposition: none` as plain
text rather than empty links, and drop the delta range from a full review.

## Writer

```markdown
<!-- at-review-pr: RUN_ID round=R phase=writer -->
## Fix dispositions — round R / LIMIT

Base: [BASE_SHA_SHORT](BASE_COMMIT_URL) · Input head: [REVIEWED_SHA_SHORT](REVIEWED_COMMIT_URL) · Result head: [RESULT_SHA_SHORT](RESULT_COMMIT_URL)
[Review](REVIEW_URL) · [Scope / AC](SCOPE_URL)
Push: verified remote head / no code changes / blocked (reason)

| ID | Disposition | Change or rebuttal/deferral reasoning | Evidence / commit / tests | Residual risk / next action |
|---|---|---|---|---|
| F001 | fixed-pending-review | Concrete fix | commit link + test result | reviewer verification |
| F002 | deferred-pending-review | Scope or effort reason | supporting evidence | impact, follow-up proposal |

Cover every open finding. Propose follow-ups without filing new issues unless
authorized. State failed or unrun tests; do not imply a rebuttal/deferral is accepted.

---
✏️ ACTUAL_AGENT ACTUAL_MODEL, ACTUAL_EFFORT · head: [RESULT_SHA_SHORT](RESULT_COMMIT_URL) · context: OBSERVED_CONTEXT_OR_NA · STARTED_TIMESTAMP..ENDED_TIMESTAMP TZ · MEASURED_ELAPSED
Requested profile: REQUESTED_PROFILE · metadata evidence: LOCAL_REFERENCE
```

## Signature fields

Each signature is exactly two rendered lines: end the first with two trailing
spaces so both join one block, and separate fields with ` · `. The coordinator
fills them from that phase's execution evidence, never from estimates or from the
text of the launch command.

| Field | Meaning | Example |
|---|---|---|
| `ACTUAL_AGENT ACTUAL_MODEL, ACTUAL_EFFORT` | Provider, model, and reasoning effort the session actually reported | `codex gpt-5.6-sol, xhigh` |
| `OBSERVED_CONTEXT_OR_NA` | Context window available to that session as reported — not tokens consumed | `context: 1M`, `context: 400k`, `context: N/A (not emitted)` |
| `STARTED_TIMESTAMP..ENDED_TIMESTAMP TZ` | Coordinator wall clock around the phase, each `yyyy-MM-dd HH:mm`, with the zone named once | `2026-09-16 08:24..2026-09-16 08:28 AEST` |
| `MEASURED_ELAPSED` | Measured duration of that phase as `H:mm` | `0:04` (4 minutes), `1:37` (1 hour 37 minutes) |
| `REQUESTED_PROFILE` | Provider/model/effort (and context variant) requested at launch | `codex/gpt-5.6-sol/xhigh`, `claude/claude-opus-5[1m]/xhigh` |
| `LOCAL_REFERENCE` | Where the sanitized per-phase metadata for these fields is kept | local-only `r1-review.metadata.json` (CLI header plus measured timing) |
| `VERDICT` (reviewer only) | Outcome label for this review | `CHANGE REQUIRED`, `APPROVAL ELIGIBLE`, `APPROVED`, `BLOCKED`, `BUDGET EXHAUSTED` |

Elapsed hours are unbounded and minutes are rounded, so a sub-minute phase shows
`0:00`; keep the raw ISO timestamps and seconds in the metadata file instead of
inflating the published value. Use the phase's own wall time, not total loop time.

`N/A (not emitted)` belongs only to a context field the CLI genuinely never
reports. Required metadata — agent, model, effort, start/end — that cannot be
observed stays `unverified` and blocks the phase; do not substitute a plausible
value or read one back from the launch flags. `REQUESTED_PROFILE` records what was
asked for, so any mismatch with the actual fields is a blocker, not a footnote.
For `LOCAL_REFERENCE`, link committed evidence when it exists; otherwise name the
local-only scratch file and say it is local. Publish only the non-secret summary,
never raw transcripts, tokens, or credentials. If a phase failed before model
execution, say "not run" rather than signing it.

The body `Verdict:` line records loop state; the footer `VERDICT` labels the
review outcome. Keep them consistent:

| Body `Verdict:` | Footer `VERDICT` |
|---|---|
| `continue` | `CHANGE REQUIRED` |
| `approval-eligible` | `APPROVAL ELIGIBLE`, becoming `APPROVED` only in a review GitHub actually accepted at that head |
| `blocked` | `BLOCKED` |
| `budget-exhausted` | `BUDGET EXHAUSTED` |

`APPROVED` therefore never appears on a plain comment. Self-authored or
permission-blocked eligibility stays `APPROVAL ELIGIBLE`, and the terminal
coordinator summary states whether GitHub accepted the approval.
