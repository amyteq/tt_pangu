# legacy-archaeologist report for the pre-M11 CTF artefacts

Source artefacts (read-only):
- `supabase/migrations/0001_init.sql:211–221` — `ctf_scopes` table.
- `supabase/migrations/0001_init.sql:6` — `project_kind` enum (includes `ctf`).
- `supabase/migrations/0001_init.sql:244` — `ctf_scopes` RLS enabled (no policies).
- `.claude/skills/ctf-sandbox/SKILL.md:1–38` — CTF workflow skill.
- `.claude/agents/safety-guard.md:3, 9` — CTF policy-sensitive guard agent.
- `.claude/skills/agent-iteration-review/SKILL.md:3, 8` — references "CTF solver results".
- `src/worker/reviewer.py:48–61` — reviewer system prompt mentions "Kaggle/CTF code agent" and "violate competition/CTF rules".
- `docs/adr/0005-job-taxonomy.md:22, 30` — `project_kind` includes `ctf-practice-may26` example; `competition.platform ∈ {kaggle, ctf, hackathon}`.
- `docs/milestones/README.md:834–851` — M11 milestone slot.
- `docs/meeting-notes/2026-05-15.md:80, 115–116, 155, 191, 586` — original brainstorm: `ctf-sandbox/SKILL.md` planned; Kaggle and CTF must be separate policies; "MVP-4: authorized CTF sandbox loop"; Python-first worker rationale includes CTF scripts; "Level 4: authorized CTF sandbox" autonomy ceiling.
- `docs/meeting-notes/2026-05-16-r2.md:3, 20, 41, 96, 181, 202, 216` — security boundary differentiation; "M8" (now renumbered M11) authorized CTF/lab workflow.

_Produced under the M11-T000 Discovery / Debate Gate. The agent body
lives in `.claude/agents/legacy-archaeologist.md`; this artefact is a
manual execution of that agent's protocol (same shape as
`docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md`)._

## 1. Workflows supported

- **Authorized-scope authorization** — a human registers a permissive
  `ctf_scopes` row binding a project to an `authorized_scope` string
  (free text), a `target_urls` JSONB list, a `local_only` flag, and an
  optional `expires_at`. Entry: `supabase/migrations/0001_init.sql:211–221`.
  No CLI exists today; insertion is bare SQL.
- **Local challenge analysis** — the `ctf-sandbox` skill describes a
  7-step workflow: restate scope, inventory files/services/ports,
  category-triage (crypto / pwn / web / reversing / forensics / misc /
  OSINT), hypothesize, log commands, build solver, write up.
  Entry: `.claude/skills/ctf-sandbox/SKILL.md:27–35`.
- **Reviewer-gated high-stakes ops** — the existing sync reviewer
  treats `kaggle_submit`, `supabase_migrate`, `git_force_push`,
  `dataset_upload`, `delete_artifact` as `DEFAULT_TRIGGER_OPS`
  (`src/worker/reviewer.py:20–26`). CTF-specific ops are mentioned in
  the system prompt (`src/worker/reviewer.py:59`) but no `ctf_*`
  operation name is in the trigger tuple.
- **Safety-guard pre-check** — the `safety-guard` agent is invoked
  proactively when "CTF/security tooling" is requested
  (`.claude/agents/safety-guard.md:3`). It returns allowed / needs
  approval / blocked without executing anything.
- **Iteration review on CTF solver output** — the
  `agent-iteration-review` skill is invoked after CTF solver output is
  available (`.claude/skills/agent-iteration-review/SKILL.md:3, 8`) to
  decide continue / revert / ask-human / stop.

Cross-cutting: **no CLI surface exists for CTF today**. There is no
`kca ctf …` subcommand; there is no `ctf_events`, `ctf_challenges`,
or `ctf_attempts` table; there is no `challenge_run`, `flag_submit`,
or `network_egress` operation on the reviewer or in
`.kca/permissions/*.yaml` (verified: `grep -in ctf
.kca/permissions/` returns no hits, see Bash output during the
prep phase).

## 2. Hidden assumptions

