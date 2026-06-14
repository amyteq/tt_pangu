# M9.4-T005: `kkr.py` / `kkr.yaml` replay through the gate + smoke tests

## Milestone
M9.4: Discovery / Debate Gate agents (planning + scaffolding).

## Goal
Validate the gate's *content* (does it actually surface what was
missed?) and its *plumbing* (do the files parse?) in one task. Replay
the original `kkr.py` / `kkr.yaml` migration through the
`design-archaeology` skill and capture the three agent transcripts.
Acceptance: the replay recovers the multi-Kaggle-account / owner / env
mapping that the live migration missed.

Origin: `docs/meeting-notes/2026-05-24-r3.md` §6 ("agent 并没有询问
原先设计中的一些理念, 比如多 Kaggle 账户提交") — this task closes the
observation gap.

## Read first

1. `docs/milestones/m9_4/loop-prompts.md` §M9.4-T005
2. `docs/tasks/m9_4/M9_4-T001..T004` closeouts
3. `tools/legacy/kkr.py`, `tools/legacy/kkr.yaml`
4. `docs/tasks/m1/M1-T000-legacy-tool-inventory.md` (what was migrated)
5. `.claude/skills/design-archaeology/SKILL.md` (from T004)
6. Memory: `feedback_use_stored_endpoints` — if a local-model run is
   wired in, use stored endpoints; do not re-ask.

## Scope

1. Invoke the `design-archaeology` skill on the `kkr.py` / `kkr.yaml`
   fixture. The orchestration order is legacy-archaeologist →
   requirements-skeptic → design-red-team (per T004).
2. Capture each agent's output as a standalone markdown file under
   `docs/evidence/m9_4-kkr-replay/`:
   - `legacy-archaeologist.md`
   - `requirements-skeptic.md`
   - `design-red-team.md`
   Each file MUST start with a one-line provenance header:
   `Source: tools/legacy/kkr.py @ <git rev>, tools/legacy/kkr.yaml @ <git rev>`.
3. Add `tests/test_m9_4_agents.py` (no DB, no creds, no network). The
   test must verify:
   - All three `.claude/agents/*.md` files exist and YAML front-matter
     parses with `name`, `description`, `tools`, `model`,
     `permissionMode` keys present.
   - `.claude/skills/design-archaeology/SKILL.md` exists and parses.
   - `docs/architecture/discovery-debate-gate.md` exists and contains
     all three agents' canonical acceptance lines as substrings.
   - The §7 heading exists in `docs/milestone-loop-protocol.md`.
   - At least one of the three evidence files explicitly names a
     multi-account / owner / env semantic (regex match for "owner",
     "account", and "env" within the legacy-archaeologist transcript).
4. The test file must pass standalone:
   `pytest tests/test_m9_4_agents.py -q` exits 0.

## Non-goals

- Do not run the legacy `kkr.py` to produce its output. The replay
  reads files; it does not execute them.
- Do not file follow-up GitHub issues here. Surface them in the T005
  closeout for T006 to bundle.
- Do not modify the agents or skill produced in T001–T004.
- Do not commit any Kaggle credentials, dotenv contents, or any other
  secret-denylist material — even if `kkr.yaml` references them by
  name.

## Acceptance criteria

- Three evidence files exist under `docs/evidence/m9_4-kkr-replay/`,
  each ≥80 lines and with the provenance header.
- The `legacy-archaeologist.md` evidence file explicitly names the
  multi-account / owner / env mapping (the gap from the meeting note).
- `tests/test_m9_4_agents.py` exists and passes (no DB / no creds /
  no network).
- `pytest tests/test_m9_4_agents.py -q` exits 0.
- No file outside `docs/evidence/m9_4-kkr-replay/` and
  `tests/test_m9_4_agents.py` is touched in T005.

## Permissions

- Local writes restricted to the paths above.
- No DB, no Kaggle, no network calls during the replay or the test.
- `git commit` / `git push` deferred to milestone closeout (T006).

## Closeout format

```
M9.4-T005 closeout
  Evidence files:
    docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md (lines=…)
    docs/evidence/m9_4-kkr-replay/requirements-skeptic.md (lines=…)
    docs/evidence/m9_4-kkr-replay/design-red-team.md (lines=…)
  Provenance header on all three: YES | NO
  Multi-account / owner / env named in legacy-archaeologist evidence: YES | NO
  Test file: tests/test_m9_4_agents.py (tests=…, pass=…)
  pytest exit code: 0 | non-zero
  Acceptance: PASS | FAIL
  Risks / blockers: …
  Next: M9.4-T006 ready
```

## Stop condition

Stop after 80 turns. If the replay does NOT surface the multi-account
/ owner / env mapping, the agents themselves are mis-specified — do
NOT massage the evidence to claim PASS. Halt and ask; T001 / T002 may
need revision.
