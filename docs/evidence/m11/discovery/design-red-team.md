# design-red-team report for the M11 CTF architecture (T000)

Sources:
- Proposed design: `docs/tasks/m11/M11-T000-discovery-debate-gate.md` +
  `docs/milestones/m11/loop-prompts.md` (`ctf_events` / `ctf_challenges` /
  `ctf_attempts` schema; new ops `challenge_run` / `flag_submit` /
  `network_egress`; CTFtime → register-as-human → per-event-creds →
  solve → submit workflow).
- Upstream archaeology: `docs/evidence/m11/discovery/legacy-archaeologist.md`
- Upstream skeptic: `docs/evidence/m11/discovery/requirements-skeptic.md`

_Produced under the M11-T000 Discovery / Debate Gate. The agent body
lives in `.claude/agents/design-red-team.md`; this artefact is a
manual execution of that agent's protocol. The "proposed design"
being refuted is the M11 trajectory described in
`docs/milestones/m11/loop-prompts.md:62–98` — a per-project `ctf_events` table
with three new approval ops, registered manually by the human and
written from `tools/kca/ctf.py`._

## alternatives

1. **Reuse `competitions` with a `competition_type` discriminator.**
   Instead of a parallel `ctf_events` / `ctf_challenges` / `ctf_attempts`
   trinity, fold CTF into the existing `competitions` /
   `submissions` tables and introduce a `competition_type` enum
   (`kaggle | ctf | hackathon | generic`). Sketch: a CTF event is a
   `competitions` row with `competition_type='ctf'`, challenges are
   `competition_subtasks` (a small new table or a JSONB column on
   `competitions`), and flag submits land in the existing
   `submissions` table with `platform='ctf'`. Key tradeoff vs the
   proposal: zero parallel-table cognitive load (one table per
   concept, not two), but the `submissions` table — already shaped
   around CSV file uploads — gains shape it wasn't designed for
   (flag string, accepted boolean, http_status). Closest precedent:
   M12 is already planning this exact discriminator at the platform
   level (`docs/milestones/README.md:891–892`). Evidence:
   `docs/adr/0005-job-taxonomy.md:30` (`competition.platform ∈
   {kaggle, ctf, hackathon}` is already the intent).

2. **Scope-as-policy: collapse `ctf_events` into rich `ctf_scopes`
   rows + `competitions` for event identity.** Promote `ctf_scopes`
   to carry the event identity (slug, year, credentials-ref,
   target_urls, expires_at, team_id) and use the existing
   `competitions` table for top-level event metadata
   (name, deadline, platform=`ctf`). Challenges become first-class
   `challenges` rows under `competitions` (one new table, not three),
   and attempts become `submissions` rows. Sketch: one new table
   (`competition_challenges`) instead of three; `ctf_scopes` gains
   `event_account`, `team_id`, and an FK to `competitions`. Key
   tradeoff vs proposal: smaller schema delta and re-uses the
   reviewer-gate/audit chain that already exists for
   `kaggle_submit` on `submissions`, but loses the clean CTF-only
   query surface (every CTF analytics query joins through
   `competitions`).

3. **Stateless / file-backed CTF identity, DB only for attempts.**
   Keep events + challenges as on-disk YAML/JSON files under
   `data/ctf/<event>/manifest.yaml` (the same place the T004 bundle
   lives) and write only `ctf_attempts` rows to the DB (FK to
   `ctf_scopes` for authorization context, FK to `projects`, no FK
   to a DB-resident `ctf_events`). Sketch: `kca ctf event register`
   becomes `kca ctf event init <slug>` which scaffolds the on-disk
   manifest; the human edits it and commits; the worker reads
   `data/ctf/<slug>/manifest.yaml` at run time. Key tradeoff vs
   proposal: events / challenges become first-class git artefacts
   (reviewable in PR, diffable, auditable), but cross-project
   analytics ("how many flags across all events") becomes a
   filesystem walk instead of a SQL query, and the schema cannot
   enforce referential integrity for `ctf_attempts.event_slug`.