- `ctf_scopes.target_urls` is a JSONB array but the legacy schema does
  not declare a shape. The free-text contract is implicit
  ("URLs the agent may hit"); a list-of-strings vs a list-of-objects
  decision is undocumented. Evidence:
  `supabase/migrations/0001_init.sql:216`.
- `ctf_scopes.local_only` defaults to `true`
  (`supabase/migrations/0001_init.sql:217`). Any code that reads it
  must treat `local_only=true` as "no network egress" — but no
  current code enforces that. The flag is a load-bearing intent that
  no live consumer honours yet.
- `ctf_scopes.authorized_scope` is plain text
  (`supabase/migrations/0001_init.sql:215`). No tag set, no controlled
  vocabulary. Downstream code that compares `authorized_scope` strings
  cannot use `=` reliably; semantic interpretation is the human's job.
- `ctf_scopes.expires_at` is nullable
  (`supabase/migrations/0001_init.sql:218`). Null = never expires.
  A scope row inserted in 2025 still authorises in 2030 unless somebody
  notices.
- RLS is on (`supabase/migrations/0001_init.sql:244`) but no policy
  defines who reads / writes the row. With the service-role DSN used by
  the worker, RLS is bypassed; with an anon role, every read fails.
  Whichever way it goes, the contract is undefined.
- The `ctf-sandbox` skill (`.claude/skills/ctf-sandbox/SKILL.md:7`)
  says "explicitly provided by the human" — i.e. the skill assumes a
  human pre-registers the scope before the agent runs. The DB path to
  register the scope is undefined.
- `docs/adr/0005-job-taxonomy.md:30` lists `ctf` as a `competition.platform`
  enum value, but `supabase/migrations/0001_init.sql` does not enforce
  this enum on the `competitions` table — `competitions.platform`
  exists as `text` (verified in line 60 of 0001_init.sql earlier; the
  ADR is aspirational here, not a constraint).
- `.claude/skills/ctf-sandbox/SKILL.md:25` forbids "CTF techniques
  outside the authorized scope" — but there is no machine-checkable
  binding from "the scope" to "the URLs the agent's tools will hit".

## 3. User personas / accounts / owners — load-bearing

This is the kkr.py-style load-bearing section. CTF is multi-event /
multi-account by structure (every event has its own credential and
team/individual identity), and the existing artefacts encode that
implicitly but not explicitly. Pre-M11, the identity model is:

- **Project** — `projects` table is the billing / access-control
  boundary (`docs/adr/0005-job-taxonomy.md:19–26`). A CTF "project"
  example is named in the ADR: `"ctf-practice-may26"`
  (`docs/adr/0005-job-taxonomy.md:22`).
- **Scope** — `ctf_scopes.project_id` (`supabase/migrations/0001_init.sql:213`)
  ties one or more scopes to a project. **Implicit assumption:**
  one project = one event. If the human runs picoCTF AND a CTFtime
  weekend event from the same project, today's schema collapses both
  into the same scope namespace. Evidence:
  `supabase/migrations/0001_init.sql:213, 214` — `(project_id, name)`
  has no uniqueness constraint and no event reference.
