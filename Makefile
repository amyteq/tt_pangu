# tt_pangu / kaggle-code-agent — top-level convenience targets.
# Most things are simple supabase / pytest wrappers — keep portable, no bashisms.

.PHONY: help \
        supabase-up supabase-down supabase-reset supabase-psql supabase-status \
        test test-smoke test-db-smoke \
        agents-sync agents-check \
        kca-help kca-runs

SUPABASE_DB_URL ?= postgres://postgres:postgres@127.0.0.1:54322/postgres

help:
	@echo "Targets:"
	@echo "  supabase-up      Start the local Supabase stack (Postgres + Storage + Studio)."
	@echo "  supabase-down    Stop the local Supabase stack."
	@echo "  supabase-reset   Drop the local DB and re-apply all migrations from supabase/migrations/."
	@echo "  supabase-status  Print URLs and keys for the running local stack."
	@echo "  supabase-psql    Open a psql shell against the local DB ($(SUPABASE_DB_URL))."
	@echo "  test             Run the M1 + M2 smoke tests (M2 tests skip without KCA_DB_TARGET)."
	@echo "  test-smoke       Run only the M1 kca CLI smoke tests."
	@echo "  test-db-smoke    Run only the M2 DB smoke tests (requires supabase-up)."
	@echo "  agents-sync      Regenerate AGENTS.md + .agents/ from CLAUDE.md (Codex parity)."
	@echo "  agents-check     Verify AGENTS.md + .agents/ are current (what CI asserts)."
	@echo "  kca-help         python tools/kca/kca.py --help."
	@echo "  kca-runs         List runs via kca (requires supabase-up)."

# --- Supabase local stack ---------------------------------------------------

supabase-up:
	supabase start

supabase-down:
	supabase stop

# Wipes the local DB and re-applies migrations 0001, 0002, ... in order.
supabase-reset:
	supabase db reset

supabase-status:
	supabase status

supabase-psql:
	@psql "$(SUPABASE_DB_URL)"

# --- Tests ------------------------------------------------------------------

test:
	python -m pytest tests/ -v

test-smoke:
	python -m pytest tests/test_kca_smoke.py -v

test-db-smoke:
	KCA_DB_TARGET=local SUPABASE_DB_URL="$(SUPABASE_DB_URL)" \
	  python -m pytest tests/test_kca_db_smoke.py -v

# --- cross-harness instruction parity (issue #189) --------------------------
# AGENTS.md and .agents/ are generated from CLAUDE.md + docs/instructions/agents-delta.md.
# See docs/tooling/codex-parity.md.

agents-sync:
	python scripts/gen_agents.py

agents-check:
	python scripts/gen_agents.py --check

# --- kca convenience --------------------------------------------------------

kca-help:
	python tools/kca/kca.py --help

kca-runs:
	KCA_DB_TARGET=local SUPABASE_DB_URL="$(SUPABASE_DB_URL)" \
	  python tools/kca/kca.py run list --json
