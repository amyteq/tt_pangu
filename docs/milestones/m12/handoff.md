# M12 → M13 Handoff Prompt

_Generated 2026-06-09 from `docs/milestones/m12/final-review.md` and
`docs/milestones/README.md` § M13._

Paste this into a fresh session that is starting **M13 (evaluation,
reliability, and regression suite)**, or into a session that will first
complete the deferred T007 real Devpost submit for M12.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M9, M9.2, M9.3, M9.4, and M12 are complete.** Your job is to
start **M13** (evaluation, reliability, and regression suite) per
`docs/milestones/m13/loop-prompts.md` — OR, if the user asks first, to complete
the deferred M12-T007 real Devpost submit (see "State at handoff" for
the resume command).

M12 shipped the generalized competition-policy layer and Devpost
hackathon workflow: ADR-0018 (`competition_type` enum; renumbered from
ADR-0016 during PR #46 merge — M11 took 0016/0017), migration 0009
(`competition_type` / `teams` / `team_memberships` / `deadline` /
`submission_format`), Devpost adapter (`kca devpost register/fetch/
info/submit`), `hackathon-experiment-loop` skill + `hackathon-runner`
permission profile, `submission_checklist` tool, two new UI pages
(`HackathonDeadline`, `SubmissionChecklist`), and a hand-driven local
end-to-end run for "Hack the Zero Stack" (`h01`) producing a submission
pack with `checklist_completion=66.67 %` on cloud Supabase. The
reviewer gate for `devpost_submit` fired; the `human_decisions` row is
pending. The actual Devpost network write is deferred until the user
provides three blocked artefacts.

## Read these files first

1. `PROJECT_STATE.md` — current state at M12 exit; open items including
   the deferred T007.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions; dev-phase secret
   carve-out active; never print the DSN.
4. `docs/milestones/README.md` — M12 done-mark + M13 section.
5. `docs/milestones/m12/final-review.md` — 48-row validation matrix; "Deviations"
   section; deferred T007 resume command; out-of-scope follow-ups.
6. `docs/milestones/m13/loop-prompts.md` — M13 Loop Prompt set (planning docs
   landed in commit `c53bbaa`).
7. `docs/engineering-practice.md` — GitHub collaboration model.
8. `docs/architecture/kca-cli-architecture.md` — four-layer model that
   M12 extended.
9. `docs/adr/0018-generalized-competition-type.md` — M12's arch ADR
   (renumbered from 0016 during PR #46 merge); M13 inherits the
   competition_type enum shape.
10. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
11. `docs/milestone-loop-protocol.md` — per-milestone worktree rules,
    secret denylist, sequencing.

## State at handoff

### M12 artefacts now on main (pending PR merge)

- **Schema:** `supabase/migrations/0009_m12_competition_type_teams.sql`
  applied to cloud Supabase (AP-Northeast-2 pooler). Local Docker
  stack was retired 2026-06-09.
- **Policy:** `competition_type` enum on `competitions`; policy
  resolver in `tools/kca/agent/permission_policy.py` routes on type;
  3 pre-existing Kaggle rows backfilled to `competition_type='kaggle'`.
- **Adapter:** `tools/kca/devpost.py` — `cmd_register`, `cmd_fetch`,
  `cmd_info`, `cmd_submit` (credentials-gated; exits non-zero without
  `DEVPOST_*` env vars). `kca devpost register/fetch/info/submit`
  wired.
- **Skill + profile:** `.kca/skills/hackathon-experiment-loop/SKILL.md`
  + `.kca/permissions/hackathon-runner.yaml`.
- **Tool:** `tools/kca/submission_checklist.py` registered.
- **UI:** `ui/src/pages/HackathonDeadline.tsx` + `SubmissionChecklist.tsx`;
  `ui/tests/e2e/m12-pages.spec.ts` (6 Playwright tests).
- **Decision API:** `GET /runs/<run_id>/submission_pack` (READ_ONLY).
- **Prototype:** `src/h01_prototype/` (shippable code for h01).
- **Tests:** `tests/test_m12_e2e.py` (6), `tests/test_m12_policy.py`
  (4), `tests/test_m12_devpost_adapter.py` (6),
  `tests/test_m12_submission_checklist.py` (8),
  `tests/test_m12_smoke.py` (5 PASS + 2 XFAIL[strict=False]).
- **Full suite posture:** no-DB 120 passed / 21 skipped; live-DB
  (cloud) 135 passed / 4 skipped / 2 xfailed / 0 failures.

### Cloud DB rows created in M12

- `competitions.id=d66f321c-3e47-4bcf-9dce-c2a0b9e9d01f` (h01, type=devpost, deadline 2026-06-30)
- `agent_jobs.id=6f6f07c1-f271-49df-963d-227cbee3dbe9` (status=succeeded, 6/80 turns)
- `experiment_runs.id=5964822d-7f8c-4e5f-9200-2436343da461` (checklist_completion=66.67)
- `agent_reviews.id=213e08e6-5ef0-4a75-b6eb-f1f6b6c85636` (verdict=abstain)
- `human_decisions.id=754cadda-3e08-4072-8bd0-2a088dbd4a06` (status=pending — T007 deferred)
- `agent_job_events.id=78` (event_type=approval_pause, target_op=devpost_submit)

### Deferred T007 — real Devpost submit

Status: `human_decisions.id=754cadda-3e08-4072-8bd0-2a088dbd4a06`,
`status=pending`. Issue #42 is labeled `policy:approval-required`.
Approval comment: #42#issuecomment-4650855888.

Three blocked artefacts the user must provide before the submit can
proceed:

1. Demo video uploaded and URL noted.
2. Live deployment link (Vercel or equivalent).
3. Screenshots / visual evidence of the prototype.

Resume command (run once artefacts are ready):

```bash
kca devpost submit --slug h01 --run-id r-20260608_154243 \
  --message "<your submit message>"
```

Then approve the pending decision:

```bash
kca decisions approve --id 754cadda-3e08-4072-8bd0-2a088dbd4a06
```

Update issue #42 with the resulting Devpost submission URL. The M12 PR
body can then be edited to check the "Live external submission" box.

### Hackathon deadline

h01 ("Hack the Zero Stack") deadline: **2026-06-30T00:00:00Z**. If the
user wants to make the real Devpost submit before M13 begins, there is
a 21-day window from this handoff date.

### DB access note

Cloud Supabase is the source of truth (project `qyoprtshfhfzrczlwbyv`,
AP-Northeast-2 pooler). Local Docker stack is retired. DB calls
require `dangerouslyDisableSandbox=true`. Never print the DSN literal.

## Cross-cutting follow-ups (open)

From M9 (still tracked):

- **A** — `competitions.repo_url` schema drift (`type:bug`, `area:kaggle`).
- **B** — Secrets-file hygiene in pytest subprocess (issue #11, P0; M10-T007 hard pre-req).
- **C** — `decision_api`: no `GET /decisions` endpoint (`type:feature`, `area:supabase`).
- **D** — `reviewer_decision` literal event_type not emitted (`type:docs`, `area:worker`).
- **E** — Migration 0004 optional columns not applied (`type:bug`, `area:supabase`).

From M12 ADR-0018:

- **F1** — jsonb type-check for `submission_format` (`type:bug`, P2 tech-debt).
- **F2** — `approved_by_user_id` FK on `human_decisions` (`type:feature`, P1).
- **F3** — resolver `profile_fallback` event type in `permission_policy.py`.
- **F4** — ship `ctf-runner.yaml` permission profile (M11 task).

New from M12:

- **G1** — Real Devpost submit for T007 (P0, deferred; see above).
- **G2** — Full team-invite / role-based permission flow (P2, follow-up issue).
- **G3** — Other hackathon platforms: HackerEarth, MLH, Devfolio.
- **G4** — Auto-generated demo video / README from agent run logs.

## Current task

Start **M13 (evaluation, reliability, and regression suite)**.
The planning docs for M13 are already on main (`c53bbaa`):
`docs/milestones/m13/loop-prompts.md` and the matching task specs. Read those
first; the entry point is M13-T000.

The h01 hackathon deadline is 2026-06-30. If the user wants to close
out the deferred T007 real Devpost submit before diving into M13, do
that first: provide the 3 blocked artefacts, run the resume command
above, then update issue #42. The M12 PR body can be updated to check
the submission box at that point.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets. Never print the Supabase DSN.
- Never submit to Devpost or Kaggle without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge
  environments (M11 scope).
- Per-milestone worktree per `docs/milestone-loop-protocol.md` §5.
  Squash-merge defaults: drop `--delete-branch` so the GitHub branch
  remains for audit.
