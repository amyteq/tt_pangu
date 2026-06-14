# M1-T000: legacy tool inventory and wrapper contract draft

## Milestone
M1 / MVP-1: local Kaggle tooling wrapper baseline.

## Goal
Inspect `tools/legacy/TOOLS.md` and the Python scripts under `tools/legacy/`, then produce a concise inventory and a first `kca` wrapper command contract. This task should prepare implementation, not rewrite the legacy tools.

## Context
The repository is building a hybrid human + AI code competition platform. M1 creates a local-first wrapper layer that Claude Code and future runtime competition agents can call safely.

Existing helper scripts and their descriptions have already been placed in:

- `tools/legacy/TOOLS.md`
- `tools/legacy/**/*.py`

## Read first
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md`
5. `docs/architecture/model-routing.md`
6. latest files in `docs/adr/`
7. `tools/legacy/TOOLS.md`
8. Python files under `tools/legacy/`

## Tasks
1. Inventory the legacy tools:
   - script path;
   - purpose;
   - input files/arguments;
   - output files/artifacts;
   - required dependencies;
   - whether it imports Kaggle APIs or shell-calls `kaggle`;
   - side-effect level: `read-only`, `local-write`, `remote-write`, `submission`;
   - whether it is safe for Claude Code to call automatically.
2. Identify the 1-2 best scripts to wrap first, prioritizing Python/IPython notebook conversion.
3. Draft stable wrapper commands for:
   - script-to-notebook conversion;
   - notebook-to-script conversion;
   - run artifact directory creation.
4. Record any unknowns/blockers, especially scripts whose behavior is unclear.

## Expected files to create or update
Prefer these files if they do not already exist:

- `docs/tooling/legacy-tool-inventory.md`
- `docs/tooling/kca-command-spec.md`
- `docs/tooling/kca-side-effect-levels.md`
- optionally update `PROJECT_STATE.md` with one short M1 status note

## Non-goals
- Do not implement `tools/kca/` yet.
- Do not modify legacy scripts unless a harmless comment/docstring fix is needed.
- Do not install dependencies.
- Do not run real Kaggle submit/kernel push/dataset upload commands.
- Do not read or print secrets, including `.env`, `~/.kaggle/kaggle.json`, `KAGGLE_USERNAME`, or `KAGGLE_KEY`.

## Acceptance criteria
- The legacy tool inventory exists and covers every Python script under `tools/legacy/`.
- The first `kca` command contract is documented.
- At least 1-2 notebook conversion scripts are selected for wrapping, or blockers are documented.
- Remote-write and submission risks are clearly identified.
- `git diff --stat` only shows documentation/status changes.

## Suggested commands
Use safe read-only commands only:

```bash
git status --short
find tools/legacy -maxdepth 3 -type f | sort
sed -n '1,220p' tools/legacy/TOOLS.md
python - <<'PY'
from pathlib import Path
for p in sorted(Path('tools/legacy').rglob('*.py')):
    print(p)
PY
```

## Stop condition
Stop after 40 turns if the legacy tool behavior is unclear, and summarize blockers with exact script paths.