- **Event identity** — **not modelled today**. There is no
  `ctf_events` table; the only place "event" lives is in the human's
  `authorized_scope` free-text and in the workflow described in
  `docs/milestones/m11/loop-prompts.md` ("CTFtime calendar → register on event
  site as a human → ~/.ctf/<event-slug>.json"). This is the M11
  artefact the legacy archaeology must surface as load-bearing — see
  §9 question 1.
- **Per-event credentials** — current state-of-the-art is "use
  `~/.ctf/<event-slug>.json` or `CTF_<EVENT>_USERNAME` /
  `CTF_<EVENT>_TOKEN`" per the planning Q&A in
  `docs/milestones/m11/loop-prompts.md:621–667`. There is **no on-disk path
  enforced by the existing artefacts**. The `safety-guard` agent
  treats credential files as policy-sensitive but does not enforce a
  per-event isolation contract.
- **Team vs individual** — `docs/milestones/m11/loop-prompts.md:665` mentions
  "optional `team_id`" in the credential JSON. Today's `projects`
  table has no team column; M12-T002 introduces `teams` /
  `team_memberships`, but M11 lands before that. CTF events can be
  "team submitted under team T" vs "solo submitted by user U" — the
  current schema cannot represent which path a flag took.
- **Kaggle owner / GitHub identity / Supabase user / CTF event
  account** are four distinct identity dimensions. The kkr.py replay
  showed Kaggle-owner-on-`runs` is required; CTF inherits the same
  problem one dimension over (event-account-on-`ctf_attempts`).

## 4. Side effects

- **Scope row insertion** — `INSERT INTO ctf_scopes` writes to the
  local Supabase. Today there's no programmatic write path; the row
  is presumably created by hand. No reverse path either: there's no
  `DELETE` workflow, no `expires_at` enforcement job.
- **Reviewer-model LiteLLM call** — `src/worker/reviewer.py:181–187`
  invokes `litellm.completion` against `DEFAULT_REVIEWER_MODEL`
  (`claude-opus-4-7`). Per-call cost is recorded on `ReviewVerdict`.
  This fires for any `DEFAULT_TRIGGER_OPS` op today; M11 adds three
  CTF-related ops to that set.
- **Filesystem writes** — none specific to CTF today. The bundled
  challenges + solver workspace land later in M11-T004 / T005.
- **External network** — none today. The existing artefacts assume
  `local_only=true` is the default posture; the M11 plan adds
  `challenge_run` against a remote endpoint + `flag_submit` against an
  event API, both gated.
- **Reviewer-gate row writes** — `src/worker/worker.py:730–810`
  writes `agent_reviews` rows + `agent_job_events` rows when the
  reviewer fires. Adding CTF ops will multiply these writes per job.

## 5. State files / registries / dotenv overrides

- **`~/.kaggle/kaggle.json`** — read by `tools/kca/kg.py` (Kaggle).
  Not CTF, but precedent for per-platform credential file. Project
  CLAUDE.md §"Dev-phase secret policy" allows it.
- **`~/.ctf/<event-slug>.json`** — proposed per planning Q&A
  (`docs/milestones/m11/loop-prompts.md:665`). **Does not exist on disk yet.**
  The pre-M11 artefacts have no mention of this path.
- **`.env` / `.env.local` / `.env.development`** — readable per the
  2026-05-24 dev-phase carve-out (`CLAUDE.md` §"Dev-phase secret
  policy"). May store `CTF_<EVENT>_*` env-var alternatives.
- **`.env.production` / `.env.test`** — protected
  (`.claude/hooks/guard_tool.py:58–60` deny list).
- **`secrets/**` — deny-listed (`.claude/hooks/guard_tool.py:49`).
- **`data/ctf/<event>/<challenge>/`** — proposed structure for the
  T004 frozen bundle. **Does not exist on disk yet.**
- **`runs/<comp>/<run_id>/`** — Kaggle precedent; M11-T005 will mirror
  this for CTF solver runs (`docs/adr/0005-job-taxonomy.md:72–78`).
- **No CTF-specific state file exists today.** The only persistent
  CTF-related artefact is the `ctf_scopes` row in the local DB.

## 6. Config dimensions

- **`ctf_scopes` columns** — `name`, `authorized_scope`, `target_urls`,
  `local_only` (default `true`), `expires_at` (nullable), `notes`
  (free text), `created_at` (default `now()`).
  `supabase/migrations/0001_init.sql:211–221`.
- **`project_kind` enum** — `kaggle | ctf | general`
  (`supabase/migrations/0001_init.sql:6`). Selecting `ctf` flags a
  project as CTF-shaped; no downstream enforcement today.
- **`competition.platform`** — string column with the ADR-suggested
  vocabulary `kaggle | ctf | hackathon`
  (`docs/adr/0005-job-taxonomy.md:30`). Not constrained by an enum.
- **Reviewer trigger set** — `DEFAULT_TRIGGER_OPS` tuple
  (`src/worker/reviewer.py:20–26`); override via
  `KCA_REVIEWER_TRIGGER_OPS` env var
  (`src/worker/reviewer.py:114–118`).
- **Permissions YAMLs** — `default.yaml`, `permissive-dev.yaml`,
  `competition-runner.yaml` (`.kca/permissions/`). No `ctf_*` operation
  appears in any of them today.
- **Hook deny patterns** — `.claude/hooks/guard_tool.py:84–123` block
  permanent-deletion remote writes, secret reads via shell, and a few
  privilege-escalation shapes. No CTF-specific allow/deny path.
- **`KCA_ALLOW_REMOTE`** — env-var gate
  (`CLAUDE.md` §"Environment configuration"); set to `1` to allow
  Kaggle submit / push / remote-write ops. M11 plans to reuse this
  for CTF remote ops alongside `dangerouslyDisableSandbox`.

## 7. Features to preserve

- **The `local_only` default-true posture** of `ctf_scopes`. Why:
  the entire CTF safety story rests on "no network unless a scope
  explicitly lets you out". Evidence:
  `supabase/migrations/0001_init.sql:217`.
- **`authorized_scope` as a free-text contract.** Why: the human is
  the source of authority; constraining it to an enum risks denying a
  legitimately authorized lab that doesn't fit the enum. Evidence:
  `supabase/migrations/0001_init.sql:215`, `.claude/skills/ctf-sandbox/SKILL.md:8`.
- **`safety-guard` pre-check**. Why: the agent has a documented
  hand-off for "policy-sensitive" tooling
  (`.claude/agents/safety-guard.md:3`); M11's new ops should plug
  into the same hand-off rather than inventing a new one.
- **Reviewer system prompt's "Kaggle/CTF" wording**. Why: the
  reviewer is one model; rewriting the system prompt per platform
  fragments the audit trail. Evidence: `src/worker/reviewer.py:48–59`.
- **The `ctf-sandbox` skill body**. Why: the 7-step workflow is
  already what humans expect; M11-T005 should extend it (cite new
  `kca ctf` commands) rather than replace it. Evidence:
  `.claude/skills/ctf-sandbox/SKILL.md:27–35`.
- **The project-as-billing-boundary contract from ADR-0005**. Why:
  CTF events are scoped under a project for audit; collapsing event
  identity into project identity (see §3) would lose this. Evidence:
  `docs/adr/0005-job-taxonomy.md:19–26`.

## 8. Features to deprecate

- **The five-platform-category ambient assumption in
  `ctf-sandbox/SKILL.md:31`** — "crypto, pwn, web, reversing,
  forensics, misc, OSINT". M11 only exercises `web` + `crypto`; the
  category enum should NOT be carved into the schema yet. Why:
  premature enum lock-in is harder to walk back than premature
  free-text. Land the constrained list later when M11-T005's solver
  shows what categories the platform actually services.
- **The `ctf_scopes.name` as the only event-identifying handle.**
  Why: M11's `ctf_events` table will introduce a slug; the `name`
  column then becomes redundant with `ctf_events.slug`. Evidence:
  `supabase/migrations/0001_init.sql:214`. Plan: keep `name` but
  document it as "human display label" once `event_id` exists.
- **The aspirational `competition.platform = 'ctf'` mention in
  ADR-0005**. Why: today nothing reads that string for CTF; M11 will
  use `ctf_events` directly off `projects.id` instead of routing CTF
  through `competitions`. Evidence: `docs/adr/0005-job-taxonomy.md:30`
  vs the M11 plan in `docs/milestones/m11/loop-prompts.md`. Don't drop the enum
  value — just stop treating it as the routing key.

## 9. Questions for `requirements-skeptic`

- **Event identity collision.** Two CTFtime events with the same slug
  (e.g. a recurring "picoCTF 2024" and "picoCTF 2025") will collide on
  any `ctf_events.slug` UNIQUE index. Do we key `ctf_events` on
  `(project_id, slug, year)` or on a generated UUID with `slug`
  non-unique? Triggered by: `supabase/migrations/0001_init.sql:213, 214`
  (no uniqueness on `(project_id, name)`).
- **Per-event credential ownership.** Can two distinct projects share
  one event credential (one human's `~/.ctf/picoctf2024.json` is read
  by two projects), or is credential ↔ project a 1:N enforced
  contract? Triggered by: `docs/milestones/m11/loop-prompts.md:621–667`,
  `.claude/agents/safety-guard.md:3`.
- **`target_urls` shape.** Is it `["https://chal.example/api/submit",
  …]` (list of strings) or `[{"url": "…", "method": "POST",
  "purpose": "flag_submit"}, …]` (list of objects)? Triggered by:
  `supabase/migrations/0001_init.sql:216` (no shape declared).
- **Local-only enforcement seam.** Where does `local_only=true`
  actually deny egress — at the hook layer, the worker, or the
  permission policy? Triggered by:
  `supabase/migrations/0001_init.sql:217`, `.claude/hooks/guard_tool.py`
  (no CTF-specific egress deny exists).
- **Flag retention.** Do `ctf_attempts` rows store the flag string
  itself? `docs/milestones/m11/loop-prompts.md:317` says "experiment_runs row
  with flag_length (NOT value)" — does that policy hold for
  `ctf_attempts` too? Triggered by:
  `src/worker/reviewer.py:59` ("violate competition/CTF rules" — flag
  hoarding is in scope).
- **Scope expiry behaviour.** When `ctf_scopes.expires_at` passes,
  does the worker hard-deny (raise), soft-deny (write an audit row
  and ask), or auto-renew (call back to the human)? Triggered by:
  `supabase/migrations/0001_init.sql:218` (nullable, no enforcement).
- **Team vs individual flag attribution.** If `ctf_attempts` is
  written under a project but the actual submission was made under a
  team account, how do we attribute the flag for the audit trail?
  Triggered by: `docs/milestones/m11/loop-prompts.md:665` ("optional team_id").
- **Cross-event flag reuse.** Some events let solvers reuse flags
  across challenges (CTF nostalgia); does `ctf_attempts` need a
  challenge FK or just an event FK? Triggered by: M11 task summary
  in `docs/milestones/m11/loop-prompts.md:102–114` (the table shows challenges
  per event but doesn't address cross-challenge reuse).

## 10. Parity tests

- `test_m11_ctf_scope_default_local_only` — assert that
  `INSERT INTO ctf_scopes (project_id, name, authorized_scope)` with
  no `local_only` produces a row with `local_only = true`. Fixture:
  the local supabase-db container. Evidence:
  `supabase/migrations/0001_init.sql:217`.
- `test_m11_ctf_scope_expiry_respected` — insert a scope with
  `expires_at = now() - interval '1 day'`; assert that any
  `challenge_run` against its `target_urls[0]` is denied at the
  reviewer-gate. Fixture: a forward-dated scope row + a stub
  reviewer call. Evidence: `supabase/migrations/0001_init.sql:218`.
- `test_m11_ctf_safety_guard_hand_off` — when the agent is asked to
  invoke a CTF tool, assert `safety-guard` is invoked first and
  returns one of {allowed, needs-approval, blocked}. Evidence:
  `.claude/agents/safety-guard.md:3`.
- `test_m11_ctf_sandbox_skill_steps_logged` — when the
  `ctf-sandbox` skill runs, assert the 7 steps appear in the
  per-job `agent_job_events` trail. Evidence:
  `.claude/skills/ctf-sandbox/SKILL.md:27–35`.
- `test_m11_ctf_reviewer_trigger_includes_new_ops` — assert
  `should_consult_reviewer("challenge_run")`,
  `should_consult_reviewer("flag_submit")`, and
  `should_consult_reviewer("network_egress")` all return True with
  the M11 default trigger set. Evidence: `src/worker/reviewer.py:20–26,
  121–123`.
- `test_m11_ctf_flag_not_echoed` — run a fake flag-submit dry-run
  and grep the stdout/stderr + the `agent_reviews.rationale` field
  + the `ctf_attempts` row for the flag string; assert zero hits.
  Evidence: `docs/milestones/m11/loop-prompts.md:317` ("flag_length (NOT value)").

Output MUST cover all 10 sections; ≥5 distinct legacy behavior dimensions must be named explicitly, including any multi-account / owner / env mapping the legacy artefact encodes.
