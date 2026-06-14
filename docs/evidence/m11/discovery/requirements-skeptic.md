# requirements-skeptic report for M11 CTF architecture (T000)

Sources:
- Task spec: `docs/tasks/m11/M11-T000-discovery-debate-gate.md`
- Milestone plan: `docs/milestones/m11/loop-prompts.md`
- Upstream archaeology: `docs/evidence/m11/discovery/legacy-archaeologist.md`
- Planning Q&A decisions: `docs/milestones/m11/loop-prompts.md:621–667` ("Human decisions needed").

_Produced under the M11-T000 Discovery / Debate Gate. The agent body
lives in `.claude/agents/requirements-skeptic.md`; this artefact is a
manual execution of that agent's protocol against the proposed M11
data model (`ctf_events` / `ctf_challenges` / `ctf_attempts`), three
new approval ops (`challenge_run` / `flag_submit` / `network_egress`),
and the CTFtime → human-register → per-event-creds → solve → submit
workflow taxonomy._

## hidden_constraints

1. What is the maximum **scope-row count** per project, and is there
   an indexed query path? — consequence if unanswered: an event with
   N challenges plus M target URLs creates N×M-ish scope rows; the
   current `ctf_scopes` table has no `(project_id, expires_at)` index,
   so `expires_at` enforcement at submit time may degrade quadratically.
   Evidence: `supabase/migrations/0001_init.sql:211–223`.
2. Does CTFtime impose a **per-event ToS / scraping policy** the
   platform must respect when fetching event metadata or challenge
   descriptions? — consequence: if T003's `kca ctf event register`
   hits CTFtime even for read-only event metadata, we may need a
   declared `User-Agent`, a polite-rate-limit, and an event-side opt-in
   for any caching we do. The M11 spec does not name CTFtime's ToS as
   a constraint.
3. Is `~/.ctf/<event-slug>.json` **machine-validated** anywhere (JSON
   schema, required-fields enforcement)? — consequence: a typo in
   `team_id` or a missing `token` should refuse before the
   `flag_submit` reviewer-gate fires, not after. Without explicit
   validation, the human's first signal is an `accepted=false` HTTP
   400 from the event API.
4. What is the platform's **flag-string retention policy**?
   `docs/milestones/m11/loop-prompts.md:317` says "experiment_runs row with
   flag_length (NOT value)" for the solver loop; does the same rule
   apply to `ctf_attempts.flag`, to `agent_reviews.rationale` (the
   reviewer sees the flag string when reviewing `flag_submit`), and
   to `agent_job_events.event_data`? — consequence: a flag accidentally
   serialised into the reviewer's `rationale` jsonb survives in the DB
   forever, and CTF event organisers consider flag leakage a write-up
   violation.
5. Does the platform respect the **event's own submission rate
   limit** in addition to KCA's `competition_policy.max_daily_submissions`?
   — consequence: a 1-submission-per-hour event will return 429 from
   `flag_submit`; KCA must back off, not retry. The M11 spec doesn't
   declare which side owns the back-off (T007 stop condition says
   "HALT and open a follow-up issue — do not silently retry"
   per `docs/milestones/m11/loop-prompts.md:401`).

## personas_and_accounts

1. **Event-account vs Kaggle-owner shape parity.** The kkr.py replay
   surfaced multi-owner as load-bearing for Kaggle; CTF has the
   structurally identical problem one dimension over (event-account
   per `ctf_attempts`). Is the M11 schema explicitly modelling
   `ctf_events.event_account` or `ctf_attempts.event_account_id`? —
   consequence: without an explicit column, every flag the platform
   submits attributes to whatever credential happens to be in the
   process env at submission time (the kkr.py failure mode, ported
   to CTF). Evidence: `docs/evidence/m11/discovery/legacy-archaeologist.md`
   §3.
2. **Team vs individual submission.** Some CTFtime events submit
   under a team token; some under an individual token; some support
   both with different endpoints. Does `ctf_attempts` distinguish
   the two? — consequence: a write-up filed under a team account
   that should have been individual contaminates the team's
   leaderboard, which is unrecoverable on most platforms.
3. **Shared event credential across projects.** Can two projects
   under the same Supabase identity submit to the same event from
   the same `~/.ctf/<event-slug>.json`, or is the credential
   project-scoped? — consequence: cross-project sharing means a
   suspended project's leftover scope could resurface flag submits
   under another project's worker if the credential file is shared.
