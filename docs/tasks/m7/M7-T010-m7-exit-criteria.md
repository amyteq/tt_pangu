# M7-T010: M7 exit criteria + final review

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 10; extracted here for the double-layer convention.

## Goal
Verify ALL M7 exit criteria. Gate before M7 is declared complete.

## Read first
1. All other M7 task specs (`docs/tasks/m7/M7-T000` through `M7-T009`).
2. `docs/milestones/m6/final-review.md` (template).
3. `docs/milestones/_templates/handoff-prompt.md` (canonical handoff template).

## Scope / Files / Implementation guidance

Run each check and report PASS / FAIL / SKIP:

### CI
1. `python -m pytest tests/ -v -m "not db"` → 0 failures, 0 errors
2. `ruff check .` → 0 issues
3. `ruff format --check .` → 0 issues
4. `python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"`
   → no exception; jobs no-db, live-db, lint all present

### Skill loader
5. `load_skill('run-milestone')` → `name == 'run-milestone'`
6. `load_skill('triage-log')` → `arguments == ['job_id']`
7. `load_skill('prepare-submission')` → `approval_policy == 'default'`
8. `load_skill('review-pr')` → `'bash' in allowed_tools` (or equivalent)
9. `load_skill('__missing__')` → `FileNotFoundError`
10. `render_skill(s, {'task_path': 'x'})` → `'x' in rendered body`

### Command registry
11. `REGISTRY.list_all()` includes skill, tool, kaggle, decisions
12. `REGISTRY.get('kaggle').side_effect == 'SUBMISSION'`

### Tool registry
13. `list_tools(side_effect='SUBMISSION')` ⊇ `{kaggle_submit, kaggle_push}`
14. `default_decision('__unknown__') == 'ask'`

### Permission policy
15. `load_policy('default').resolve('kaggle_submit') == 'ask'`
16. `load_policy('permissive-dev').resolve('bash') == 'allow'`
17. `load_policy('competition-runner').resolve('kaggle_submit', mode='competition-finalization') == 'allow'`

### kca skill CLI
18. `kca skill list --json` → ok=true, list includes the 4 seed skills
19. `kca skill show run-milestone --json` → ok=true, meta fields present
20. `kca skill run run-milestone --arg task_path=docs/tasks/m7/M7-T001.md --dry-run --json`
    → ok=true, `rendered_prompt` contains `'docs/tasks/m7/M7-T001.md'`,
      `tool_permissions` list non-empty
21. `kca skill run _test_fixture --dry-run --json` (missing --arg)
    → ok=false or exit != 0

### kca tool CLI
22. `kca tool list --json` → ok=true, ≥ 15 tools
23. `kca tool doctor --json` → ok=true, issues=[]
24. `kca tool audit --json` → ok=true (may be empty)

### Audit
25. Running `kca skill run _test_fixture --arg task_path=x` writes `.agent/audit.jsonl`
    with a record whose decision ∈ {allow, ask}

### Architecture doc
26. `docs/architecture/kca-cli-architecture.md` exists, ≥ 80 lines
27. Headings: Overview, Four layers, Skill format, Tool registry, Permission policy,
    Audit trail, Decision gate, Directory layout, Adding a new command,
    Adding a new skill, Adding a new tool — all present

### Smoke tests
28. `python -m pytest tests/test_m7_smoke.py -v` → 15/15 pass (or >= 12 + any extras)

## Final document
- Print full validation matrix (check | PASS/FAIL/SKIP | note).
- If all non-SKIP pass → output `M7 EXIT CRITERIA MET`.
- Create `docs/milestones/m7/final-review.md` following the same structure as
  `docs/milestones/m6/final-review.md` with:
  - Validation matrix.
  - What landed (files created/modified).
  - DB access note (if any DB checks ran).
  - M8 follow-ups list.

Also update, in order:
1. `PROJECT_STATE.md` — set current milestone to M8, summarise M7 deliverables,
   clear M7 open decisions.
2. `README.md` — update "Current milestone" section from M7 to M8.
3. `docs/milestones/README.md` — mark M7 ✓ done with one-line summary.
4. `docs/milestones/m7/handoff.md` — write a per-milestone handoff prompt for the
   next AI tool / session that will start M8. Use `docs/milestones/_templates/handoff-prompt.md` as
   the canonical template and populate:
   - Read-first list (`PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`, the M8 section
     of `docs/milestones/README.md`, this `docs/milestones/m7/final-review.md`, latest ADRs,
     `docs/architecture/kca-cli-architecture.md`).
   - "State at M7 exit" (1–3 lines summarising what landed + the 28-check
     exit matrix outcome + the M8 follow-ups list).
   - "Current task" stub for the first M8 task (typically Prompt 0 of
     `docs/milestones/m8/loop-prompts.md` once that file exists).

   This step is required by `docs/milestones/README.md` § Milestone final-review
   protocol; do not skip it.

## Acceptance criteria
- Validation matrix above all PASS (or SKIP with documented reason).
- `docs/milestones/m7/final-review.md` exists and mirrors the m6 layout.
- `M7 EXIT CRITERIA MET` printed.
- `PROJECT_STATE.md`, `README.md`, `docs/milestones/README.md`, `docs/milestones/m7/handoff.md` updated.
- Report: full matrix, final status.

## Stop condition
Stop after 30 turns.
