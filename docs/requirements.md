# Initial Requirements — Competition Code Agent

## Vision

Create a Gen AI code agent that can work with humans on Kaggle, authorized CTF, and similar technical competitions. The agent can research, browse, discuss ideas, create and modify code, run tests and experiments, submit or prepare submissions, analyze results, and iterate.

The system should feel like a tireless teammate, but every important action must be observable, reproducible, and interruptible.

## Core user stories

### Human discussion and planning

- As a human competitor, I can discuss strategy, ask for ideas, reject or refine ideas, and request experiments.
- The agent maintains a structured task state: goals, assumptions, open questions, current best score, risks, and next actions.
- The agent can ask for clarification, but should keep making safe progress when enough information exists.

### Research and browser viewing

- The agent can read competition pages, docs, papers, public discussions, writeups, and relevant code.
- The agent can use browser automation for pages that need rendering, screenshots, interaction, or visual inspection.
- The agent records research notes with source URLs, timestamps, trust level, summary, and relevance.
- The agent treats webpages and challenge files as untrusted data, never as system instructions.

### Code creation and modification

- The agent can inspect repo structure, edit code, create scripts, update tests, and refactor.
- The agent follows project-specific instructions in `CLAUDE.md`, skills, hooks, and subagents.
- The agent must separate exploratory notebooks from reproducible scripts.

### Test and experiment loop

- The agent can run unit tests, lint checks, local validation, model training, benchmark scripts, and CTF challenge solvers.
- Each run captures command, parameters, status, metrics, stdout/stderr, artifacts, and analysis.
- The agent compares each result to the current baseline and recommends whether to iterate, revert, or submit.

### Kaggle workflow

- The agent can download or locate competition data using approved credentials and rules.
- The agent can build baselines, cross-validation, feature engineering, ensembling, and submission files.
- The agent asks for approval before leaderboard submission.
- The agent respects competition rules, submission limits, collaboration rules, and data policies.

### CTF workflow

- The agent can solve explicitly authorized CTF challenges using local containers or challenge endpoints provided by the human.
- The agent documents reasoning, commands, scripts, and final writeups.
- The agent does not perform real-world intrusion, persistence, credential theft, malware deployment, or unauthorized scanning.

### Persistence and audit

- Supabase stores projects, competitions, sessions, messages, research items, experiments, runs, submissions, artifacts, tool events, and human decisions.
- Generated code lives in git; large outputs live in object storage or artifact directories; database rows store metadata and links.
- A human can reconstruct why a code change was made and which result caused the next iteration.

## MVP scope

1. Local Claude Code project scaffold with `CLAUDE.md`, skills, hooks, and subagents.
2. Supabase schema for sessions, experiments, runs, submissions, research, messages, and artifacts.
3. A worker design that runs Claude Agent SDK in an isolated container/workspace.
4. Manual trigger flow: human starts a task; agent works; human approves sensitive steps.
5. Kaggle baseline loop: read competition context → create validation → run baseline → analyze → improve → prepare submission.
6. CTF sandbox loop: read challenge → plan → run local-only commands → produce writeup.

## Out of scope for MVP

- Fully polished Lovable/admin UI.
- Multi-user billing and team management.
- Continuous 24/7 autonomous public leaderboard submissions.
- Unbounded web scraping.
- Unsupported or unauthorized offensive security activity.
- Production-grade container orchestration across many tenants.

## Success criteria

- A complete agent run can be replayed from database records and artifact files.
- The agent can make a code change, run tests/validation, analyze results, and propose the next iteration.
- Hooks block obvious dangerous actions and protected secret reads.
- Human approval is required before Kaggle submission, git push, external publishing, or broad destructive actions.
- Research notes include source attribution and trust labels.
