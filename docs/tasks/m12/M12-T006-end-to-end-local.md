# M12-T006: Local end-to-end hackathon flow

## Milestone
M12: live end-to-end hackathon regression on a Devpost-style event.

## Goal
Drive the AgentWorker through the `hackathon-experiment-loop` skill
end-to-end for the picked hackathon, producing a complete submission
pack at `runs/<slug>/<run_id>/submission_pack/`. No external write.
The reviewer-gate path runs in T007, not here — T006 stops before
`devpost_submit`.

This is the M12 analog of M9-T002 / M10-T002 (baseline loop), but the
"metric" is a checklist completion percentage rather than a CV score.

## Tag

Routine.

## Read first

1. `PROJECT_STATE.md`, `AGENTS.md`, `CLAUDE.md`
2. `docs/milestones/README.md` §M12
3. `docs/milestones/m12/loop-prompts.md` Loop Prompt 6
4. M12-T000 closeout (picked slug)
5. M12-T002, M12-T003, M12-T004, M12-T005 closeouts
6. `src/worker/worker.py`, `src/worker/budget.py`, `src/worker/tools.py`
7. `tools/kca/run.py` — kg-run backend
8. `tools/kca/submission_checklist.py` (T004 output)
9. `.kca/skills/hackathon-experiment-loop/SKILL.md` (T004 output)
10. `docs/tasks/m9/M9-T002-baseline-loop.md` — CSV-baseline precedent
11. `docs/tasks/m10/M10-T002-baseline-notebook.md` — notebook-flow precedent
12. Memory: `feedback_use_stored_endpoints.md`, `reference_local_llm_endpoints.md`
    (model routing options)

## Scope

1. Confirm M12-T003 + T004 + T005 closeouts are PASS and the picked
   hackathon's `competitions` row exists with
   `competition_type='devpost'` (or the value ADR-0018 picked).
2. Launch the AgentWorker with skill = `hackathon-experiment-loop`,
   competition slug = picked slug, permission profile =
   `hackathon-runner`. Budget: 80 turns, $10 cost cap (mirror M9
   baseline), 60-min runtime cap.
3. The skill flow runs four phases:
   a. **Research** — agent reads the hackathon page (via T003's
      `kca devpost fetch`) and records rules, deadline, submission
      format. Writes a research_items row.
   b. **Idea** — agent proposes 1–3 ideas (recorded under
      `experiment` rows tied to the competition). Picks one to
      prototype. No human gate; this is local-only.
   c. **Prototype** — agent implements the minimum viable demo
      (small code surface, no real-world deploy). Calls
      `kca run init` and `kca run record-metric` per existing kg-run.
   d. **Submission pack** — agent assembles
      `runs/<slug>/<run_id>/submission_pack/` with:
        - `README.md` (problem statement + idea + how-to-run)
        - `demo-plan.md` (what the demo will show; no live demo)
        - `source/` (link or copy of the prototype code path —
          symlink or `git ls-files`-derived listing, NOT a full
          duplicate of the repo)
        - `submission-checklist.json` (output of the
          `submission_checklist` tool from T004)
4. Record one `experiment_runs` row with `metric_name =
   'checklist_completion'` and `metric_value` = the percentage of
   checklist items in `done` status.
5. Verify via `kca run list --json --competition <slug>` that the run
   shows the metric.
6. Stop **before** `devpost_submit`. The skill's stop-condition note
   (T004) requires this. The run output is the input to T007.

## Non-goals

- Do NOT call `tools/kca/devpost.py::cmd_submit` (it doesn't exist
  yet anyway — T007 adds it).
- Do NOT call `kaggle competitions submit` / `kaggle kernels push`.
- Do NOT upload any artifact to Devpost / Kaggle / external storage.
- Do NOT iterate beyond one idea / prototype cycle in T006. A second
  prototype belongs to a follow-up issue.
- Do NOT publish or push the prototype source to a public repo. The
  hackathon submission in T007 may require a public repo URL; if so,
  T007 handles that explicitly under human approval.
- Do NOT extend the schema. T002 already shipped what's needed.

## Acceptance criteria

- `runs/<slug>/<run_id>/submission_pack/README.md` exists and is
  non-empty.
- `runs/<slug>/<run_id>/submission_pack/demo-plan.md` exists.
- `runs/<slug>/<run_id>/submission_pack/source/` exists (file or
  symlink to source path).
- `runs/<slug>/<run_id>/submission_pack/submission-checklist.json`
  exists; parses as JSON; structure matches the tool's contract.
- `experiment_runs` row exists with `metric_name =
  'checklist_completion'` and `metric_value > 0` (it does not need to
  be 100; T007 may surface remaining gaps as part of the human
  approval review).
- `kca run list --json --competition <slug>` shows the run.
- `agent_job_events` records the skill phases; no
  `target_op="devpost_submit"` event yet (that fires in T007).
- The agent's budget tracker shows under-budget completion (no
  truncation due to the cost cap).

## Permissions

- File writes under `runs/<slug>/<run_id>/submission_pack/` and the
  prototype code path the agent chooses (must be under
  `src/` or a new directory in this worktree — the prototype is
  shippable code if T007 needs a public repo).
- DB writes for `research_items`, `experiments`, `experiment_runs`,
  `agent_job_events`.
- Network access for `kca devpost fetch` (READ_ONLY, T003 surface);
  any LLM-routed calls per the existing routing config (memory
  references).
- No `devpost_submit` / `demo_upload` / `team_invite` calls.

## Closeout format

```
M12-T006 closeout
  Picked slug: <slug>
  Run: runs/<slug>/<run_id>/
  Submission pack: README.md | demo-plan.md | source/ | submission-checklist.json (all present)
  Checklist completion %: <int>
  experiment_runs row: <uuid> (metric_name='checklist_completion', metric_value=<int>)
  Budget: <turns>/80 turns, $<cost>/$10 cap, <runtime>/60min
  Acceptance: PASS | FAIL — link to closing issue
  Risks / blockers: ...
  Next: M12-T007 (reviewer gate + ONE real Devpost submit)
```

## Related issues

- Closing issue for M12 — gets a comment with the run id, checklist
  completion %, and a link to the submission_pack directory in the
  worktree.

## Stop condition

Stop after 100 turns. If the agent's prototype phase hits a tooling
gap not anticipated by the skill (e.g. the hackathon requires a video
demo and the agent has no video tool), halt and ask — do NOT silently
skip the requirement (it would surface as a `blocked` checklist item
in T007 and could cause the approved submission to be rejected). If
the budget cap fires, halt and ask before raising it.
