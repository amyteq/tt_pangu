# Review and disposition reports

Use these formats as Markdown comments. Replace placeholders with observed facts;
omit no-findings rows rather than inventing findings. Empty tables may be replaced
by "No new findings" / "No fixes required" plus the ledger summary. Escape pipes
inside table cells. Link exact file lines at the reviewed commit, tests, and prior
comments. Include the run/round/phase marker to reconcile uncertain publication.

## Reviewer

```markdown
<!-- pr-review-loop: RUN_ID round=R phase=review|closing-review -->
## PR review — round R / LIMIT — full|delta|final-full

PR: URL · Base: BASE_SHA · Reviewed head: HEAD_SHA
Scope / AC: issue or approved scope link
Previous review: URL or none · Writer disposition: URL or none
Delta range: PREVIOUS_HEAD..HEAD_SHA (full reviews: complete PR diff)

| ID | Priority | Finding / concrete impact | Evidence at reviewed head | Ledger state / adjudication |
|---|---|---|---|---|
| F001 | P1 | Trigger and resulting defect | file:line + test/reproduction | open |

Ledger: resolved IDs; accepted rebuttals; accepted deferrals with residual severity;
pending/reopened IDs and new evidence. Do not restate accepted requests as new findings.
Validation: commands/results actually observed, skipped checks with reasons.
Verdict: continue / approval-eligible / blocked / budget-exhausted.
Unresolved P0/P1: IDs or none. Residual P2/P3: IDs or none.

---
Review signature — agent: ACTUAL_AGENT; model: ACTUAL_MODEL;
effort: ACTUAL_EFFORT; context: OBSERVED_CONTEXT_OR_NA;
started: UTC_ISO; ended: UTC_ISO; elapsed: MEASURED_SECONDS s.
Requested profile: REQUESTED_PROFILE; metadata evidence: LOCAL_REFERENCE.
```

## Writer

```markdown
<!-- pr-review-loop: RUN_ID round=R phase=writer -->
## Fix dispositions — round R / LIMIT

PR: URL · Base: BASE_SHA · Input head: REVIEWED_SHA · Result head: RESULT_SHA
Review: URL · Scope / AC: link
Push: verified remote head / no code changes / blocked (reason)

| ID | Disposition | Change or rebuttal/deferral reasoning | Evidence / commit / tests | Residual risk / next action |
|---|---|---|---|---|
| F001 | fixed-pending-review | Concrete fix | commit link + test result | reviewer verification |
| F002 | deferred-pending-review | Scope or effort reason | supporting evidence | impact, follow-up proposal |

Cover every open finding. Propose follow-ups without filing new issues unless
authorized. State failed or unrun tests; do not imply a rebuttal/deferral is accepted.

---
Fix signature — agent: ACTUAL_AGENT; model: ACTUAL_MODEL;
effort: ACTUAL_EFFORT; context: OBSERVED_CONTEXT_OR_NA;
started: UTC_ISO; ended: UTC_ISO; elapsed: MEASURED_SECONDS s.
Requested profile: REQUESTED_PROFILE; metadata evidence: LOCAL_REFERENCE.
```

The coordinator fills timing/profile fields from execution evidence, not estimates.
Use UTC ISO 8601 start/end and elapsed wall time for the phase, not total loop time.
If a phase fails before model execution, say "not run"; if metadata is missing,
say "unverified" and report the blocker. Never manufacture a provider signature.
Keep raw metadata/transcripts local; publish only the necessary non-secret summary.
An approval uses the final full-review table/signature and reviewed commit, while
the terminal coordinator summary states whether GitHub actually accepted it.
