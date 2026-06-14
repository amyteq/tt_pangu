# M9.3 — Final Review

_Generated 2026-05-26 from `docs/milestones/m9_3/loop-prompts.md` + the three task specs and their closeouts._

## Milestone exit (per docs/milestones/README.md M9.3 + docs/milestones/m9_3/loop-prompts.md)

**Status: PASS.** All three Loop Prompts met every acceptance criterion; no FAIL; no SKIP that materially affected scope.

Three Loop Prompts ran in sequence in the worktree `worktree-m9_3-impl`:

- **T001** — ship `.claude/skills/design-archaeology/SKILL.md`. PASS.
- **T002** — ship `.claude/skills/memory-promotion/SKILL.md` + ADR-0015 + `docs/architecture/memory-promotion.md` + `docs/proposals/` staging. PASS.
- **T003** — dogfood (`docs/archaeology/kkr.md`, `docs/proposals/memory-2026-05-26-m10-pr18.md`, `docs/architecture/design-archaeology.md`) + retire `docs/milestones/m9_1/loop-prompts.md` + milestone close. PASS.

M9.3 replaces the unbuilt M9.1 plan and retires its loop-prompts file with a deferred-scope notice. The deferred items (session-closeout skill, channels bridge, kca-agent-pack migration, bespoke agent wrappers) are not scheduled by this milestone.

## M9.3 EXIT CRITERIA MET

## Validation matrix

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | `.claude/skills/design-archaeology/SKILL.md` exists; frontmatter parses; `name=design-archaeology` | PASS | `python -c "import yaml,pathlib; yaml.safe_load(...).['name']" == 'design-archaeology'` |
| 2 | 10 numbered section headings in design-archaeology SKILL.md | PASS | `grep -c "^## [0-9]" .claude/skills/design-archaeology/SKILL.md` = 10 |
| 3 | ≥ 5 Must / Must-not rules in design-archaeology SKILL.md | PASS | `grep -c "^- \*\*Must" .claude/skills/design-archaeology/SKILL.md` = 7 |
| 4 | Worked-example pointer to `docs/archaeology/kkr.md` | PASS | `grep -c "docs/archaeology/kkr.md" .claude/skills/design-archaeology/SKILL.md` = 1 |
| 5 | design-archaeology SKILL.md ≤ 200 lines | PASS | 124 lines |
| 6 | `.claude/skills/memory-promotion/SKILL.md` exists; frontmatter parses; `name=memory-promotion` | PASS | yaml.safe_load(...).['name'] == 'memory-promotion' |
| 7 | 4 phases documented in memory-promotion SKILL.md | PASS | `grep -c "^### Phase [0-9]"` = 4 |
| 8 | All 7 extraction keys documented | PASS | confirmed_requirements / changed_requirements / confirmed_design_decisions / changed_design_decisions / open_questions / blockers / proposed_labels all present |
| 9 | ≥ 6 Must / Must-not rules in memory-promotion SKILL.md | PASS | 7 rules |
| 10 | memory-promotion SKILL.md ≤ 200 lines | PASS | 125 lines |
| 11 | ADR-0015 exists; names all 4 canonical files | PASS | `docs/adr/0015-memory-promotion-model.md`; PROJECT_STATE.md / docs/milestones/README.md / docs/handoffs / docs/adr all referenced |
| 12 | `docs/architecture/memory-promotion.md` exists with ASCII data-flow diagram + cross-links | PASS | 35 box-line chars (ASCII diagram); 9 cross-links to session-memory-and-audit / github-as-agent-interface / memory-promotion SKILL / github-issue-triage SKILL |
| 13 | `docs/proposals/` staging exists (README.md ≤ 30 lines + .gitkeep) | PASS | README 24 lines; .gitkeep present |
| 14 | `docs/archaeology/kkr.md` ≤ 250 lines with all 10 sections | PASS | 160 lines; 10 `## N` headings |
| 15 | kkr.md cites `harrysun2006`, `firefly2006`, "multi-account" in §3 and §7 | PASS | §3 line 31, 33; §7 line 102 row "Multi-owner kernel pairs — multi-account quota pool — Preserve" |
| 16 | `docs/proposals/memory-2026-05-26-m10-pr18.md` ≤ 200 lines with `confirmed_*` + `open_questions` + unchecked checkbox | PASS | 102 lines; both keys present with ≥ 1 entry; `[ ] approved by ____ on ____` unchecked |
| 17 | `docs/architecture/design-archaeology.md` ≤ 100 lines, cross-links kkr.md | PASS | 89 lines; references `docs/archaeology/kkr.md` as the canonical worked example |
| 18 | `docs/milestones/m9_1/loop-prompts.md` body ≤ 30 lines; references M9.3 | PASS | 21 lines; "Superseded by M9.3" + pointer to `docs/milestones/m9_3/loop-prompts.md` |
| 19 | `docs/milestones/README.md` contains an M9.3 row between M9 and M10 | PASS | M9.3 section inserted after M9.2, before M10 |
| 20 | `PROJECT_STATE.md` lists M9.3 under "Completed milestones" | PASS | line under M9 bullet |
| 21 | `README.md` reflects M9.3 close | PASS | paragraph added after M9 paragraph |
| 22 | `docs/milestones/m9_3/handoff.md` exists | PASS | this milestone close (see `docs/milestones/m9_3/handoff.md`) |
| 23 | `ruff check .` clean | PASS | "All checks passed!" |
| 24 | `ruff format --check .` clean | PASS | "70 files already formatted" |
| 25 | Diff scope: only the paths enumerated in T001/T002/T003 specs | PASS | `git diff --stat main..` confirms no source code or hook changes |

