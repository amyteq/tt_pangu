---
name: kg-audit
description: Use to independently review a competition pipeline before an expensive run or a submission — leakage, split validity, metric fidelity, reproducibility, rules compliance, and whether the offline gate actually predicts the leaderboard.
---

# kg-audit — the review that runs before the expensive thing

Use this on entry to `INDEPENDENT_AUDIT`: an implementation is ready and a long run or a submission is next. Its verdict is `pass`, `pass with findings`, or `block`, and a `block` stops the run — which is the point. An audit that cannot stop anything is a comment.

**Independent means a different reader.** Run it as a separate session or sub-agent where the harness supports one; Codex ships no repo-level sub-agent format, so a Codex session runs the same checklist in-session and **says so** — an in-session review is a weaker claim than an independent one, and reporting it as independent is the failure this note prevents (`.agents/README.md` § *No Codex counterpart*).

Absorbs the retired `kaggle-evaluation-harness` checklist (issue #192) and the `ladder-predictive-gate` candidate from `competitions/_shared/skill-candidates.md`.

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | The implementation diff, the frozen validation protocol and its `split_id`, the `Experiment` record, `competitions/<slug>/rules.md`, and the offline gate or evaluation harness the competition uses. No access to the leaderboard is needed or wanted: this is a review of the method, not of the score. |
| **Output schema** | An audit verdict recorded against the experiment: `pass` / `pass with findings` / `block`, each finding naming a `file:line` or an exact config key, what it would corrupt, and what would fix it. Plus an explicit statement of whether the review was independent or in-session. |
| **State transition** | `IMPLEMENT` → `INDEPENDENT_AUDIT` → `TRAIN_VALIDATE` on `pass`, or back to `IMPLEMENT` on `block`. Also runs before `PRE_SUBMIT_GATE` when the artifact path changed since the last audit. |
| **Allowed tools** | Read, Glob, Grep, and Bash for read-only checks — re-running a validation split, hashing an artifact, diffing a config. `read-only`. It fixes nothing: a reviewer who edits the code is no longer reviewing it. |
| **Budget** | Wall-clock and `budget.llm.max_turns_per_research_task`. It is cheap by design, and that is the trade it exists to make: minutes of review against the GPU-hours a leak would waste. It never spends a submission slot. |
| **Prerequisite approvals** | None — it dispatches nothing. It **reports** on approval-relevant facts (`require_repro` and `rules_check` are ADR-0022 §5's two hard gates) but does not grant them; granting is `kg-submit`'s, under the rules that skill states. |
| **Idempotency** | Safe to re-run, and re-running after a fix is the normal path. Each verdict is dated and names the commit it reviewed, so a stale `pass` against an older commit is visibly stale rather than silently reused. |
| **Failure classes** | Leak found → `block`, and the experiment returns to `IMPLEMENT`. Split cannot be reproduced → `block`; there is no ruler. Rules violation found → `block`, and if the rules are *ambiguous* rather than violated that is `WAIT_HUMAN`, `state_reason: ambiguous rules` (an always-human item). Cannot read what it needs to review → `FAILED` naming the missing input, never a pass by default. |
| **Acceptance tests** | The verdict is one of the three tokens and names the commit reviewed. Every finding cites `file:line` or an exact key. A `block` is recorded on the experiment and the run did not start. The independence statement is present and accurate. |

## The checklist

Each item is a question with an answer in the code, not a value judgement.

**Leakage** — the defect that flatters every experiment equally and so never looks anomalous.

- Does any feature use information unavailable at prediction time? Target encodings, aggregates and counts fitted on the full data before splitting are the usual route.
- Is the split grouped where the data is grouped, and time-ordered where the data is time-ordered? A random split over either leaks.
- Are preprocessing, imputation, scaling and feature selection fitted **inside** each fold, or once over everything?
- Does any test-derived artifact — labels, pseudo-labels, statistics — reach training?

**Split and metric**

- Is the `split_id` the frozen one, unchanged since the baseline? A changed split invalidates every comparison to the number it is being compared against.
- Is the local metric the competition's metric, with the same direction and the same tie handling?
- Is the fold-to-fold spread reported alongside the mean? A mean without a spread hides an unstable result, and an improvement inside the spread is not an improvement.

**Reproducibility** — ADR-0022 §5's `require_repro` is a hard gate, so this is the half of the audit a submission cannot proceed without.

- Are the seed, the exact command and the artifact path recorded?
- Does the run record carry `code_commit`, `data_version` and `config_hash`?
- Does re-running the recorded command from a clean checkout reproduce the recorded number?

**Rules** — `rules_check` is the other hard gate.

- Does the approach stay inside `rules.md`: external data, pretrained weights, team rules, internet access inside the kernel, runtime caps?
- Is the artifact in the shape this `submission_mode` requires?
- Is anything here an attempt to work around a submission limit or a competition restriction? That is refused outright, not audited.

**Does the offline gate predict the leaderboard?** — the `ladder-predictive-gate` lesson, from orbit-wars: self-play and a naive offline gate had **no** predictive power for the live ladder, and work was gated on a number that did not mean what it looked like.

- Has the gate ever been checked against a real leaderboard or ladder result? If not, it is an untested proxy and should be labelled one.
- For a ladder or simulation competition: does the opponent suite span real strength, from weak to strong? Self-play measures consistency with yourself, which is not the quantity of interest.
- Is the gate's disagreement with the leaderboard recorded when it happens? That record is the only way the proxy ever improves.

## Steps

1. **Read the diff and the protocol before the narrative.** The write-up says what was intended; the code says what runs.
2. **Work the checklist in order.** Leakage first: it is the finding that invalidates the others.
3. **Re-run one thing yourself** — the split, or the recorded command on one fold. A review that only reads is weaker than one that reproduces.
4. **Write findings with `file:line`**, each with what it would corrupt and what would fix it. Do not fix them.
5. **State the verdict and the independence claim**, record it against the experiment, and hand back.

## Safety

- Never resolve a rules ambiguity yourself. Ambiguous competition rules are an always-human item (`CLAUDE.md` principle 6): the audit reports the ambiguity and the competition waits in `WAIT_HUMAN`.
- Do not audit against the leaderboard. Fitting the method to the public score is the failure mode this stage exists to catch, not a technique it uses.
