# ADR-0022: Long-run competition operating model

## Status

Accepted (2026-09-14). Directed by the project owner in [discussion #185 — task comment](https://github.com/amyteq/tt_pangu/discussions/185#discussioncomment-18426101) ("上面的建议都很中肯,全部采纳" / "§9 可以进一步放宽"), filed as issue #190.

- **Extends** ADR-0020 (goal-driven Kaggle loop) — and **inverts its state authority for phase 1** (see "Relationship to ADR-0020").
- **Widens** ADR-0021 (KCA autonomy model) §2 — screening stops being a quota gate and becomes ordering + safety. ADR-0021 §1 (two agents), its always-human-gated set, and §3 (eval) stay in force. See "Relationship to ADR-0021" for the section-by-section disposition.
- Cross-references ADR-0006 (configurable approval gates), ADR-0018 (generalized competition type), ADR-0019 (eval regression suite).

This ADR is the operating model for **phase 1 (long-run validation, driven by Claude Code / Codex)** and the **contract phase 2 (KCA) inherits**. It is written to be loaded into an agent context in full — that is its purpose.

## Context

The repository audit on discussion #185 found that the long-run operating model existed only as a discussion thread. Concretely:

- The five real competitions under `competitions/` keep their state in `competitions/<slug>/*.md` plus GitHub issues #86 / #87. **Not one row reached Supabase**, even though eleven migrations model exactly that.
- `competitions/<slug>/competition.yaml` carries two overlapping progress fields (`status:` and `phase:`) whose value sets do not even agree between the template and the live files — two vocabularies before anyone writes a third.
- There is no checkpoint, no lease, no restart recovery, and no submission reconciliation. M14's smart poller + stuck detector are the closest existing machinery and cover neither "the host restarted" nor "the submit request was sent but the response was lost".
- ADR-0021 made the KCA product autonomous but kept a `screen.beats_best` gate that, read literally, leaves daily submission quota unused. The owner's §9 instruction is the opposite: **inside budget, use as much as you can get.**

The owner's framing splits the work in two phases, and the boundary between them is itself a decision that has to be written down:

> 注意 KCA 还是使用基于 supabase 来登记、跟踪比赛情况,不要和长程运行验证搞混
>
> *(KCA still registers and tracks competitions on Supabase — do not conflate that with the long-run validation.)*

## Decision

### 1. Phase 1 / phase 2 boundary — exactly one writable authority per phase

| | **Phase 1 — long-run validation** | **Phase 2 — KCA product** |
|---|---|---|
| State authority (writable) | GitHub tracking issues + `competitions/<slug>/` files | Supabase |
| Driver | Claude Code CLI / Codex | KCA runtime |
| Audit log | Claude Code hook log `.agent/audit/tool-events.jsonl` | KCA's own log — today `.agent/kca/audit.jsonl`, **design and final location deferred to phase 2** (#203) |
| Human interface | Dashboard issue #199 + per-competition tracking issue | Approval Inbox / `services/decision_api/` |
| This ADR is | the operating model | the contract to implement |

Rules that follow:

1. **No dual-write.** A phase-1 session must not write competition state to Supabase, and phase-2 KCA must not treat a tracking issue as writable state. The `kca` subcommands that carry phase-1-shaped state are **DB-backed today and have no filesystem-only mode**: `tools/kca/run.py:82` gates its Supabase writes on `SUPABASE_DB_URL` being set *alone* (not on `KCA_DB_TARGET`), and `goal.py`, `explore.py` and `stuck.py` call `_db.get_conn()` unconditionally on their main paths. So a phase-1 session that merely has a DSN in its environment writes experiment, run and goal rows into KCA's control plane as a side effect.

   **The DB-writing surface is wider than those four, and an allow-list cannot close it.** "`push` writes to the DB on exactly two arguments" is the intuitive rule and it is wrong; the way it is wrong is the reason this is deny-by-default:

   | Path | What writes | Trigger |
   |---|---|---|
   | `kca kaggle push --watch` (the default) | `db.set_run_analysis_jsonb` (`kg.py:839-848`) | `--run-id` |
   | the same watcher | `UPDATE submissions SET status = 'stalled'` (`kg.py:879-915`) | `--competition` |
   | **any gated `kaggle` command that *refuses*** | `db.insert_approval_request` → a pending `human_decisions` row (`kg.py:62-79`, reached from `_emit_blocked`) | **the refusal itself** — no argument opts out |
   | `kca competition register` / `refresh-rules` | `_db.update_competition`, `_db.refresh_competition_rules` (`competition.py:44-65`) | the command |
   | `kca kaggle score --update-db` | `db.update_submission` (`kg.py:1355-1366`) | `--update-db` |

   Note the third row: the write happens on the path that *blocks* the action, so "it refused, therefore nothing happened" is wrong. Error handling differs by path: `_emit_blocked` reports `approval_recorded` / `approval_warning`, while the watcher suppresses some DB failures. Neither behaviour provides storage isolation.

   **Rule until a storage mode exists — deny by default, not a list.** Phase 1 does not run `kca` subcommands that carry competition state: not `kca run` / `goal` / `explore` / `stuck`, not `kca competition register` / `refresh-rules`, not `kca kaggle score --update-db`. For the Kaggle side it runs `kca kaggle push` with **`--no-watch`** and without `--run-id` / `--competition`, polls the kernel separately, and records the outcome in `competitions/<slug>/`. Any other `kca` subcommand is out of scope until someone has read its call graph down to `tools/kca/db.py` — the enumeration above is evidence that the surface is not knowable from the command name.

   **One residual dual-write is accepted and named:** the `human_decisions` insert on the refusal path. It cannot be avoided without the storage mode, it fires only when an action was *blocked*, and what it records is an approval request rather than competition state. That makes it tolerable, not correct, and the follow-up must cover it. It is also the reason this rule is a *written* rule: nothing enforces it (§5's A5 paragraph makes the same point about submission approval). Phase-1 experiment and run records live in `competitions/<slug>/` and `runs/<competition>/<run_id>/` as files, and in the tracking issue. Unsetting the DSN is *not* the control — an unset variable is an accident away from being set.

   **No open issue owns this.** Issue #192 covers `kg-*` skill migration and skill retirement, not storage isolation; the storage-mode flag and the test proving phase 1 leaves KCA state untouched need an issue of their own (see "Follow-ups").
2. **Markdown/YAML are the authority in phase 1**, not an export view. The reverse of discussion #185 §14's default, and deliberately so: phase 1 has no supervisor process to own a database.
3. **One vocabulary across the boundary.** The state names in §3 below, the ledger contracts (ADR-0023 / issue #191), and any future KCA column use the same tokens. A phase-2 migration is a change of *storage*, never a change of *names*.

### 2. Two loops — the human approves direction and budget, not batches

**Outer loop (direction, slow):**

```text
RESEARCH → IDEAS → RANKING → [HUMAN DIRECTION] → STRATEGY
    ▲                                              │
    └───────── FINDINGS / NEW QUESTIONS ────────────┘
```

**Inner loop (experiments, fast):**

```text
PLAN EXPERIMENT → IMPLEMENT → AUDIT → TRAIN/VALIDATE
        ▲                                  │
        └──────── ANALYZE / NEXT ───────────┘
```

The inner loop runs **freely inside an approved strategy + budget envelope**. Offline validation, not the leaderboard, decides which results are worth submitting.

**What the human approves (owner's §9 relaxation — binding):**

| The human decides | The agent decides |
|---|---|
| **Priority across concurrently-running competitions** (the routine decision) | Which experiments to run, in what order, how many |
| The budget envelope (§6) and its extension | How to spend that envelope — GPU, submissions, subscription usage |
| The always-gated set (§5) | Whether a candidate is submitted, within budget and rules |
| Direction changes it chooses to make | When to re-enter RESEARCH or propose a direction change |

`[HUMAN DIRECTION]` is bracketed above because it is **optional and agent-initiated**: the agent enters it when it needs a priority call or hits a gated point, not on every cycle. This corrects issue #190's body text ("the human approves a **scoped batch**"), which the owner's later review flagged as re-introducing the interruptions §9 removes. The *scoped batch* is the **budget envelope**, approved once per cycle — not a per-batch experiment approval.

Corollary: **no reply ≠ approval.** An unanswered decision request holds the competition in `WAIT_HUMAN`; it never decays into consent. Other competitions keep running.

### 3. Per-competition state machine — the canonical vocabulary

```text
DISCOVER ──► SELECT ──► ONBOARD ──► BASELINE
                                       │
                                       ▼
         RESEARCH ──► IDEA_GENERATION ──► IDEA_RANKING
            ▲                                 │
            │                                 ├──(gated point only)──► HUMAN_DIRECTION
            │                                 ▼                              │
            │                        EXPERIMENT_PLAN ◄───────────────────────┘
            │                                 │
            │                                 ▼
            │             IMPLEMENT ──► INDEPENDENT_AUDIT ──► TRAIN_VALIDATE
            │                                                       │
            │                                                       ▼
            │                                                   EVALUATE
            │                                                       │
            │                                                       ▼
            │                                            SUBMISSION_ELIGIBILITY
            │                                                       │
            │                              ┌────────────────────────┴──────────┐
            │                              ▼                                   ▼
            │                       SKIP_SUBMISSION                    PRE_SUBMIT_GATE
            │                              │                                   │
            │                              │                                   ▼
            │                              │                          SUBMIT ──► WAIT_SCORE
            │                              │                                   │
            │                              └───────────────┬───────────────────┘
            │                                              ▼
            │                                      RESULT_ANALYSIS ──► FINDINGS
            │                                                              │
            └──────────────────────────────────────────────────────────────┘
                                   (or ──► EXPERIMENT_PLAN for the next experiment)
```

**Canonical state tokens.** `UPPER_SNAKE_CASE`; a slash in discussion #185 collapses to an underscore (`TRAIN / LOCAL_VALIDATE` → `TRAIN_VALIDATE`). No aliases, no per-competition spellings.

| State | Means |
|---|---|
| `DISCOVER` | Registered as a candidate on dashboard #199; not selected |
| `SELECT` | Chosen for active work; the human's priority call is recorded |
| `ONBOARD` | Task, rules, data, metric, limits, submission protocol verified and dated |
| `BASELINE` | Reproducible baseline + frozen validation protocol + first valid artifact |
| `RESEARCH` | Gathering sourced evidence and open questions |
| `IDEA_GENERATION` | Evidence → structured, de-duplicated ideas |
| `IDEA_RANKING` | Ideas ordered by expected gain / cost / risk |
| `HUMAN_DIRECTION` | **Applying** a human direction decision that has already been answered — turning it into a strategy or experiment plan. Optional: entered only when a decision was needed. The *waiting* happens in `WAIT_HUMAN`, never here |
| `EXPERIMENT_PLAN` | One experiment designed: hypothesis, changed variable, acceptance, budget |
| `IMPLEMENT` | Code/config written against the plan |
| `INDEPENDENT_AUDIT` | Independent reviewer checked leakage, CV, metric, reproducibility, rules |
| `TRAIN_VALIDATE` | Run executing: training and/or local validation |
| `EVALUATE` | Metrics computed and compared to baseline/best under the same `split_id` |
| `SUBMISSION_ELIGIBILITY` | Deciding whether this result should consume a submission slot |
| `SKIP_SUBMISSION` | Recorded as not worth a slot, with the reason |
| `PRE_SUBMIT_GATE` | Format/inference validation, rules check, budget reservation |
| `SUBMIT` | External submission dispatched via the adapter |
| `WAIT_SCORE` | Bounded-backoff polling for the external result |
| `RESULT_ANALYSIS` | Score attributed to experiment, run, artifact, code version |
| `FINDINGS` | Conclusion + lessons persisted; feeds the next experiment or RESEARCH |

**Side states** — enterable from any state, **per competition, never global** (one competition in `WAIT_HUMAN` never stops the others):

| Side state | Entered when | Leaves when |
|---|---|---|
| `WAIT_HUMAN` | A gated point (§5), an expired approval, or timing data too stale to classify (§5) — **the only state in which the loop waits on a person** | The human answers; an unanswered request stays here |
| `PAUSED_BUDGET` | A budget dimension is exhausted **or unconfirmable** (§6) | **Exhausted:** the cycle rolls over or the budget is extended. **Unconfirmable:** only when the value is set or re-verified — a rollover never clears an unknown (§6) |
| `RETRY_AT` | Transient failure, rate limit, temporary platform error | The backoff deadline passes |
| `NEEDS_RECONCILIATION` | An external side effect's outcome is unknown — the classic case: the submit request was sent and the response was lost | The platform record is queried and matched; **never by blind retry** |
| `FAILED` | Terminal failure of this unit of work, cause recorded | A new experiment/run supersedes it |
| `STOPPED` | Stop condition hit (§6) or the human stopped it | The human restarts it |

**A side state must record how to come back.** A scalar `state` is not enough: a fresh session has to resume deterministically without re-deriving intent. Whenever a competition enters a side state it also records, alongside `state`:

| Field | Meaning |
|---|---|
| `resume_state` | The main-path state to return to when the side state clears |
| `state_reason` | Why it was entered — the gate name, the failing budget dimension, the error class |
| `decision_id` | For `WAIT_HUMAN`: the decision request this is blocked on, and its expiry |
| `retry_at` | For `RETRY_AT`: the backoff deadline (UTC) |
| `external_ref` | For `NEEDS_RECONCILIATION`: the persisted intent's unique `ref`; its platform id may still be unknown after a lost response |

**Where the state is recorded (phase 1):** `competitions/<slug>/competition.yaml:state` plus the fields above. One current state per competition; history lives in the ledgers (#191).

**Precedence, so that "mirrored" is deterministic.** Four surfaces carry competition status in phase 1, and a mirror that may be edited independently is a second authority. Strictly ordered:

| Rank | Surface | Role |
|---|---|---|
| 1 | `competitions/<slug>/competition.yaml` — `state`, the side-state fields above, `status`, `best`, `current_blocker`, `next_task`, `last_updated` | **The only writable authority.** A state change is this file changing. |
| 2 | `competitions/README.md` (dashboard) and the dashboard issue #199 | **Mirror.** Derived from rank 1, updated in the same change, never edited on its own. |
| 3 | `competitions/<slug>/tracking.md` (+ `tracking_zh.md`) | **Narrative, not state.** Reasoning, experiment history, LB writeups, decisions and their evidence. It may hold facts rank 1 does not, but it may not hold a *different* `state`, `status` or `best`. |
| 4 | The per-competition tracking issue (#86, #87, …) | **Human-facing mirror** of ranks 1 and 3, plus live discussion. Discussion is not state. |

Two rules follow, and they are what makes a fresh session deterministic:

- **On conflict, the lower rank is stale, not authoritative** — including when it is obviously fresher. The session's job is to fix the mirror, not to infer a state from it, and where the mirror carries evidence the YAML lacks (a score, a submission id), that evidence is what the YAML update is *made of*. An unreconciled conflict is itself a finding: record it in `current_blocker`.
- **`best` records the competition's eligible best.** Before close, this is a verified in-deadline score; after close, selection/eligibility for the final standing must also be supported by evidence. Unknown final eligibility means `best.public_lb`, `best.private_lb` and `best.submission_id` are `null`, not the last measured candidate. Historical, late and unselected scores stay in the narrative and comments; they must be labelled as observations rather than final results in the dashboard. For example, nemo's selected soup is **0.86 / 0.85**, its late eq-aug **0.86 / 0.86** is excluded, orbit's measured **703.9** entry was evicted before close, and sec-attack's **7.200 / 1.800** entry has unverified final eligibility. The last two have unknown final `best`.
- **Mirrors are updated in the same change as rank 1**, never later. "Future status updates live in `tracking.md`, not in the issue" (the note at the head of `nvidia-nemotron/tracking.md` and `orbit-wars/tracking.md`) was written before this vocabulary existed and is corrected by those files in this ADR's change: narrative moved out of the issues, but the *state fields* were always rank 1's.

**Field reconciliation — this replaces the two overlapping fields:**

| Field | Before | After this ADR |
|---|---|---|
| `state` | — (did not exist) | **The canonical token above. The single progress field.** |
| `phase` | `research \| baseline \| iteration \| submission \| postmortem \| unknown` | **Removed** — superseded by `state` |
| `status` | `research \| active \| submission \| closed` (live files) vs `active \| paused \| archived \| unknown` (template) — two sets, overlapping `state` | Narrowed to a **fact about the competition**, not about us: `open \| closed \| unknown` (is the official submission window open), verified from the competition rules/deadline; post-deadline practice submissions do not reopen it |

Legacy → canonical migration:

| Legacy `phase` | Canonical `state` |
|---|---|
| `prep` | `ONBOARD` |
| `research` | `RESEARCH` |
| `baseline` | `BASELINE` |
| `iteration` | the precise inner-loop state (`EXPERIMENT_PLAN` … `FINDINGS`) — do not keep a coarse token |
| `submission` | `PRE_SUBMIT_GATE` / `SUBMIT` / `WAIT_SCORE` as applicable |
| `postmortem` | `FINDINGS` |
| `unknown` | `DISCOVER` |

`competitions/_templates/competition.yaml` **and all five live `competition.yaml` files** adopt this in the same change as this ADR — a vocabulary that only the template speaks is two vocabularies, not one. The migration applied:

| Competition | was `phase:` / `status:` | now `state:` / `status:` |
|---|---|---|
| `arc-agi2` | `prep` / `research` | `WAIT_HUMAN` (`resume_state: HUMAN_DIRECTION`) / `open` |
| `arc-agi3` | `research` / `active` | `PAUSED_BUDGET` (`resume_state: PRE_SUBMIT_GATE`) / `open` |
| `nvidia-nemotron` | `submission` / `active` | `FINDINGS` / `closed` |
| `orbit-wars` | `iteration` / `active` | `FINDINGS` / `closed` |
| `sec-attack` | `iteration` / `active` | `FINDINGS` / `closed` |

The three closed competitions land in `FINDINGS` because that is what is true of them: the competition is over and only the writeups and post-mortem remain. This incidentally corrects the three stale `status: active` values issue #195 was opened for; #195 keeps the rest of its scope (what under `competitions/` is source-controlled).

**The two open competitions do not land on their old `phase` token at all**, and that is the migration working rather than failing. A rename would have carried the stale value across: both files said `research` / `prep` while the tree recorded work well past it — four arc-agi3 agents built, pushed and two scored (`arc-agi3/submissions.md`), and two arc-agi2 TTT rungs trained and evaluated at 0% (`competitions/README.md` 2026-06-29). Migrating a field means restating what is true, so each was re-derived from the freshest evidence in the tree, and each landed on a **side state** because that is what is true:

- **`arc-agi3` → `PAUSED_BUDGET`, `resume_state: PRE_SUBMIT_GATE`.** Its next step is to submit the two kernels that are built, pushed and queued, which needs a submission slot; `budget.submissions.verified_daily_limit` is `null`, and §6 refuses a reservation against a null cap. `submissions.md` records 1/account/day read on 2026-06-27, but without `verified_source` / `verified_at` in the block that number is not verified in the sense **A3** means, so the fail-closed reading stands.
- **`arc-agi2` → `WAIT_HUMAN`, `resume_state: HUMAN_DIRECTION`.** Both rungs scored 0%, the analysis is written (the lever is the data pipeline, not model size), and what remains is a direction choice between a multi-day RE-ARC / synthetic-data pipeline and a pivot to the Grand-Prize writeup. That is ADR-0006's "major direction change" and §2's human column, so it waits. `decision_id` is `null` because the request channel is follow-up #197; until it exists the request *is* `state_reason` plus the dashboard row, and a null `decision_id` in `WAIT_HUMAN` means exactly that — never "no request".

**Submission topology is per competition, never "upload a CSV".** `competition.yaml:submission_mode` already carries it, and `PRE_SUBMIT_GATE` → `SUBMIT` → `WAIT_SCORE` mean different concrete work per mode:

| `submission_mode` | What SUBMIT actually does | Live example |
|---|---|---|
| `file` | Upload a predictions file to the competition | M9 `spaceship-titanic` |
| `notebook` | Push and run the notebook, then explicitly submit the required output/kernel version using the competition's protocol | `arc-agi2`, `arc-agi3` |
| `kernel` | Push a kernel, wait for it to reach COMPLETE, **then** submit its output file | `nvidia-nemotron`, `sec-attack` |
| `agent` | Submit an agent file/tarball that is then played on a ladder; the score arrives over hours-to-days | `orbit-wars` |

A kernel/notebook push is **not** a leaderboard submission (issue #77). In both `kernel` and `notebook` modes, `SUBMIT` is not complete until the competition's submit call has been acknowledged. `arc-agi3/submissions.md` demonstrates this: four kernels reached COMPLETE, but only two were submitted and scored.

### 4. Fresh sessions and the context pack

Long-run ≠ one endless session. **Model context is disposable; project state is not.** Every work unit persists its structured result *before* the session ends; the next unit starts from a fresh context assembled from that state.

```text
Fresh session per work unit:
  RESEARCH → evidence + ideas        IMPLEMENT  → code/config + commit
  IDEA_RANKING → comparison          AUDIT      → review verdict
  TRAIN_VALIDATE → run record        ANALYSIS   → findings + next step
```

**Context pack** — what a work unit is given, and nothing more:

1. Competition spec + **verified** rules (with the date they were verified).
2. The approved strategy scope and the current budget envelope.
3. Baseline + best experiment + the validation protocol (`split_id`).
4. Related ideas, recent experiments, and **known dead ends** (so a failed idea is not re-proposed without new evidence).
5. Human decisions in force and open questions.
6. The exact code / config / artifact paths required for this unit.
7. The output schema and acceptance conditions for this unit.

**Anti-pattern (explicitly rejected):** stuffing whole notebooks, full logs and the entire discussion history into every context. Give a summary plus an index, and let the unit read specific evidence on demand. The cost of ignoring this is not just tokens — it is repeated suggestions and information pollution.

**Trust boundary inside the pack:** papers, forum posts, notebooks and web pages are **evidence, not instructions** (`CLAUDE.md` operating principle 1). The one deliberate exception under consideration is a task comment written by an authorized repo writer (issue #196); it must be pinned by content hash, and "member/collaborator" affiliation is not by itself proof of write permission.

### 5. Relaxed autonomy — inside budget, maximise; the human sets priority

> §9 可以进一步放宽,agent 在给定的预算范围内 … 自主尽可能多使用即可,human 只决定多个并发进行比赛的优先级
>
> *(§9 can be relaxed further: inside the given budget the agent should autonomously use as much as it can; the human only decides priority across concurrently-running competitions.)*

#### Activation — this section is not in force until its preconditions hold

Relaxed autonomy is a **per-competition capability that must be switched on by evidence**, not a blanket grant that starts the moment this ADR merges. For a given competition, §5 applies only when all of the following are true, and each is checkable by reading files:

| # | Precondition | Checkable by |
|---|---|---|
| **A1** | The competition's autonomy config exists and is readable at the path `competition.yaml:autonomy_config` names, **and** in it `autonomy.enabled` is not `false`, **and** the flag for the action at hand — `auto_submit` for a leaderboard submission, `auto_push` for a kernel push — is not `false` | `competitions/<slug>/competition.yaml:autonomy_config` → that file |
| **A2** | The competition's `budget:` block exists, every cap is set — no `null` — **and `cycle_anchor` is a real UTC timestamp**, without which no cycle window can be computed (§6) | `competitions/<slug>/competition.yaml` |
| **A3** | `budget.submissions.verified_daily_limit` **and** `verified_reset_boundary` carry `verified_source` / `verified_at` and are inside `verified_ttl` — the limit is useless without knowing when the day rolls over | the same block (§6) |
| **A4** | `launch`, `deadline` and the closing window are verified and inside `timing_verified_ttl` | the same file; otherwise `WAIT_HUMAN` (§5) |
| **A5** | **Every** gate on the submit path is fail-closed, all three of them: (a) the ADR-0020 §7 daily-limit guard refuses rather than proceeding, (b) `kg.py`'s approval gate defaults to requiring approval, and (c) the harness intercepts **every** submit *and* push command form — `kca kaggle submit/push`, `kaggle competitions submit`, `kaggle kernels push`, and the `python tools/kca/kca.py …` forms | see the paragraphs below |
| **A6** | A submission-intent record is written and persisted before dispatch | §5 "Recording an autonomous submission" |
| **A7** | Every shared budget scope it spends against has a reachable machine-absolute ledger + lock, reserving is atomic under that lock, and every cross-host scope names **this** host in an unexpired `<scope>/driver.yaml` lease — one driver **per scope** (not per competition) | §6 "A shared counter cannot live in a worktree" |

**Which file A1 reads is declared, not guessed.** `kca-<slug>.yaml` is a convention, not a rule, and it is already broken in the tree: `nvidia-nemotron`'s file is `competitions/nvidia-nemotron/kca-nemo.yaml` (the alias, not the slug), so a checker resolving `kca-<slug>.yaml` would look for `kca-nvidia-nemotron.yaml`, find nothing, and have to decide what "nothing" means. So the path is a declared field — `competition.yaml:autonomy_config`, relative to the competition directory — and A1 reads that file and no other. Two consequences, both fail-closed:

- **The block is read from one of two fixed places, and A1 fails if it is in neither or in both.** ADR-0021 §2 documents the schema as living under the config's `_base:` key — the per-variant defaults convention `kca-nemo.yaml` uses — while a competition with no variants would naturally put it at the top level. Both are legitimate, so A1 accepts **exactly one of**: a top-level `autonomy:` mapping, or `_base.autonomy`. Absent from both, present in both, unparseable file, missing file, or no `autonomy_config` at all — every one of those fails. "Present in both" fails for the same reason the rest do: A1 must be able to name *the* value it checked, and two candidates name none.
- **The blockless case is the one that matters most, because it reads as a pass.** With no block anywhere, `autonomy.enabled` is not `false` and neither action flag is `false`, so a literal check of the row succeeds while nothing was checked at all. That is `competitions/arc-agi3/kca-arc-agi3.yaml` today: it exists, it parses, and it carries no `autonomy:` block in either place, so arc-agi3 fails A1 — the right answer for a competition sitting in `PAUSED_BUDGET` with `resume_state: PRE_SUBMIT_GATE`, one step from a submission. `competitions/nvidia-nemotron/kca-nemo.yaml:51` has its block under `_base:`, so it *is* A1-readable; nemo fails §5 on A2, A3, A4, A5 and A7 instead (the full per-condition inventory is in Consequences), on a competition that closed 2026-06-15 and is in `FINDINGS`.
- **A per-section override merges onto `_base`, and A1 evaluates the merged result.** ADR-0021 §2 calls the block "overridable per section", and a `kca-<slug>.yaml` section is a variant (`v14`, `b1`, …), not a competition. A1 is a per-competition question, so the section that matters is the one the action at hand runs under: its `autonomy:` keys override `_base.autonomy` key by key, and A1 reads the **effective** block. A section-level `autonomy:` is therefore not a forbidden third location — it is an override *on* one of the two, and it does not make the file ambiguous. One rule keeps this safe in the only direction that matters: **a `false` anywhere in the merge — `_base` or section — is an absolute veto and survives the merge.** An override may narrow autonomy, never widen it, which is the same asymmetry `autonomy.enabled` already has ("evidence can only switch autonomy on where it was already permitted").
- **None of this contradicts ADR-0021 §2's "default ON".** That default says autonomy is *permitted* without a config, and it stands. A1 asks a different question — can the three vetoes be *read*? — and each failure case above answers it with "no". Unknown is never unlimited (§6), here as everywhere.
- **Glob-matching `kca-*.yaml` is not the fallback.** Two matches, or one matching an alias of a different competition, is exactly the ambiguity the declared field removes.

**`autonomy.enabled: false` is an absolute veto, checked before everything else.** It is the one-line opt-out ADR-0021 §2 gives a competition that needs strict human-in-the-loop, and no amount of evidence overrides it: a competition that has opted out never activates §5, however complete its budget block is. Evidence can only switch autonomy *on* where it was already permitted — it can never switch it on where it was refused.

**The action-level flags are vetoes too, at their own granularity.** ADR-0021 §2 gives a competition three switches, not one: `autonomy.enabled`, `autonomy.auto_push` and `autonomy.auto_submit`. §5 widens *how much* an enabled competition may do — it removes the per-action and per-batch approval and demotes `beats_best` to an ordering key — but it does not collapse three switches into one. `auto_submit: false` with `enabled: true` means "run autonomously, but a leaderboard submission is still a human's call", and that reading survives this ADR: the flag for the action being taken is part of **A1**, evaluated per action. A competition may therefore have §5 active for kernel pushes and inactive for submissions. Nothing in §5 sets, defaults or overrides these fields — absent means the ADR-0021 default (`true`), and an explicit `false` is always a refusal.

**Until a competition satisfies A1–A7, it runs under the narrower ADR-0021 §2 model** — screened autonomy with `beats_best` as a gate. This is deliberate: the widened licence and the machinery that bounds it ship together or not at all.

**Neither the widened nor the narrower model is implemented — and neither is the approval gate.** This is the most important paragraph in this ADR for an agent about to submit something, so every claim in it is a checkable fact about the tree rather than a policy preference. There are four layers, and it matters which one actually executes:

| # | Layer | What it would do | What it does today |
|---|---|---|---|
| 1 | ADR-0022 §5 (this section) | push/submit with no per-action **or per-batch** approval | **inactive** — no competition meets A1–A7 |
| 2 | ADR-0021 §2 | push/submit with no per-action approval *if screening passes* | **unimplemented** — the block exists in exactly one file in the tree (`competitions/nvidia-nemotron/kca-nemo.yaml:51-68`; `rg '^\s*autonomy:' competitions` returns that line and no other), and nothing under `tools/` / `src/` / `scripts/` reads it, so "screening passes" cannot be evaluated |
| 3 | `.kca/permissions/*.yaml` | `kaggle_submit` / `kaggle_push` = `default_decision: ask` — declared in three of the four profiles (`default.yaml:2-9`, `permissive-dev.yaml:2-9`, `competition-runner.yaml:2-14`); `hackathon-runner.yaml` declares neither and inherits them from `default.yaml` through the resolver's fallback chain, so the *effective* decision is `ask` in all four but the file says so in three | **not on the submit path** — the only production import of `permission_policy.resolve_for_skill` is `tools/kca/skill.py:15`; the installed `kca` entry point (`pyproject.toml:32-33`) reaches `tools/kca/kg.py` directly |
| 4 | `tools/kca/kg.py` | the gate that the `kca kaggle submit` / `push` commands actually call | **fail-open** — see below |

Layer 4 is the one that runs, and it does not gate. `kg.py:315` calls `_check_approval_gate("kaggle_submit", _policy_from_env())`; with no `KCA_POLICY` in the environment `_policy_from_env()` returns `{}` (`kg.py:126-130`), so the operation's default decides, and `OPERATION_DEFAULTS["kaggle_submit"]` is `False` — *allow* — at `kg.py:21-22`. `_gate()` at `kg.py:53-59`, which would refuse any remote side effect without `KCA_ALLOW_REMOTE=1`, **has no call sites**. So with credentials present, `kca kaggle submit` dispatches to the real Kaggle API with no approval of any kind.

**And the harness does not catch it either, so nothing enforces the approval today.** It would be comfortable to say the Claude Code harness asks before the command runs. It does not, for any submit form. Per-command, this is what the two mechanisms actually do:

| Command form | Harness hook | KCA gate | Result |
|---|---|---|---|
| `kca kaggle submit …` | no pattern matches | fail-open (`kg.py:21-22`) | **submits** |
| `kaggle competitions submit …` | **allow-listed**, `.claude/settings.json:91` | n/a | **submits** |
| `python tools/kca/kca.py kaggle submit …` | **allow-listed**, `.claude/settings.json:92` | fail-open | **submits** |
| `kca kaggle push …` | no pattern matches — `guard_tool.py:177` requires the literal `python tools/kca/kca.py` prefix | `kernel_push: False` | **pushes** |
| `python tools/kca/kca.py kaggle push …` | `guard_tool.py:177` → ask | — | gated |
| `kaggle kernels push …` | `guard_tool.py:171` → ask | — | gated |

Kernel push is gated in two of its three forms. **Submission is gated in none of its three.** That inverts the risk ordering this repo states elsewhere: a leaderboard submission consumes an irreversible quota slot, a kernel push does not (#77).

So the only thing between an agent and an unapproved submission is the *written instruction* in `CLAUDE.md`, `AGENTS.md` and `PROJECT_STATE.md` that it must ask — prose, which an agent can misread, and which §5 is in the business of relaxing. This ADR does not claim that floor is enforced. It claims three things instead:

- **A5 is failed for three independent reasons**, not one: the ADR-0020 §7 daily-limit guard is fail-open, `kg.py`'s approval gate defaults to *allow*, and the harness intercepts no submit form. §5 cannot activate for any competition until all three close. This is the ADR's central safety property and it is currently satisfied by nothing.
- **Phase 1 relies on the acting agent following the written approval rule.** Human observation is not guaranteed and is not an enforcement mechanism. Neither phase may treat this ADR as proof that a runtime guard exists.
- **Both gaps are follow-ups with `file:line` evidence**, below, so activation is blocked on them rather than the problem being rediscovered later.

Neither fix belongs in this ADR. `OPERATION_DEFAULTS` is ADR-0006's documented default, so changing it is a `kca` behaviour change needing its own PR. Note what does **not** protect it: `tests/test_m4_smoke.py:228-234` is named `test_approval_gate_allows_by_default` but passes an explicit `{"approval_gates": {"kaggle_submit": False}}`, so it never reads `OPERATION_DEFAULTS` and would not fail if the default flipped. The default is currently untested, which is a reason the follow-up must add a real test — `_check_approval_gate("kaggle_submit", {})` — not a reason to change it here. `.claude/settings.json` and `.claude/hooks/guard_tool.py` are the harness's own guard configuration: an agent session cannot write them — they are read-only in the sandbox, by design — and an agent widening or narrowing its own guard is the human's decision, not a side effect of a docs PR.

**The pre-submit gate today is fail-open, and that blocks activation.** `tools/kca/kg.py` implements ADR-0020 §7 as an explicit *courtesy* guard: `tools/kca/kg.py:205-217` returns `None` (proceed) when the competition slug is missing or the DB is unreachable, and `tools/kca/kg.py:252` reads `competitions.max_daily_submissions` from Supabase — a phase-2 authority that phase 1 does not write (§1). Nothing in the tree reads `verified_daily_limit`, `require_repro` or `rules_check`. A fail-open courtesy guard is not adequate under **either** model. It would have been defensible under ADR-0021 if `beats_best` independently limited what gets submitted — but nothing evaluates `beats_best` either (same paragraph above), so that limiter is documentary too, and §5 removes it explicitly. Two documentary limiters do not make one real one. Until a fail-closed gate consuming the phase-1 YAML contract exists — *and* `kg.py`'s approval gate defaults to requiring approval rather than allowing it — *and* the harness intercepts every submit form, not just two of three push forms — no competition meets **A5**, and §5's submission autonomy is inert. Implementing all three is a follow-up, not part of this ADR.

#### Inside the envelope

**Inside the approved budget the agent runs autonomously and should maximise the resources it already has**, rather than conserving them:

- **Local GPU** (snorlax / RTX 4090, may / RTX 3090): idle GPU hours inside the cycle budget are waste, not savings.
- **The competition's daily submission allowance**: an unused slot does not roll over. Scenario 2 below is the rule — when nothing beats the best, spend the slots on exploration near the baseline rather than banking them.
- **Claude Code / Codex / ChatGPT subscription usage**: subscription capacity is a flat-rate resource; use it.

**The human's routine decision is priority across concurrently-running competitions.** Not per-action approval, not per-batch approval. Ideas, unblocking and course-correction from the human remain welcome but are not required for the loop to proceed.

**Always human-gated, regardless of budget or autonomy setting:**

1. Irreversible / permanent deletion.
2. Real-money spend beyond the configured budget (subscription usage is not real-money spend; metered API spend is).
3. Ambiguous competition rules — including unverifiable or expired rule sources.
4. **Accepting new terms, joining a competition, or any team change.**
5. **Choosing the competition's final submissions** — which one or two runs are entered as the final answer — whenever that choice is made. (ADR-0006's "final submission selection".)
6. Promoting a candidate when the competition is closing soon — scenario 4 below. This is item 5's special case, kept as its own line because it also gates the *ordinary* promotion of a better score once the closing window opens, when picking the final entry is not yet on the table.
7. **Adopting external data, or expanding training data beyond the competition's own data.** (ADR-0006's "data policy decisions".) This is a rules-compliance surface and a licence commitment, so it is gated whether or not the rules look clear — distinct from item 3, which covers rules that are ambiguous.

**This set is a floor, not a default, and it is NOT configurable.** ADR-0006 makes approval gates configurable per project / per competition / per job; that mechanism may only **tighten** the set above — add gates, or turn an autonomous action back into an approval. No project config, competition policy, `autonomy:` block or job override may remove or weaken any of the seven. A config that appears to do so is a bug, and the action stays gated. Anything *not* in this set is genuinely autonomous inside budget **and inside the approved strategy** — the set lists irreversible *actions*, and §2's table separately reserves **direction changes** to the human. A direction change is not gated here because it is not an action: it is enforced by the state machine, which routes it through `WAIT_HUMAN` (`resume_state: HUMAN_DIRECTION`) rather than letting the agent adopt it (§3, and the ADR-0006 disposition below). The test for "is this a direction change?" is mechanical: if the next experiment is not derivable from the approved strategy, it is one. Inside those two boundaries, ADR-0006's configurability applies.

**Harness carve-out (unchanged).** §5 governs *competition* actions. The Claude Code harness still asks before destructive host commands and credential/paid-API use — it protects the human's machine and accounts, which is a different concern from competition autonomy (ADR-0021 §1).

#### Autonomous submission strategy (the single copy)

`CLAUDE.md` held this table until #188 moved it to ADR-0021 §4; it lands here because ADR-0022 is the single source for how wide autonomy is and because two of its rows read differently under §5: scenario 2's unused slots are **spent** on exploration rather than "not wasted", and scenario 3's N is bounded by the competition's **verified** daily limit, never an assumed 5. ADR-0021 §4 now points here — one copy.

Target submission roughly 2 hours before the daily roll-over — **which is whatever the competition says it is, not 00:00 UTC**. Kaggle sets this per competition: the Jaguar Re-identification rules say "the daily submission limit resets at midnight Central European Time", and a scheduler assuming UTC would submit into the wrong day and miscount the current one. The boundary is therefore read from the competition's own rules into `budget.submissions.verified_reset_boundary` with the same provenance the limit carries, and §5's **A3** fails while it is `null`. "Per competition day" below means a day delimited by that boundary. Apply per competition day:

**The closing window is checked first, before the candidate count.** Scenarios 1-3 are the *outside-the-window* rules. Inside it, promoting anything is always-gated item 6, so the candidate count is irrelevant: one winner is as gated as five. Reading the table by count first is how an exactly-one-winner day inside the window matches the autonomous row and dispatches a submission the floor reserves for the human — so the predicate order is normative, not stylistic.

| Scenario | Condition | Action |
|---|---|---|
| **0** | **The competition is inside its closing window** (`closing_window_days`, §5) — *any* number of candidates, including one, including zero | **`WAIT_HUMAN`.** The human chooses what is promoted; scenarios 1-3 do not apply. No new experiments start (§6); analysis and completion of already-budgeted work may continue |
| 1 | Outside the window, exactly 1 candidate beats the current best score | Submit that candidate; use remaining slots (up to the **effective** daily limit below) for exploration near the baseline |
| 2 | Outside the window, no candidate beats the current best score | Do not bank the daily balance; use the effective limit's slots for exploration near the baseline |
| 3 | Outside the window, multiple candidates beat best score | Submit the best N (up to the **effective** daily limit); queue the remainder for the next competition day |
| 4 | Inside the window, multiple candidates beat best score | **Ask the human** which candidates to promote — the case scenario 0 generalises, kept as its own row because ADR-0020 and ADR-0021 both name it |

**"Up to the daily limit" means the *effective* limit, never the raw one.** In every row above the number of slots the agent may consume is `budget.submissions.verified_daily_limit − budget.submissions.reserve_for_human` (§6). Scenario 2's "use all slots" means all *effective* slots: held-back slots are held back from exploration first, not last.

**Closing threshold — defined, not inferred.** Scenario 4 is an always-gated point, so the boundary between 3 and 4 must be computable without judgement:

- `competition_period` = `competition.yaml:launch` → `competition.yaml:deadline` (the final submission deadline), both as verified at `ONBOARD`.
- Default threshold = `competition_period × 0.1`, rounded up to whole days — 5 days for a 50-day competition.
- `competition.yaml:closing_window_days` overrides it per competition, and is the value of record once set.
- The **internal safety window** in §6's stop conditions is the same field: inside it the competition **starts no new experiments**, which is not the same as stopping. Scenario 4 is what the window exists for — the competition sits in `WAIT_HUMAN`, and the human's promotion decision is still carried out, re-entering `PRE_SUBMIT_GATE` → `SUBMIT`.

**Missing or stale timing data fails to the human, never to scenario 3.** Timing carries its own provenance — `timing_verified_source`, `timing_verified_at`, `timing_verified_ttl` — because the file-level `last_updated` says when the *file* changed, not when the *deadline* was checked. If `launch` or `deadline` is absent, or `timing_verified_at` is missing or older than `timing_verified_ttl`, the competition goes to `WAIT_HUMAN` — an agent must never classify an undated or stale competition as "open enough" to promote candidates autonomously.

The daily limit is **the verified limit for this competition and team**, not an assumed 5. Quota is per *team* for submissions and per *account* for notebook compute — they are different budgets (issue #193 owns the multi-account pool).

#### Screening: ordering and safety, not a quota gate

ADR-0021's `screen` block is retained with a changed role:

| Criterion | Role under this ADR |
|---|---|
| `require_repro` (seed + artifact path + exact command recorded) | **Hard gate** — blocks the submission |
| `rules_check` (competition rules, submission limits, no leakage) | **Hard gate** — blocks the submission |
| `beats_best`, `min_margin` | **Ordering only** — decides *which* candidate goes first, and which scenario above applies. It does **not** block spending a slot that would otherwise expire |

#### Recording an autonomous submission — driver-neutral, written before dispatch

The audit trail is the mitigation that makes wide autonomy acceptable, so it cannot depend on which harness happens to be driving. Phase 1 names **both** Claude Code and Codex as drivers (§1), but `.claude/hooks/audit_event.py` is a Claude Code hook: it fires only for Claude Code sessions, and it stores the generic tool payload — it does not require, or validate, the fields §5 depends on. The `.agents/` mirror added for issue #189 gives Codex no counterpart: it mirrors the skills, and Codex hooks are per-user configuration (`~/.codex/config.toml` or a managed directory) rather than anything a repository ships. So the harness hook log is **evidence, not the record**.

The record is a **submission-intent file**, written and flushed *before* the external call and owned by the competition, not by the driver:

```yaml
# Phase 1: competitions/<slug>/submissions/<utc-timestamp>-<intent-id>.yaml
competition: <slug>
experiment_id: EXP-027
run_id: <run>
artifact: <path>            # the exact file dispatched
artifact_sha256: <hash>
code_commit: <git-sha>
expected_score: 0.86        # and the metric it is on
reason: <why this candidate, in one line>
scenario: 1                 # 1 | 2 | 3 from the table above -- autonomous rows only. 0 and 4
                            #   are inside the closing window and human-gated, so no
                            #   autonomous intent record ever carries them
screen: {require_repro: pass, rules_check: pass}
ref: INT-20260915-215804-7c92  # unique per intended external action, across competitions
                            #   and runs; NEVER the experiment id. Two submissions of one
                            #   experiment need different refs. Resume/reconciliation of
                            #   the SAME action retains its ref and must not dispatch again
budget_reservations:        # "<scope>/<dimension>" -> reservation id. One action reserves
  competition:<slug>/submissions: RES-0007   #   in EVERY scope that caps the dimension
  team:<competition-slug>:<team>/submissions: RES-0008          #   (§6's all-or-none rule), so this is a map,
                            #   not a scalar -- a scalar could name only one of them and
                            #   settlement would strand the rest. Every id listed here has
                            #   the same intent `ref`, and §6's correlation reads `external_id`
                            #   back from this file, not from the ledger
driver: codex              # claude-code | codex
submitted_at: null          # filled after dispatch
external_id: null           # filled at reconciliation
```

`experiment_id` groups experiments; `ref` identifies one external action. A new submission after reconciliation has proved the previous action absent gets a new `ref` and records its predecessor. An unknown outcome never authorizes a second dispatch. A6 applies in both phases, but the repository file above is **phase 1 only**: phase 2 persists the same intent payload transactionally in Supabase, its sole writable authority (§1). Audit logs and exported files are supplementary views, never a second writable intent record.

A submission whose intent record could not be persisted **does not dispatch** — that is **A6** above. Autonomous actions must also stay **traceable and supersedable** — kernel versions retained, submission IDs recorded — so a human can see exactly what was sent and supersede it with a later submission. They are deliberately *not* described as reversible: a dispatched submission cannot be recalled, and the quota slot it consumed does not come back. That asymmetry is the reason the budget is reserved **before** dispatch (§6) rather than reconciled after it — reconciliation can explain an overspend, it cannot undo one.

### 6. Budgets, quotas and stop conditions

**Budget dimensions** (per competition, per cycle):

```yaml
# competitions/<slug>/competition.yaml — the same block as in
# competitions/_templates/competition.yaml. The KEY STRUCTURE is canonical: a key the
# template does not have, a missing key, or a renamed one is a bug rather than a local
# override. The VALUES are per competition — the template ships the caps null precisely
# so that filling one in is a deliberate, sourced act (A2/A3), and a live file still
# carrying the template's nulls is a competition that cannot activate §5.
budget:
  cycle: 7d                             # window every max_per_cycle is measured over
  cycle_anchor: null                    # UTC timestamp cycle 0 started; all arithmetic is UTC
  experiments:
    max_per_cycle: null
  compute:
    max_gpu_hours_per_cycle: null
  llm:
    max_turns_per_research_task: 100
    max_metered_cost_per_cycle_usd: 0   # 0 = subscription-only spend; null blocks metered spend
  submissions:
    require_verified_competition_limit: true
    verified_daily_limit: null          # fill at ONBOARD from the competition's own rules; never assume 5
    verified_source: null               # where that number was read (URL / API field)
    verified_at: null                   # <YYYY-MM-DD> it was read
    verified_reset_boundary: null       # WHEN the daily quota rolls over, as read from the
                                        # competition's own rules: e.g. "00:00Z" or "00:00+01:00".
                                        # Never assumed — Kaggle competitions differ, and a wrong
                                        # boundary miscounts the day. null blocks submission.
    verified_ttl: 30d                   # past this the limit is unverified again and blocks
    reserve_for_human: 0
  failures:
    max_retries_per_task: 3
    pause_after_consecutive_failures: 3
  progress:
    review_after_no_gain_experiments: 5
```

**Shared pools** (`competitions/_shared/budget.yaml`) — because competitions run concurrently, the per-competition caps are not sufficient. This file holds **caps only**; the consumption against them lives in the machine-absolute ledger below, never in the repo:

- **Account-level:** per Kaggle account weekly GPU hours, concurrent kernel slots, and the per-*team* daily submission quota (shared across the accounts of one team).
- **Machine-level:** GPU hours per day on snorlax (4090) and may (3090), plus any future cloud GPU; a GPU is held by a **lease** with a timeout and a heartbeat so two competitions cannot claim the same card (issue #194).
- **Subscription-level:** Claude Code / Codex / ChatGPT usage, tracked separately from metered spend.

Those pools have incompatible units and windows — a daily count, a weekly hour budget, a concurrency ceiling, a monetary cap — so a cap is meaningless without its unit and its window, and a ledger `amount` is meaningless without the cap it is drawn against. The file is a map from **scope identity** to cap, and the scope identity is the string a reservation carries:

```yaml
# competitions/_shared/budget.yaml — caps only; consumption lives in the runtime ledger.
scopes:
  team:<competition-slug>:<team-name>:
    submissions:
      unit: submission            # one leaderboard submission
      window: 1d                  # rolls at the platform's own boundary, not ours
      anchor: 00:00Z              # each scope carries its own anchor — they do not align
      cap: null                   # null blocks: an unknown is never unlimited
  account:<kaggle-user>:
    compute:
      unit: gpu_hour
      window: 7d
      anchor: 2026-09-15T00:00:00Z
      cap: null
    kernel_slots:
      unit: concurrent_kernel     # a ceiling on things held at once, not spend per window
      window: instantaneous
      cap: null
  machine:snorlax:
    compute: {unit: gpu_hour, window: 1d, anchor: 00:00Z, cap: null}
  subscription:claude-code:
    llm: {unit: subscription_usage, window: 5h, anchor: rolling, cap: null}
```

The dimension names in this file and in a reservation record are **one vocabulary**: `submissions | compute | llm | experiments | kernel_slots`. A cap with no matching dimension is unreservable and a reservation naming a dimension with no cap is refused.

A team submission scope includes **both competition and team identity**: `team:<competition-slug>:<team>`. The same people entering two competitions do not share one daily submission allowance or reset boundary. Account, machine and subscription scopes can span competitions; their caps remain shared where the provider actually shares them.

A reservation names the scope identity and the dimension, and its `amount` is in that cap's `unit`; a reservation whose unit does not match its cap's unit is rejected, not converted. `window: instantaneous` caps what is *held*, so its reservations are released rather than settled. Windows are independent: a `1d` submissions window and a `7d` compute window roll on their own anchors, and nothing re-bases one onto the other.

**The cycle needs an anchor, and a quota needs provenance.** Two sessions must compute the same answer from the same files:

- `budget.cycle` is a duration; `budget.cycle_anchor` is the UTC timestamp the first cycle started. Cycle *n* runs `[anchor + n×cycle, anchor + (n+1)×cycle)`. All budget arithmetic is stored and computed in UTC, which is a *representation* choice and not a claim about when anyone's day starts.
- **The submissions dimension is the exception: its window is the competition's day, not ours.** A per-day quota resets on the platform's boundary, so the `submissions` window runs between consecutive `verified_reset_boundary` instants (converted to UTC for storage), not between `cycle_anchor` multiples. Getting this wrong is not a rounding error: at 23:30 UTC, a fixed 00:00+01:00 reset has already started the next competition day, while a UTC-midnight counter is still in the previous one.
- `verified_daily_limit` is inert without `verified_source` (where the number was read), `verified_at` (when), and `verified_ttl` (how long that reading may be trusted), and so is `verified_reset_boundary` — a limit of 5/day says nothing usable until you know which interval between verified resets is the competition day. Past the TTL either field is *unverified* again and §5's **A3** fails — the competition drops back to the ADR-0021 model rather than guessing.
- The per-*team* daily submission quota and the per-*account* notebook/GPU quota are separate ledgers and are never traded against each other (#193).

**Reserve before dispatch, settle after completion.** A unit of work reserves its budget *before* it starts and settles the actual consumption when it finishes. Counting only after every parallel worker has spent its resources guarantees an overrun.

**A shared counter cannot live in a worktree.** This is where the obvious design fails. Reservations are shared state: per-team submission quota spans workers and accounts within one competition, and a GPU spans everything on that machine, so several workers — in several **git worktrees**, which is how phase 1 runs concurrent competitions (§1) — reserve against one counter. A path like `competitions/_shared/budget/...` is *worktree-relative*: each worktree has its own copy at its own inode, so two workers would lock different files, read different ledgers, and both dispatch. A repo-relative lock is not a lock.

So the shared ledger lives at one machine-absolute location, outside every checkout:

```text
${KCA_BUDGET_DIR:-$HOME/.kca/budget}/
  <scope>.lock                                    # flock target: one per shared counter
  <scope>/<dimension>/<window-id>/RES-0007.yaml   # one immutable record per reservation
  <scope>/<dimension>/<window-id>/RES-0007.terminal.yaml
```

`<window-id>` is derived from the matched cap, so every window kind has exactly one conforming directory and the reduction below is the same operation in all three cases:

| Cap's window | `<window-id>` | Example |
|---|---|---|
| A fixed span (`1d`, `7d`) | the window's start instant, UTC; outstanding records from earlier windows must also be checked before dispatch | `2026-09-15T00:00:00Z` |
| `anchor: rolling` | the literal `rolling` — one directory, filtered by time at read | `rolling` |
| `window: instantaneous` | the literal `held` — no window exists | `held` |

It is runtime state, not project state: never committed, never inside a worktree, and not the `competition.yaml` `budget:` block — that holds the **caps**, which are reviewed in git; this holds the **consumption**, which is not.

**Fixed-window rollover does not erase live work.** A job's enforceable ceiling includes the earliest end of every fixed window it reserves against. It must stop/checkpoint and settle there before reserving a continuation in the new window. Reading a new directory does not establish that the previous work stopped: any outstanding earlier-window record blocks a new reservation for that scope+dimension until reconciled. For a submission whose dispatch/acceptance straddles a reset, retain the old reservation and resolve the actual platform window before allowing another submission; a lost response never expires into a free slot. A submission's `consumed_until` is the platform acceptance/charge time, not the time the local response arrived. Fixed-window reduction includes settled submissions charged in that window even if their reservation file is in an earlier directory, grouped once by reservation id. If the charge time cannot be established, the old record remains unresolved and blocks. A launcher that cannot enforce these rules cannot satisfy A7.

**A per-competition cap is a scope too.** `budget.experiments.max_per_cycle`, `budget.compute.max_gpu_hours_per_cycle` and `budget.llm.max_metered_cost_per_cycle_usd` are per competition, and a cap with no counter bounds nothing: the repo side deliberately keeps no counter, so these must be reserved against the same ledger as the shared pools, under the scope identity `competition:<slug>`. Its cap values come from that competition's `budget:` block rather than from `competitions/_shared/budget.yaml`, and its window comes from `budget.cycle` anchored at `budget.cycle_anchor` — which is why **A2** requires the anchor to be set. Everything else — `O_EXCL` records, the lock, the reduction rule, the ceiling rule — is identical. A submission therefore reserves against *both* `competition:<slug>` and `team:<competition-slug>:<team>`, all-or-none, by the ordered multi-scope rule below.

**A scope holds more than one dimension, and the window is the dimension's, not the scope's.** `competition:<slug>` carries a `submissions` counter alongside the three above, and it does *not* inherit `budget.cycle` from them. The general rule, stated once so a second dimension never has to re-litigate it: **a reservation's window comes from the cap the *dimension* is drawn against, never from the scope the record is filed under.** Within `competition:<slug>` that gives:

| Dimension | Cap | Window |
|---|---|---|
| `experiments`, `compute`, `llm` | that competition's `budget:` block | `budget.cycle` @ `budget.cycle_anchor` |
| `submissions` | `verified_daily_limit − reserve_for_human` (below) | the **competition day**, delimited by `verified_reset_boundary` — the same window the `team:` submissions cap uses |

Without that rule a submission's `competition:<slug>` record is placeable in a `7d` cycle directory or a competition-day one depending on which paragraph an implementer read, and a counter with two possible directories is two counters. With it, a submission files two records under the *same* window bounds — which is the point: one counter bounds this competition's share of the day, the other the whole team's.

**`reserve_for_human` is subtracted from the agent's cap, not from the quota, and it is per competition day.** `budget.submissions.reserve_for_human: N` means the agent's effective cap for **that competition day** is `verified_daily_limit − N` — not per `budget.cycle`, because the quota it carves up resets on the day boundary. The reduction compares against that number; the last `N` slots are refused to an autonomous reservation and remain available to a human-approved one. `N` defaulting to `0` means no slots are held back. Every "up to the daily limit" in §5's scenario table means this effective number (§5).

**Records are immutable; one file per reservation, created `O_EXCL`.** A YAML list read, modified and written back loses one of two concurrent reservations, and the loser's spend is invisible. An exclusive create either wins or fails:

```yaml
# ${KCA_BUDGET_DIR}/team:<competition-slug>:<team>/submissions/2026-09-15T00:00:00Z/RES-0008.yaml
id: RES-0008                # one value in submission-intent's `budget_reservations` map
dimension: submissions      # submissions | compute | llm | experiments | kernel_slots
amount: 1
unit: submission            # must equal the cap's `unit`; mismatches are rejected, not converted
scope: team:<competition-slug>:<team>          # competition:<slug> | team:<competition-slug>:<team> | account:<name>
                            #   | machine:<name> | subscription:<name>
window:                     # the MATCHED CAP's window, never the competition's
  kind: fixed               #   `budget.cycle`. fixed | rolling | instantaneous
  id: 2026-09-15T00:00:00Z  #   == <window-id> in the path above
  ends: 2026-09-16T00:00:00Z  # fixed only; this is the team's 1d submissions cap
reserved_at: 2026-09-15T21:58:04Z
competition: <slug>         # who spent it — the repo side keeps no counter
ref: INT-20260915-215804-7c92  # the intent that reserved this, verbatim from the
                            #   submission-intent record's `ref` (§5). Every record of the
                            #   same intent, in every scope, repeats it; it is how
                            #   reconciliation finds the intent holding the `external_id`
```

Settlement and release never edit that file. They write **exactly one terminal sidecar**, also `O_EXCL`, so a second writer cannot produce a second outcome:

```yaml
# ${KCA_BUDGET_DIR}/team:<competition-slug>:<team>/submissions/2026-09-15T00:00:00Z/RES-0008.terminal.yaml
id: RES-0008
outcome: settled            # settled | released
amount: 1                   # settled: what was actually consumed — NEVER more than reserved
                            # released: always 0 — the reservation was not spent
at: 2026-09-15T22:06:11Z    # when this sidecar was written
consumed_until: 2026-09-15T22:06:04Z  # settled: when consumption actually STOPPED. With
                            #   `reserved_at` this is the consumption interval a rolling
                            #   window reduces over (above). Defaults to `at` when the
                            #   dimension is instantaneous; omitted for `released`.
evidence: <submission-id>   # for `released`: what was checked to prove it was not spent
```

**The window comes from the cap, not from the competition.** A reservation is drawn against one shared cap, so its interval — and therefore its window directory — is that cap's `window` and `anchor`, not `competition.yaml:budget.cycle`. A daily team submissions cap produces a one-day directory even when the competition's own experiment cycle is `7d`. Two dimensions in one job therefore land in two directories, which is correct: they are two counters.

The two non-fixed kinds keep the same directory shape and differ only in **which records in it are in scope** when reducing:

- **`anchor: rolling`** (a sliding window, e.g. subscription usage over `5h`): the `rolling` directory holds every record for that scope+dimension, and a record is in scope when its **consumption interval overlaps the lookback**, not when its `reserved_at` does. Concretely:
  - **Live** (no terminal sidecar) ⇒ **always in scope**, whatever its age. A job that outlasts the window would otherwise vanish from the count while still consuming the resource, and its capacity would be handed to someone else.
  - **Terminated** ⇒ in scope while `[reserved_at, consumed_until]` overlaps the lookback, where `consumed_until` is the terminal sidecar's field of that name (for `settled`, the instant consumption stopped; for `released`, irrelevant — a released record counts 0). Ageing a terminated record by `reserved_at` alone is the failure this prevents: a six-hour job under a five-hour window starts outside the lookback, consumes right through it, and would fall out of the count the moment it settled — handing its capacity away immediately after it was spent.
  - Only records whose whole consumption interval is outside the window are inert, and only those may be pruned.
- **`window: instantaneous`** (a ceiling on what is *held*, e.g. `kernel_slots`): the `held` directory has no time window, and reduction considers **live holds** — reservations with no terminal sidecar. These always end `outcome: released`, never `settled`: nothing was consumed over time, the slot was occupied and then given back. An instantaneous hold that outlives its work is a leak, which is why GPUs carry a lease timeout and heartbeat (issue #194).

**Reduction rule — each reservation counts exactly once.** Take the records in scope for the window kind above and group them by `id`. A reservation with no terminal sidecar counts at its reserved `amount`; one with a terminal sidecar counts at the sidecar's `amount` (so `released` counts 0). A reservation can never count twice, and `reserved` plus `settled` for the same id is one logical reservation, not two. An `id` carrying more than one terminal sidecar is corruption: it counts at the **larger** amount and raises `NEEDS_RECONCILIATION`.

**A reservation is a ceiling, not an estimate.** Settlement may come in *under* the reservation — that is ordinary, and the difference is returned to the cycle. It may never come in *over* it. The cap is compared before dispatch, so a settlement larger than its reservation means the human-approved envelope was exceeded after the spend had already happened and nothing could refuse it. For a dimension whose consumption is only known afterwards — metered LLM cost, GPU hours — the reservation is therefore a **hard limit passed to the job** (the token / wall-clock / spend ceiling it runs under), not a guess recorded beside it. A job that would exceed its reservation stops at the ceiling and reserves again, atomically, under the rules above; if that second reservation is refused, the work stops rather than continuing uncovered. A terminal sidecar whose `amount` exceeds its reservation is a **budget violation, not accounting**: it counts at its own larger amount, raises `NEEDS_RECONCILIATION`, and puts the competition in `PAUSED_BUDGET` until a human resolves it.

**Atomicity is the check, not just the write.** Creating the file atomically is not enough: *counting remaining capacity and then reserving* is two steps, and two workers can both read "one slot left". So every reservation against a shared scope runs under the scope's lock:

1. `flock` the scope's lock file at the absolute path above — one lock per shared counter, not per competition, because the counter is what is shared.
2. Under the lock: reduce the window directory by the rule above, compare to the cap, and `O_EXCL`-create the new record. Release the lock.
3. Dispatch. Then write the terminal sidecar.

**One job, several scopes: all-or-none, in one fixed order.** A submission spends against `competition:<slug>` *and* `team:<competition-slug>:<team>`; a GPU job against `competition:<slug>` and `machine:<name>`. Reserving them one at a time would let the first succeed and the second fail, leaving a phantom reservation that suppresses capacity nobody is using — or, worse, two jobs each holding one of the two locks and waiting for the other. So:

1. **Collect every (scope, dimension) pair the job will spend against, before locking anything.** A missing pair found before dispatch requires a fresh reservation plan. If dispatch has started, stop further work and reconcile; never release capacity that may already have been spent or repeat the external action.
2. **Sort the scopes by their absolute ledger path and `flock` them in that order**, ascending, without releasing any. A total order on the lock set is what makes deadlock impossible; byte-wise path order is one every host computes identically.
3. **Under all the locks: reconcile, reduce and compare every pair.** If *any* pair is over its cap, create no record at all, release the locks, and enter `PAUSED_BUDGET` naming the dimension that refused (§3's `state_reason`).
4. **If all pass, `O_EXCL`-create every record, then release in reverse order.** The records share one `ref`, so reduction still counts each once per scope, and settlement writes one terminal sidecar per record.

A partial failure at step 4 — some records created, one create failing — is the `NEEDS_RECONCILIATION` case: the created records stay (they are the honest record that capacity was taken) and are then explicitly `released` with evidence, never deleted.

**A lock is machine-local; some scopes are not.** `flock` coordinates workers on one host. A `team:` scope does not stop there — the same competition/team quota is spendable from another machine, and no local lock can see that. For any scope that spans hosts, the local lock is necessary but not sufficient, and two further rules apply:

- **One designated driver host per shared scope at a time** — per `team:` / `account:` / subscription scope, because the scope is what is shared. A per-competition designation does not serialise two competitions drawing on one account's GPU quota: each would reconcile against the same platform count, reserve in its own host's ledger, and both dispatch.

  **The designation is a lease file, not an issue comment** — `A1-A7` promises every condition is checkable by reading files, and a designation copied into N tracking issues is N copies that drift and none that a local session can read. One canonical file per scope, beside the counter it protects:

  ```yaml
  # ${KCA_BUDGET_DIR:-$HOME/.kca/budget}/<scope>/driver.yaml
  host: harry-arch              # the only host that may spend against this scope
  lease_expires_at: 2026-09-16T00:00:00Z   # past this the scope has NO driver
  updated_at: 2026-09-15T12:00:00Z
  ```

  This file exists **only on the designated host**; another host must contact that host's coordinator, never create a local copy and name itself. The initial host binding is owner-set and shared by every consumer. A lease file and `flock` on each of two machines cannot elect a unique driver. Automatic election/failover is out of scope: an expired or unreachable driver pauses spending. Owner-managed transfer must stop/fence the old driver, reconcile every outstanding reservation, and transfer the ledger before the new driver is enabled. A timestamp alone never proves the old worker stopped.

  On the designated host the file is written under the scope's own `flock`; its lease is checked again immediately before dispatch. An expired lease is *not* a lease: A7 fails, and the fail-closed rule below applies. The tracking issue of every competition spending against the scope carries the same information as a **mirror** (rank 4, §3's precedence order) so a human can see it without the machine — and where issue and file disagree, the file is right. A host that is not the scope's driver does not spend against that scope, whichever competition is asking — so all workers using the same pool reserve through the same host, against the same ledger, under the same lock, which is what makes the machine-local `flock` sufficient again.
- **Reconcile before reserving — every time, under the lock.** For any scope whose quota something outside the ledger can consume (a human submitting by hand, a teammate, another tool), the platform's own count is the authority and it is read **immediately before each reservation, inside the scope's lock**, not once per cycle. A count read at cycle start is stale the moment anyone spends out of band, and a stale count is how the ledger reserves a slot that is already gone. If that read fails, the reservation fails: `PAUSED_BUDGET`, not "proceed on the local number". The local ledger is a fast path *within* a cycle for detecting our own concurrent reservations; it is never the authority on what the platform has already counted.

  **Reading the platform under our lock does not lock the platform.** Every spender of an activated shared pool, including human-approved work and other tools, must reserve through the designated coordinator. If an external spender cannot participate, the pool cannot activate A7. Reconciliation detects historical/out-of-band spend; it does not prevent someone racing the next dispatch. Human approval does not bypass this coordination requirement or the platform's hard limit.
- **How the two numbers combine — stated, because adding them double-counts and replacing loses live work.** For a scope+dimension that has an external authority:

  ```text
  remaining = cap
            − platform_count
            − Σ max(0, local_charge − amount_proven_in_this_platform_snapshot)
  ```

  `platform_count` is the authority's own count for *this* window, read under the lock. The sum walks **every reservation in scope**, including work not dispatched yet. `local_charge` is its reserved amount while live, its actual amount when settled, and zero when released. Only consumption proved in this snapshot, in the same unit and window, is subtracted from that charge. Settlement is local and the authority's snapshot is remote, and step 3 above writes the sidecar *after* dispatch. A submission can therefore be `settled` here and not yet visible there. `released` records are the only ones excluded unconditionally: they consumed nothing, by definition.

  Each remaining record is correlated by the `external_id` its intent record carries, with the same three cases whether it is live or settled:

  | Record (live or `settled`) | In the sum? |
  |---|---|
  | `external_id: null` — not dispatched yet, or the dispatch outcome is unknown | **Yes.** The capacity is taken locally and the authority cannot know it |
  | `external_id` present **and its full local charge** is proved in this snapshot | **No** — `platform_count` already includes it. An id alone is insufficient for partially consumed GPU hours or subscription usage; deduct only the amount proved and retain the rest |
  | `external_id` present and **not** found in this snapshot | **Yes.** For a *live* record that is ordinary — the platform has not caught up. For a `settled` one, also raise `NEEDS_RECONCILIATION`: we recorded a completed spend the authority does not show |

  So "already counted there" is a fact to be *checked against the snapshot in hand*, never inferred from the sidecar's existence. Inferring it is how a dispatched submission falls out of both counters at once — local settlement says "the platform has it", the platform's snapshot does not show it yet, and the next reservation passes on a quota that is already spent. If any record cannot be correlated at all, it counts as **spent** and the competition raises `NEEDS_RECONCILIATION` — fail-closed, the same direction as everywhere else here.

  **The terminal sidecar records the local outcome; the platform snapshot proves external accounting.** Neither substitutes for the other. Deferring settlement is conservative because the live reservation keeps its full charge. Prompt settlement is also safe when the formula retains every amount not yet proved in the snapshot. A discrete submission settles one slot; metered resources can settle below their reservation ceiling.
- **Authority is selected per (scope, dimension), not by dimension name.** A local `machine:/compute` or `competition:/llm` cap uses ledger reduction alone. Platform `account:/compute`, `account:/kernel_slots`, `subscription:/llm`, and `team:/submissions` quotas require the external snapshot and correlation above. If a platform cannot expose usable consumption/provenance for its unit and window, that shared quota is unknown and refuses autonomous dispatch; calling the dimension `compute` or `llm` is not an exemption.

If a scope's driver designation is missing, expired, or named differently by two competitions that share it, then **every** competition spending against that scope is `PAUSED_BUDGET` — not just the one that noticed. Two hosts believing they are the driver is precisely the double-submission this whole section exists to prevent.

**A job that spends against several scopes reserves against all of them or none** — a single submission consumes a `competition:<slug>` slot *and* a `team:` slot; a training run reserves its applicable competition, account and machine compute caps (plus metered USD only if it spends money). The procedure is the ordered four-step rule under "One job, several scopes" above, and it is the **only** one: collect every pair, lock in ascending absolute-path order, check every pair while holding all the locks, then create every record or none. In particular, do **not** reserve scope by scope and release what was already taken when a later scope refuses. That releases under contention — another worker can win the freed capacity between the release and the retry — and it is exactly the partial reservation the rule exists to prevent. Partial reservation is the deadlock and the overspend.

**If coordination is unavailable, nothing dispatches.** An unreachable ledger directory, an unobtainable lock, an unreadable cap, or an unknown driver designation is *not* a reason to proceed — it is `PAUSED_BUDGET`. Same fail-closed rule as A5, applied to the counter instead of the gate. An agent may never "reserve optimistically and settle later".

A crash leaves a reservation with no terminal sidecar. Reconciliation must prove whether it spent capacity: settle observed consumption; release only proven unused capacity after the worker is stopped. An external spend needs platform evidence, and a local compute job needs process/resource evidence. An expired lease or window alone proves neither. Unknown outcomes retain their charge and block further work in that scope+dimension. An `instantaneous` hold is released only after the held resource is proved free.

**"Unknown" is never "unlimited".** A `null` in any cap is an unknown, and an unknown blocks **the work that would spend against that dimension** — not every activity the competition has. A null `experiments.max_per_cycle` refuses experiment dispatch; a null `compute.max_gpu_hours_per_cycle` refuses GPU work; a null `submissions.verified_daily_limit` refuses submission. The competition enters `PAUSED_BUDGET` when it needs a blocked dimension in order to make progress, and `resume_state` records where it was (§3). This is per dimension because the alternative is false: a competition in `RESEARCH`, spending only subscription LLM turns against set per-task limits (`max_turns_per_research_task: 100`, `max_metered_cost_per_cycle_usd: 0`) and a known, coordinated subscription quota may continue. A set local turn limit alone does not prove that the shared subscription has capacity; its scope must satisfy the shared-pool rules too.

**`ONBOARD` need not wait for caps it does not consume.** Reading rules and recording budget facts must remain possible before experiment/GPU/submission caps are filled. This is not an exemption for metered API or subscription usage: onboarding work that consumes either needs its own known envelope, just like any other state.

The rule applies with full force to `llm.max_metered_cost_per_cycle_usd` — an unset metered-cost cap refuses every metered call (subscription-only work is unaffected). Note the distinction that makes this compatible with §5: `0` means "subscription only, no metered spend" and is a *set* value; `null` is not. Likewise `submissions.verified_daily_limit: null` blocks submission, because the competition's real limit has not been read.

**Stop / pause conditions** → the side state each one produces:

| Condition | State |
|---|---|
| Human pause, or the approved scope expired | `STOPPED` / `WAIT_HUMAN` |
| Inside the internal safety window, deadline not yet reached | `WAIT_HUMAN` — no new experiments start; the human's scenario-4 promotion decision still runs, re-entering `PRE_SUBMIT_GATE` → `SUBMIT` |
| Competition deadline passed | `RESULT_ANALYSIS` → `FINDINGS`; `STOPPED` only once the findings are recorded, or when a human stops it outright |
| Budget exhausted, **or budget/quota state unconfirmable** | `PAUSED_BUDGET` |
| Consecutive failures over the limit | `FAILED` → `WAIT_HUMAN` |
| N consecutive experiments with no meaningful CV gain | `WAIT_HUMAN`, `resume_state: HUMAN_DIRECTION` — the review needs a decision, and waiting for one never happens in `HUMAN_DIRECTION` (§3) |
| Unexplained CV / LB divergence | `WAIT_HUMAN`, `resume_state: HUMAN_DIRECTION` — investigate and decide before spending more slots |
| External data / licence / rule compatibility unclear | `WAIT_HUMAN` (gated point 3) |
| Artifact, data version, or submission attribution unconfirmable | `NEEDS_RECONCILIATION` |

"No improvement" triggers a **strategy review, not necessarily a permanent stop** — and a review must never silently extend the budget. A flat public LB is a reason to review, never the sole reason to stop.

#### Contract acceptance cases

These are review cases for the future runtime, **not claims that it exists or passes**. An implementation must test these boundaries before enabling A5/A7. The repository's `tests/test_competition_contract.py` separately checks the current YAML vocabulary, dashboard state/status, gate-floor annotations and the intent/ledger example joins.

| Input or event | Required result |
|---|---|
| Two submissions from one experiment, including different runs | Distinct intent refs and reservation sets; retrying reconciliation retains the original ref |
| Dispatch response lost, platform id unavailable | Reconcile by persisted intent; no second dispatch and no automatic release |
| Exactly one winner inside the closing window | `WAIT_HUMAN`; no new experiment or autonomous submission |
| Two worktrees on one host both see one remaining slot | Same absolute ledger/lock; exactly one reservation succeeds |
| Another host has an expired/unreachable driver | Pause; no local self-election or empty replacement ledger |
| Old driver still has live jobs during a proposed transfer | Fence/stop and reconcile before enabling the new driver |
| A GPU job would cross a fixed-window reset | Stop/settle at the boundary; reserve the continuation before resuming; an unresolved old record blocks |
| Submission reserved before reset, accepted after it | Charge the acceptance window even when the reservation file is in the previous directory; unknown acceptance time keeps the scope blocked |
| A settled submission is absent from the platform snapshot | Its charge remains counted and reconciliation is required |
| 4 GPU-hours reserved; snapshot proves 1 already consumed | Retain 3 hours locally in addition to the platform's 1; an id alone never drops the full reservation |
| An uncoordinated teammate/tool can spend from the same pool | A7 cannot activate; a snapshot plus a local lock does not prevent the race |
| Same team name in different competitions | Separate competition/team submission scopes and verified reset boundaries |
| Post-deadline practice endpoint still accepts submissions | Competition status remains `closed`; practice does not reopen final eligibility |
| Final selection unknown or measured entry evicted | Final `best` is null; keep the measured candidate in labelled historical notes |
| Four notebooks COMPLETE, only two accepted as submissions | Two submissions, not four; push success never closes `SUBMIT` |
| Phase-2 intent persistence | Supabase transaction only; repository intent files belong to phase 1 |

## Relationship to ADR-0020 (goal-driven Kaggle loop)

**Extends it, and supersedes three of its eight decisions.** ADR-0020 was written for a single competition driven by a human-approved daily push batch; §5 of this ADR removes that approval, so the decisions that encode it have to move with it. Decision by decision:

| ADR-0020 decision | Disposition under ADR-0022 |
|---|---|
| **§1** `goal.md` schema — `target_lb_score` primary, `exit_strategy`, `max_total_pushes`, `stuck_threshold` | **Kept.** The per-competition target contract is unchanged; `max_total_pushes` and `stuck_threshold` are budget dimensions in §6's sense. |
| **§1/§2** "The DB `goals` row is authoritative; `experiments/<comp>/goal.md` is a human-readable mirror" | **Inverted for phase 1.** Under §1 the repo file + tracking issue are authoritative and Supabase is not written. The `goals` table stays the phase-2 authority. |
| **§2** `goals` table, FKs, migration 0011 | **Kept, phase 2 only.** When a state column is added it uses §3's vocabulary. |
| **§3** `experiment_runs.analysis_jsonb` | **Kept, phase 2 only.** Phase 1's equivalent is the run record under `runs/<competition>/<run_id>/` and the ledgers (#191). |
| **§4** Search-space spec — YAML cross-product with optional random sub-sample | **Kept.** It is the `EXPERIMENT_PLAN` → `IMPLEMENT` fan-out mechanism, unchanged. |
| **§5** Exploration-batch lifecycle — five states, **promotion limited to "top-K qualifying cells"** | **Amended.** The five batch states sit *inside* `EXPERIMENT_PLAN`…`EVALUATE` and are kept. "Qualifying" no longer means "beats best": under §5 a non-qualifying cell may still be promoted to fill a submission slot that would otherwise expire (scenario 2). `require_repro` and `rules_check` still qualify it; `beats_best` only orders it. |
| **§6** Smart-polling state machine — QUEUED Fibonacci ramp, RUNNING stable, size-fallback terminal | **Kept.** It is the implementation of `WAIT_SCORE`, and its backoff is what `RETRY_AT` means in practice. |
| **§7** Concurrency + daily-budget courtesy guard | **Superseded for activated competitions.** A5 requires a fail-closed gate consuming the phase's authoritative budget. The existing courtesy guard is not sufficient under either autonomy model; until the follow-up is implemented, the written human-approval rule applies (§5). |
| **§8** Stuck detector + escalation | **Kept** — waiting for the answer maps to `WAIT_HUMAN`, with `resume_state: HUMAN_DIRECTION`; only applying an answered decision enters `HUMAN_DIRECTION` (§3). |
| **§8** **Per-batch push approval: the `kernel_push` gate fires once per batch, the budget is a `human_decisions` row, and it "expires at UTC midnight and must be re-approved the next day"** | **Superseded.** This is exactly the per-batch approval the owner's §9 relaxation removes (§2). The daily grant is replaced by the budget envelope in §6, which does not expire nightly and is not re-approved per day. The `human_decisions` row remains the right record for the decisions that *are* still gated (§5's always-gated set). |

Note the ordering this implies: while §5 is inactive for a competition, ADR-0020 §7 and §8 still govern it in full, including the nightly re-approval. Supersession follows activation, per competition — not the merge date of this ADR.

## Relationship to ADR-0021 (KCA autonomy model)

**Widens it.** Section by section:

| ADR-0021 | Disposition under ADR-0022 |
|---|---|
| §1 Two agents — governance and audit-log table | **In force, unchanged.** The harness carve-out in §5 above is exactly this rule. |
| §2 "performs push/submit without per-action approval **provided ALL screening criteria pass**" | **Superseded.** `beats_best` / `min_margin` become ordering criteria; only `require_repro` and `rules_check` remain hard gates. Unused quota is spent on exploration, not conserved. |
| §2 `autonomy.enabled` default ON, opt-out with `enabled: false` | **In force.** Per-competition opt-out is still one line. |
| §2 `daily_submit_budget: 5` | **Superseded.** The limit is the *verified* per-team limit for that competition (`budget.submissions.verified_daily_limit`); an unverified limit blocks (§6), and 5 is never assumed. |
| §2 "Human role: contribute ideas, unblock, course-correct" | **Widened.** The human's *routine* decision is cross-competition priority (§5). Ideas and course-correction remain welcome, but the loop does not wait for them. |
| §2 Always-human-gated set (irreversible delete / over-budget spend / ambiguous rule / scenario 4) | **In force, extended from four items to seven** — with "accepting new terms, joining a competition, or any team change" (§5.4), "choosing the competition's final submissions" (§5.5) and "adopting external data or expanding beyond the competition's own data" (§5.7). The last two carry ADR-0006's intervention points forward; see the ADR-0006 table below. ADR-0021 §2 is amended in this change to list all seven. |
| §2 Scope: "the KCA product agent" only | **Extended.** This model governs phase-1 Claude Code / Codex sessions as well, minus the harness carve-out. |
| §2 "Autonomous actions must stay **auditable and reversible** … so a human can override or roll back after the fact" | **Superseded, and ADR-0021 is amended in this change.** A dispatched submission cannot be recalled and its quota slot does not come back, so "reversible" was never true of the action this model widens; calling it reversible made the stated mitigation look stronger than it is. The requirement is **auditable and supersedable** — kernel versions retained, submission ids recorded, a later submission able to replace an earlier one — and the binding protection is the reserve-before-dispatch cap in §6, not the record written afterwards (§5 "Recording an autonomous submission"). |
| §3 eval / audit clarifications, `.agent/kca/audit.jsonl` namespacing | **In force, unchanged.** |

Net effect: there is **one** autonomy model. ADR-0021 remains the source for the two-agent boundary and the per-competition `autonomy:` block schema; ADR-0022 is the source for how wide autonomy actually is and what the human decides.

## Relationship to ADR-0006 (configurable approval gates)

**Its mechanism is kept; its four "human intervention points" are dispositioned here, one by one.** ADR-0006 §"Human intervention points (unchanged)" (`docs/adr/0006-configurable-approval-gates.md:134-143`) says four things "always require human judgment". §5's always-gated set is a floor, so any of those four that §5 dropped without saying so would be a silently removed safety gate. Point by point:

| ADR-0006 human intervention point | Disposition under ADR-0022 |
|---|---|
| **Budget exhaustion** | **Kept, and made mechanical.** §6 turns it from a judgement call into `PAUSED_BUDGET` plus always-gated item 2 ("real-money spend beyond the approved budget"). An exhausted cycle never extends itself; only the human extends it (§2). |
| **Data policy decisions** | **Kept and strengthened** — now always-gated **item 7**, and phrased to bind whether or not the rules look clear, because it is a licence commitment as well as a rules question. |
| **Final submission selection** | **Kept and generalised** — now always-gated **item 5**. An earlier draft of this ADR gated it only "when the competition is closing soon", which was *narrower* than ADR-0006; that closing-window case is now item 6, the special case, rather than the rule. |
| **Major direction changes** | **Kept, and enforced in the state machine rather than in the gate list.** §2's table assigns "direction changes it chooses to make" to the human and "propose a direction change" to the agent; §3 makes that concrete — the agent enters `WAIT_HUMAN` with `resume_state: HUMAN_DIRECTION`, and `HUMAN_DIRECTION` is *applying* an answered decision, never deciding one. §6's review triggers (no CV gain, CV/LB divergence) route the same way. This is the one point that is not in the always-gated set, because that set enumerates irreversible actions; a direction change is a decision, and decisions are gated by the state machine. |

Net effect: ADR-0006 is unchanged as a mechanism — per-project / per-competition / per-job gate configuration, resolving through the same override pattern — and none of its four intervention points is dropped. Two of them become explicit items in §5's floor, one becomes a budget state, and one becomes a state-machine transition. What ADR-0006's configurability may still do is **tighten**: add gates, or turn an autonomous action back into an approval. It may never remove one of the seven.

## Consequences

- **Policy of record now — but §5 activates per competition, not on merge.** This ADR plus `CLAUDE.md` and `AGENTS.md` (which link it) are the loadable operating model. Merging it changes no competition's behaviour on its own: until a competition meets §5's activation conditions A1–A7 it keeps running under ADR-0021 §2 and ADR-0020 §7/§8, nightly batch approval included. The `CLAUDE.md` autonomous-submission table now lives here; `CLAUDE.md` links rather than duplicates it.
- **`competition.yaml` gains `state` and loses `phase`**, and `status` narrows to a fact about the competition. The template and all five live files change with this ADR, so no file is left speaking the old vocabulary.
- **Budget caps are declared, not yet filled.** §6 pins the contract (paths, key names, semantics), and the template plus all five live `competition.yaml` files now carry the `budget:` block, so the schema is real rather than promised. Its caps ship `null`: under §6 each null refuses the work that would spend against that dimension, and under A2/A3 it means no competition can activate §5 today. That is the intended behaviour — a number has to be verified before it can bound anything. The full inventory follows, because a partial one reads as a readiness count: **every live competition fails A2, A3, A4, A5 and A7, and four of the five also fail A1.**

  | Condition | Why it fails, for all five unless noted |
  |---|---|
  | **A1** | Four of five: three declare `autonomy_config: null` (no config exists), and `arc-agi3`'s config resolves but carries no `autonomy:` block in either accepted location. `nvidia-nemotron`'s *is* readable (under `_base:`) — the only A1 pass in the tree |
  | **A2** | Required experiment/GPU caps and `cycle_anchor` are `null`; the metered-cost cap is explicitly 0 |
  | **A3** | `verified_daily_limit` and `verified_reset_boundary` are `null`, with no provenance |
  | **A4** | **No live file carries `timing_verified_source` / `timing_verified_at` / `timing_verified_ttl` at all** — only the template does, so timing is unverified everywhere by omission, not by a stale value |
  | **A5** | All three gates on the submit path are fail-open (§5's A5 paragraph names the `file:line` for each) |
  | **A7** | The atomic reservation protocol, the ledger and the driver lease are specified in §6 and **implemented nowhere** — see Follow-ups |

  A6 is the only condition not statically failed, because it is a property of an action rather than of a file. So the answer to "how close is anything to activating?" is **six independent locks for four of the competitions and five for `nvidia-nemotron`** — A1 is the only condition nemo passes. Not one, and not three. `competitions/_shared/budget.yaml` is written when the first competition is selected on #199.
- **This ADR does not implement recovery.** `RETRY_AT`, `NEEDS_RECONCILIATION`, leases, checkpoints and restart recovery are *named* here so there is one vocabulary for them; the implementation and its fault-injection tests (host restart, lost submission response, budget exhaustion, fresh-session continuation) need their own issue and are the real gate on "long-run validated". The audit's mapping of that gap to "#190 §15" was wrong: it is not in this ADR's scope.
- **Risk.** Wider autonomy spends more real quota with less human contact. The mitigations are the ones this ADR makes mandatory: a verified daily limit, reserve-before-dispatch budgets, the two hard screening gates, the always-gated set, per-competition side states that never stop the fleet, and an audit trail that makes every autonomous action reconstructable and supersedable. Note what that trail does *not* buy: a spent submission slot is gone, so the binding protection is the reserve-before-dispatch cap, not the record written afterwards.

## Follow-ups

| Work | Owner |
|---|---|
| Ledger contracts (Experiment ≠ Run) using this vocabulary | #191 (ADR-0023) |
| `kg-*` skills implementing these states end-to-end | #192 |
| Multi-account pool → verified per-team / per-account quotas | #193 |
| Compute registry + GPU leases (machine-level budget) | #194 |
| Remaining `competitions/` source-control policy (the rest of #195's scope) | #195 |
| Task-comment pinning + authorization (the §4 trust exception) | #196 |
| Decision request / notification channel (`WAIT_HUMAN` round trip) | #197 |
| **Recovery + fault-injection implementation and tests** | *needs an issue* |
| **Fail-closed pre-submit gate** reading the phase-1 `budget:` contract — §5 activation condition **A5** | *needs an issue* |
| **Harness does not gate Kaggle submission**: `.claude/settings.json:91-92` allow-lists `kaggle competitions submit` and `python tools/kca/kca.py kaggle submit`, and `guard_tool.py:171,177` matches no submit form (nor the installed `kca kaggle push`). Third part of **A5** | *needs an issue* — human-only: the agent cannot write its own guard config |
| **`kg.py` approval gate is fail-open**: `OPERATION_DEFAULTS["kaggle_submit"] = False` (`kg.py:21-22`) and `_gate()` (`kg.py:53-59`) has no call sites, so `kca kaggle submit` dispatches unapproved. Also the second half of **A5** | *needs an issue* — touches ADR-0006's defaults; must also add the missing default-behaviour test, since `tests/test_m4_smoke.py:228-234` passes an explicit policy and never exercises `OPERATION_DEFAULTS` |
| **Atomic shared-budget reservation** — the machine-absolute lock + `O_EXCL` protocol, the ordered multi-scope rule, and the `<scope>/driver.yaml` lease behind **A7** | *needs an issue* |
| **`autonomy_config` reader** for **A1** — resolve the declared path, accept the `autonomy:` mapping at the top level *or* under `_base:` but never both, and fail closed on absent / unparseable / blockless / ambiguous | *needs an issue* |
| **Verified quota reset boundary** — read `verified_reset_boundary` per competition and window the `submissions` dimension on it instead of on `cycle_anchor` (**A3**) | *needs an issue* |
| **Filesystem-only storage mode** for `kca run/goal/explore/stuck` + a test proving phase 1 writes no KCA rows | *needs an issue* (not #192) |

## Cross-references

- Discussion #185 §3, §4, §8, §9, §10, §13, §15 — the source material.
- ADR-0006 (configurable approval gates) — the gated points in §5 resolve through the same per-project / per-competition override pattern.
- ADR-0018 (generalized competition type) — `competition_type` and the policy resolver; `submission_mode` in §3 is the execution-topology counterpart.
- ADR-0019 (eval regression suite) — reads `.agent/kca/audit.jsonl`; unchanged.
- `docs/architecture/goal-driven-kaggle-loop.md` — the M14 inner-loop reference implementation.
