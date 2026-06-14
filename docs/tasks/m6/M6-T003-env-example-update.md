# M6-T003: env.example update for local endpoints + reviewer + OTEL

## Milestone
M6.

## Goal
Document every new env knob from M6 in `env.example` so a fresh checkout
can `cp env.example .env`, fill in nothing M6-specific, and still pass the
no-DB smoke. Concrete defaults for the user's snorlax + may hosts go in
commented-out form so they show as documentation, not as defaults.

## Read first
1. `env.example` (current state — M3..M5 vars only).
2. `docs/tasks/m6/M6-T002-local-model-layer.md` (variable contract).

## Schema to add (append at the bottom of `env.example`)

```bash
# -----------------------------------------------------------------------------
# Local LLM endpoints (M6-T002 / ADR-0011)
# -----------------------------------------------------------------------------
# Iterated as KCA_LOCAL_ENDPOINT_<N>_* until the first missing _NAME.
# These hosts are on a private LAN; from inside the Claude Code sandbox they
# need dangerouslyDisableSandbox=true to reach 192.168.x ranges.

# snorlax — RTX 4090, Void Linux. vllm-coder runs Qwen2.5-Coder-14B-Instruct-AWQ
# under the served name "rtx4090". Ollama is installed but inactive by default.
# KCA_LOCAL_ENDPOINT_0_NAME=snorlax-vllm
# KCA_LOCAL_ENDPOINT_0_URL=http://192.168.18.66:8000/v1
# KCA_LOCAL_ENDPOINT_0_MODEL=rtx4090
# KCA_LOCAL_ENDPOINT_0_BACKEND=vllm
# KCA_LOCAL_ENDPOINT_0_API_KEY=local

# KCA_LOCAL_ENDPOINT_1_NAME=snorlax-ollama
# KCA_LOCAL_ENDPOINT_1_URL=http://192.168.18.66:11434/v1
# KCA_LOCAL_ENDPOINT_1_MODEL=qwen3:30b-a3b-instruct-2507-q4_K_M
# KCA_LOCAL_ENDPOINT_1_BACKEND=ollama
# KCA_LOCAL_ENDPOINT_1_API_KEY=ollama

# may — RTX 3090, Windows WSL Debian. Both vllm + ollama are inactive most of
# the time; the host itself may be shut down. The router will skip it cleanly
# when the probe times out.
# KCA_LOCAL_ENDPOINT_2_NAME=may-vllm
# KCA_LOCAL_ENDPOINT_2_URL=http://192.168.18.77:8000/v1
# KCA_LOCAL_ENDPOINT_2_MODEL=rtx3090
# KCA_LOCAL_ENDPOINT_2_BACKEND=vllm
# KCA_LOCAL_ENDPOINT_2_API_KEY=local

# KCA_LOCAL_ENDPOINT_3_NAME=may-ollama
# KCA_LOCAL_ENDPOINT_3_URL=http://192.168.18.77:11434/v1
# KCA_LOCAL_ENDPOINT_3_MODEL=qwen3:1.7b
# KCA_LOCAL_ENDPOINT_3_BACKEND=ollama
# KCA_LOCAL_ENDPOINT_3_API_KEY=ollama

# Routing knobs (used by src/worker/local_model.py + routing.py)
KCA_LOCAL_PRIORITY_ORDER=snorlax-vllm,may-vllm,snorlax-ollama,may-ollama
KCA_LOCAL_PROBE_TIMEOUT_S=2
KCA_LOCAL_PROBE_CACHE_TTL_S=60
KCA_LOCAL_FALLBACK_MODEL=claude-haiku-4-5
# Set to 1 to refuse to dispatch local-model jobs when no endpoint is up
# instead of silently falling back. Default: 0 (fall back).
KCA_LOCAL_REQUIRE_LOCAL=0

# -----------------------------------------------------------------------------
# Reviewer agent (M6-T004 / ADR-0012)
# -----------------------------------------------------------------------------
# Sync reviewer fires before high-stakes ops (kaggle_submit, supabase_migrate,
# git_force_push, dataset_upload, delete_artifact). Verdict + rationale land
# in agent_reviews; an approve verdict satisfies the matching approval gate
# without human intervention.
KCA_REVIEWER_MODEL=claude-opus-4-7
KCA_REVIEWER_MAX_TOKENS=2048
KCA_REVIEWER_TIMEOUT_S=120
# Comma-separated approval-gate operations that trigger a reviewer run.
KCA_REVIEWER_TRIGGER_OPS=kaggle_submit,supabase_migrate,git_force_push,dataset_upload,delete_artifact
# Set to 1 to make every reviewer reject also notify a human via human_decisions.
KCA_REVIEWER_ESCALATE_REJECT=1

# -----------------------------------------------------------------------------
# OTEL telemetry (M6-T005 / ADR-0013)
# -----------------------------------------------------------------------------
KCA_OTEL_ENABLED=1
# Comma-separated exporters: console, sqlite, supabase
KCA_OTEL_EXPORTERS=console,sqlite,supabase
KCA_OTEL_SQLITE_PATH=.agent/telemetry.sqlite
# Drop spans whose duration is below this threshold (ms). Default 0 = keep all.
KCA_OTEL_MIN_DURATION_MS=0
```

## Acceptance criteria
- `cat env.example | grep -c "KCA_LOCAL_ENDPOINT_"` ≥ 20 (4 endpoints × 5
  knobs each, all commented out).
- `cat env.example | grep -c "^KCA_REVIEWER_"` == 5 (uncommented defaults).
- `cat env.example | grep -c "^KCA_OTEL_"` == 4 (uncommented defaults).
- `python -c "import os; from src.worker.local_model import load_endpoints; print(load_endpoints())"`
  prints `[]` against the default env.example (all endpoints commented out).
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 10 turns. If the file already has any of these keys (e.g. from a
prior partial M6 attempt), de-duplicate rather than appending blindly.
