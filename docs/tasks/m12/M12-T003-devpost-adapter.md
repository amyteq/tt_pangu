# M12-T003: Devpost adapter — READ_ONLY register / fetch / info

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Add `tools/kca/devpost.py` and three READ_ONLY subcommands so the
agent can register the picked hackathon in the local control plane
and read its metadata. No submit / draft / upload paths in this task —
that's M12-T007.

The shape mirrors `tools/kca/competition.py` (Kaggle side) and reuses
the lightweight HTTP + optional Playwright pattern from
`tools/kca/research_fetch.py`.

## Tag

Routine.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 3
4. `docs/adr/0018-generalized-competition-type.md` (T001 output)
5. `docs/evidence/m12/t000-candidates.md` (the picked slug)
6. `tools/kca/research_fetch.py` — HTTP + readability + Playwright opt-in
7. `tools/kca/competition.py` — register/fetch/info shape on the Kaggle side
8. `tools/kca/kca.py` — subcommand registration; add a `devpost` parser
9. `src/db/competition.py` (or wherever competition CRUD lives)
10. `env.example` — to document any new env var names; only document, don't add values
11. `supabase/migrations/0009_m12_competition_type_teams.sql` (T002)

## Scope

1. Create `tools/kca/devpost.py` with three subcommand functions:
   - `cmd_register(slug: str, name: str | None = None) -> None`
     - If `name` is None, call `cmd_fetch` to extract it from the
       public page.
     - Insert a `competitions` row with `competition_type='devpost'`
       (or `'hackathon_devpost'` if ADR-0018 picked that value
       explicitly for this slug; default to `'devpost'` if the ADR is
       silent).
     - Populate `competitions.deadline` and `competitions.submission_format`
       from the fetched page.
     - Idempotent: if the slug is already registered, update the
       deadline / submission_format / name fields and skip the insert.
   - `cmd_fetch(slug: str, playwright: bool = False) -> dict`
     - READ_ONLY HTTP GET against `https://<slug>.devpost.com/` (or
       the platform-equivalent URL the candidate page documented in
       T000).
     - Extract: `title`, `deadline_utc`, `prize_summary`,
       `submission_format` (the list of required fields / artifacts —
       README, demo video, source repo URL, etc.). Use
       `tools/kca/research_fetch.py`'s readability path by default.
     - If `playwright=True`, fall back to a Playwright fetch — same
       opt-in shape as `research_fetch.py`. Default off.
   - `cmd_info(slug: str) -> None`
     - Print the local `competitions` row (READ_ONLY DB).
2. Wire the three commands into `tools/kca/kca.py` as
   `kca devpost {register, fetch, info}`. The subparser registration
   should mirror the existing `kca competition` registration.
3. Document the auth shape used (cookie? API token? anonymous read?).
   `cmd_fetch` MUST work for anonymous reads — the public hackathon
   page is sufficient. If a candidate platform requires login for
   metadata, halt and ask before adding the env-var.
4. Add 3–4 unit tests in `tests/test_m12_devpost_adapter.py` (no
   network):
   - `cmd_fetch` parses a fixture HTML file and returns the four
     expected fields.
   - `cmd_register` is idempotent (run twice, same row).
   - `cmd_info` for an unknown slug exits non-zero with a clean
     error message.
   - Sanity: importing `tools.kca.devpost` does not import Playwright
     eagerly.

## Non-goals

- Do NOT add `cmd_submit`, `cmd_draft`, `cmd_upload`, or any write
  path. T007 adds `cmd_submit`.
- Do NOT add a new permission profile or skill — those are T004.
- Do NOT add UI changes — those are T005.
- Do NOT change `tools/kca/competition.py` (the Kaggle adapter stays
  untouched; the M9 / M10 baseline rows route through
  `competition_type='kaggle'`).
- Do NOT log the raw HTML fetched. Capture only the four extracted
  fields for the closeout.
- Do NOT write any cookie / session token to disk. If a future
  task needs auth, it lives behind `os.environ.get("DEVPOST_*")`.

## Acceptance criteria

- `tools/kca/devpost.py` exists with three functions matching the
  signatures in scope step 1.
- `kca devpost --help` lists `register`, `fetch`, `info`.
- `kca devpost fetch --slug <picked-slug>` returns a dict with
  `title`, `deadline_utc`, `prize_summary`, `submission_format` keys
  (anonymous HTTP path; no Playwright required for the picked slug).
- `kca devpost register --slug <picked-slug>` inserts a `competitions`
  row with `competition_type='devpost'` and populates `deadline` +
  `submission_format`.
- `kca devpost info --slug <picked-slug>` prints the row contents
  (no secrets; the prize_summary may be paraphrased to avoid quoting
  copyrighted text).
- Running `register` twice produces the same row (idempotent).
- `tests/test_m12_devpost_adapter.py` passes; uses fixture HTML, no
  network.
- `ruff check .` clean.
- `python -m pytest tests/ -q` clean; no regressions in M9 / M10
  smoke tests.

## Permissions

- File writes to: `tools/kca/devpost.py`, `tools/kca/kca.py` (add the
  subparser only), `tests/test_m12_devpost_adapter.py`,
  `tests/fixtures/devpost_*.html` (small fixture files).
- HTTP GET to `https://*.devpost.com/` (or the candidate-platform
  equivalent) is allowed — READ_ONLY, no cookies, no submission paths.
- DB writes via `cmd_register` to the local Supabase; needs
  `dangerouslyDisableSandbox=true`.
- No real Devpost write actions. No Playwright unless explicitly
  enabled via `--playwright`.

## Closeout format

```
M12-T003 closeout
  tools/kca/devpost.py: present (register, fetch, info — READ_ONLY)
  CLI: kca devpost register/fetch/info wired
  Picked slug: <slug-from-T000>
  Competition row: <uuid> (competition_type='devpost')
  Deadline: <iso8601-utc>
  Submission format keys: <comma-separated key list>
  Tests: tests/test_m12_devpost_adapter.py (PASS / N tests)
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T004 (hackathon-experiment-loop skill + permission profile)
```

## Related issues

- ADR-0018 (T001 output) — referenced for the enum value
  (`devpost` vs `hackathon_devpost`).
- Closing issue for M12 — gets a comment confirming READ_ONLY only
  (zero write actions).

## Stop condition

Stop after 60 turns. If the picked slug's public page requires login
even for metadata, halt and ask — do NOT add auth env-vars without
human approval. If `cmd_fetch` extracts fewer than the four required
fields, halt and ask; do NOT silently fill in partial data.
