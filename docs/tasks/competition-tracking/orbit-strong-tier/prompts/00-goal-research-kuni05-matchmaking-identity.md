---
id: OW-P0-RESEARCH-001
title: Research kuni05-class source, matchmaking behavior, and Kaggle identity mapping
kind: claude-code-task
status: ready
scope: docs-and-read-only-kaggle-research
competition_slug: orbit-wars
created: 2026-06-16
remote_side_effects: read-only-only
allowed_paths:
  - competitions/orbit-wars/**
  - competitions/README.md
  - docs/tasks/competition-tracking/orbit-strong-tier/**
forbidden_paths:
  - .kca/**
  - tools/**
  - src/**
  - services/**
  - supabase/**
  - ui/**
  - tests/**
  - .github/workflows/**
  - .env
  - .env.*
  - kaggle.json
  - .kaggle/kaggle.json
  - secrets/**
allowed_credential_files_for_readonly_kaggle:
  - .vscode/.env.harry
  - .vscode/.env.may
---

# Task: Research kuni05-class source, matchmaking behavior, and Kaggle identity mapping

## Mission

Before building the next Orbit Wars architecture, establish the ground truth for three operational questions:

1. Can we download or inspect a public `kuni05` / kuni05-class agent source to study integrated-system design?
2. Does Kaggle assign opponents randomly, by similar skill, by weak-to-strong curriculum, or by another observable pattern?
3. How do we reliably map Kaggle `username`, profile/display name, team name, leaderboard row, submission id, and replay `TeamNames`?

This is a research/docs task only. Do not change agent code. Do not submit. Do not push kernels.

## Read first

- `competitions/orbit-wars/README.md`
- `competitions/orbit-wars/tracking.md`
- `competitions/orbit-wars/submissions.md`
- `competitions/orbit-wars/EPISODES.md`
- `competitions/orbit-wars/ops/episode_discover.py`
- `competitions/orbit-wars/ops/track_submission.py`
- `competitions/orbit-wars/ops/episode_analyze.py`
- `competitions/orbit-wars/ops/kaggle_auth.py`
- `competitions/orbit-wars/references.md`

## Research topic A — public kuni05-class source

Search Kaggle Code/discussions/read-only sources for public kuni05-class Orbit Wars agents, especially:

```text
kuni05/lb-1240-5-orbit-wars-producer-agent-submission
```

Allowed read-only commands, if credentials are available:

```bash
kaggle kernels pull kuni05/lb-1240-5-orbit-wars-producer-agent-submission \
  -p competitions/orbit-wars/sources/kuni05_producer_agent -m
```

Rules:

- Pull only public code/notebook source and metadata.
- Do not submit or push anything.
- Do not vendor large generated outputs.
- Preserve license/attribution notes.
- If source is public and usable, create a system-study summary; do not blindly copy it into our from-scratch agent.
- If reused for an attributed submission, clearly label it as attributed public source, not our own from-scratch agent.

Create/update:

```text
competitions/orbit-wars/discussions/YYYY-MM-DD-kuni05-system-study.md
competitions/orbit-wars/references.md
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
```

The system-study summary should answer:

- What files/classes/functions define the agent architecture?
- Is it rules/search/model/hybrid?
- How does it represent battlefield state?
- How does it choose targets and ship sizes?
- Does it have a landing/path oracle?
- Does it do multi-source scheduling, hub-and-hammer, defense ledger, supply chain, or endgame banking?
- What is safe to learn conceptually without copying?
- What needs attribution if reused?

## Research topic B — opponent assignment / matchmaking behavior

Investigate official and empirical evidence for matchmaking.

Official evidence:

- Kaggle competition overview / docs statements about simulation competitions and skill rating.
- Orbit Wars overview/rules if accessible.
- Kaggle docs about submissions playing episodes against agents with similar skill rating.

Empirical evidence:

Use `EpisodeService/ListEpisodes` through existing tooling if possible:

```bash
python competitions/orbit-wars/ops/episode_discover.py --submission-id <known_submission_id>
python competitions/orbit-wars/ops/track_submission.py --once --submission-id <known_submission_id> --decide-after 10 --max 20
```

For several known submissions, collect:

- episode order by id/time if available;
- number of 2p/4p matches;
- initialScore and updatedScore for our submission;
- opponent initialScore distribution;
- opponent names/profile names;
- whether first episodes are systematically weak, similar, or mixed;
- whether assignment becomes closer to current μ over time;
- whether 4p games also update μ.

Deliver a cautious conclusion:

```text
official_matching_rule: similar_skill | random | unknown
empirical_initial_behavior: weak_first | similar_first | mixed | unknown
confidence: low | medium | high
operational_policy: how the ladder loop should interpret first 10/20 episodes
```

Do not overstate if evidence is incomplete.

## Research topic C — player identity mapping

Investigate and document how to map:

```text
Kaggle username / account alias
profile display name
team name
leaderboard display
submission id
EpisodeService agents[].submissionId
replay info.TeamNames[seat]
replay rewards[seat]
```

Specific known issue to resolve:

```text
flyingfox == harrysun2006 profile/display name, not external opponent
```

Create/update:

```text
competitions/orbit-wars/live/player_identity_map.md
competitions/orbit-wars/references.md
competitions/orbit-wars/EPISODES.md
competitions/orbit-wars/insights.md
```

The identity map should include:

```md
| account alias | Kaggle username | profile/display name | team name / replay name | evidence | notes |
|---|---|---|---|---|---|
```

If a profile name is inferred by reward matching rather than direct API identity, mark it as inferred and include evidence.

## Credential and secret policy

You may use `.vscode/.env.harry` and `.vscode/.env.may` only for read-only Kaggle queries if needed.

Never print, copy, commit, or write credential values. Usernames and profile names may be shown.

Do not read any other secret path.

## Validation

Run:

```bash
git status --short
git diff --stat
git diff --name-status
find competitions/orbit-wars -maxdepth 4 -type f | sort | sed -n '1,200p'
```

## Acceptance criteria

- Kuni05-class public source availability is answered with evidence.
- If public source is downloadable, it is pulled or a precise blocker is documented.
- `discussions/YYYY-MM-DD-kuni05-system-study.md` exists or a blocker explains why not.
- Matchmaking official statement and empirical evidence are summarized.
- Player identity mapping is documented, including the `flyingfox` correction.
- `tasks.md` / `tracking.md` include follow-up tasks from research.
- No agent code is changed.
- No Kaggle submit/kernel push/dataset upload is performed.
- No secrets are exposed.

## Stop conditions

Stop if:

- credentials would need to be exposed;
- Kaggle public source is inaccessible and no local evidence can answer the question;
- a required action would modify agent code;
- a required action would submit/push/upload;
- source identity remains too ambiguous and could cause false attribution.

## Final response requirements

Report:

- public source availability and path/blocker;
- matchmaking conclusion and confidence;
- identity map conclusion;
- files modified;
- read-only commands run;
- follow-up tasks created;
- risks and next steps.
