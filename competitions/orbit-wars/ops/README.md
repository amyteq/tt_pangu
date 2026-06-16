# Orbit Wars live loop (`ops/`)

Bounded live submission loop for Orbit Wars. Implements task **KCT-OW-LIVE-002**:
track active slots across two Kaggle accounts, ingest/analyze episodes, detect
hard algorithmic bugs (esp. sun collisions), classify agents, plan latest-2 slot
replacement, and perform **gated autonomous** Kaggle submit/push within budget.

> Secrets: only `.vscode/.env.harry` / `.vscode/.env.may` are read, only into a
> subprocess env, never printed/copied/committed. Usernames may be shown.

## Modules

| file | role |
|---|---|
| `kaggle_auth.py` | credential-safe account loader + output redactor + `run_kaggle` |
| `slot_state.py` | agent-status model (`neutral/strong/weak/fix_required/retired/unknown`) + weak/strong classification rules |
| `account_manager.py` | read-only Kaggle status → latest-2 active-slot model |
| `episode_fetch.py` | download replay JSON by id / drain `live/pending_episodes.txt` |
| `episode_analyze.py` | decode launches, **sun-collision/hard-bug detection**, winner-reason, flag interesting/unexpected episodes, record CSV + render `episodes_findings.md` |
| `evaluate_candidate.py` | wrap arena gates → submit-ready verdict (crash/weak-tier/2p-vs-baseline/4p) |
| `submit_manager.py` | budget + replacement plan + **gated autonomous submit** via `submit.py` |
| `live_loop.py` | orchestrate one bounded `--once` cycle (or bounded `--watch`) |

## Commands

```bash
# one bounded cycle (read-only status + ingest/analyze + plan; no submit)
python competitions/orbit-wars/ops/live_loop.py --once

# allow a gated real submit inside the cycle (only fires if all gates pass)
python competitions/orbit-wars/ops/live_loop.py --once --submit-if-gated

# bounded watch for a human/cron (hard-capped, never indefinite)
python competitions/orbit-wars/ops/live_loop.py --watch --interval-minutes 5 --max-cycles 3

# pieces
python competitions/orbit-wars/ops/account_manager.py --status
python competitions/orbit-wars/ops/episode_fetch.py --episode-id <id>
python competitions/orbit-wars/ops/episode_analyze.py --episode-json replays/<id>.json
python competitions/orbit-wars/ops/evaluate_candidate.py --agent <f> --baseline <f> --games 30 --seed0 <s>
python competitions/orbit-wars/ops/submit_manager.py --plan
python competitions/orbit-wars/ops/submit_manager.py --account auto --dry-run \
    --candidate agent/main.py --candidate-verdict live/last_eval.json
python competitions/orbit-wars/ops/submit_manager.py --account auto --submit-if-gated \
    --candidate <f> --candidate-verdict <eval.json>
```

## Autonomous write budget (per task run)

`max 4 submits total / 2 per account`, `max 4 pushes / 2 per account`,
`leave >= 1 daily quota/account`, `>= 5 min between same-account submits`,
`final_lock_mode: false`. Tracked in `live/budget_state.json`.

## State files (`live/`)

`account_status.md`, `agent_status.md`, `active_agents.yaml`, `submit_plans.md`,
`push_submit_audit.md`, `episodes_index.csv`, `episodes_findings.md`, `matches.csv`,
`pending_episodes.txt`, `budget_state.json`. Raw replays go to the gitignored `replays/`.

## Episode findings for manual review

Every analyzed episode is recorded with its **watch link** (Kaggle replay viewer)
and **replay-JSON link** in `live/episodes_index.csv`, and surfaced in the
human-reviewable `live/episodes_findings.md` (regenerated each cycle). Episodes are
flagged **interesting / needs-manual-review** when they show a correctness anomaly
(hard bug / sun proximity) or a result the winner-reason heuristic cannot explain
(`unexplained-result`) or a notable strategic loss pattern — these get a `REVIEW:`
follow-up note and a dedicated "🔎 Needs manual review" section with direct links,
so a human can open the unexpected/interesting replays and analyze them.

## Episode discovery

Automatic ladder→episode discovery is not exposed by the Kaggle API for this
competition, so the loop uses the **manual queue** `live/pending_episodes.txt`
(one episode id or leaderboard URL per line). Add ids there and re-run `--once`.
