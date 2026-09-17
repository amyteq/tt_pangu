---
name: prepare-submission
description: Validate a run's submission.csv, check format and metric, and create a submission decision record ready for human approval.
version: "1.0"
argument-hint: "[run-dir]"
arguments:
  - run_dir
allowed-tools:
  - read_file
  - bash
  - create_artifact
  - litellm_call
approval-policy: default
tags:
  - kaggle
  - submission
---

Prepare submission for run at `$run_dir`.

Steps:
1. Verify submission.csv exists and header matches competition format.
2. Check row count and that target column values are valid.
3. Load metrics.json; confirm cv_score is recorded.
4. Summarise: run_id, competition, cv_score, submission_path, artifact_hash.
5. Create a decision record: `kca decision create --operation kaggle_submit --run-id <id> --reason "CV:<score>"`
6. Print the decision record ID. Do NOT submit — human must approve via `kca decision approve <id>`.

Stop if:
- submission.csv is missing or malformed → fail with clear error.
- cv_score is missing → warn and stop.