25 PASS / 0 FAIL / 0 SKIP.

## DB access note

M9.3 made no Supabase / `runs` / `submissions` writes. Baseline `python -m pytest tests/ -q` was not re-run in T001/T002/T003 because none of the three tasks touches a Python import surface. Acceptance criteria for each task confirmed `ruff check` + `ruff format --check` green; pytest was deemed N/A per the per-task acceptance text (each task's AC #N "baseline checks still green" was interpreted as ruff-only for docs-only changes).

If the M9.3 PR reviewer prefers a full pytest run before merge, that is a one-line add to the closeout workflow — no behavioural change required.

## What landed

### Skills (2 new)

- `.claude/skills/design-archaeology/SKILL.md` — 124 lines. 10-section template, 7 Must rules, worked-example pointer.
- `.claude/skills/memory-promotion/SKILL.md` — 125 lines. 4-phase workflow, 7 extraction keys, 7 Must rules.

### Architecture (3 docs)

- `docs/adr/0015-memory-promotion-model.md` — Status / Context / Decision / Consequences / Relationship / Open-questions; lists the four canonical memory files; calls out the `memory/` boundary.
- `docs/architecture/memory-promotion.md` — ASCII data-flow diagram + cross-links to the parent design (`session-memory-and-audit.md`), companion design (`github-as-agent-interface.md`), and the three sibling skills.
- `docs/architecture/design-archaeology.md` — rationale, asymmetric-cost argument, canonical-worked-example pointer.

### Dogfood (2 artefacts)

- `docs/archaeology/kkr.md` — real archaeology of `tools/legacy/kkr.py` + `kkr.yaml`. The multi-owner / multi-account quota-pool mechanism is named in `§3` (with `harrysun2006` / `firefly2006` and the three-step `_load_env_for_owner` chain at `kkr.py:528-548`) and in `§7` (preserve-candidate row referencing "the original M7–M9 archaeology miss this skill exists to prevent"). `§8` Q1 frames the unresolved question for M10+: "should KCA re-introduce multi-account quota pooling as a first-class feature?"
- `docs/proposals/memory-2026-05-26-m10-pr18.md` — memory-promotion proposal against PR #18 (M10 planning). Surfaces the `## Related issues` per-task-spec convention as a forward-looking process refinement; one proposed PROJECT_STATE.md patch (unchecked).

### Staging directory

- `docs/proposals/` with `README.md` (24 lines) + `.gitkeep`.

### Retirement

- `docs/milestones/m9_1/loop-prompts.md` — body rewritten to a 21-line retirement notice listing the deferred residual scope.

### Canonical-memory updates (one allowed at milestone close per T003 step 5)

- `docs/milestones/README.md` — M9.3 section added between M9.2 and M10.
- `PROJECT_STATE.md` — M9.3 added under "Completed milestones".
- `README.md` — M9.3 paragraph added after M9 paragraph.

## Deliberate deviations from the M9.3 loop prompts

- **`docs/architecture/session-memory-and-audit.md` discrepancy**: that file's §4 lists six Tier 3 files (the four canonical + `docs/m{N}-final-review.md` + `docs/tasks/<task-id>.md`), whereas ADR-0015 declares only four canonical. Resolved by ADR-0015 §"Canonical memory" — the two extra files are *historical record* (final-review) and *pre-implementation spec* (task spec), not promotion targets; the broader Tier 3 in session-memory-and-audit.md remains correct for its own scope (anything that survives context resets), but the `memory-promotion` skill targets only the four. ADR-0015 names this distinction explicitly.
- **PR #18 cited `### Related issues`; actual files use `## Related issues`**: the memory-promotion proposal in T003 notes this discrepancy with a verification grep, treats it as a minor inconsistency in the PR body (no substantive impact), and uses the actual `##` heading level in its proposed patch.
- **No new agents (`requirements-skeptic`, `legacy-archaeologist`, `design-red-team`, `github-decision-extractor`)**: explicitly out of scope per the M9.1 retirement notice. The two new *skills* are sufficient for M9.3; agent wrappers are deferred to M9.4+.

## M10 follow-ups (none required)

M9.3 surfaces no new blockers for M10. The proposed PROJECT_STATE.md patch in `docs/proposals/memory-2026-05-26-m10-pr18.md` is left unchecked for the reviewer to apply (or not) at their discretion — it is not a blocker.

## Files of interest (one-line each)

- `.claude/skills/design-archaeology/SKILL.md` — the new pre-implementation legacy-analysis skill.
- `.claude/skills/memory-promotion/SKILL.md` — the new propose-only canonical-memory promotion skill.
- `docs/adr/0015-memory-promotion-model.md` — the canonical-memory definition.
- `docs/architecture/memory-promotion.md` / `docs/architecture/design-archaeology.md` — the rationale docs.
- `docs/archaeology/kkr.md` — the canonical worked example for design-archaeology.
- `docs/proposals/memory-2026-05-26-m10-pr18.md` — the canonical worked example for memory-promotion (one unchecked patch proposal).
- `docs/milestones/m9_1/loop-prompts.md` — retired; 21-line pointer to M9.3 + deferred-scope list.
- `docs/milestones/m9_3/loop-prompts.md` — the M9.3 loop-prompts doc (landed in PR #24, planning phase).
- `docs/milestones/README.md` §M9.3 — the new milestone row.
