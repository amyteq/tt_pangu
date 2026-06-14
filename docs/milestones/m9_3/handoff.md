# M9.3 → next Handoff Prompt

_Generated 2026-05-26 from `docs/milestones/m9_3/final-review.md`._

Paste this into a fresh session that is starting any work that needs to use the two new skills (`design-archaeology`, `memory-promotion`) or that picks up the deferred M9.1 residual scope (provisional M9.4).

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0–M9 + M9.3 are complete.** M10 (notebook-submission regression on Petals to the Metal) remains the "current milestone" — M9.3 was a sibling sub-milestone that did not change M10's scope.

## Read these files first

In order, before doing any work:

1. `PROJECT_STATE.md` — confirms M9.3 closed; M10 still current.
2. `AGENTS.md` and `CLAUDE.md` — operating principles + dev-phase secret carve-out.
3. `docs/milestones/README.md` — M9.3 row sits between M9.2 and M10.
4. `docs/milestones/m9_3/final-review.md` — 25-check validation matrix.
5. `docs/adr/0015-memory-promotion-model.md` — canonical memory list + propose-only rule.
6. `docs/architecture/memory-promotion.md` — data-flow diagram.
7. `docs/architecture/design-archaeology.md` — rationale + worked-example pointer.
8. `docs/archaeology/kkr.md` — canonical archaeology worked example (10 sections).
9. `docs/proposals/memory-2026-05-26-m10-pr18.md` — canonical memory-promotion worked example (one unchecked patch).
10. `docs/milestones/m9_1/loop-prompts.md` — retirement notice + deferred-scope list.

## State at M9.3 exit

- Two new skills under `.claude/skills/`: `design-archaeology` (124 lines), `memory-promotion` (125 lines).
- ADR-0015 codifies the four canonical memory files: `PROJECT_STATE.md`, `docs/milestones/README.md`, `docs/milestones/m{N}/handoff.md`, `docs/adr/NNNN-*.md`.
- `docs/proposals/` is the new staging directory. One real proposal lives there (PR #18 memory-promotion, unchecked).
- `docs/archaeology/` is the new directory for design-archaeology reports. One real report lives there (`kkr.md`).
- No source / hook / settings.json changes. No DB writes.

## Rules

- **The four canonical memory files are not edited silently.** Use the `memory-promotion` skill to produce a proposal under `docs/proposals/`, then have a human apply it as a normal diff. Milestone close is the one exception explicitly authorised by ADR-0015.
- **Legacy migrations start with design-archaeology.** Before writing any code that replaces / ports / rewrites a legacy script or config, produce a 10-section archaeology report at `docs/archaeology/<short>.md`. Code work is blocked until the report exists and `§8` open questions are acknowledged by a human.
- **`memory/` (user auto-memory) is sandboxed.** The new skills do not touch it. Per-user Claude Code memory rules continue to apply there.

## Follow-ups / Open decisions carried forward from M9.3

1. **Multi-account quota pooling (kkr.md §8 Q1).** Should KCA M10+ re-introduce the `harrysun2006` / `firefly2006` paired-kernel pattern as a first-class feature, or treat it as a manual two-call workflow? Not a blocker for M10 itself, but worth deciding before any new Kaggle-account multi-tenant work.
2. **Owner → env mapping for KCA (kkr.md §8 Q2).** Three options: port `_envs:` into a KCA owners config, keep `.env.{owner}` convention but document it, or add `kca kaggle --profile <owner>`. Each has a different secret-leak blast radius.
3. **Local registry vs Supabase `runs` table (kkr.md §8 Q3).** Confirm `.kkr/registry/` is being replaced (not duplicated) by the existing `runs` table.
4. **`_stub` / `_exts` legacy injection (kkr.md §8 Q4).** Port to KCA, replace with skills, or drop?
5. **`docker_image` + `machine_shape` (kkr.md §8 Q5).** Generalise to `{cpu, gpu, tpu, byod-docker}` profiles, or keep free-form?
6. **PR #18 spec convention (proposal docs/proposals/memory-2026-05-26-m10-pr18.md).** Apply the proposed PROJECT_STATE.md patch about the `## Related issues` per-spec convention? Resolve the open question of whether to backfill M9 specs and whether to lift the rule into `docs/engineering-practice.md`.
7. **Deferred M9.1 residual scope** (provisional M9.4 or later, not scheduled): session-closeout skill, `scripts/claude_export_session.py`, GitHub→Channels bridge, `kca-agent-pack` migration, four bespoke agent wrappers.

None of these blocks M10 execution.
