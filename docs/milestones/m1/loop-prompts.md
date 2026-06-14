# M1 / MVP-1 Loop Prompts

_For sequential autonomous execution on Arch Linux via `claude --dangerously-skip-permissions` or a permissive settings profile._

---

## Architecture answers (read before starting)

### Skills naming convention

Claude Code skill names are **flat kebab-case directory names** under `.claude/skills/`. There is no multi-level `/kaggle/evaluation-harness` path syntax in the skill invocation — the slash is the command prefix, not a namespace separator.

Recommended platform skill names (short, verb-or-noun-first, `kg-` prefix groups Kaggle tools):

| Old name                      | New name     | Invocation     |
|-------------------------------|-------------|----------------|
| `kaggle-evaluation-harness`   | `kg-eval`   | `/kg-eval`     |
| `kaggle-tooling-integration`  | `kg-tool`   | `/kg-tool`     |
| `kaggle-experiment-loop`      | `kg-loop`   | `/kg-loop`     |
| `research-brief`              | `research`  | `/research`    |
| `ctf-sandbox`                 | `ctf`       | `/ctf`         |
| `agent-iteration-review`      | `iter`      | `/iter`        |

New skills to add in M1:
- `kg-nb` → `/kg-nb` — notebook ↔ script conversion via kca
- `kg-run` → `/kg-run` — run init/record via kca

### Component calling rules

```
User / Claude Code agent
    │
    ├─ invokes Skills  (.claude/skills/*/SKILL.md)
    │     Skills are PROMPT TEMPLATES only.
    │     They instruct Claude how to use kca CLI.
    │     Skills never call each other directly.
    │
    ├─ calls kca CLI  (tools/kca/kca.py or kca entrypoint)
    │     kca is the stable, safety-classified execution layer.
    │     Subcommands: kca nb | kca run | kca kaggle | kca eval
    │     Each subcommand wraps one or more legacy tools.
    │     All output is structured JSON.
    │     Side-effect level declared per command (read-only, local-write, remote-write, submission).
    │
    ├─ hooks in .claude/settings.json
    │     PreToolUse  → guard_tool.py  (blocks/gates dangerous Bash patterns)
    │     PostToolUse → audit_event.py (logs all tool calls)
    │     Hooks operate at the Bash/Edit/Read tool level, BELOW skills.
    │
    └─ artifact output: runs/<competition>/<run_id>/
          Created by `kca run init`.
          Owned by kca; never created manually.

Calling direction (one-way):
  Skills → kca CLI → legacy tools → artifact layout
  Hooks  → intercept Bash calls at any level
  kca    does NOT call skills
  legacy tools do NOT call kca (they are wrapped, not aware of it)
```

### Permissions for autonomous loop

For long autonomous loops, expand `settings.json` allow-list temporarily:
```json
"allow": [
  "Bash(python tools/kca/*)",
  "Bash(python tools/legacy/*)",
  "Bash(python -m pytest tests/*)",
  "Bash(find . *)",
  "Bash(ls *)",
  "Bash(cat *)"
]
```
Keep `ask` for: `kaggle competitions submit`, `kaggle kernels push`, `git push`, `git commit`.
Keep `deny` for: `.env`, secrets, `rm -rf`, `sudo`.

---

## Loop Prompt 0 — Context loader (run first, not a build prompt)

```
Read the following files in order and build a mental model before starting M1 work:
1. PROJECT_STATE.md
2. CLAUDE.md
3. tools/legacy/TOOLS.md
4. .claude/settings.json
5. docs/milestones/m1/loop-prompts.md (this file)

Then do:
- `find tools/legacy -type f` to list all legacy scripts
- Try: `python tools/legacy/py2nb.py --help` and `python tools/legacy/nb2py.py --help`
- Try: `python tools/legacy/kkr.py --help`
- Try: `python tools/legacy/nb2test.py --help`

Report:
- Which tools have --json flag
- Which tools have external deps (import lines in first 30 lines)
- Any tools that import sqlite3 (to be migrated to Supabase later)
- Any tools that are broken or missing deps

Do not make any changes in this prompt. Output a brief inventory table.
```

