# M9.4 — Final Review

_Discovery / Debate Gate agents: `requirements-skeptic`,
`legacy-archaeologist`, `design-red-team`._

Status: PASS — 17 PASS / 1 SKIP / 0 FAIL.
Closed: 2026-05-26.
Closing branch: `worktree-m9_4-execute` (PR against `main`).

## Scope reminder

M9.4 ships the three role-isolated subagents specified in
`docs/meeting-notes/2026-05-24-r3.md` §6 ("做法 3 — 增加反方 agent")
plus the `discovery-debate-gate` architecture doc and a single
additive section (§7) of `docs/milestone-loop-protocol.md`. Origin
gap: the original `tools/legacy/kkr.py` migration missed multi-Kaggle-
account / owner / env semantics because no agent role was responsible
for surfacing them.

M9.4 is **planning + scaffolding** — no `src/`, `tools/kca/`, `ui/`,
`services/`, `supabase/migrations/`, or hook changes; no real Kaggle
calls; no DB schema changes.

## Scope deviations applied in flight

| Original plan | Deviation | Reason |
|---|---|---|
| T004: create `.claude/skills/design-archaeology/SKILL.md` | DROPPED | M9.3-T001 (PR #24, merged) owns this artefact. |
| T004: create `docs/architecture/design-archaeology.md` | DROPPED | M9.3-T003 owns this artefact. |
| T005: invoke the `design-archaeology` skill | RE-SCOPED | The skill file is not yet on disk (M9.3-T001 not executed). T005 ran the three agents directly against `kkr.py` / `kkr.yaml` and emitted compatible-shape transcripts. |
| T005 test: hard-assert skill loader resolves the skill | SOFT-SKIPPED | `tests/test_m9_4_agents.py::test_design_archaeology_skill_present_or_skipped` uses `pytest.skip(...)` until M9.3 lands. Becomes a hard PASS when M9.3-T001 is on disk. |

No other deviations.

## Acceptance matrix

### M9.4-T001 — `requirements-skeptic`

| AC | Evidence | Result |
|---|---|---|
| `.claude/agents/requirements-skeptic.md` exists, YAML parses | `tests/test_m9_4_agents.py::test_agent_frontmatter_parses[requirements-skeptic.md]` | PASS |
| Five mandatory categories (`hidden_constraints`, `personas_and_accounts`, `side_effects`, `edge_cases`, `rollback`) listed verbatim | grep on file | PASS |
| Four Must-NOT rules listed verbatim | regex `^- Do not …` ≥4 | PASS |
| Acceptance line verbatim | `tests/…::test_agent_has_canonical_acceptance_line[requirements-skeptic.md]` | PASS |
| No other file touched in T001 | `git diff --stat` scope to `.claude/agents/requirements-skeptic.md` only | PASS |

### M9.4-T002 — `legacy-archaeologist`

| AC | Evidence | Result |
|---|---|---|
| `.claude/agents/legacy-archaeologist.md` exists, YAML parses | `tests/…::test_agent_frontmatter_parses[legacy-archaeologist.md]` | PASS |
| All 10 mandatory output sections listed verbatim in order | regex 10 numbered headers in body | PASS |
| Four Must-NOT rules listed verbatim | regex `^- Do not …` ≥4 | PASS |
| Acceptance line (with multi-account/owner/env explicitly named) verbatim | `tests/…::test_agent_has_canonical_acceptance_line[legacy-archaeologist.md]` | PASS |
| No other file touched in T002 | `git diff --stat` | PASS |

### M9.4-T003 — `design-red-team`

| AC | Evidence | Result |
|---|---|---|
| `.claude/agents/design-red-team.md` exists, YAML parses | `tests/…::test_agent_frontmatter_parses[design-red-team.md]` | PASS |
| Four mandatory output sections (`alternatives:`, `dropped_capabilities:`, `long_term_costs:`, `open_disagreements:`) | grep on file | PASS |
| Four Must-NOT rules listed verbatim | regex `^- Do not …` ≥4 | PASS |
| Acceptance line verbatim | `tests/…::test_agent_has_canonical_acceptance_line[design-red-team.md]` | PASS |
| No other file touched in T003 | `git diff --stat` | PASS |

### M9.4-T004 — discovery-debate-gate doc + protocol §7

| AC | Evidence | Result |
|---|---|---|
| `docs/architecture/discovery-debate-gate.md` exists, contains union of three acceptance lines, the `arch:` / `legacy-migration:` tag convention, and the closeout-evidence path convention | `tests/…::test_discovery_debate_gate_doc_present` | PASS |
| `docs/milestone-loop-protocol.md` ends with new §7 with exact heading "## 7. Discovery / Debate Gate" | `tests/…::test_protocol_section_7_present` | PASS |
| Protocol §1–§6 byte-identical to pre-T004 | `git diff origin/main…HEAD -- docs/milestone-loop-protocol.md` shows only an additive tail | PASS |
| `.claude/skills/design-archaeology/SKILL.md` NOT recreated (M9.3 owns it) | `ls .claude/skills/design-archaeology/` is absent on this branch | PASS (deviation noted above) |

### M9.4-T005 — kkr replay + smoke tests

| AC | Evidence | Result |
|---|---|---|
| Three evidence files under `docs/evidence/m9_4-kkr-replay/`, each ≥80 lines, each with provenance header | `wc -l` ⇒ 216 / 144 / 151; tests `test_kkr_replay_evidence_present` | PASS |
| Multi-account / owner / env explicitly named in the legacy-archaeologist evidence (the load-bearing M9.4 gate) | `tests/…::test_legacy_archaeologist_evidence_names_multi_account` — verifies `harrysun2006`, `firefly2006`, `.env.{owner}`, `owner` | PASS |
| `tests/test_m9_4_agents.py` exists and runs with no DB / no creds / no network | `python -m pytest tests/test_m9_4_agents.py -q` | PASS (10 passed, 1 skipped) |
| `pytest tests/test_m9_4_agents.py -q` exits 0 | local run | PASS |
| Skill-loader assertion | `test_design_archaeology_skill_present_or_skipped` | SKIP — by design until M9.3-T001 lands |

### M9.4-T006 — exit criteria + final review (this doc)

| AC | Evidence | Result |
|---|---|---|
| `docs/milestones/m9_4/final-review.md` exists, matches M8.5 / M9 layout, every AC mapped to evidence | this file | PASS |
| `PROJECT_STATE.md` reflects M9.4 done | `git diff` on PROJECT_STATE.md in this PR | PASS |
| `docs/milestones/README.md` has §M9.4 entry | `git diff` on docs/milestones/README.md in this PR | PASS |
| `README.md` correct for active milestone (M10 remains active) | unchanged | PASS |
| One commit per Loop Prompt landed | `git log --oneline origin/main..HEAD` shows 6 commits | PASS (see worktree-milestone-pr output at close time) |
| Branch pushed; PR open against `main` with this file as body | gh pr create | PASS |

## Files added / modified

```
.claude/agents/requirements-skeptic.md    (new, 3621 bytes)
.claude/agents/legacy-archaeologist.md    (new, 5355 bytes)
.claude/agents/design-red-team.md         (new, 4333 bytes)
docs/architecture/discovery-debate-gate.md(new, 6171 bytes)
docs/milestone-loop-protocol.md           (additive §7 only; §1–§6 unchanged)
docs/evidence/m9_4-kkr-replay/legacy-archaeologist.md  (new, 216 lines)
docs/evidence/m9_4-kkr-replay/requirements-skeptic.md  (new, 144 lines)
docs/evidence/m9_4-kkr-replay/design-red-team.md       (new, 151 lines)
tests/test_m9_4_agents.py                 (new, 10 passed / 1 skip)
docs/milestones/m9_4/final-review.md                 (new, this file)
PROJECT_STATE.md                          (M9.4 ✓ added)
docs/milestones/README.md                        (§M9.4 entry added)
```

Not touched: `src/`, `tools/kca/`, `ui/`, `services/`, `supabase/migrations/`,
`.claude/hooks/`, `.claude/settings.json`, `README.md`,
`tools/legacy/kkr.py`, `tools/legacy/kkr.yaml`.

## Counts

- PASS: 17
- SKIP: 1 (`test_design_archaeology_skill_present_or_skipped` — by design, deferred to M9.3-T001)
- FAIL: 0

## Risks carried out of M9.4

- **M9.3 dependency**: §7 of the protocol gains its skill-orchestration
  path only when `.claude/skills/design-archaeology/SKILL.md` is on
  disk. Until then, the gate runs by direct subagent invocation
  against `docs/architecture/discovery-debate-gate.md`, which is
  functional. The soft-skip test makes this explicit.
- **Hook-based enforcement** of the gate (e.g. PreToolUse refusing
  `Edit` on `src/**` when an `arch:` task has no `discovery/`
  evidence) is out of scope. File a follow-up if wanted.
- **Runtime / SDK version** of the three agents (i.e. inside
  `src/worker/`) is out of scope.

## Follow-up issues to propose

1. After M9.3-T001 lands, replace the soft-skip in
   `tests/test_m9_4_agents.py::test_design_archaeology_skill_present_or_skipped`
   with a hard assertion that the skill resolves to a parseable YAML
   front-matter (labels: `area:agents`, `type:test`).
2. File issue to add an explicit `owner` field to `runs` /
   `experiment_runs` and a `--owner` flag to `kca kaggle push` /
   `kca kaggle submit`, surfaced as the load-bearing
   `open_disagreements` entry in
   `docs/evidence/m9_4-kkr-replay/design-red-team.md`
   (labels: `area:kaggle`, `type:feature`, `policy:approval-required`).
3. File issue to research the `kkr.py` JSON-shape contract
   (`_emit_ok` at `tools/legacy/kkr.py:332`) for outside-repo
   consumers before the M10 `cmd_push --json` shape is locked
   (labels: `area:kaggle`, `type:research`).
4. File issue for hook-based enforcement of the Discovery / Debate
   Gate (labels: `area:safety`, `type:feature`).

## Cross-references

- `docs/meeting-notes/2026-05-24-r3.md` §6 — origin
- `docs/milestones/m9_4/loop-prompts.md` — milestone overview + 6 Loop Prompts
- `docs/architecture/discovery-debate-gate.md` — canonical AC template
- `docs/milestone-loop-protocol.md` §7 — additive gate wiring
- M9.3 sibling: `docs/milestones/m9_3/loop-prompts.md` (skill side)
