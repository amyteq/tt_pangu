---
name: triage-log
description: Summarise and classify a job's event log into actionable findings using a local or cloud LLM.
version: "1.0"
argument-hint: "[job-id]"
arguments:
  - job_id
allowed-tools:
  - read_file
  - litellm_call
approval-policy: permissive-dev
tags:
  - triage
  - log-analysis
---

Triage agent job `$job_id`.

Steps:
1. Fetch the job's event trail via `kca run logs --job-id $job_id`.
2. Route to a local model endpoint if available (see `kca local probe`).
3. Produce a structured summary:
   - Job status and outcome.
   - Key decisions made.
   - Errors and failures with root causes.
   - Recommended next action: retry / escalate / close.
