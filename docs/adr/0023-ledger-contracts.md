# ADR-0023: Ledger contracts — one entity model for phase 1 files and phase 2 Supabase

## Status

Accepted (2026-09-17). Directed by the project owner in [issue #191 — task comment](https://github.com/amyteq/tt_pangu/issues/191#issuecomment-5676170732), which implements the entity model of [discussion #185](https://github.com/amyteq/tt_pangu/discussions/185) §5.

- **Implements** ADR-0022 §1.3 ("one vocabulary across the phase boundary") and is the contract ADR-0022's follow-up table calls "Ledger contracts (Experiment ≠ Run) using this vocabulary".
- **Depends on** ADR-0022 for the state vocabulary (§3), the submission-intent record path (§5, activation condition **A6**) and the budget envelope (§6). This ADR does not widen, narrow or renumber any of them.
- **Absorbs** `docs/experiment-discipline.md`: that file's per-experiment checklist is now `contracts/experiment.yaml` + `contracts/run.yaml`, and the file stays as its human-readable summary.
- Cross-references ADR-0006 (approval gates), ADR-0008 (artifact storage + URI scheme), ADR-0015 (memory promotion — where a `Finding` goes when it outlives its competition), ADR-0018 (generalized competition type), ADR-0019 (eval), ADR-0021 (autonomy), ADR-0024 (markdown soft wrap, which this file obeys).
- Number **0023** was reserved for this work while #193 took 0024; nothing is renumbered.

## Context

ADR-0022 fixed *where* state lives per phase — phase 1 writes GitHub tracking issues plus `competitions/<slug>/` files, phase 2 writes Supabase — and then §1.3 made one promise about the boundary: a migration changes **storage**, never **names**. That promise had no artefact behind it. Concretely, at the time of writing:

- Eleven Supabase migrations model `competitions` / `research_items` / `experiments` / `experiment_runs` / `submissions` / `human_decisions` / `artifacts`, and **not one row of real competition history ever reached them** (discussion #185 audit).
- The five real competitions keep their history in hand-written Markdown — nemo's `tracking.md` alone holds three tables, `submissions.md` a fourth, `insights.md` an `INS-###` list, `bugs.md` a `B#` list — with no machine-checkable shape anywhere, so a missing `code_commit` or an unhashed artifact is invisible until someone tries to reproduce a result.
- `competitions/<slug>/competition.yaml` is already a de-facto `Competition` record, and PR #201 has just rewritten it (dropping `phase:`, restricting `status:` to `open | closed | unknown`, adding `closing_window_days`). It was the only entity with any shape at all, and the shape was only enforced by one test comparing the `budget` subtree.
- ADR-0022 §5 **A6** makes a persisted submission-intent record a *precondition of dispatch* — "a submission whose record could not be written does not dispatch" — while leaving the record's own fields to this ADR. A precondition with no schema cannot fail closed.
- `docs/experiment-discipline.md` carries a per-experiment checklist and says outright that it is an interim home awaiting this ADR.

Two failure modes motivated the work, and both have already happened here:

1. **A result that cannot be reproduced.** nemo's best public score (0.86 / private 0.85) came from a kernel pushed out of a dirty working tree: no commit, no config hash, no seed, and no frozen validation split until the last day of the competition. The number is real; the recipe is partly gone.
2. **A submission whose fate is unknown.** sec-attack's `jed-v4` (Kaggle submission 54134273) read `COMPLETE` with scores on 2026-06-29 and `ERROR` on a re-poll on 2026-09-13, *with the scores still attached*. A timeout or a contradictory poll is not a failure, and treating it as one is how a competition gets a duplicate submission charged against a daily quota it cannot get back.

## Decision

### 1. One definition, two storages — and it lives in `contracts/` at the repo root

There is **one** schema per entity, and both phases validate against it. Phase 1 stores a record as a YAML file under `competitions/<slug>/`; phase 2 will store the same record as a Supabase row. The field **names** are the same in both, which is the whole point of ADR-0022 §1.3.

The schemas live in **`contracts/` at the repository root**, as the task comment directed. The choice is worth stating because three other locations were live options:

| Location | Why not |
|---|---|
| `docs/contracts/` | Puts a machine-checked artefact under a tree that CI treats as prose. A schema that CI validates against real records is code, not documentation. |
| `tools/kca/contracts/schemas/` | Buries the shared vocabulary inside one consumer. Phase 1's consumer is Claude Code / Codex reading files; the `kca` CLI is *a* validator, not the owner. Nesting it there would also re-create issue #65's confusion (harness vs product) at the file-tree level. |
| Generated from `supabase/migrations/` | Inverts the dependency. The migrations are phase 2's storage, and §7 shows they already disagree with what phase 1 actually writes — four entities have no table at all. Generating the contract from the drifted side would ratify the drift. |
| **`contracts/` at the root** | **One directory, visible from the tree root, owned by neither phase, referenced by both. A new competition, a new driver, or KCA itself reaches it by the same relative path.** |

Each schema is a **standalone JSON Schema 2020-12 document written in YAML**, with no `$ref` and no `$defs`. A reader (human or agent) can open one file and understand the entity without resolving a reference, and any JSON Schema implementation can load it alone. `contracts/README.md` carries the entity index and the editing rules.

Two shape rules apply to every schema, and they are deliberate:

- **A declared property is `required`; an unknown value is `null`, never a missing key.** This is the rule ADR-0022 §6 already states for the `budget:` block, generalised: a missing key is a bug, not a local override. So `type: [string, "null"]` is the normal declaration for a value that may not be known yet. Exactly nine properties are exempt, all of them named in their schema and pinned by a test so the set cannot grow silently: `Competition`'s `aliases`, `tracking_issue` and its five side-state fields (`resume_state`, `state_reason`, `decision_id`, `retry_at`, `external_ref`) — a competition that has never entered a side state has nothing to say there — and `Submission.screen`'s `beats_best` and `min_margin`, which ADR-0022 §5 defines as ordering signals rather than gates.
- **Ledger records are closed (`additionalProperties: false`); `Competition` is open (`additionalProperties: true`).** `competition.yaml` is a live, human-edited file that legitimately carries per-competition extras (`sdk:` for sec-attack, `prize_pool_usd:` for arc-agi2). Its canonical keys are still fixed, and §7 D3 records the one extra key that turned up inside a canonical block.

### 2. The entity chain, and the `Experiment` ≠ `Run` split

The chain from discussion #185 §5, unchanged:

`Competition → ResearchItem → Idea → Decision/Strategy → Experiment → Run → Artifact → Submission → Score → Finding → (new Strategy)`

It is a loop, not a pipeline. A `Finding` either promotes to a new `Strategy` (closing the loop) or promotes out of the competition entirely, to a reusable insight (ADR-0015). `Decision` and `Strategy` sit side by side at the same step because they answer different questions about the same moment: a `Decision` is *who approved what, when*; a `Strategy` is *what we are therefore doing until further notice*. An `Experiment` may cite either, both, or neither.

#### `Experiment` ≠ `Run`

**An `Experiment` is a hypothesis under test. A `Run` is one attempt to execute it.** They are separate entities, with separate ids, in separate files.

An `Experiment` holds everything that is *identical across attempts* — `hypothesis`, `changes`, `code_commit`, `data_version`, `config_hash`, `split_id`, `metric`, `seeds` — plus the interpretation that only exists once: `results`, `conclusion`, `lessons`, `findings`. A `Run` holds everything that *varies per attempt*: `attempt`, `command`, `seed`, `executor`, `external_ref`, `started_at` / `finished_at`, `gpu_hours`, `status`, `metrics`, `error_class`, `error_summary`.

**One `Experiment` may hold several `Run`s** — folds of a cross-validation, seeds of a variance check, the same code re-run on a different accelerator. Those are not separate experiments: the hypothesis did not change, so splitting them would make the ledger claim more hypotheses were tested than were.

**The retry rule: a retry creates a *new* `Run`, and failure history is never overwritten.**

- A new attempt is a new file with `attempt: n+1` and `supersedes: <the run it retries>`. The superseded record keeps its `status: failed`, its `error_class` and its `error_summary`, permanently.
- No `Run` record is ever edited to turn a failure into a success. Editing one is the single most attractive shortcut in this whole model and the one that destroys the ledger's only real value — there would be no way to tell a recipe that works from a recipe that worked on the fourth try for a reason nobody wrote down.
- `attempt: 1` cannot `supersede` anything; `attempt: n > 1` must. A run cannot supersede itself, a run of a different experiment, or a run with an equal-or-higher attempt number.
- **A succeeded run is never retried.** If a successful run is superseded, that is a new `Experiment` (different code, config or data), not a retry. The validator enforces this: `supersedes` may only point at a `failed` or `cancelled` run.
- `(experiment_id, attempt)` is unique. Two files claiming attempt 2 of the same experiment is a contradiction, not a merge conflict to resolve by preference.

nemo's EXP-0001 is the worked example and it is real: `RUN-0001` failed (`error_class: kernel_runtime` — `apply_chat_template` returned a `BatchEncoding`, so the kernel scored 0 samples, recorded in `bugs.md` as B3), and `RUN-0002` superseded it and completed 254/254 steps. The experiment's `results` are RUN-0002's. The bug is still in the ledger, which is why the same mistake is now cheap to recognise.

### 3. The eleven entities

| Entity | The question it answers | id | Schema |
|---|---|---|---|
| `Competition` | What are we competing in, under what rules, budget and state? | the slug | [`contracts/competition.yaml`](../../contracts/competition.yaml) |
| `ResearchItem` | What did we read, from where, and how much do we trust it? | `RI-####` | [`contracts/research-item.yaml`](../../contracts/research-item.yaml) |
| `Idea` | What could we try, at what expected gain and cost? | `IDEA-####` | [`contracts/idea.yaml`](../../contracts/idea.yaml) |
| `Decision` | Who approved what, when, and against which plan? | `DEC-####` | [`contracts/decision.yaml`](../../contracts/decision.yaml) |
| `Strategy` | What are we doing until further notice, and on what evidence? | `STRATEGY-###` | [`contracts/strategy.yaml`](../../contracts/strategy.yaml) |
| `Experiment` | Which hypothesis is under test, with which code, data and split? | `EXP-####` | [`contracts/experiment.yaml`](../../contracts/experiment.yaml) |
| `Run` | What actually executed, when, and did it fail? | `RUN-####` | [`contracts/run.yaml`](../../contracts/run.yaml) |
| `Artifact` | Which file is it, where, and is it still the same file? | `ART-####` | [`contracts/artifact.yaml`](../../contracts/artifact.yaml) |
| `Submission` | What are we about to send, and what happened to it? | the intent `ref` | [`contracts/submission.yaml`](../../contracts/submission.yaml) |
| `Score` | What did the platform say, on which leaderboard, and when? | `SCORE-####` | [`contracts/score.yaml`](../../contracts/score.yaml) |
| `Finding` | What do we now know that outlives this experiment? | `FIND-####` | [`contracts/finding.yaml`](../../contracts/finding.yaml) |

`RI-` is the `ResearchItem` prefix rather than the more obvious `RES-` because ADR-0022 §6 already spends `RES-` on budget reservations, and a shared prefix across two id spaces is a debugging tax with no upside.

Three enums are **reused verbatim** from the Supabase migrations rather than re-invented, so the phase boundary costs nothing at those fields: `run_status` (`queued | running | succeeded | failed | cancelled`) on `Run.status`, `trust_level` (`official | trusted_public | community | untrusted | unknown`) on `ResearchItem.trust`, and `decision_status` (`pending | approved | rejected | expired`, extended here with `superseded`) on `Decision.status`.

`Score` is a separate entity rather than four columns on `Submission` for a reason phase 1 already met: **the private score arrives later than everything else**. nemo's private leaderboard was released on 2026-06-16, the day after the competition closed and after the session that made the submission had ended. A late-arriving fact that mutates an earlier record in place is a fact you cannot audit; a new record with its own `private_released_at` and `read_at` is one you can.

### 4. Where a record lives

| Entity | Phase-1 record path |
|---|---|
| `Competition` | `competitions/<slug>/competition.yaml` |
| `ResearchItem` | `competitions/<slug>/ledger/research/<id>.yaml` |
| `Idea` | `competitions/<slug>/ledger/ideas/<id>.yaml` |
| `Decision` | `competitions/<slug>/ledger/decisions/<id>.yaml` |
| `Strategy` | `competitions/<slug>/ledger/strategies/<id>.yaml` |
| `Experiment` | `competitions/<slug>/ledger/experiments/<id>.yaml` |
| `Run` | `competitions/<slug>/ledger/runs/<id>.yaml` |
| `Artifact` | `competitions/<slug>/ledger/artifacts/<id>.yaml` |
| `Submission` | `competitions/<slug>/submissions/<utc-timestamp>-<intent-id>.yaml` |
| `Score` | `competitions/<slug>/ledger/scores/<id>.yaml` |
| `Finding` | `competitions/<slug>/ledger/findings/<id>.yaml` |

One file per record, one directory per entity, under `competitions/<slug>/ledger/`. One file per record rather than one appended list per entity, because two agents working the same competition concurrently then never edit the same line — and because `git log --follow` on a single record is the cheapest audit trail available.

`Competition` keeps its existing path. `competition.yaml` is already the de-facto record, the context pack (ADR-0022 §4) already reads it first, and precedence rank 1 in ADR-0022 §3 already names it. Moving it would break all three for nothing.

`Run` records are committed at `ledger/runs/<id>.yaml` and **point at** the bulk output they describe via `run_dir`. `runs/` is gitignored (`.gitignore:58`) and stays that way — a `Run` record is metadata (a few hundred bytes), not the checkpoints, logs and predictions it names. `run_dir` is therefore nullable: for a Kaggle kernel there is no local run directory at all, and `external_ref` (the kernel slug or version) is the handle instead.

That naming collides with `.gitignore`, and the collision is worth recording because it was invisible: the bulk-output rules `artifacts/` and `runs/` (`.gitignore:57-58`) match a directory of that name at **any** depth, so `competitions/<slug>/ledger/runs/` and `.../ledger/artifacts/` were excluded from the commit while the validator — which reads the working tree — stayed green. Two re-include lines naming those directories fix it, and a test asserts that **no record path is gitignored**, because a record the VCS cannot see is not a record.

**The `Submission` path is not under `ledger/`.** ADR-0022 §5 **A6** already fixed it at `competitions/<slug>/submissions/<utc-timestamp>-<intent-id>.yaml`, and a merged ADR's path is not something this contract renames. What §5 left open, this ADR pins:

- **`<intent-id>` is the record's own `ref`, verbatim.** Given a ref, the file is findable from the ref alone — which is the lookup reconciliation actually performs, hours or months later, from a platform response that knows nothing but the id it was given.
- **`<utc-timestamp>` is `YYYY-MM-DDTHHMMSSZ`**, always UTC, so the directory sorts chronologically in any listing and a day's dispatches are countable against a daily quota by prefix.
- The `ref` is the `Submission`'s identity. There is no separate `id` field: a submission's identity is the intent that authorised it, not a row number assigned afterwards.

### 5. The invariants

The schemas describe **shape**. They deliberately do not attempt the ledger's **invariants** — id uniqueness, cross-file foreign keys, the retry rule, the reconciliation rules — because those are cross-record and conditional on values, and a schema language contorted into expressing them stops being readable by the humans and agents who have to follow it. `kca contracts validate` checks them as a second pass. This is the list; `INVARIANTS` in `tools/kca/contracts.py` is the implementation, and the two are meant to be read together.

| # | Invariant |
|---|---|
| **I1** | A record's filename and its own id agree. For a `Submission`, the filename is `<utc-timestamp>-<ref>.yaml` (§4); for everything else the stem *is* the id, and the id matches the entity's prefix pattern. |
| **I2** | A record's `competition` field matches the directory it lives in. A record cannot claim to belong to another competition. |
| **I3** | Ids are unique within a competition and entity. |
| **I4** | Every reference resolves, to a record of the right entity, in the same competition. A dangling `experiment_id`, `run_id`, `score_id`, `decision_id` or `supersedes` is an error, not a placeholder. |
| **I5** | The retry rule (§2): `(experiment_id, attempt)` is unique; `attempt: 1` supersedes nothing and `attempt: n > 1` supersedes exactly one earlier run of the *same* experiment with a *lower* attempt number and a `failed` or `cancelled` status; a run never supersedes itself; a `failed` run carries an `error_class` other than `none` **and** an `error_summary`; a `succeeded` run carries no `error_class`. |
| **I6** | `Experiment.runs` and `Run.experiment_id` agree **in both directions** — a run that names an experiment not listing it is as much an error as a listed run that names another experiment. An experiment cannot be its own parent. An evaluated experiment has a `conclusion`. |
| **I7** | A `live` record carries what reproducibility needs: `ResearchItem.fetched_at`; `Experiment.code_commit`, `data_version`, `config_hash`, `split_id` and at least one seed; `Run.command` and `started_at`; `Submission.artifact_sha256`. A `backfilled` record is exempt from completeness but not from shape (§6), and a `backfilled` `Submission`'s `ref` must start with `INT-BACKFILL-` while a `live` one must not. |
| **I8** | ADR-0022 §5's two hard gates block a dispatch: if `screen.require_repro` or `screen.rules_check` is not `pass`, the record's `status` cannot be a dispatched one. `beats_best` and `min_margin` are ordering signals and are **not** checked here, exactly as §5 says. |
| **I9** | Scenarios 0 and 4 are inside the closing window and human-gated, so such a `Submission` carries a `decision_id`. |
| **I10** | The reconciliation rules (§6): `status: needs_reconciliation` requires `reconciliation.required: true` and an unresolved `outcome`; `outcome: absent` contradicts a dispatched status; a `scored` submission has a `score_id`; an `intent` record has not been dispatched, so its `submitted_at` is null; and a replacement may only supersede a submission whose reconciliation outcome is **`absent`**. |
| **I11** | A rejected `Idea` keeps its `rejection_reason`. A revival (`re_proposal_of`) cites `new_evidence` — re-proposing a rejected idea unchanged is how a loop becomes a spiral. |
| **I12** | `content_hash` and `hash_algo` are set together. A hash without its algorithm is not an identity. |
| **I13** | A rank carries its denominator (`public_rank` → `public_total`, `private_rank` → `private_total`), and a `private_score` carries `private_released_at`. |
| **I14** | A `Competition` in one of ADR-0022 §3's six side states records `resume_state` and `state_reason`. A `verified_daily_limit` carries its `verified_source`, `verified_at` and `verified_reset_boundary`, and is never below `reserve_for_human`. |
| **I15** | An `active` `Strategy` has no `in_force_to`; a superseded or retired one has. |
| **I16** | An `approved` `Decision` names what was chosen (`selected`, one of the `options` offered) and when (`decided_at`); a `pending` one names neither. |

### 6. `provenance`, and why a timeout is not a failure

Every ledger record carries **`provenance: live | backfilled`**.

- **`live`** — written by the loop as it ran. The full reproducibility set is required (I7).
- **`backfilled`** — reconstructed afterwards from tracking issues, notes, kernel logs or leaderboards. Shape is validated; completeness is not.

This is the mechanism that lets real history into the ledger without either fabricating the fields it never had or starting from an empty directory. Every record shipped with this ADR is `backfilled`, and each one names the source it was reconstructed from and the fields that could not be recovered. Those gaps are §7's drift register. The alternative — inventing a plausible `config_hash` — would make the ledger worse than no ledger, because it would be trusted.

A `backfilled` `Submission` additionally takes the **`INT-BACKFILL-`** prefix on its `ref` (I7). A submission-intent record is a *dispatch authorization* under ADR-0022 §5 A6; a record reconstructed after the fact must never be readable as one, by a human or by a future gate that scans the directory.

#### A timeout is not a failure

Discussion #185 §11's rule, carried into `Submission.status` and the `reconciliation` block:

**When a dispatch's outcome is unknown, the state is `NEEDS_RECONCILIATION` — never `failed`.** A lost response, a timeout, a 5xx, a killed session: none of them is evidence that the submission did not land. Recording an unknown as a failure is how a retry becomes a duplicate submission charged against a daily quota that does not roll over (ADR-0022 §6).

The rule that follows: **query the platform before any retry.** `reconciliation` records that query — `queried_at`, `source`, and an `outcome` of `present | absent | ambiguous | unresolved | not_required` — and I10 permits a replacement dispatch **only** when the outcome is `absent`, i.e. only when the platform has been asked and has said the submission is not there. `ambiguous` and `unresolved` are terminal without a human: they route to `WAIT_HUMAN`, they do not decay into `absent` because time passed.

`ambiguous` is not hypothetical. sec-attack's `jed-v4` (external id 54134273) read `COMPLETE` with both scores on 2026-06-29 and `ERROR` on a re-poll on 2026-09-13 **with the scores still attached**. Its record carries `outcome: ambiguous`, both observations, and no retry. It is the reason this section exists rather than a paragraph saying timeouts should be handled carefully.

### 7. Mapping: contract field → Supabase column → phase-1 tracking issue

The mapping below is the **as-built** correspondence, per the task's deliverable 4. Where the three disagree, **the drift is recorded and the schema is not migrated** — KCA's own feature development is on hold (`CLAUDE.md`, "Two phases"), and a migration written now against un-exercised columns would be a guess dressed as a decision. Migration column references are `<migration>:<table>.<column>`.

`↦` means a direct correspondence, `—` means the target has no place for the value.

#### Competition

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `slug`, `kaggle_slug` | `0001:competitions.slug` (unique with `platform`) | tracking-issue title; `competition.yaml` | |
| `title` | `0001:competitions.title` | issue body | |
| `metric` | `0001:competitions.metric_name`, `.objective` | `strategy.md` prose | |
| `status` (`open\|closed\|unknown`) | — | issue label / body prose | |
| `state` (ADR-0022 §3, 20+6 tokens) | — | issue body "current snapshot" | **D2** |
| `resume_state`, `state_reason`, `retry_at`, `external_ref` | — | prose, when written at all | **D2** |
| `competition_type` (task taxonomy) | `0009:competitions.competition_type` (**platform** taxonomy) | prose | **D1** |
| `launch`, `deadline` | `0009:competitions.deadline`, `0011:competitions.deadline_at` (two columns) | issue body | **D15** |
| `closing_window_days` | — | — | |
| `timing_verified_source\|_at\|_ttl` | `0011:competitions.last_rules_fetch_at` (partial) | — | |
| `data_policy` | `0004:competitions.competition_policy` (jsonb) | `rules.md` | **D16** |
| `submission_mode`, `primary_artifact` | `0011:competitions.submission_format` (jsonb) | `rules.md` | |
| `budget.submissions.verified_daily_limit` | `0001/0011:competitions.max_daily_submissions` (no provenance columns) | `rules.md` | |
| `budget.*` (compute, llm, failures, progress) | — | — | |
| `best.{cv_metric,cv_score,public_lb,private_lb,submission_id}` | `0001:competitions.current_best_metric`, `.current_best_submission_id` (one scalar for four) | `submissions.md` table | **D3** |
| `autonomy_config` | — | `kca-<slug>.yaml` | |
| `tracking_issue`, `aliases` | `0004:competitions.repo_url` (different thing) | the issue itself | |

#### ResearchItem

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `id` | `0001:research_items.id` (uuid) | `references.md` bullet | |
| `title`, `source_reference` | `0001:research_items.title`, `.url` | `references.md` | |
| `source_type` | `0001:research_items.source_type`, `0005:.source_kind` (two columns) | prose | |
| `trust` | `0001:research_items.trust` (`trust_level`) ↦ verbatim | — | |
| `summary`, `quotes` | `0001:research_items.summary`, `.relevant_quotes` | `research.md` | |
| `fetched_at` | `0001:research_items.fetched_at` | — | |
| `content_hash`, `fetcher` | `0005:research_items.content_hash`, `.fetcher`, `.html_artifact_id`, `.text_artifact_id` | — | **D6** |
| `related_ideas` | — (`0005:research_citations` links to runs/experiments, not ideas) | prose | **D7** |

#### Idea

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| *(the whole entity)* | — **no table** | `tracking.md` Table 2 (`T#` rows), `strategy.md` "Hypotheses" | **D12** |
| `hypothesis`, `expected_gain`, `cost`, `risks` | — | Table 2 "Direction" cell, prose | |
| `required_approvals` | — | Table 1 (`D#`) cross-reference | |
| `status`, `rank` | — | Table 2 status emoji | |
| `rejection_reason`, `re_proposal_of`, `new_evidence` | — | `strategy.md` "Rejected ideas" prose | **D7** |

#### Decision

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `id` | `0001:human_decisions.id` | `tracking.md` Table 1 `D#` | |
| `question`, `options`, `selected`, `rationale` | `0001:human_decisions.prompt`, `.options`, `.selected`, `.rationale` | Table 1 "Topic" / "Decision" cells | |
| `status` | `0001:human_decisions.status` (`decision_status`) ↦ verbatim, plus `superseded` here | ✅ in the cell | |
| `requested_at`, `decided_at`, `expires_at` | `0001:human_decisions.created_at`, `.decided_at`, `.expires_at` | date in the section header only | **D8** |
| `decided_by`, `channel` | `0001:human_decisions.decided_by`, `.requested_by` | the comment author | |
| `gate` (the seven always-gated actions + `direction` + `agent_screened`) | `0001:human_decisions.decision_type` (free text, approval-shaped) | prose | **D13** |
| `plan_hash` | — | — | **D8** |

#### Strategy

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| *(the whole entity)* | — **no table** | `strategy.md` "Current direction" | **D12** |
| `statement`, `derived_from`, `evidence` | — | prose | |
| `scope.frozen_split_id` | — (`0001:experiments.dataset_version` is the nearest, and is not a split) | — | **D4** |
| `status`, `in_force_from`, `in_force_to` | — | the file's edit history | |

#### Experiment

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `id` | `0001/0004:experiments.id` | `tracking.md` Table 2 `T#`, `versions/v##` | |
| `hypothesis` | `0001:experiments.hypothesis` ↦ | Table 2 cell | |
| `changes` | `0001:experiments.config` (jsonb) | prose | |
| `code_commit` | `0001:experiments.code_ref`, `0004:.branch` | — | **D5** |
| `data_version` | `0001:experiments.dataset_version` ↦ | prose | |
| `config_hash`, `split_id`, `seeds` | — | — | **D4**, **D5** |
| `metric`, `results.{cv_mean,cv_std,public_lb,private_lb}` | `0002:experiment_run_metrics` (key/value rows, per **run**) | `submissions.md` columns | |
| `parent_experiment` | `0001:experiments.baseline_experiment_id` ↦ | prose | |
| `idea_id`, `strategy_id`, `decision_id` | — | Table 1 / Table 2 cross-references | **D12** |
| `runs`, `artifacts`, `findings` | FK from the child rows | prose | |
| `status`, `conclusion`, `lessons` | `0001:experiments.status` (`run_status`), `0004:.status` (free text `'active'`) — two vocabularies | Table 2 status, `insights.md` | **D2** |
| `resource` | — (`0003:agent_jobs.cost_usd` is the nearest, and is a job cost) | prose | |

#### Run

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `id` | `0001:experiment_runs.id` | — (usually unnamed in prose) | |
| `experiment_id` | `0001:experiment_runs.experiment_id` ↦ | implied by section | |
| `attempt` | `0001:experiment_runs.run_number` (unique with experiment) ↦ | — | |
| `supersedes` | — | prose ("second attempt after the fix") | **D5** |
| `command`, `status`, `metrics` | `0001:experiment_runs.command`, `.status` (`run_status` ↦), `.metrics` | prose | |
| `started_at`, `finished_at` | `0001:experiment_runs.started_at`, `.ended_at`, `0004:.finished_at` (two columns) | prose | |
| `run_dir`, `external_ref` | `0002:experiment_runs.run_dir`, `.external_run_id` ↦ | kernel slug in `tracking.md` "Kernel push status" | |
| `executor`, `seed`, `config_hash`, `gpu_hours` | — | prose | **D5** |
| `error_class`, `error_summary` | `0001:experiment_runs.stderr_artifact_id` (the log, not the class) | `bugs.md` `B#` | |
| `artifacts`, `log_paths` | `0001:experiment_runs.artifacts`, `0004:.artifact_paths` (two columns) | prose | |

#### Artifact

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `id` | `0001:artifacts.id` | — | |
| `kind`, `path`, `byte_size` | `0001:artifacts.kind`, `.storage_path` (ADR-0008 URI scheme), `.byte_size` | prose | |
| `content_hash` | `0001:artifacts.content_hash` ↦ | — | **D10** |
| `hash_algo` | — (the column holds a hash with no algorithm) | — | **D10** |
| `storage`, `retention` | — | prose | **D10** |
| `produced_by_run`, `produced_at` | `0001:experiment_runs.{stdout,stderr}_artifact_id` (inverted direction) | prose | |

#### Submission

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| `ref` (**the identity**) | — (`0001:submissions.id` is a uuid; no intent column) | filename | **D14** |
| `competition`, `experiment_id`, `run_id` | `0001:submissions.competition_id`, `.experiment_run_id`, `0004:.run_id` | `submissions.md` "Run/Experiment" | |
| `artifact`, `artifact_sha256` | `0001:submissions.submission_file_artifact_id`, `0004:.file_path` | "Artifact" column | **D10** |
| `code_commit` | — | — | **D5** |
| `expected_score`, `expected_metric` | `0004:submissions.cv_score` (score only) | "Local CV" column | |
| `reason`, `scenario`, `screen`, `budget_reservations` | `0001:submissions.notes`, `0004:.note` (two free-text columns) | "Notes" column | **D14** |
| `status` | `0001:submissions.status` (free text, default `'prepared'`) | prose | **D14** |
| `submitted_at` | `0001:submissions.submitted_at` ↦ | "Date" column | **D11** |
| `external_id` | `0001:submissions.external_submission_id` ↦ | prose | |
| `reconciliation.*` | — | — | **D14** |
| `account`, `team` | `0009:teams`, `0009:team_memberships` (membership, not attribution) | prose ("harrysun2006" / "firefly2006") | |
| `driver` | `0003:agent_jobs.model` (the model, not the driver) | — | |
| `selected_for_final`, `supersedes` | — | prose | |

#### Score

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| *(the whole entity)* | — **no table**; scores are columns **on `submissions`** | `submissions.md` LB columns | **D12** |
| `public_score`, `private_score` | `0001:submissions.public_score`, `.private_score`, `0004:.public_lb_score` (three columns) | "Public LB" / "Private LB" | |
| `public_rank`, `public_total`, `private_rank`, `private_total` | — | prose | **D12** |
| `scored_at`, `private_released_at`, `read_at` | — | prose | **D12** |
| `is_eligible`, `selected_for_final`, `source` | — | prose | **D12** |

#### Finding

| Contract field | Supabase | Phase-1 tracking issue / file | Drift |
|---|---|---|---|
| *(the whole entity)* | — **no table** | `insights.md` `INS-###` blocks | **D12** |
| `statement`, `type`, `confidence`, `status` | — | the `INS-###` fields ↦ (same four names) | |
| `evidence`, `from_experiments`, `from_scores` | — | "evidence:" bullet | |
| `transfer_scope` | — | "transfer scope:" bullet ↦ | |
| `new_strategy`, `insight_ref` | — | prose; ADR-0015 promotion target | |

#### Drift register

Every disagreement above, named once. **None of these is migrated by this ADR.**

| # | Drift | Disposition |
|---|---|---|
| **D1** | `competition_type` names two different axes: the contract's is a **task** taxonomy (`tabular \| cv \| nlp \| llm \| simulation_agent \| notebook \| reasoning`), `0009:competitions.competition_type` is a **platform** taxonomy (`kaggle \| devpost \| hackathon_devpost \| ctf \| generic`). | Phase 2 needs both axes; renaming either one now would break the other's consumers. Contract keeps the task axis (it is what phase 1 writes and what ADR-0018 reasons about); phase 2 adds a `platform` field rather than overloading this one. |
| **D2** | ADR-0022 §3's state vocabulary has **no Supabase home**: `competitions` has no `state` column, the side-state fields have none, and `experiments.status` is `run_status` in 0001 but free text defaulting to `'active'` in 0004 — two vocabularies for one column. | Recorded. The state machine is phase-1 authority (ADR-0022 §3 precedence rank 1 is `competition.yaml`); phase 2 must add the column using **these** tokens, not invent a third set. |
| **D3** | orbit-wars carries `best.attributed_entry_lb`, a sixth key inside a block whose five canonical keys are what ADR-0022 §3 reads. | `best` is left open in the schema with a comment. An extra key is an observation, not a new canonical field; ADR-0022 §3 still reads five. |
| **D4** | **No frozen validation split anywhere in phase-1 history.** `Strategy.scope.frozen_split_id` and `Experiment.split_id` are null across nemo's campaign; every cross-adapter comparison before 2026-06-15 rested on the public leaderboard, and the local ranking only became possible when T12 built the hard-val set. | Both fields are `live`-required (I7), so a `live` experiment cannot repeat it. History stays `backfilled` and honest. |
| **D5** | **No `code_commit` / `config_hash` / `seeds` / `supersedes` on historical experiments and runs**: kernels were pushed from a dirty working tree, so the best score in the repository is only partly reproducible. | `live`-required (I7). This is precisely what ADR-0022 §5's `require_repro` hard gate exists to block, and the backfilled nemo records say so in their own `notes`. |
| **D6** | Sources were **cited in prose and never archived** — no `content_hash`, no stored text, despite `0005` adding exactly those columns. | Recorded. `ResearchItem.fetched_at` is `live`-required; archiving is a phase-2 capability (ADR-0008 storage), not a phase-1 backfill. |
| **D7** | A rejected idea's predecessor exists only as `strategy.md` prose, so `Idea.re_proposal_of` cannot be reconstructed backwards. | Recorded. I11 makes it enforceable going forward. |
| **D8** | Decisions record the **answer, not the bound request**: no `requested_at`, no `plan_hash`. `0001:human_decisions` has `prompt`/`options`/`expires_at` but no `plan_hash` either. | Recorded. Discussion #185 §9 wants both for a live gate; `plan_hash` is in the contract so a future gate has somewhere to write it. |
| **D9** | nemo's soup **merge computation is not a recorded `Run`** — it happened inside the packaging kernel, so `RUN-0003` records packaging and the merge itself has no run record. | Recorded. I6's both-directions check makes the omission visible in future, where the merge would be its own run. |
| **D10** | **Artifacts were never hashed**, and one Kaggle dataset's slug was not recorded, so `ART-0003` has no resolvable path. `0001:artifacts.content_hash` exists but holds a hash with no algorithm column. | `hash_algo` is contract-side (I12). Where a file is committed, the backfill uses its **git blob sha1** — exact and immutable, unlike a sha256 of a working tree that was later reformatted. |
| **D11** | The nemo soup submission time disagrees between sources: `submissions.md` says "~12", the kernel log says 03:22Z. | Record takes **03:22Z** (two sources agree on it and it is the more precise); the disagreement is noted in the record itself. |
| **D12** | **No Supabase table exists for `Idea`, `Strategy`, `Score` or `Finding`.** Scores are columns on `submissions`, so a late private score would mutate the submission row (§3). | Recorded, not migrated. These four are the largest phase-2 schema gap and the reason this ADR defines them file-first. |
| **D13** | `0001:human_decisions` is **approval-shaped** (`decision_type`, `prompt`, `options`, `selected`) with no place for a **direction proposal** — which ADR-0022 §5 explicitly routes differently: the agent proposes and waits in `WAIT_HUMAN`, it does not gate an action. | Contract covers it with `gate: direction`. Phase 2 inherits the distinction rather than collapsing a proposal into an approval. |
| **D14** | `Submission` identity and lifecycle diverge: phase 1's identity is the intent `ref` (ADR-0022 §5 A6), Supabase's is a uuid with `external_submission_id`; there is no intent column, no `reconciliation` block, `status` is free text defaulting to `'prepared'`, and `notes`/`note` are two free-text columns doing the work of `reason`, `scenario`, `screen` and `budget_reservations`. | Recorded. The intent record is a **precondition of dispatch**, so its shape is contract-side and fail-closed; phase 2 must store the ref, not re-key on a uuid. |
| **D15** | **orbit-wars' deadline is unresolved**: `competition.yaml` says 2026-06-23, the discussion #185 audit's Kaggle API read says 2026-07-07. Supabase has two deadline columns (`0009:.deadline`, `0011:.deadline_at`) and would not resolve it either. | `deadline` is left as it was, the conflict is recorded as a comment in the file, and `timing_verified_*` stay null — which under ADR-0022 §5 **A1** fails activation for that competition, correctly. |
| **D16** | Live values outside the template's comment enums: `data_policy: api` (arc-agi3) and `competition_type: reasoning` (arc-agi2). | Contract enums widened to include both; the template's comments updated to match. A real value beats a template's guess. |

### 8. Validation and the CI gate

`kca contracts validate` is the validator, registered as a **`READ_ONLY`, no-DB, no-network** command (`tools/kca/contracts.py`, `tools/kca/agent/command_registry.py`). It runs in two passes — schema shape, then the §5 invariants — over every record under `competitions/`, and takes `--competition <slug>` to narrow and `--require-all-entities` to also fail when an entity has no record at all. `kca contracts schemas` lists the eleven entities with their schema file, id pattern and record path.

It **implements the JSON Schema keyword subset the schemas actually use**, with no third-party dependency, so validation works from a bare checkout: `type · enum · const · properties · required · additionalProperties · items · pattern · minimum · minItems · minLength`. Two tests keep that honest: one asserts the schemas use **nothing outside that list** (so a new keyword cannot be added without extending the validator or failing CI), and one re-validates every real record with the `jsonschema` library's `Draft202012Validator` (a `dev` extra), so the subset stays standards-conformant rather than merely self-consistent.

**CI validates real records, not fixtures.** `tests/test_contracts.py` runs in the existing `no-db pytest` job and the workflow also runs `kca contracts validate --require-all-entities` as its own named step, so the gate is legible in the checks list. The coverage floor is **at least one real record per entity**, taken from the two competitions with the richest history: `nvidia-nemotron` (the LoRA-soup campaign, with its failed-then-retried kernel run) and `sec-attack` (three breadth experiments and the `NEEDS_RECONCILIATION` submission). The suite additionally walks nemo's chain end to end — `RI-0001 → IDEA-0001 → DEC-0001 → STRATEGY-001 → EXP-0001/EXP-0002 → RUN-000n → ART-000n → the intent record → SCORE-0001 → FIND-0001` — so a schema change that breaks the *relationships* fails, not only one that breaks a field.

A fixture-only gate would have passed on day one and told us nothing. Every record in this ADR is a real thing that happened, which is why writing them surfaced sixteen drifts instead of zero.

### 9. What `competitions/_templates/` emits

The templates are **extended, not replaced** — `competition.yaml`, `strategy.md`, `tasks.md`, `submissions.md`, `insights.md`, `bugs.md`, `references.md`, `rules.md`, `postmortem.md` all stay, and `competition.yaml` remains the `Competition` record. A parallel format would have meant every competition carrying two.

What changes:

- **`competitions/_templates/ledger/README.md`** carries a ready-to-copy, fully commented skeleton for each of the ten ledger entities, the path each one goes to, and the four rules that catch most mistakes (every key stays, `provenance`, the retry rule, reconciliation). One file rather than ten placeholder records, because a placeholder record copied into a live competition is a record that validates and lies; a fenced block copied out of a README cannot be mistaken for history.
- **Each Markdown template gains a two-line header** naming the ledger directory that holds the record it summarises and the command that checks it: `strategy.md` → `ledger/strategies/` + `ledger/decisions/` + `ledger/ideas/`, `tasks.md` → `ledger/ideas/` + `ledger/experiments/`, `submissions.md` → `submissions/` + `ledger/scores/`, `insights.md` → `ledger/findings/`, `references.md` → `ledger/research/`, `bugs.md` → the failed `Run`'s `error_class`, `experiment-readme.md` → `ledger/experiments/` + `ledger/runs/`.
- **`competition-readme.md`** drops its stale `phase:` line (PR #201 removed the field) for `state:`, and lists `competition.yaml` + `ledger/` as the authoritative record above the prose links.
- **`competition.yaml`'s comment enums** gain `reasoning` and `api` so the template stops disagreeing with live records (§7 D16).

The division of labour is the point: **the ledger is the record, the Markdown is the reading view.** Prose that contradicts a ledger record loses — ADR-0022 §3's precedence order already says `competition.yaml` (rank 1) beats `tracking.md` (rank 3), and this extends it to the rest of the entities.

### 10. Scope boundary and hand-over

Deliberately **not** in this ADR, with the issue that owns each:

- **`.claude/skills/**` — #192.** No skill is re-pointed here and `kg-run` is untouched. The hand-over is this path: the contracts are `contracts/*.yaml`, the entity index and editing rules are `contracts/README.md`, the record paths are §4 above, and the check is `kca contracts validate`. A skill that needs to emit or read a ledger record reads those and nothing else.
- **Account / credential modelling — #193.** `Submission.account` and `.team` are free-text attribution of what actually ran (`harrysun2006` / `firefly2006`), not a credential model.
- **`competitions/**/*.md` reduction — #195.** Nothing is deleted here. The Markdown keeps its content and gains a pointer.
- **`tools/kca/COMMANDS.md` rewrite — #198.** Only the two `kca contracts` rows are added, on top of the merged version of that file.
- **KCA's audit-log design — #203.** A ledger record is competition-owned and committed; the acting agent's audit log is driver-specific and gitignored. ADR-0022 §5 is explicit that the audit log is *supplementary evidence of what ran, never the record*, and nothing here changes that.
- **Activation of relaxed autonomy — ADR-0022 §5 A1–A7.** This ADR supplies the **shape** of the A6 submission-intent record. It does not activate anything, does not implement the §5 pre-submit gate, and does not change the standing rule: **ask before every Kaggle submission or kernel push.**

## Consequences

- There is now one vocabulary with one definition, and it is machine-checked. A phase-2 migration changes storage; the field names are already fixed and already exercised against real records.
- ADR-0022 §5 **A6** becomes implementable: the intent record has a schema, a pinned path, and two hard-gate invariants (I8) that a pre-submit gate can fail closed against.
- A retry can no longer quietly erase a failure. The ledger distinguishes "this recipe works" from "this recipe worked on the fourth attempt", which is the difference between a reproducible campaign and a folklore one.
- A submission whose outcome is unknown has a state that is not "failed", and a replacement dispatch requires a platform query first. This costs one API call and saves a duplicate submission against a non-rolling daily quota.
- Sixteen drifts between phase-1 practice, the Supabase schema and the tracking issues are written down instead of discovered during a migration. Four entities (`Idea`, `Strategy`, `Score`, `Finding`) have no Supabase table at all, which is now a known gap with a defined shape rather than a surprise.
- The cost is real and worth naming: every experiment now writes two records instead of one prose line, and a `live` record without a commit, config hash, split and seed fails CI. That is the intended friction — it is the same friction `require_repro` will apply at submission time, moved earlier where it is cheap to fix.
- Historical records are `backfilled` and will stay that way. They validate for shape, they do not pretend to reproducibility, and the difference is a field anyone can grep.

## Alternatives considered

- **Generate the contracts from `supabase/migrations/`.** Rejected: §7's register lists every place the migrations disagree with what phase 1 actually writes, including four entities with no table at all. Generating from the drifted side would ratify the drift and make phase 1 the deviation from a schema no row has ever used.
- **One append-only file per entity per competition** (`ledger/experiments.yaml` holding a list). Rejected: concurrent agents collide on the same line, `git log --follow` stops working per record, and a single malformed entry invalidates every record in the file.
- **Full JSON Schema with `$ref` and a shared `$defs` bundle.** Rejected for phase 1: the records' primary readers are humans and agents reading one file, and a `$ref` chain is exactly the kind of indirection that gets a field wrong in an agent context. The cost is some duplication across schemas, which the subset test and the `jsonschema` cross-check keep consistent.
- **Depend on `jsonschema` at runtime.** Rejected: `kca contracts validate` must work from a bare checkout with no extras installed. The library is a `dev` extra and used in tests to prove the hand-written subset conforms.
- **A single `Result` entity instead of `Submission` + `Score`.** Rejected by phase-1 evidence: nemo's private score arrived a day after the competition closed, and sec-attack's scores changed status on a re-poll three months later. Both are new facts about an old dispatch, and a separate record dates them.
- **Wait for phase 2 and model this in Supabase first.** Rejected: KCA feature development is on hold, and phase 1 is generating the history right now. A contract written after the history is a contract written against fabricated fields.

## Follow-ups

| Item | Where |
|---|---|
| Emit `live` records from the loop rather than backfilling them | phase-1 competition work (the first `live` record is the real test of I7) |
| Skills that read / emit ledger records | #192 |
| Account + credential model behind `Submission.account` | #193 |
| Reduce `competitions/**/*.md` now the ledger holds the record | #195 |
| `COMMANDS.md` rewrite around these commands | #198 |
| Supabase columns for `state` / `Idea` / `Strategy` / `Score` / `Finding` (drifts D2, D12) | phase 2, on the ADR-0022 §1 boundary |
| A pre-submit gate that fails closed on I8 | ADR-0022 §5 condition A5 |

## Cross-references

- `docs/adr/0022-long-run-competition-operating-model.md` — §1.3 one vocabulary, §3 state machine, §4 context pack, §5 A6 intent record, §6 budgets.
- `docs/adr/0021-kca-autonomy-model.md` — the always-human-gated set that `Decision.gate` enumerates.
- `docs/adr/0008-artifact-storage-local-first.md` — the artifact URI scheme `Artifact.path` follows.
- `docs/adr/0015-memory-promotion-model.md` — where a `Finding` goes when it outlives its competition.
- `docs/experiment-discipline.md` — the human-readable per-experiment checklist, now backed by `contracts/experiment.yaml` + `contracts/run.yaml`.
- `contracts/README.md` — the entity index, the editing rules and the keyword subset.
- [Issue #191](https://github.com/amyteq/tt_pangu/issues/191) — the task; [discussion #185](https://github.com/amyteq/tt_pangu/discussions/185) §5 / §9 / §11 — the entity model, the decision gate and the reconciliation rule.