---

## Loop Prompt 1 — kca CLI skeleton

```
Goal: create tools/kca/ Python CLI skeleton following these rules:
- Single entrypoint: tools/kca/kca.py
- Subcommand groups: `kca nb`, `kca run`, `kca kaggle`, `kca eval`
- Each subcommand must emit structured JSON ({"ok": bool, ...}) and exit 0/1
- Side-effect level must be declared as a constant per subcommand: READ_ONLY | LOCAL_WRITE | REMOTE_WRITE | SUBMISSION
- No third-party deps in kca itself; use only stdlib + tools already used by legacy scripts
- Follow Clean Architecture: separate cli layer (argument parsing) from domain layer (business logic) from infrastructure layer (file I/O, subprocess calls)
- Module layout:
    tools/kca/
      kca.py          ← entrypoint + top-level argparse
      nb.py           ← notebook subcommands (stubs only for now)
      run.py          ← run management subcommands (stubs only)
      kaggle.py       ← kaggle remote subcommands (stubs only, all SUBMISSION level)
      eval.py         ← evaluation subcommands (stubs only)
      _types.py       ← shared dataclasses / TypedDict / enums
      _util.py        ← emit_json(), run_cmd(), SideEffect enum
      COMMANDS.md     ← side-effect level table (auto-generated or hand-written)

Stub behavior: each stub subcommand should:
1. Print `{"ok": true, "stub": true, "command": "<name>", "side_effect": "<level>"}` and exit 0
2. Log a NOT-IMPLEMENTED warning to stderr

Smoke test: after scaffolding, run:
  python tools/kca/kca.py nb to-py --help
  python tools/kca/kca.py nb to-ipynb --help
  python tools/kca/kca.py run init --help
  python tools/kca/kca.py kaggle submit --help
All must exit 0 and show help text.

Do not connect to legacy tools yet. Stubs only.
Record any open questions in a comment block at the top of COMMANDS.md.
Do NOT git add or commit.
```

---

## Loop Prompt 2 — nb2py and py2nb wrappers

```
Goal: implement `kca nb to-py` and `kca nb to-ipynb` as real wrappers around tools/legacy/nb2py.py and tools/legacy/py2nb.py.

Context: read tools/legacy/TOOLS.md section "nb2py.py / py2nb.py" and read the first 60 lines of each legacy script to understand their interface.

Requirements:
- `kca nb to-py <source.ipynb> [--output <dest.py>] [--json]`
  → calls `python tools/legacy/nb2py.py SOURCE [DEST] --json`
  → re-emits the legacy JSON output under kca's envelope: {"ok": bool, "src": "...", "dst": "...", "side_effect": "LOCAL_WRITE", ...}
  → if legacy tool fails (non-zero exit), emit {"ok": false, "error": "...", "side_effect": "LOCAL_WRITE"}

- `kca nb to-ipynb <source.py> [--output <dest.ipynb>] [--json] [--keep-markdown]`
  → calls `python tools/legacy/py2nb.py SOURCE [DEST] --json [--keep-markdown]`
  → same envelope wrapping

Implementation rules:
- Place subprocess call logic in _util.py: `run_legacy(cmd: list[str]) -> tuple[bool, dict]`
- nb.py should only parse args and call domain functions; no subprocess logic there
- Do not swallow stderr; capture and include in error envelope
- Side effect for both: LOCAL_WRITE (never touches remote)

After implementing, run these smoke tests and report results:
  echo "# %% [markdown]" > /tmp/test_kca.py
  echo "# Hello" >> /tmp/test_kca.py
  echo "# %%" >> /tmp/test_kca.py
  echo "x = 1" >> /tmp/test_kca.py
  python tools/kca/kca.py nb to-ipynb /tmp/test_kca.py --output /tmp/test_kca.ipynb --json
  python tools/kca/kca.py nb to-py /tmp/test_kca.ipynb --output /tmp/test_kca_roundtrip.py --json

Both must exit 0 and emit {"ok": true, ...}.
Report cell counts from the JSON output.
Do NOT git add or commit.
```

---