4. **GitHub-identity vs CTF-event-identity vs reviewer-identity.**
   The closing issue for T007 is opened under a GitHub identity; the
   `decision:confirmed` comment is approved by a Supabase reviewer
   identity; the actual submit hits an event endpoint with a CTF
   credential. None of these three need be the same human. Does the
   M11 audit row capture all three? — consequence: an audit gap in
   the "who approved what flag submission under which event account"
   chain breaks incident response.
5. **Service account for the agent worker.** Today the worker
   probably reads the local DSN via the dev-phase carve-out
   (`CLAUDE.md` §"Dev-phase secret policy"). Does the worker also
   read `~/.ctf/<event-slug>.json` directly, or is credential access
   mediated by the new `flag_submit` op (so the worker never sees
   raw token bytes)? — consequence: direct-read makes a worker
   compromise a credential leak; mediated access narrows the blast
   radius to one tool call.

## side_effects

1. **`challenge_run` against a live event challenge endpoint** writes
   nothing on the event side (typically a GET / POST that returns
   problem data) but the platform spends a network round-trip and an
   approval-gate decision. What reverses an over-eager `challenge_run`?
   — consequence: the network call already happened by the time the
   reviewer rejects; the audit row is the only durable artefact.
2. **`flag_submit` against a live event** is irreversible — most
   events count a wrong submission against the team's penalty
   counter (CTFd's "incorrect submission" event). What reverses it?
   — consequence: nothing. Same posture as Kaggle's "no submission
   deletion"; the gate must prevent rather than recover. Is the
   `challenge_run` round-trip cost being conflated with the
   `flag_submit` irreversibility cost in one approval template?
3. **`network_egress` denials against non-scoped hosts** — when the
   worker accidentally tries to hit `kaggle.com` from a CTF job
   context (the T008 case-c test), does the deny write an
   `agent_reviews.verdict=reject` row, an `agent_tool_audit` row,
   or both? — consequence: if both are written, the audit is
   double-counted; if only one, downstream analytics under-count
   the cross-platform refusal rate.
4. **`ctf_scopes` row insertion** by the T003 `kca ctf scope set`
   subcommand — is this a LOCAL_WRITE (no approval, just an audit
   row) or an `ask` op? — consequence: LOCAL_WRITE means the agent
   can widen its own authorization without human review; that is
   the wrong default. The M11 spec implies `LOCAL_WRITE`
   (`docs/milestones/m11/loop-prompts.md:247`) but does not call this out
   as the security-sensitive case it is.
5. **Filesystem writes under `data/ctf/<event>/<challenge>/`** for
   bundle attachments — are these gitignored above a size cap?
   `docs/milestones/m11/loop-prompts.md:281` says "1MB cap per file; bigger =
   gitignored". What enforces the cap on commit (a `pre-commit`
   hook, a `.gitignore` line, or human discipline)? — consequence:
   a 200MB attachment slipped into the repo bloats every clone
   forever.

## edge_cases

1. **Two events with the same slug across years** — picoCTF 2024 vs
   picoCTF 2025; what does `ctf_events.slug UNIQUE` do? — consequence:
   inserting picoCTF 2025 fails after picoCTF 2024 was registered;
   the human must rename. Better: `(slug, year)` composite or a
   generated UUID PK with `slug` non-unique.
2. **A challenge re-released mid-event** with the same slug but a
   different prompt — does `ctf_challenges` keep the old version,
   or overwrite? — consequence: a solver that solved v1 against a
   v2 challenge produces a wrong flag; the audit row points at v2.
3. **A flag accepted by the event but the network ack lost** (HTTP
   timeout after the event recorded the submission) — does
   `ctf_attempts.accepted` get marked `false` or `pending`? —
   consequence: a marked-false attempt looks identical to a real
   wrong submission and triggers a retry — which the event side
   sees as a duplicate.
4. **A flag rejected by the event but with a 200 + `accepted=false`
   body** vs **rejected by the event with a non-2xx status** — does
   the platform treat both as `ctf_attempts.accepted=false` with the
   same row shape? — consequence: silent merging of "wrong flag" and
   "rate-limited" produces misleading analytics.
