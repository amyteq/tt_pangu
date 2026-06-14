# Milestone/task docs migration report

_Task: `temp/01.docs-housekeeping.md` (HK-001). Docs-only migration; no source
code, tests, migrations, workflows, or KCA core touched. Executed in worktree
`worktree-docs-housekeeping-hk001`._

> **Update (post-merge follow-ups).** The original migration (PR #96) kept two
> compatibility stubs and could not edit `.claude/**` (read-only in that worktree):
>
> - PR #97 — updated the milestone agent/skill path references under
>   `.claude/agents/**` and `.claude/skills/**` (follow-up #1 below).
> - This PR — **retired both compatibility stubs** (`docs/milestones.md`,
>   `docs/handoff-prompt.md`) and repointed every remaining active reference to the
>   new paths (`docs/milestones/README.md`, `docs/milestones/_templates/handoff-prompt.md`),
>   including the previously-blocked `.github/workflows/claude-routine.yml` and
>   `.github/pull_request_template.md`. Old-path references now remain only in
>   historical `logs/**` / `worklogs/**` session dumps (point-in-time records).
>
> Sections below describe the original PR #96 state and are retained as the
> historical record; where they say a stub "remains", it has since been retired.

## Summary

Consolidated all milestone-related documentation under `docs/milestones/` and
reorganized `docs/tasks/` by milestone.

- **213 files moved** with `git mv` (history preserved — git reports them as renames).
- `docs/milestones.md` → `docs/milestones/README.md` (canonical index); a <10-line
  compatibility **stub** remains at `docs/milestones.md` so links in files this task
  may not edit (`.github/workflows/claude-routine.yml`, `.github/pull_request_template.md`)
  keep resolving.
- `docs/handoff-prompt.md` → `docs/milestones/_templates/handoff-prompt.md`; a small
  stub remains at the old path (the read-only `.claude/agents/milestone-closeout.md`
  references it and could not be edited — see "Ambiguous items").
- Per-milestone `final-review.md`, `handoff.md`, `loop-prompts.md`, `references.md`,
  `notes.md` now live under `docs/milestones/m{N}/`.
- Task specs grouped into `docs/tasks/m{N}/`; folder names lowercase the milestone
  token and map `.`→`_` (`M8.5`→`m8_5/`, `M9.3`→`m9_3/`); filenames keep their casing.
- Two empty directories removed after moves: `docs/prompts/`, `docs/handoffs/`.
- New files: `docs/milestones.md` (stub), `docs/handoff-prompt.md` (stub),
  `docs/milestones/m1/README.md`, `docs/tasks/_templates/task.md`, this report.
- Updated `docs/tasks/README.md` to describe the new organization.

## Files moved

### Milestone index + handoff template
```text
docs/milestones.md -> docs/milestones/README.md
docs/handoff-prompt.md -> docs/milestones/_templates/handoff-prompt.md
```

### Per-milestone final-review files
```text
docs/m10-final-review.md -> docs/milestones/m10/final-review.md
docs/m11-final-review.md -> docs/milestones/m11/final-review.md
docs/m12-final-review.md -> docs/milestones/m12/final-review.md
docs/m13-final-review.md -> docs/milestones/m13/final-review.md
docs/m14-final-review.md -> docs/milestones/m14/final-review.md
docs/m2-final-review.md -> docs/milestones/m2/final-review.md
docs/m4-final-review.md -> docs/milestones/m4/final-review.md
docs/m5-final-review.md -> docs/milestones/m5/final-review.md
docs/m6-final-review.md -> docs/milestones/m6/final-review.md
docs/m7-final-review.md -> docs/milestones/m7/final-review.md
docs/m8_5-final-review.md -> docs/milestones/m8_5/final-review.md
docs/m8-final-review.md -> docs/milestones/m8/final-review.md
docs/m9_2-final-review.md -> docs/milestones/m9_2/final-review.md
docs/m9_3-final-review.md -> docs/milestones/m9_3/final-review.md
docs/m9_4-final-review.md -> docs/milestones/m9_4/final-review.md
docs/m9-final-review.md -> docs/milestones/m9/final-review.md
docs/tasks/M12-T009-final-review.md -> docs/tasks/m12/M12-T009-final-review.md
```

### Per-milestone loop-prompts files
```text
docs/m10-loop-prompts.md -> docs/milestones/m10/loop-prompts.md
docs/m11-loop-prompts.md -> docs/milestones/m11/loop-prompts.md
docs/m12-loop-prompts.md -> docs/milestones/m12/loop-prompts.md
docs/m13-loop-prompts.md -> docs/milestones/m13/loop-prompts.md
docs/m14-loop-prompts.md -> docs/milestones/m14/loop-prompts.md
docs/m1-loop-prompts.md -> docs/milestones/m1/loop-prompts.md
docs/m3-loop-prompts.md -> docs/milestones/m3/loop-prompts.md
docs/m4-loop-prompts.md -> docs/milestones/m4/loop-prompts.md
docs/m5-loop-prompts.md -> docs/milestones/m5/loop-prompts.md
docs/m6-loop-prompts.md -> docs/milestones/m6/loop-prompts.md
docs/m7-loop-prompts.md -> docs/milestones/m7/loop-prompts.md
docs/m8_5-loop-prompts.md -> docs/milestones/m8_5/loop-prompts.md
docs/m8-loop-prompts.md -> docs/milestones/m8/loop-prompts.md
docs/m9_1-loop-prompts.md -> docs/milestones/m9_1/loop-prompts.md
docs/m9_2-loop-prompts.md -> docs/milestones/m9_2/loop-prompts.md
docs/m9_3-loop-prompts.md -> docs/milestones/m9_3/loop-prompts.md
docs/m9_4-loop-prompts.md -> docs/milestones/m9_4/loop-prompts.md
docs/m9-loop-prompts.md -> docs/milestones/m9/loop-prompts.md
```

### Per-milestone references
```text
docs/m8_5-references.md -> docs/milestones/m8_5/references.md
```

### Per-milestone handoff files
```text
docs/handoffs/m10-handoff.md -> docs/milestones/m10/handoff.md
docs/handoffs/m11-handoff.md -> docs/milestones/m11/handoff.md
docs/handoffs/m12-handoff.md -> docs/milestones/m12/handoff.md
docs/handoffs/m13-handoff.md -> docs/milestones/m13/handoff.md
docs/handoffs/m14-handoff.md -> docs/milestones/m14/handoff.md
docs/handoffs/m1-handoff.md -> docs/milestones/m1/handoff.md
docs/handoffs/m2-handoff.md -> docs/milestones/m2/handoff.md
docs/handoffs/m3-handoff.md -> docs/milestones/m3/handoff.md
docs/handoffs/m4-handoff.md -> docs/milestones/m4/handoff.md
docs/handoffs/m5-handoff.md -> docs/milestones/m5/handoff.md
docs/handoffs/m6-handoff.md -> docs/milestones/m6/handoff.md
docs/handoffs/m7-handoff.md -> docs/milestones/m7/handoff.md
docs/handoffs/m8_5-handoff.md -> docs/milestones/m8_5/handoff.md
docs/handoffs/m8-handoff.md -> docs/milestones/m8/handoff.md
docs/handoffs/m9_2-handoff.md -> docs/milestones/m9_2/handoff.md
docs/handoffs/m9_3-handoff.md -> docs/milestones/m9_3/handoff.md
docs/handoffs/m9-handoff.md -> docs/milestones/m9/handoff.md
```

### M1 loop-prompts variant → notes (see decision below)
```text
docs/prompts/M1-loop-prompts.md -> docs/milestones/m1/notes.md
```

### Task specs (docs/tasks/M*.md → docs/tasks/m{N}/M*.md)
```text
docs/tasks/M0-T001-project-baseline.md -> docs/tasks/m0/M0-T001-project-baseline.md
docs/tasks/M10-T000-kaggle-credentials.md -> docs/tasks/m10/M10-T000-kaggle-credentials.md
docs/tasks/M10-T001-data-discovery-manifest.md -> docs/tasks/m10/M10-T001-data-discovery-manifest.md
docs/tasks/M10-T002-baseline-notebook.md -> docs/tasks/m10/M10-T002-baseline-notebook.md
docs/tasks/M10-T003-kernel-push-reviewer-gate.md -> docs/tasks/m10/M10-T003-kernel-push-reviewer-gate.md
docs/tasks/M10-T004-real-kernel-push.md -> docs/tasks/m10/M10-T004-real-kernel-push.md
docs/tasks/M10-T005-second-experiment.md -> docs/tasks/m10/M10-T005-second-experiment.md
docs/tasks/M10-T006-regression-assertions.md -> docs/tasks/m10/M10-T006-regression-assertions.md
docs/tasks/M10-T007-e2e-dryrun-test.md -> docs/tasks/m10/M10-T007-e2e-dryrun-test.md
docs/tasks/M10-T008-m10-exit-criteria.md -> docs/tasks/m10/M10-T008-m10-exit-criteria.md
docs/tasks/M11-T000-discovery-debate-gate.md -> docs/tasks/m11/M11-T000-discovery-debate-gate.md
docs/tasks/M11-T001-ctf-schema-db.md -> docs/tasks/m11/M11-T001-ctf-schema-db.md
docs/tasks/M11-T002-approval-gates.md -> docs/tasks/m11/M11-T002-approval-gates.md
docs/tasks/M11-T003-kca-ctf-cli.md -> docs/tasks/m11/M11-T003-kca-ctf-cli.md
docs/tasks/M11-T004-frozen-challenges.md -> docs/tasks/m11/M11-T004-frozen-challenges.md
docs/tasks/M11-T005-local-solve-loop.md -> docs/tasks/m11/M11-T005-local-solve-loop.md
docs/tasks/M11-T006-reviewer-gate.md -> docs/tasks/m11/M11-T006-reviewer-gate.md
docs/tasks/M11-T007-live-flag-submission.md -> docs/tasks/m11/M11-T007-live-flag-submission.md
docs/tasks/M11-T008-e2e-dryrun-test.md -> docs/tasks/m11/M11-T008-e2e-dryrun-test.md
docs/tasks/M11-T009-m11-exit-criteria.md -> docs/tasks/m11/M11-T009-m11-exit-criteria.md
docs/tasks/M12-T000-survey-and-pick-target.md -> docs/tasks/m12/M12-T000-survey-and-pick-target.md
docs/tasks/M12-T001-discovery-debate-gate.md -> docs/tasks/m12/M12-T001-discovery-debate-gate.md
docs/tasks/M12-T002-schema-and-policy.md -> docs/tasks/m12/M12-T002-schema-and-policy.md
docs/tasks/M12-T003-devpost-adapter.md -> docs/tasks/m12/M12-T003-devpost-adapter.md
docs/tasks/M12-T004-hackathon-skill.md -> docs/tasks/m12/M12-T004-hackathon-skill.md
docs/tasks/M12-T005-ui-pages.md -> docs/tasks/m12/M12-T005-ui-pages.md
docs/tasks/M12-T006-end-to-end-local.md -> docs/tasks/m12/M12-T006-end-to-end-local.md
docs/tasks/M12-T007-real-submit.md -> docs/tasks/m12/M12-T007-real-submit.md
docs/tasks/M12-T008-regression-tests.md -> docs/tasks/m12/M12-T008-regression-tests.md
docs/tasks/M12-T009-final-review.md -> docs/tasks/m12/M12-T009-final-review.md
docs/tasks/M13-T000-eval-architecture.md -> docs/tasks/m13/M13-T000-eval-architecture.md
docs/tasks/M13-T001-migration-and-cli.md -> docs/tasks/m13/M13-T001-migration-and-cli.md
docs/tasks/M13-T002-tool-smoke-suite.md -> docs/tasks/m13/M13-T002-tool-smoke-suite.md
docs/tasks/M13-T003-kaggle-replay-suite.md -> docs/tasks/m13/M13-T003-kaggle-replay-suite.md
docs/tasks/M13-T004-notebook-kernel-dryrun-suite.md -> docs/tasks/m13/M13-T004-notebook-kernel-dryrun-suite.md
docs/tasks/M13-T005-reasoning-benchmark.md -> docs/tasks/m13/M13-T005-reasoning-benchmark.md
docs/tasks/M13-T006-model-route-comparison.md -> docs/tasks/m13/M13-T006-model-route-comparison.md
docs/tasks/M13-T007-report-aggregator.md -> docs/tasks/m13/M13-T007-report-aggregator.md
docs/tasks/M13-T008-ci-and-tests.md -> docs/tasks/m13/M13-T008-ci-and-tests.md
docs/tasks/M13-T009-m13-exit-criteria.md -> docs/tasks/m13/M13-T009-m13-exit-criteria.md
docs/tasks/M14-T000-goal-loop-architecture.md -> docs/tasks/m14/M14-T000-goal-loop-architecture.md
docs/tasks/M14-T001-migration-and-helpers.md -> docs/tasks/m14/M14-T001-migration-and-helpers.md
docs/tasks/M14-T002-kca-goal-cli.md -> docs/tasks/m14/M14-T002-kca-goal-cli.md
docs/tasks/M14-T003-kca-explore.md -> docs/tasks/m14/M14-T003-kca-explore.md
docs/tasks/M14-T004-multi-push-concurrency.md -> docs/tasks/m14/M14-T004-multi-push-concurrency.md
docs/tasks/M14-T005-smart-polling.md -> docs/tasks/m14/M14-T005-smart-polling.md
docs/tasks/M14-T006-idea-sourcing.md -> docs/tasks/m14/M14-T006-idea-sourcing.md
docs/tasks/M14-T007-stuck-escalation.md -> docs/tasks/m14/M14-T007-stuck-escalation.md
docs/tasks/M14-T008-live-e2e.md -> docs/tasks/m14/M14-T008-live-e2e.md
docs/tasks/M14-T009-m14-exit-criteria.md -> docs/tasks/m14/M14-T009-m14-exit-criteria.md
docs/tasks/M1-T000-legacy-tool-inventory.md -> docs/tasks/m1/M1-T000-legacy-tool-inventory.md
docs/tasks/M1-T001-kca-cli-skeleton.md -> docs/tasks/m1/M1-T001-kca-cli-skeleton.md
docs/tasks/M1-T002-notebook-conversion-wrappers.md -> docs/tasks/m1/M1-T002-notebook-conversion-wrappers.md
docs/tasks/M1-T003-run-artifact-layout-and-smoke-tests.md -> docs/tasks/m1/M1-T003-run-artifact-layout-and-smoke-tests.md
docs/tasks/M1-T004-kaggle-remote-operation-approval-hooks.md -> docs/tasks/m1/M1-T004-kaggle-remote-operation-approval-hooks.md
docs/tasks/M1-T005-m1-final-integration-review.md -> docs/tasks/m1/M1-T005-m1-final-integration-review.md
docs/tasks/M2-T001-schema-reconciliation.md -> docs/tasks/m2/M2-T001-schema-reconciliation.md
docs/tasks/M2-T002-local-supabase-dev.md -> docs/tasks/m2/M2-T002-local-supabase-dev.md
docs/tasks/M2-T003-python-db-layer.md -> docs/tasks/m2/M2-T003-python-db-layer.md
docs/tasks/M2-T004-kca-run-db-writers.md -> docs/tasks/m2/M2-T004-kca-run-db-writers.md
docs/tasks/M2-T005-approval-event-recording.md -> docs/tasks/m2/M2-T005-approval-event-recording.md
docs/tasks/M2-T006-artifact-storage-adr.md -> docs/tasks/m2/M2-T006-artifact-storage-adr.md
docs/tasks/M2-T007-db-smoke-tests.md -> docs/tasks/m2/M2-T007-db-smoke-tests.md
docs/tasks/M2-T008-final-integration-review.md -> docs/tasks/m2/M2-T008-final-integration-review.md
docs/tasks/M3-T000-hotfix-kaggle-rename.md -> docs/tasks/m3/M3-T000-hotfix-kaggle-rename.md
docs/tasks/M3-T001-migration-0003-job-events.md -> docs/tasks/m3/M3-T001-migration-0003-job-events.md
docs/tasks/M3-T002-workspace-management.md -> docs/tasks/m3/M3-T002-workspace-management.md
docs/tasks/M3-T003-worker-scaffold.md -> docs/tasks/m3/M3-T003-worker-scaffold.md
docs/tasks/M3-T004-agent-worker-core.md -> docs/tasks/m3/M3-T004-agent-worker-core.md
docs/tasks/M3-T005-approval-gate-worker.md -> docs/tasks/m3/M3-T005-approval-gate-worker.md
docs/tasks/M3-T006-local-job-runner.md -> docs/tasks/m3/M3-T006-local-job-runner.md
docs/tasks/M3-T007-worker-smoke-tests.md -> docs/tasks/m3/M3-T007-worker-smoke-tests.md
docs/tasks/M3-T008-m3-exit-criteria.md -> docs/tasks/m3/M3-T008-m3-exit-criteria.md
docs/tasks/M4-T000-pyproject-kca-entry-point.md -> docs/tasks/m4/M4-T000-pyproject-kca-entry-point.md
docs/tasks/M4-T001-migration-0004-competition-repo.md -> docs/tasks/m4/M4-T001-migration-0004-competition-repo.md
docs/tasks/M4-T002-db-layer-competition-experiment.md -> docs/tasks/m4/M4-T002-db-layer-competition-experiment.md
docs/tasks/M4-T003-kca-competition-commands.md -> docs/tasks/m4/M4-T003-kca-competition-commands.md
docs/tasks/M4-T004-workspace-repo-flag-and-kca-run.md -> docs/tasks/m4/M4-T004-workspace-repo-flag-and-kca-run.md
docs/tasks/M4-T005-run-job-competition-lifecycle.md -> docs/tasks/m4/M4-T005-run-job-competition-lifecycle.md
docs/tasks/M4-T006-approval-gate-policy-resolution.md -> docs/tasks/m4/M4-T006-approval-gate-policy-resolution.md
docs/tasks/M4-T007-real-kaggle-cli-wiring.md -> docs/tasks/m4/M4-T007-real-kaggle-cli-wiring.md
docs/tasks/M4-T008-tc1-titanic-end-to-end.md -> docs/tasks/m4/M4-T008-tc1-titanic-end-to-end.md
docs/tasks/M4-T009-m4-smoke-tests.md -> docs/tasks/m4/M4-T009-m4-smoke-tests.md
docs/tasks/M4-T010-m4-exit-criteria.md -> docs/tasks/m4/M4-T010-m4-exit-criteria.md
docs/tasks/M5-T000-migration-0005-research-citations.md -> docs/tasks/m5/M5-T000-migration-0005-research-citations.md
docs/tasks/M5-T001-db-layer-research.md -> docs/tasks/m5/M5-T001-db-layer-research.md
docs/tasks/M5-T002-browser-fetch-tool.md -> docs/tasks/m5/M5-T002-browser-fetch-tool.md
docs/tasks/M5-T003-kca-research-cli.md -> docs/tasks/m5/M5-T003-kca-research-cli.md
docs/tasks/M5-T004-kaggle-download-checksum.md -> docs/tasks/m5/M5-T004-kaggle-download-checksum.md
docs/tasks/M5-T005-resume-paused-jobs.md -> docs/tasks/m5/M5-T005-resume-paused-jobs.md
docs/tasks/M5-T006-model-routing.md -> docs/tasks/m5/M5-T006-model-routing.md
docs/tasks/M5-T007-ci-github-actions.md -> docs/tasks/m5/M5-T007-ci-github-actions.md
docs/tasks/M5-T008-tc2-house-prices.md -> docs/tasks/m5/M5-T008-tc2-house-prices.md
docs/tasks/M5-T009-m5-smoke-tests.md -> docs/tasks/m5/M5-T009-m5-smoke-tests.md
docs/tasks/M5-T010-m5-exit-criteria.md -> docs/tasks/m5/M5-T010-m5-exit-criteria.md
docs/tasks/M6-T000-migration-0006-reviews-spans.md -> docs/tasks/m6/M6-T000-migration-0006-reviews-spans.md
docs/tasks/M6-T001-db-layer-reviews-telemetry.md -> docs/tasks/m6/M6-T001-db-layer-reviews-telemetry.md
docs/tasks/M6-T002-local-model-layer.md -> docs/tasks/m6/M6-T002-local-model-layer.md
docs/tasks/M6-T003-env-example-update.md -> docs/tasks/m6/M6-T003-env-example-update.md
docs/tasks/M6-T004-reviewer-worker.md -> docs/tasks/m6/M6-T004-reviewer-worker.md
docs/tasks/M6-T005-otel-instrumentation.md -> docs/tasks/m6/M6-T005-otel-instrumentation.md
docs/tasks/M6-T006-local-model-job-types.md -> docs/tasks/m6/M6-T006-local-model-job-types.md
docs/tasks/M6-T007-kca-review-cli.md -> docs/tasks/m6/M6-T007-kca-review-cli.md
docs/tasks/M6-T008-tc3-spaceship-titanic.md -> docs/tasks/m6/M6-T008-tc3-spaceship-titanic.md
docs/tasks/M6-T009-m6-smoke-tests.md -> docs/tasks/m6/M6-T009-m6-smoke-tests.md
docs/tasks/M6-T010-m6-exit-criteria.md -> docs/tasks/m6/M6-T010-m6-exit-criteria.md
docs/tasks/M7-T000-ci-workflows-repair.md -> docs/tasks/m7/M7-T000-ci-workflows-repair.md
docs/tasks/M7-T001-skill-loader.md -> docs/tasks/m7/M7-T001-skill-loader.md
docs/tasks/M7-T002-command-registry.md -> docs/tasks/m7/M7-T002-command-registry.md
docs/tasks/M7-T003-tool-registry.md -> docs/tasks/m7/M7-T003-tool-registry.md
docs/tasks/M7-T004-permission-policy.md -> docs/tasks/m7/M7-T004-permission-policy.md
docs/tasks/M7-T005-kca-skill-cli.md -> docs/tasks/m7/M7-T005-kca-skill-cli.md
docs/tasks/M7-T006-audit-logging.md -> docs/tasks/m7/M7-T006-audit-logging.md
docs/tasks/M7-T007-seed-skills.md -> docs/tasks/m7/M7-T007-seed-skills.md
docs/tasks/M7-T008-m7-smoke-tests.md -> docs/tasks/m7/M7-T008-m7-smoke-tests.md
docs/tasks/M7-T009-architecture-doc.md -> docs/tasks/m7/M7-T009-architecture-doc.md
docs/tasks/M7-T010-m7-exit-criteria.md -> docs/tasks/m7/M7-T010-m7-exit-criteria.md
docs/tasks/M8.5-T001-ci-repair.md -> docs/tasks/m8_5/M8.5-T001-ci-repair.md
docs/tasks/M8.5-T002-engineering-practice-github-interface.md -> docs/tasks/m8_5/M8.5-T002-engineering-practice-github-interface.md
docs/tasks/M8.5-T003-m9-planning-only.md -> docs/tasks/m8_5/M8.5-T003-m9-planning-only.md
docs/tasks/M8-T000-ui-stack-adr-scaffold.md -> docs/tasks/m8/M8-T000-ui-stack-adr-scaffold.md
docs/tasks/M8-T001-agent-tool-audit-migration.md -> docs/tasks/m8/M8-T001-agent-tool-audit-migration.md
docs/tasks/M8-T002-skill-schema-gate.md -> docs/tasks/m8/M8-T002-skill-schema-gate.md
docs/tasks/M8-T003-skill-worker-wiring.md -> docs/tasks/m8/M8-T003-skill-worker-wiring.md
docs/tasks/M8-T004-ui-app-shell.md -> docs/tasks/m8/M8-T004-ui-app-shell.md
docs/tasks/M8-T005-ui-dashboard.md -> docs/tasks/m8/M8-T005-ui-dashboard.md
docs/tasks/M8-T006-ui-run-timeline.md -> docs/tasks/m8/M8-T006-ui-run-timeline.md
docs/tasks/M8-T007-ui-experiments-runs.md -> docs/tasks/m8/M8-T007-ui-experiments-runs.md
docs/tasks/M8-T008-ui-research.md -> docs/tasks/m8/M8-T008-ui-research.md
docs/tasks/M8-T009-ui-approval-inbox.md -> docs/tasks/m8/M8-T009-ui-approval-inbox.md
docs/tasks/M8-T010-ui-artifact-browser.md -> docs/tasks/m8/M8-T010-ui-artifact-browser.md
docs/tasks/M8-T011-ci-ui-build.md -> docs/tasks/m8/M8-T011-ci-ui-build.md
docs/tasks/M8-T012-smoke-tests-playwright.md -> docs/tasks/m8/M8-T012-smoke-tests-playwright.md
docs/tasks/M8-T013-m8-architecture-doc.md -> docs/tasks/m8/M8-T013-m8-architecture-doc.md
docs/tasks/M8-T014-m8-exit-criteria.md -> docs/tasks/m8/M8-T014-m8-exit-criteria.md
docs/tasks/M9_2-T000-save-log-scaffold-and-impl.md -> docs/tasks/m9_2/M9_2-T000-save-log-scaffold-and-impl.md
docs/tasks/M9_2-T001-save-log-smoke-and-docs.md -> docs/tasks/m9_2/M9_2-T001-save-log-smoke-and-docs.md
docs/tasks/M9_2-T002-m9_2-exit-criteria.md -> docs/tasks/m9_2/M9_2-T002-m9_2-exit-criteria.md
docs/tasks/M9.3-T001-design-archaeology-skill.md -> docs/tasks/m9_3/M9.3-T001-design-archaeology-skill.md
docs/tasks/M9.3-T002-memory-promotion-skill.md -> docs/tasks/m9_3/M9.3-T002-memory-promotion-skill.md
docs/tasks/M9.3-T003-dogfood-kkr-and-recent-pr.md -> docs/tasks/m9_3/M9.3-T003-dogfood-kkr-and-recent-pr.md
docs/tasks/M9_4-T001-requirements-skeptic.md -> docs/tasks/m9_4/M9_4-T001-requirements-skeptic.md
docs/tasks/M9_4-T002-legacy-archaeologist.md -> docs/tasks/m9_4/M9_4-T002-legacy-archaeologist.md
docs/tasks/M9_4-T003-design-red-team.md -> docs/tasks/m9_4/M9_4-T003-design-red-team.md
docs/tasks/M9_4-T004-discovery-debate-gate.md -> docs/tasks/m9_4/M9_4-T004-discovery-debate-gate.md
docs/tasks/M9_4-T005-kkr-replay-and-smoke.md -> docs/tasks/m9_4/M9_4-T005-kkr-replay-and-smoke.md
docs/tasks/M9_4-T006-exit-criteria.md -> docs/tasks/m9_4/M9_4-T006-exit-criteria.md
docs/tasks/M9-T000-kaggle-credentials.md -> docs/tasks/m9/M9-T000-kaggle-credentials.md
docs/tasks/M9-T001-data-download.md -> docs/tasks/m9/M9-T001-data-download.md
docs/tasks/M9-T002-baseline-loop.md -> docs/tasks/m9/M9-T002-baseline-loop.md
docs/tasks/M9-T003-reviewer-approval-gate.md -> docs/tasks/m9/M9-T003-reviewer-approval-gate.md
docs/tasks/M9-T004-real-submission.md -> docs/tasks/m9/M9-T004-real-submission.md
docs/tasks/M9-T005-second-experiment.md -> docs/tasks/m9/M9-T005-second-experiment.md
docs/tasks/M9-T006-regression-assertions.md -> docs/tasks/m9/M9-T006-regression-assertions.md
docs/tasks/M9-T007-e2e-dryrun-test.md -> docs/tasks/m9/M9-T007-e2e-dryrun-test.md
docs/tasks/M9-T008-m9-exit-criteria.md -> docs/tasks/m9/M9-T008-m9-exit-criteria.md
```

## Files merged

None. No file contents were merged. The two M1 loop-prompt documents were kept
as **separate** files (see "Ambiguous items").

## Files deleted

No documentation files were deleted. Two **empty directories** were removed
after their contents moved out:

- `docs/prompts/` — emptied once `M1-loop-prompts.md` moved to `docs/milestones/m1/notes.md`.
- `docs/handoffs/` — emptied once all `m{N}-handoff.md` files moved to `docs/milestones/m{N}/handoff.md`.

## Files created

- `docs/milestones.md` — <10-line compatibility stub → `docs/milestones/README.md`.
- `docs/handoff-prompt.md` — <10-line compatibility stub → `docs/milestones/_templates/handoff-prompt.md`.
- `docs/milestones/m1/README.md` — explains the two M1 prompt files.
- `docs/tasks/_templates/task.md` — blank task-spec template.
- `docs/milestones/migration-report.md` — this report.

## Files left in place

- `docs/milestone-loop-protocol.md` — cross-cutting process doc (not a per-milestone
  file) referenced by ~18 loop-prompt files via `Follow: docs/milestone-loop-protocol.md`.
  Left at its path; only its internal path-pattern references were updated
  (`docs/m*-loop-prompts.md` → `docs/milestones/m*/loop-prompts.md`;
  `docs/m{N}-final-review.md` → `docs/milestones/m{N}/final-review.md`).
- `docs/adr/`, `docs/architecture/`, `docs/meeting-notes/`, `docs/evidence/`,
  `docs/proposals/`, `docs/issues/`, `docs/logs/`, `docs/testing/`, `docs/tooling/`,
  `docs/archaeology/`, `docs/requirements.md`, `docs/design-decisions.md`,
  `docs/architecture.md`, `docs/testing.md` — not milestone/handoff/prompt/task files.

## Reference updates

Path references were rewritten with deterministic, content-preserving
substitutions (path strings only — no prose rewritten into summaries).

**Concrete moved-file paths — updated everywhere in the allowed set**
(`README.md`, `PROJECT_STATE.md`, `CLAUDE.md`, `AGENTS.md`, all writable `docs/**`):

- `docs/m{N}-final-review.md` → `docs/milestones/m{N}/final-review.md`
- `docs/m{N}-loop-prompts.md` → `docs/milestones/m{N}/loop-prompts.md`
- `docs/m8_5-references.md` → `docs/milestones/m8_5/references.md`
- `docs/handoffs/m{N}-handoff.md` → `docs/milestones/m{N}/handoff.md`
- `docs/handoff-prompt.md` → `docs/milestones/_templates/handoff-prompt.md`
- `docs/tasks/M{N}-T...md` → `docs/tasks/m{N}/M{N}-T...md`

**Removed-directory references — updated in writable allowed files** (the dir no
longer exists, so these were dead): bare `docs/handoffs/`, `docs/handoffs/**`, and
`docs/handoffs/m{N}-handoff.md` placeholder forms → `docs/milestones/*/handoff.md`
/ `docs/milestones/m{N}/handoff.md`.

**`docs/milestones.md` → `docs/milestones/README.md`** — updated in the canonical /
operational set only: `README.md`, `PROJECT_STATE.md`, `docs/engineering-practice.md`,
`docs/tasks/README.md`, and `docs/milestones/README.md` itself. Historical docs that
still say `docs/milestones.md` resolve via the stub (intentional — see below).

**Protocol / placeholder wording** updated by hand in:

- `docs/milestones/README.md` — final-review protocol step 4 now says per-milestone
  handoffs live at `docs/milestones/m{x}/handoff.md` and the generic template at
  `docs/milestones/_templates/handoff-prompt.md`.
- `docs/milestone-loop-protocol.md` — lines 6 / 66 / 105 path patterns.
- `docs/tasks/README.md` — rewritten folder-organization, naming, how-to-execute,
  category, and uncategorized sections; table file column re-pathed to `m{N}/...`.

## Ambiguous items

1. **`.claude/agents/**` and `.claude/skills/**` are mounted READ-ONLY in the
   execution worktree** (harness protection, same as `.claude/settings*.json` and
   `.claude/hooks/**`). Although the task lists them as allowed, no write succeeded
   (`touch` and `perl -i` both returned "Read-only file system"). Their references
   could therefore **not** be edited in this PR. Most are to `docs/milestones.md`
   (still valid via stub). The ones that need a follow-up edit when `.claude` is
   writable:
   - `.claude/agents/milestone-closeout.md` — writes `docs/m{N}-final-review.md`
     and `docs/handoffs/m{N}-handoff.md`; uses `docs/handoff-prompt.md` template
     → should become `docs/milestones/m{N}/final-review.md`,
     `docs/milestones/m{N}/handoff.md`, `docs/milestones/_templates/handoff-prompt.md`.
   - `.claude/agents/milestone-loop-runner.md`, `.claude/agents/milestone-reviewer.md`,
     `.claude/skills/milestone-final-review/SKILL.md`,
     `.claude/skills/worktree-milestone-pr/SKILL.md`,
     `.claude/skills/memory-promotion/SKILL.md`,
     `.claude/skills/milestone-review/SKILL.md` — `docs/m{N}-final-review.md` /
     `docs/m{N}-loop-prompts.md` / `docs/handoffs/...` placeholders.
   The two compatibility stubs (`docs/milestones.md`, `docs/handoff-prompt.md`) keep
   these read-only references resolving in the meantime.

2. **Two M1 loop-prompt files.** `docs/m1-loop-prompts.md` (canonical) →
   `docs/milestones/m1/loop-prompts.md`; `docs/prompts/M1-loop-prompts.md` (an older
   Arch-Linux-runner-oriented variant) → `docs/milestones/m1/notes.md`. They are
   **not** duplicates — the second covers runner setup and per-task `claude --bg`
   invocations not reproduced in the canonical file — so it was **moved (kept), not
   deleted**. Recorded in `docs/milestones/m1/README.md`.

3. **`docs/milestone-loop-protocol.md`** — judged a cross-cutting process doc, not a
   per-milestone file; left in place (see "Files left in place").

## Stale references intentionally preserved

- **`docs/milestones.md` references in historical docs** (≈50 in `docs/milestones/**`
  historical milestone docs, ≈56 in `docs/tasks/**` historical task specs, plus a
  handful in `docs/meeting-notes/`, `docs/adr/`, `docs/architecture/`,
  `docs/evidence/`, `docs/proposals/`, `docs/issues/`). These resolve via the
  `docs/milestones.md` stub and are point-in-time records (e.g. "Read these files
  first" lists and "update docs/milestones.md" closeout steps in completed task
  specs). Not rewritten, per "preserve useful history."
- **`docs/milestones/m9_3/final-review.md:33`** — a validation-matrix cell recording
  the canonical-memory file set as referenced at M9.3 close (`... docs/handoffs ...`,
  no trailing slash). Historical record; preserved.
- **Out-of-scope files** (`.github/**`, `tests/**`, `scripts/**`, `INSTALL.md`,
  `logs/**`, `worklogs/**`): all references found there are comments, docstrings,
  illustrative examples, or historical logs — none are load-bearing path reads, so
  moving the docs breaks no code/CI. Not in this task's allowed paths; left untouched.
  The single load-bearing one (`.github/workflows/claude-routine.yml`: "Read CLAUDE.md
  and docs/milestones.md") is kept valid by the stub.

## Pre-existing dangling references (NOT introduced by this migration)

These prose references pointed at non-existent files **at HEAD already**; the
migration faithfully updated only their path prefix.

**Fixed** (mistyped task-spec filenames, corrected to the real files in a
follow-up — references live in `docs/milestones/m13/loop-prompts.md`,
`docs/tasks/m13/M13-T003-kaggle-replay-suite.md`,
`docs/tasks/m13/M13-T005-reasoning-benchmark.md`):

- `docs/tasks/m4/M4-T008-titanic-end-to-end.md` → `docs/tasks/m4/M4-T008-tc1-titanic-end-to-end.md` ✅
- `docs/tasks/m5/M5-T008-house-prices.md` → `docs/tasks/m5/M5-T008-tc2-house-prices.md` ✅
- `docs/tasks/m5/M5-T002-research-fetch.md` → `docs/tasks/m5/M5-T002-browser-fetch-tool.md` ✅

**Left as-is** (not mistyped names — references to docs that were never created,
or illustrative examples; no real target exists to point at):

- `docs/milestones/m3/final-review.md` — M3 never had a final-review doc.
- `docs/milestones/m9_4/handoff.md` — M9.4 never had a handoff doc.
- Illustrative / hypothetical paths in `docs/meeting-notes/**` (`docs/tasks/M001.md`,
  `docs/tasks/M7-T001.md`, `docs/tasks/M8.6-...md`, `docs/milestones/m9_6/handoff.md`,
  `docs/milestones/mx/handoff.md`) and `docs/tasks/templates/agent-skill-import-*.md`
  — examples/placeholders, never real files.

## Validation commands run

```bash
git status --short          # 211 renames (R/RM), 4 new files, 0 unexpected deletes
git diff --stat             # 244 files changed, ~1229 insertions / ~1169 deletions
git diff --name-status      # renames + content edits only under allowed paths
find docs -maxdepth 5 -type f | sort   # new structure verified
```

- Stale-reference grep (task validation): remaining `docs/milestones.md` hits all
  resolve via the stub; `docs/handoffs/` fully cleared from writable allowed files.
- Link-integrity check on 188 distinct concrete `docs/(milestones|tasks)/*.md`
  references: all resolve **except** the pre-existing dangling set above and this
  report (which now exists).
- No Markdown lint command is configured in this repo for docs-only changes; none run.
- Confirmed unchanged: `.claude/settings*.json`, `.claude/hooks/**` (and all of
  `.claude/**`, which is read-only in the worktree); no `src/`, `tests/`,
  `supabase/`, `.github/`, `tools/`, `ui/`, `services/` files modified.

## Follow-up recommendations

1. When `.claude/**` is writable, update the milestone agents/skills path references
   listed in "Ambiguous items #1", then the two compatibility stubs can be retired.
2. Fix the pre-existing dangling task-name references (M4-T008, M5-T008, M5-T002).
3. Optionally decide whether the `docs/milestones.md` references in historical task
   specs/milestone docs should be bulk-rewritten to `docs/milestones/README.md`
   (currently resolved via stub) or left as historical record.
4. Optionally backfill per-milestone `README.md` files for milestones other than M1
   if a navigation index per folder is wanted.