## Loop Prompt 3 — Artifact layout: `runs/<competition>/<run_id>/`

```
Goal: implement `kca run init` to create a structured artifact directory.

Artifact layout spec:
  runs/<competition>/<run_id>/
    meta.json         ← run metadata: competition, run_id, created_at, hypothesis, tags
    config.json       ← parameters/config snapshot (user-provided key-value pairs)
    metrics.json      ← initially empty {}; updated by `kca run record-metric`
    logs/             ← directory for log files
    artifacts/        ← directory for output files

Commands to implement (all LOCAL_WRITE):
1. `kca run init --competition <slug> [--run-id <id>] [--hypothesis <text>] [--json]`
   → Creates the directory tree above
   → run_id defaults to UTC timestamp: YYYYMMDD_HHMMSS
   → emits {"ok": true, "run_dir": "runs/<slug>/<run_id>", "run_id": "..."}

2. `kca run record-metric --run-dir <path> --key <name> --value <float> [--json]`
   → Appends to runs/.../metrics.json: {"<key>": <value>, "recorded_at": "<iso>"}
   → emits {"ok": true, "run_dir": "...", "key": "...", "value": ...}

3. `kca run list [--competition <slug>] [--json]`
   → Lists run dirs and their meta.json summaries
   → READ_ONLY

Place all run management logic in tools/kca/run.py.
Add a runs/ entry to .gitignore if not already present (runs/ should not be committed).

After implementing, run:
  python tools/kca/kca.py run init --competition titanic --hypothesis "baseline logistic regression" --json
  python tools/kca/kca.py run list --competition titanic --json
Both must succeed and emit valid JSON.
Do NOT git add or commit.
```

---

## Loop Prompt 4 — Smoke test suite

```
Goal: create a pytest smoke test suite at tests/test_kca_smoke.py covering M1 commands.

Test cases (each as a separate pytest function):
1. test_nb_to_ipynb_roundtrip
   - Write a minimal percent-format .py to a tmp file
   - Run `kca nb to-ipynb` via subprocess
   - Assert exit 0, JSON ok=true, output file exists

2. test_nb_to_py_roundtrip
   - Use the ipynb from test 1 (or create a minimal one with json.dumps)
   - Run `kca nb to-py` via subprocess
   - Assert exit 0, JSON ok=true, output .py file exists

3. test_run_init_creates_layout
   - Run `kca run init --competition test_smoke --json`
   - Assert exit 0, run_dir exists, meta.json and metrics.json exist

4. test_run_record_metric
   - Init a run, then `kca run record-metric --run-dir ... --key cv_score --value 0.82 --json`
   - Assert metrics.json contains cv_score: 0.82

5. test_kaggle_submit_is_stub_or_blocked
   - Run `kca kaggle submit --competition test --file /dev/null --message test --json`
   - Assert it either exits non-zero OR emits {"ok": false} OR emits {"stub": true}
   - Purpose: confirm the dangerous path does NOT silently succeed

Rules:
- Use subprocess.run() to call kca.py, not direct import (test the CLI surface, not internals)
- Use tmp_path pytest fixture for all file I/O
- No network calls in any test
- Tests should pass with: python -m pytest tests/test_kca_smoke.py -v

Run the tests after writing them and fix failures before finishing.
Do NOT git add or commit.
```

---

## Loop Prompt 5 — Approval gate for dangerous kca commands