5. **A scope whose `expires_at` falls between `challenge_run` and
   `flag_submit`** (the human's scope expired mid-solve). Does the
   `flag_submit` gate re-check expiry, or rely on the original
   `challenge_run` check? — consequence: stale-scope flag submits
   are a policy violation the gate can prevent only if both ops
   re-check expiry independently.
6. **Concurrent `flag_submit` jobs against the same challenge** —
   the worker runs two attempts in parallel by mistake; both pass
   the reviewer gate; both hit the event. Does the platform
   serialise per-challenge submissions? — consequence: most events
   penalise duplicate submissions even if both flags are correct.
7. **Malformed `target_urls` JSONB** — a string instead of a list;
   a list of integers; a list of strings containing newlines. Does
   the schema constrain shape (CHECK constraint), or is the worker
   the only validator? — consequence: shape-invalid scopes silently
   widen to "anything" or silently narrow to "nothing".

## rollback

1. **Schema rollback for migration `0008_m11_ctf.sql`** — if the
   migration ships and a downstream tool depends on the table
   shape, is there a `0009_m11_ctf_revert.sql`? — consequence:
   reverting M11 requires either dropping the tables (audit loss)
   or schema-only patches against the live DB.
2. **Permission policy rollback** — adding `challenge_run` /
   `flag_submit` / `network_egress` to `.kca/permissions/*.yaml`
   means every existing project picks up the new ops. If a project
   wants to opt out, is there a `default_decision: allow` override,
   or is opt-out only via removing the op entirely from the YAML? —
   consequence: a coarse rollback (delete the op) re-introduces the
   pre-M11 state where the worker can't even attempt a CTF flow at
   all.
3. **The 1 live submission in T007** — what reverses it? — consequence:
   nothing. Same as M9-T004 / M10-T003: the audit row is the only
   reversal. Does the closing-issue approval comment commit the
   reviewer / project owner to "do not retry this submission" if
   it bounces? The M11 spec says HALT
   (`docs/milestones/m11/loop-prompts.md:585–589`); is HALT enforced by a
   feature flag or by human discipline?
4. **`~/.ctf/<event-slug>.json` deletion** — if the human deletes
   the credential file mid-solve, does the worker fail loudly or
   silently fall back to env vars? — consequence: silent fallback
   means the audit row attributes to the env-var account; loud
   failure means the human must rotate twice.
5. **Bundle rollback** — if the T004 bundled crypto challenge turns
   out to have a non-permissive license (the upstream archive's
   license header was misread), does removing
   `data/ctf/<event-slug>/crypto-1/` revert cleanly? — consequence:
   if `ctf_challenges` references the bundle path, the FK must
   either cascade-delete or hard-fail.

## explicit_unknowns

- Whether CTFtime's calendar API has a stable JSON schema or whether
  T003 must scrape HTML (the planning Q&A names `https://ctftime.org/calendar/`
  but doesn't pin a JSON endpoint).
- Whether the chosen live event for T007 (planning Q&A names
  `bbbctf.com` as a reference but does not pin a slug) uses CTFd,
  rCTF, picoCTF's bespoke platform, or another flag-submit API —
  the credential JSON shape may differ per backend.
- Whether `team_id` in `~/.ctf/<event-slug>.json` is a string
  (CTFtime team slug) or an integer (CTFd internal team_id) — the
  schema field type can't be decided without an event API sample.
- Whether the worker's existing OTEL span schema
  (`agent_telemetry_spans` from M6) carries enough columns to
  attach `(event_slug, challenge_slug, ctf_attempts.id)` without a
  migration; if not, M11 may need an OTEL schema patch.
- Whether `ctf_scopes.target_urls` should support wildcards
  (`https://chal.example/*` to cover N challenge subpaths in one
  row) or whether one URL per row is the contract — affects the
  ergonomics of the T003 `kca ctf scope set` flag.
- Whether the M11 `network_egress` op should also fire for outbound
  DNS lookups (some egress denials need to deny DNS resolution to
  prevent timing side-channels) or only for HTTP/TCP connects.
- Whether the same human who approves the T007 `flag_submit` is
  expected to be the same identity that registered the event
  credential — the M11 spec doesn't enforce a "credential-owner ==
  approver" rule, but a tighter pairing reduces the
  approval-shopping attack surface.
- The actual frozen-bundle event slug for T004: picoCTF YYYY is a
  candidate, but pwnable.kr or CSAW Quals are alternatives and
  each carries a different license + attachment-size profile.

Output MUST contain ≥5 questions spread across ≥3 categories, and an `explicit_unknowns:` section listing things the agent could not answer without human input.
