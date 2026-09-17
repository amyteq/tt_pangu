# ADR-0005: Job taxonomy and platform terminology

Status: accepted  
Date: 2026-05-19  
Decided in: `docs/meeting-notes/2026-05-19-r1.md`

---

## Context

The platform uses several related terms — project, competition, session, job, experiment, run, submission — that are easily confused. This ADR defines each term precisely so that all AI tools, platform code, and human users share the same vocabulary.

---

## Definitions

### Project
A top-level working context owned by a user.  
Corresponds to: `projects` table.  
Example: `"flower-tpu-2026"`, `"ctf-practice-may26"`.

One project can contain many competitions and sessions. It is the billing and access-control boundary.

### Competition
A specific contest the user has entered on an external platform.  
Corresponds to: `competitions` table.  
Fields: slug, platform (kaggle / ctf / hackathon), metric, objective, daily submission limit.  
Example: `flower-classification-with-tpus` on `kaggle`.

A competition belongs to one project. It carries the rules, metric name, and current best result.

### Session
A working period grouping related jobs under a shared goal.  
Corresponds to: `agent_sessions` table.  
Example: "May 19 afternoon — try EfficientNetB3 and Mixup augmentation".

A session has a branch/worktree reference and an overall goal. Jobs within a session share context (but NOT file state — each job gets its own workspace).

### Job ← primary schedulable unit
**One discrete task assigned to one AI agent worker.**  
Corresponds to: `agent_jobs` table.  
The job is the smallest unit of work the platform queues, executes, and records independently.

A job has:
- `job_type`: the kind of work (see job types below)
- `prompt`: the English-language instruction to the agent
- `model`: LiteLLM model string
- `policy`: sampling params + budget limits + approval settings
- `workspace_path`: isolated git worktree for this job
- `status`: queued → running → succeeded / failed / paused
- `agent_job_events`: turn-by-turn audit log

**A job is NOT:**
- The whole competition (that is a `competition`)
- A multi-day session (that is a `session`)
- The code execution itself (that is an `experiment_run`)
- A human decision (that is a `human_decision`)

### Experiment
A hypothesis and configuration being tested.  
Corresponds to: `experiments` table.  
Example: "EfficientNetB3 with Mixup, lr=1e-4, 20 epochs".

An experiment is typically created by an `implement` or `experiment` job. It records the hypothesis, code ref, config, and dataset version.

### Run (experiment run)
One execution of experiment code.  
Corresponds to: `experiment_runs` table + `runs/<competition>/<run_id>/` on disk.  
Created by `kca run init`, updated by `kca run record-metric`.

A run records: command, status, metrics (cv_score, val_loss, etc.), artifact paths, wall-clock time, analysis notes.

### Submission
A file submitted to the external competition leaderboard.  
Corresponds to: `submissions` table.  
Created by a `prepare_submission` job; submitted by a `submit` job (or human).

### human_decision
A human approval or rejection of a proposed action.  
Corresponds to: `human_decisions` table.  
Created when a job hits a configured approval gate.  
Resolved by `kca decisions approve/deny` or the platform UI.

---

## Job types

| job_type | Description | Typical tools used | Approval needed (default) |
|---|---|---|---|
| `research` | Read competition pages, discussions, papers; produce a brief | read_file, grep, (browser via future MCP) | No |
| `implement` | Write or modify Python/notebook code | read_file, write_file, edit_file, run_bash(kca nb) | No |
| `experiment` | Run code, record metrics | run_bash(kca run, pytest), read_file | No |
| `debug` | Diagnose and fix a specific error | read_file, edit_file, run_bash(pytest) | No |
| `eval` | Compare runs, produce analysis | read_file, run_bash(kca run list) | No |
| `prepare_submission` | Generate and validate submission.csv | read_file, write_file, run_bash(kca) | No |
| `submit` | Submit to Kaggle leaderboard | run_bash(kca kaggle submit) | Configurable (default: No — see ADR-0006) |
| `kernel_push` | Push notebook to Kaggle kernel | run_bash(kca kaggle push) | Configurable (default: No — see ADR-0006) |
| `monitor` | Watch a Kaggle kernel run, fetch results | run_bash(kca kaggle watch, fetch) | No |
| `analysis` | Summarise results, recommend next steps | read_file, write_file | No |
| `git_commit` | Stage and commit workspace changes | run_bash(git add, git commit) | No |
| `git_push` | Push branch to remote | run_bash(git push) | Configurable (default: No — see ADR-0006) |

---

## Object hierarchy

```
Project
  └─ Competition (one or more)
       └─ Session (one or more per competition)
            └─ Job (one or more per session)       ← agent_jobs
                 ├─ agent_job_events               ← turn/tool audit log
                 ├─ human_decisions (0 or more)    ← approval gates
                 └─ Experiment (0 or more)         ← experiments table
                      └─ Run (one or more)         ← experiment_runs + runs/ dir
                           └─ Submission (0 or 1)  ← submissions table
```

---

## Consequences

- All code, prompts, and docs should use these exact terms.
- If a concept doesn't map to one of these terms, it's either a UI concern (future M7) or needs a new ADR.
- `agent_sessions` and `agent_jobs` table names already match these definitions.
- The term "task" is ambiguous (used differently in todos, Supabase, LangGraph); prefer "job" for the schedulable unit and "step" for sub-steps within a job turn.