```
Goal: ensure that `kca kaggle submit`, `kca kaggle push`, and `kca kaggle upload` cannot run silently in an automated loop.

Two-layer approach:
Layer A — kca internal gate (implemented in kca/kaggle.py):
  - All SUBMISSION and REMOTE_WRITE commands check for env var KCA_ALLOW_REMOTE=1
  - If not set, emit {"ok": false, "error": "remote operation requires KCA_ALLOW_REMOTE=1 and human approval", "side_effect": "SUBMISSION"} and exit 2
  - If set, emit a WARNING to stderr: "REMOTE OPERATION: kaggle submit — KCA_ALLOW_REMOTE is set" and proceed (stub only for now)

Layer B — .claude/settings.json hook strengthening:
  - Add to the "ask" list:
      "Bash(python tools/kca/kca.py kaggle*)"
      "Bash(python tools/kca/kca.py run push*)"
  - Add to "deny" list (hard block, not ask):
      "Bash(kaggle competitions submit*)" ← direct CLI bypass prevention
      "Bash(kkr.py submit*)"              ← legacy bypass prevention
      "Bash(python tools/legacy/kkr.py submit*)"
  - Keep existing deny patterns

After implementing:
  KCA_ALLOW_REMOTE= python tools/kca/kca.py kaggle submit --competition x --file /dev/null --message test --json
  → must exit 2 and emit ok=false

  KCA_ALLOW_REMOTE=1 python tools/kca/kca.py kaggle submit --competition x --file /dev/null --message test --json
  → must emit stub warning and ok=true (stub)

Document the two layers in tools/kca/COMMANDS.md under a "Safety" section.
Do NOT git add or commit.
```

---

## Loop Prompt 6 — COMMANDS.md and side-effect documentation

```
Goal: write tools/kca/COMMANDS.md as the canonical side-effect reference.

Required sections:

## Side-effect levels
| Level        | Meaning                                          | Default policy           |
|-------------|--------------------------------------------------|--------------------------|
| READ_ONLY   | No writes anywhere                               | Always allowed           |
| LOCAL_WRITE | Writes only inside the repo/workspace            | Allowed, logged          |
| REMOTE_WRITE| Writes to external service (Kaggle, kernel push) | Requires KCA_ALLOW_REMOTE=1 + human approval |
| SUBMISSION  | Kaggle competition submission                    | Requires KCA_ALLOW_REMOTE=1 + explicit human approval |

## Command table
(One row per kca subcommand, filled in from what exists after Loop Prompt 1–5)

| Command                     | Side-effect  | Wraps legacy tool    | Notes                        |
|-----------------------------|-------------|----------------------|------------------------------|
| kca nb to-py                | LOCAL_WRITE  | nb2py.py             |                              |
| kca nb to-ipynb             | LOCAL_WRITE  | py2nb.py             |                              |
| kca run init                | LOCAL_WRITE  | (native)             | Creates runs/ artifact dir   |
| kca run record-metric       | LOCAL_WRITE  | (native)             |                              |
| kca run list                | READ_ONLY    | (native)             |                              |
| kca kaggle submit           | SUBMISSION   | kkr.py submit        | Blocked without KCA_ALLOW_REMOTE=1 |
| kca kaggle push             | REMOTE_WRITE | kkr.py push          | Blocked without KCA_ALLOW_REMOTE=1 |
| kca kaggle watch            | READ_ONLY    | kkr.py watch         |                              |
| kca kaggle fetch            | READ_ONLY    | kkr.py fetch         |                              |
| kca kaggle list             | READ_ONLY    | kkr.py list          |                              |

## Skill invocation reference
| Skill     | Invocation   | Typical kca commands called           |
|-----------|-------------|---------------------------------------|
| /kg-nb    | /kg-nb      | kca nb to-py, kca nb to-ipynb         |
| /kg-run   | /kg-run     | kca run init, kca run record-metric   |
| /kg-eval  | /kg-eval    | kca eval (future)                     |
| /kg-loop  | /kg-loop    | kca nb + kca run + kca kaggle watch   |

After writing, verify the table is consistent with the actual implemented stubs/commands.
Do NOT git add or commit.
```

---

## Loop Prompt 7 — New skills: /kg-nb and /kg-run

```
Goal: write two new skill SKILL.md files for M1-era kca commands.

File 1: .claude/skills/kg-nb/SKILL.md
Purpose: guide Claude to correctly call `kca nb to-py` and `kca nb to-ipynb`.
Content must include:
- When to use this skill (user asks to convert notebook ↔ script)
- Exact command templates with all flags
- How to interpret the JSON output (ok, dst, written_cells)
- Common failure modes and how to handle them (missing dep, format error)
- Safety note: side_effect = LOCAL_WRITE, no remote calls

File 2: .claude/skills/kg-run/SKILL.md
Purpose: guide Claude to initialize a run artifact directory and record metrics.
Content must include:
- When to use this skill (starting a new experiment)
- Exact command templates: kca run init, kca run record-metric, kca run list
- How to pick a meaningful hypothesis string
- How to interpret run_dir from the JSON output
- Reminder: run_dir goes into experiment notes; never commit runs/ directory

Keep each SKILL.md under 80 lines. No prose padding — write as concise reference cards.
Do NOT git add or commit.
```