4. **(Bonus) Per-event sandbox with no shared identity.** Spin
   each event up in its own short-lived docker network with its
   own `~/.ctf/<event-slug>.json` mounted; the worker has no
   ambient credential and no cross-event view. Sketch: the M11
   `challenge_run` op is implemented as `docker run --network
   ctf-<slug> --env-file ~/.ctf/<slug>.env …`; `flag_submit` is
   `httpx.post` from inside the same container. Key tradeoff:
   strongest isolation (a compromise of one event's worker
   cannot read another event's credential), but doubles the
   per-job latency and complicates the OTEL telemetry pipeline.

## dropped_capabilities

- **Per-challenge attempts-per-hour rate-limit** as a first-class
  schema field. The proposed `ctf_attempts` shape captures only
  `accepted` + `http_status` after the fact; the platform has no
  pre-submit gate that consults a per-challenge attempt-counter.
  Evidence: `docs/milestones/m11/loop-prompts.md:111` ("M11-T005 records
  `ctf_attempts` row + `experiment_runs`") and
  `supabase/migrations/0001_init.sql:211–223` (no `attempts_count`
  or `last_attempt_at` column on `ctf_scopes`). Survives in:
  alternative 1 (CTFd-style rate-limit could live as a column on
  `competitions.submission_format` JSONB), alternative 2
  (`ctf_scopes.max_attempts_per_hour`), legacy (kkr.py had
  `--interval`/`--timeout` flags at `tools/legacy/kkr.py:2207–2215`
  for Kaggle; CTF needs an analogue).
- **Multi-event credential identity on the attempt row.** The
  proposed `ctf_attempts` is FK'd to `ctf_challenges`+`ctf_events`
  but does not carry the credential identity that actually made the
  submission (event_account / team_id). Evidence: the M11 task
  summary at `docs/milestones/m11/loop-prompts.md:62–77` mentions team_id only
  in the credential JSON file, not in the attempts row; the kkr.py
  replay precedent at
  `docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md` §3 calls
  out exactly this "owner on the submission row" gap. Survives in:
  alternative 2 (`ctf_scopes.event_account` carries through to the
  attempt), alternative 4 (the sandbox network is the identity).
- **`--env <path>` override on a per-invocation basis.** The legacy
  kkr.py exposed `--env <path>` at `tools/legacy/kkr.py:535–537`;
  the M11 plan does not surface an analogous flag on `kca ctf flag
  submit` (the credential is implicitly `~/.ctf/<slug>.json` or the
  `CTF_<EVENT>_*` env vars; no override path). Evidence:
  `docs/milestones/m11/loop-prompts.md:621–667` (planning Q&A item 5
  describes the two paths and treats them as exhaustive).
  Survives in: legacy, alternative 2 (the scope row could carry a
  `credentials_path_override` column), alternative 4 (the
  `--env-file` is a docker flag).
- **CTF-category enumeration enforced by the schema.** The proposal
  leaves `ctf_challenges.category` as free text per
  `docs/milestones/m11/loop-prompts.md:62–77`; this drops the ability to do
  `WHERE category IN ('web', 'crypto')` queries with type safety.
  Evidence: archaeology §8 (`ctf-sandbox/SKILL.md:31` lists the
  five categories as ambient assumption, not enforced enum). The
  proposal explicitly accepts this; the cost is downstream
  analytics drift.
- **Stable JSON shape for `kca ctf flag submit --json`.** The
  proposal at `docs/milestones/m11/loop-prompts.md:255–256` says "echo only
  `accepted=true|false` + http status, never the flag string
  itself", but does not pin the JSON keys. Evidence: unavailable
  in the current branch — route to `open_disagreements`.

## long_term_costs

cognitive_load:    A new contributor must hold three new tables
                   (`ctf_events`, `ctf_challenges`, `ctf_attempts`)
                   plus the existing `ctf_scopes` plus the
                   relationship-to-`projects`-but-not-`competitions`
                   asymmetry in their head before they can write
                   one CTF query. Alternative 1 trades all three for
                   one `competition_type` column; alternative 2 adds
                   one new table; alternative 3 keeps only the
                   `ctf_attempts` table. The proposal carries the
                   most cognitive weight of all four options.
ops_burden:        Four-tables-with-FKs means a schema migration
                   failure leaves a half-applied state; `0008_m11_ctf.sql`
                   must wrap in a transaction with savepoints, and
                   the rollback `0009_*` must drop tables in
                   FK-reverse order. At 3am, a failed submit during
                   T007 must be reconcilable from the
                   `agent_reviews` row alone — does the proposal
                   guarantee the `(agent_reviews.id, ctf_attempts.id)`
                   pairing? Skeptic §side_effects/3 calls this out
                   (`docs/evidence/m11/discovery/requirements-skeptic.md`).
extensibility:     Next likely scope expansions: (a) M12's
                   `competition_type` enum (in progress per
                   `docs/milestones/README.md:891–892`), and (b) a second
                   CTF event running concurrently under the same
                   project (the picoCTF-during-weekend-CTF case).
                   The proposal needs a schema migration for (a) and
                   needs `ctf_events.is_active` plus an index for
                   (b); alternative 1 absorbs both for free
                   (because `competition_type` already lives on
                   `competitions`).
blast_radius:      Worst case: a wrong flag is submitted under
                   the wrong event-account because the
                   `ctf_attempts` row has no event_account
                   discriminator and the worker picked the wrong
                   credential file from `~/.ctf/*.json`. The
                   `submissions`-style audit row points at the
                   project but not the event-account, so the
                   incident response cannot answer "which credential
                   ran this" without re-reading the worker's
                   in-process env. This is the kkr.py failure mode
                   re-incarnated; the proposal does not structurally
                   prevent it (see `dropped_capabilities` §2).
                   Alternative 2 and alternative 4 prevent it
                   structurally.

## open_disagreements

- The proposal adds three new tables when M12 is already planning
  a `competition_type` enum that would let CTF reuse `competitions`
  + `submissions`. Disagree — next step: open a follow-up issue
  (labels: `area:supabase`, `area:ctf`, `area:schema`,
  `policy:approval-required`) asking whether M11-T001 should land a
  parallel schema or wait for M12-T002's `competition_type` and
  fold CTF in at M12 close. Evidence:
  `docs/milestones/README.md:891–892`, `docs/milestones/m12/loop-prompts.md`
  (alternative 1 is already partly committed at the M12 layer).
- `ctf_attempts` has no `event_account` / `team_id` / `submitted_by`
  column to record *which* credential actually hit the event.
  Disagree — next step: spike a schema patch adding
  `ctf_attempts.event_account` (text) and `ctf_attempts.team_id`
  (text, nullable) before M11-T001 is committed; the kkr.py replay
  precedent shows the kind of gap this prevents. Evidence:
  `docs/evidence/m11/discovery/legacy-archaeologist.md` §3,
  `docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md` §3.
- The proposed `network_egress` op is described as "deny outside
  an authorized `ctf_scopes.target_urls` row; ask when scope+URL
  match" (`docs/milestones/m11/loop-prompts.md:212–214`). It is unclear at
  which layer the deny actually fires — hook (`.claude/hooks/guard_tool.py`),
  reviewer (`src/worker/reviewer.py`), or HTTP client (httpx
  request interceptor). Disagree — next step: ask human which
  layer owns enforcement; the wrong choice means the deny can be
  bypassed by a tool that does not go through that layer (e.g.
  subprocess curl bypasses an httpx interceptor).
- The proposal leaves `ctf_challenges.category` as free text
  (M11-T001 spec) but the M11 plan exercises only `web` + `crypto`.
  Disagree — next step: file a follow-up issue (labels:
  `area:ctf`, `area:schema`, `type:tech-debt`) to revisit
  enum-ifying `category` after M11-T009 once the actual taxonomy is
  empirically known. Evidence:
  `docs/milestones/m11/loop-prompts.md:317` (web+crypto exercised), legacy
  archaeology §8 (`ctf-sandbox/SKILL.md:31` ambient five-category
  list).
- The proposal does not pin a JSON-output shape for `kca ctf flag
  submit --json` beyond "accepted + http status"
  (`docs/milestones/m11/loop-prompts.md:255–256`). Disagree — next step:
  research-brief whether any downstream tool (the M11 UI Approval
  Inbox, the T008 audit-grep test, the milestone-final-review
  pipeline) parses this output; if yes, pin the keys in ADR-0016.
  Evidence: unavailable in the current branch (parallel to the
  kkr.py `_emit_ok` JSON-shape question at
  `docs/evidence/m9_4-kkr-replay/design-red-team.md` §dropped_capabilities/4).
- The proposal treats `~/.ctf/<event-slug>.json` as ambient state
  read by the worker process; the hook-layer carve-out
  (`docs/milestones/m11/loop-prompts.md:213`, "extend `.claude/hooks/guard_tool.py`
  to cover `~/.ctf/*.json` reads outside the allow-listed `kca ctf`
  flow") mitigates direct shell reads but not Python `open()`
  calls from inside the worker. Disagree — next step: spike whether
  the credential should be read by a dedicated subprocess
  (kkr.py-replay alternative 2's posture) so the parent worker
  never holds the token in-process. Evidence:
  `docs/evidence/m9_4-kkr-replay/design-red-team.md` §alternatives/2
  (subprocess isolation as a recurring solution to ambient-credential
  drift).

Output MUST include ≥3 alternatives, ≥1 dropped capability with file:line evidence, all four long-term-cost axes, and ≥1 actionable `open_disagreements` entry.
