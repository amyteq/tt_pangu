# Design archaeology — pre-implementation legacy analysis

Status: design note. Source: `docs/meeting-notes/2026-05-24-r3.md` §6 (Discovery / Debate Gate) and `docs/meeting-notes/2026-05-25-r1.md`.

This document explains the *why* and *boundary* of the [`design-archaeology`](../../.claude/skills/design-archaeology/SKILL.md) skill. The skill itself defines the 10-section report template and the must / must-not rules; this doc is the rationale and the worked-example pointer that justifies the rules.

Pairs with [`session-memory-and-audit.md`](session-memory-and-audit.md) (Tier 1/2/3 model — design-archaeology output lands in Tier 2 / Tier 3 evidence territory) and with [`memory-promotion.md`](memory-promotion.md) (open questions surfaced in `§8` of an archaeology report often feed memory proposals).

---

## 1. The problem the skill solves

The agent will often "take over" a legacy script or config and start writing the replacement straight away. Without an explicit, structured first pass, hidden assumptions vanish silently:

- Multi-account / multi-owner support (the canonical M7–M9 miss — see worked example).
- Dry-run defaults and side-effect classes.
- Local state files / registries that callers depend on.
- CLI flag semantics that the new implementation must preserve.

The fix is a discovery / debate gate: a structured 10-section report whose presence is the precondition for code work. The skill never writes code; the human acknowledges `§8` and then a separate task implements the migration.

---

## 2. The 10 required sections

These are defined in the skill body; do not duplicate them here. Read [`.claude/skills/design-archaeology/SKILL.md`](../../.claude/skills/design-archaeology/SKILL.md) for the canonical list. The 10 sections are not negotiable — a report with 9 or 11 is a defect, regardless of how thoroughly the content is filled out.

The shape is what matters: every legacy artifact gets the same skeleton so the reviewer can scan for the same things in the same order. Variation in *content* is welcomed; variation in *structure* is not.

---

## 3. Why the skill blocks code work

The hard rule "may not write code outside `docs/archaeology/<short-name>.md` until the report exists and `§8` is acknowledged" exists because the failure mode is asymmetric:

- **Cost of writing the report first**: a 20-30 minute structured read of the legacy artifact. Worst case, the report exposes nothing the agent didn't already know — net cost: the report itself.
- **Cost of skipping the report**: a half-built migration that silently dropped multi-account support, multi-owner env mapping, or a state-file convention callers depend on. Worst case: a regression that takes another milestone to undo (this is the M7–M9 → M9.3 motivating failure).

Asymmetric cost ⇒ make the report mandatory.

`§8` (open questions) is the second half of the gate: even when the agent feels confident, `§8` must contain at least one question. This invites the human to push back and surfaces *unknown unknowns* the structured skim missed.

---

## 4. Canonical worked example

[`docs/archaeology/kkr.md`](../archaeology/kkr.md) — design archaeology of `tools/legacy/kkr.py` + `tools/legacy/kkr.yaml`, produced in M9.3-T003. Use it as the reference for the expected level of detail on multi-owner / multi-account assumptions in legacy CLI tools.

Two `§3` / `§7` rows from `kkr.md` illustrate the bar:

- `§3` enumerates the two Kaggle owners (`harrysun2006`, `firefly2006`) and the three-step `_load_env_for_owner` resolution chain (`--env` → `_envs[owner]` → `.env.{owner}` fallback) with `tools/legacy/kkr.py:528-548` cited.
- `§7` Preserve / change / drop matrix carries an explicit "Multi-owner kernel pairs — multi-account quota pool — **Preserve** (subject to `§8` Q1)" row whose rationale names "the original M7–M9 archaeology miss this skill exists to prevent."

A future report missing this level of detail in `§3` / `§7` for a multi-account-shaped legacy tool is a defect.

---

## 5. Where the report lives

- Output path: `docs/archaeology/<short-name>.md` (markdown, committed).
- The skill never edits the legacy tree.
- The report is read-only after acknowledgement: changes to the legacy artifact's actual behavior (because migration started) are tracked in the migration's own task spec, not by editing the archaeology report retroactively.

---

## 6. Relationship to other skills

| Skill | Relationship to design-archaeology |
|---|---|
| [`inventory-drift-audit`](../../.claude/skills/inventory-drift-audit/SKILL.md) | Sibling. Scans the whole repo for drift; design-archaeology focuses on one artifact's hidden assumptions. No overlap. |
| [`research-brief`](../../.claude/skills/research-brief/SKILL.md) | Sibling pattern (read-only on untrusted content, evidence-cited). External research; design-archaeology is on-disk legacy. |
| [`memory-promotion`](../../.claude/skills/memory-promotion/SKILL.md) | `§8` open questions in an archaeology report are good source material for memory-promotion proposals to `docs/milestones/*/handoff.md` or ADRs once the human answers them. Different surfaces, complementary lifecycle. |
| [`milestone-final-review`](../../.claude/skills/milestone-final-review/SKILL.md) | If a milestone includes a legacy migration, `milestone-final-review` should reference the archaeology report as evidence the discovery gate was crossed. |

---

## 7. Non-goals

- This doc does not duplicate the skill body. The skill (`SKILL.md`) is the canonical source for section headings, rules, and frontmatter.
- It does not describe the migration that *follows* the archaeology — that's a separate task spec.
- It does not regulate the user's `memory/` auto-memory directory (separate system; see [ADR-0015](../adr/0015-memory-promotion-model.md)).