---

## Loop Prompt 8 — M1 exit criteria validation

```
Goal: validate that ALL M1 exit criteria are met. This is the final gate before M1 is declared complete.

Run each check and report PASS/FAIL:

1. kca nb wrappers:
   - `python tools/kca/kca.py nb to-ipynb --help` exits 0 (PASS/FAIL)
   - `python tools/kca/kca.py nb to-py --help` exits 0 (PASS/FAIL)
   - Roundtrip smoke: py→ipynb→py preserves a code cell (PASS/FAIL)

2. Artifact layout:
   - `python tools/kca/kca.py run init --competition m1_check --json` exits 0 (PASS/FAIL)
   - Directory runs/m1_check/ exists with meta.json and metrics.json (PASS/FAIL)

3. Approval gate:
   - `KCA_ALLOW_REMOTE= python tools/kca/kca.py kaggle submit --competition x --file /dev/null --message t --json` exits non-zero (PASS/FAIL)
   - settings.json deny list includes direct `kaggle competitions submit*` (PASS/FAIL)

4. Smoke tests:
   - `python -m pytest tests/test_kca_smoke.py -v` all pass (PASS/FAIL with counts)

5. Documentation:
   - tools/kca/COMMANDS.md exists and has side-effect table (PASS/FAIL)
   - .claude/skills/kg-nb/SKILL.md exists (PASS/FAIL)
   - .claude/skills/kg-run/SKILL.md exists (PASS/FAIL)

Output a summary table:
| Check | Result | Notes |
|-------|--------|-------|

If any FAIL: fix the issue and re-run the failing check before reporting done.
If all PASS: output "M1 EXIT CRITERIA MET" and list files changed (for human git review).
Do NOT git add or commit — human will review and commit manually.
```

---

## Running on Arch Linux

### One-time setup

```bash
# From the project root
pip install nbformat pyyaml pytest  # legacy tool deps

# Verify kca entrypoint
python tools/kca/kca.py --help
```

### Running a single loop prompt

```bash
claude "$(cat docs/milestones/m1/loop-prompts.md | sed -n '/## Loop Prompt 1/,/## Loop Prompt 2/p')"
# Or just paste the prompt block directly into the claude CLI
```

### Full autonomous loop (sequential, Arch Linux)

```bash
# Run prompts 1-8 sequentially with a single claude session
# using /loop or manual sequential invocation

# Option A: manual sequential (recommended for first run)
claude < <(cat <<'EOF'
[paste Loop Prompt 1 here]
EOF
)

# Option B: feed all prompts as a session plan
claude "
First, execute Loop Prompt 1 (kca skeleton) fully.
Then without stopping, execute Loop Prompt 2 (nb wrappers).
Then Loop Prompt 3 (artifact layout).
Then Loop Prompt 4 (smoke tests).
Then Loop Prompt 5 (approval gates).
Then Loop Prompt 6 (COMMANDS.md).
Then Loop Prompt 7 (skills).
Then Loop Prompt 8 (exit criteria validation).
Do not commit anything. Report result of each loop inline.
Reference: docs/milestones/m1/loop-prompts.md for the full spec of each prompt.
"
```

### Recommended settings.json additions for autonomous M1 loop

Add to the `allow` list in `.claude/settings.json`:
```json
"Bash(python tools/kca/kca.py*)",
"Bash(python tools/legacy/nb2py.py*)",
"Bash(python tools/legacy/py2nb.py*)",
"Bash(python tools/legacy/nb2test.py*)",
"Bash(find tools*)",
"Bash(find tests*)",
"Bash(find runs*)",
"Bash(ls *)",
"Bash(mkdir *)",
"Bash(python -m pytest tests/test_kca_smoke*)"
```
