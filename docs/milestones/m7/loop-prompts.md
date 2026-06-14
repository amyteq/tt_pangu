# M7 Loop Prompts

_KCA CLI architecture — command / skill / tool / job / permission policy._
_For sequential autonomous execution on Arch Linux._
_Prerequisite: M6 exit criteria confirmed met (see `docs/milestones/m6/final-review.md`)._

---

## M7 at a glance

M7 gives the KCA platform a stable, inspectable CLI architecture with four
explicit layers:

| Layer | Role |
|---|---|
| **Command** | Deterministic CLI/API entry points (`kca job run`, `kca decision approve`). Already partially implemented. |
| **Skill** | Agent-facing workflow recipes stored in `.kca/skills/<name>/SKILL.md` with YAML frontmatter. New. |
| **Tool** | Executable actions with schema, timeout, approval policy label, sandbox metadata, and audit logging. New registry. |
| **Job** | Durable records that run a skill through the agent loop with budget, turn, cost, runtime limits, and decision gates. Already in DB; M7 wires the CLI surface. |

The key new deliverables are:

1. **Skill loader** — reads `.kca/skills/<name>/SKILL.md`, parses YAML
   frontmatter, performs `$arg` substitution, and resolves `approval-policy`
   from `.kca/permissions/<profile>.yaml`.
2. **Tool registry** — `tools/kca/agent/tool_executor.py` with tool metadata
   (schema, side-effect level, approval label) and policy-gated execution.
3. **Permission policy layer** — `tools/kca/agent/permission_policy.py`
   resolves `allow | ask | deny` for any `(operation, mode)` pair from a
   structured YAML/JSON policy file — same semantics as Claude Code's
   `settings.json` but product-level and data-driven.
4. **`kca skill` subcommand** — `list / show / run [--dry-run]` surface.
5. **Seed skills** — `run-milestone`, `triage-log`, `prepare-submission`,
   `review-pr` under `.kca/skills/`.
6. **CI fix** — audit `.github/workflows/test.yml` failures and make the
   `no-db + lint` jobs green on main.

DB and sandbox notes carry over from M6:

```bash
SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
KCA_DB_TARGET=local
```

Container IP may change on `docker compose down/up`; refresh with:
```bash
docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

DB calls require `dangerouslyDisableSandbox: true`; cloud LLM calls stay in
the sandbox.

---

## M7 task summary

| Task | Goal | Loop Prompt |
|---|---|---|
| M7-T000 | Audit + repair `.github/workflows/` — fix failing CI checks | Prompt 0 |
| M7-T001 | Skill loader — `.kca/skills/<name>/SKILL.md` + YAML frontmatter + arg substitution | Prompt 1 |
| M7-T002 | Command registry — declarative subcommand registration | Prompt 2 |
| M7-T003 | Tool registry — tool metadata, approval labels, sandbox metadata | Prompt 3 |
| M7-T004 | Permission policy layer — allow/ask/deny from YAML/JSON policy records | Prompt 4 |
| M7-T005 | `kca skill list / show / run [--dry-run]` CLI | Prompt 5 |
| M7-T006 | Audit logging — record every tool execution + policy decision | Prompt 6 |
| M7-T007 | Seed `.kca/skills/` with 4 workflow recipes | Prompt 7 |
| M7-T008 | `tests/test_m7_smoke.py` (12–15 tests, no credentials) | Prompt 8 |
| M7-T009 | Architecture doc `docs/architecture/kca-cli-architecture.md` | Prompt 9 |
| M7-T010 | M7 exit criteria + `docs/milestones/m7/final-review.md` | Prompt 10 |

---

## Loop Prompt 0 — CI repair (M7-T000)

```
Read:
1. .github/workflows/test.yml
2. pyproject.toml   (dev extras, entry points)
3. python -m pytest tests/ -v --tb=short 2>&1 | tail -40   (current local state)
4. docs/milestones/README.md   (M7 section)

Goal: make the GitHub Actions `no-db` and `lint` jobs pass on the current
main branch without requiring a live DB, Kaggle credentials, or GPU endpoints.
The `live-db` job is allowed to skip on forks; it must pass on push to main.

Step 1 — run the test suite locally and catalogue every failure:
  python -m pytest tests/ -v --tb=short 2>&1 | grep -E "FAILED|ERROR|error" | head -30

Step 2 — run ruff and capture failures:
  ruff check . --output-format=concise 2>&1 | head -30
  ruff format --check . 2>&1 | head -20

Step 3 — fix each failure in turn:
  - If a test imports a missing module: add the module stub or fix the import.
  - If a test calls a missing function: add the function or mark as xfail with a clear message.
  - If ruff reports lint errors: fix them (prefer ruff --fix for style-only issues).
  - If ruff reports format issues: run ruff format . (not --check).
  - If a test requires a real DB and is not marked @pytest.mark.db: add the mark
    and confirm it skips when SUPABASE_DB_URL is unset.

Step 4 — validate the workflow file itself:
  python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml')); print('YAML ok')"

Step 5 — final local simulation:
  python -m pytest tests/ -v -m "not db"   → 0 failures, 0 errors
  ruff check .                              → 0 issues
  ruff format --check .                    → 0 issues

Do NOT git add or commit. Report: count of failures before/after, list of
fixes applied, final pytest + ruff results.
```

---

## Loop Prompt 1 — Skill loader (M7-T001)

```
Read:
1. docs/milestones/README.md   (M7 section — four-layer model + skill format)
2. docs/meeting-notes/2026-05-21-r1.md   (§1–3: skill YAML frontmatter design)
3. tools/kca/kca.py   (current subcommand registration pattern)
4. src/worker/_types.py   (JobPolicy shape, for approval-policy integration)

Goal: implement tools/kca/agent/skill_loader.py.

Directory: .kca/skills/<name>/SKILL.md
YAML frontmatter fields (all optional except `name` and `description`):
  name: str
  description: str
  version: str (default "1.0")
  argument-hint: str
  arguments: list[str]   # positional arg names for $arg substitution
  allowed-tools: list[str]
  approval-policy: str   # profile name in .kca/permissions/<profile>.yaml
  disable-model-invocation: bool (default false)
  tags: list[str]

Implementation:
  @dataclass
  class SkillMeta:
      name: str
      description: str
      version: str
      argument_hint: str
      arguments: list[str]
      allowed_tools: list[str]
      approval_policy: str
      disable_model_invocation: bool
      tags: list[str]
      body: str            # everything after the frontmatter separator

  @dataclass
  class Skill:
      meta: SkillMeta
      path: Path           # absolute path to SKILL.md
      rendered_body: str   # body after $arg substitution

  def load_skill(name: str, *, skills_root: Path | None = None) -> Skill
      # skills_root defaults to repo_root / ".kca" / "skills"
      # Raises FileNotFoundError if SKILL.md is missing.
      # Raises ValueError if frontmatter is malformed.

  def list_skills(*, skills_root: Path | None = None) -> list[SkillMeta]
      # Walks .kca/skills/ and loads every SKILL.md.

  def render_skill(skill: Skill, args: dict[str, str]) -> str
      # Returns body with $argname substituted from args dict.
      # Raises ValueError if a declared argument is missing.

Rules:
  - Parse frontmatter between the first and second `---` separators only.
  - Body begins on the line after the closing `---`.
  - If no frontmatter delimiters: entire content is body, meta is defaults.
  - Never import or execute the skill body.

Verification:
  # Create a minimal fixture skill:
  mkdir -p .kca/skills/_test_fixture
  cat > .kca/skills/_test_fixture/SKILL.md << 'EOF'
  ---
  name: _test_fixture
  description: Fixture skill for unit tests.
  arguments:
    - task_path
  allowed-tools:
    - read_file
    - bash
  approval-policy: permissive-dev
  ---
  Run task at $task_path.
  Check output.
  EOF

  python -c "
  from tools.kca.agent.skill_loader import load_skill, list_skills, render_skill
  s = load_skill('_test_fixture')
  assert s.meta.name == '_test_fixture'
  assert 'task_path' in s.meta.arguments
  assert 'read_file' in s.meta.allowed_tools
  rendered = render_skill(s, {'task_path': 'docs/tasks/m7/M7-T001.md'})
  assert 'docs/tasks/m7/M7-T001.md' in rendered
  print('PASS load + render')
  skills = list_skills()
  assert any(m.name == '_test_fixture' for m in skills)
  print('PASS list')
  "

  python -c "
  from tools.kca.agent.skill_loader import load_skill
  try:
      load_skill('__nonexistent__')
      print('FAIL: should raise')
  except FileNotFoundError:
      print('PASS FileNotFoundError on missing skill')
  "

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: each verification + fixture skill created.
```

---

## Loop Prompt 2 — Command registry (M7-T002)

```
Read:
1. tools/kca/kca.py   (build_parser, current add_parsers pattern)
2. tools/kca/agent/skill_loader.py   (from Prompt 1)
3. docs/milestones/README.md   (M7 — Command vs Skill distinction)
4. docs/meeting-notes/2026-05-21-r1.md   (§2: KCA CLI command suggestions)

Goal: implement tools/kca/agent/command_registry.py — a central registry that
records metadata about every kca subcommand group.

@dataclass
class CommandSpec:
    name: str               # e.g. "skill", "job", "kaggle"
    description: str
    side_effect: str        # READ_ONLY | LOCAL_WRITE | REMOTE_WRITE | SUBMISSION
    requires_db: bool
    add_parsers_fn: Callable  # the add_parsers function from the module

class CommandRegistry:
    def register(self, spec: CommandSpec) -> None
    def get(self, name: str) -> CommandSpec | None
    def list_all(self) -> list[CommandSpec]

REGISTRY: CommandRegistry  # module-level singleton

Populate REGISTRY at import time by registering all existing kca subcommand
groups with accurate side_effect and requires_db values:
  nb        → READ_ONLY, requires_db=False
  run       → LOCAL_WRITE, requires_db=True
  kaggle    → SUBMISSION (most dangerous op), requires_db=True
  eval      → READ_ONLY, requires_db=False
  workspace → LOCAL_WRITE, requires_db=True
  decisions → LOCAL_WRITE, requires_db=True
  competition → LOCAL_WRITE, requires_db=True
  research  → LOCAL_WRITE, requires_db=True
  local     → READ_ONLY, requires_db=False
  review    → READ_ONLY, requires_db=True
  skill     → READ_ONLY, requires_db=False   (new; from Prompt 5)

Update kca.py to build_parser() using REGISTRY.list_all() instead of the
current hardcoded imports, so new commands auto-register.

Verification:
  python -c "
  from tools.kca.agent.command_registry import REGISTRY
  specs = REGISTRY.list_all()
  names = {s.name for s in specs}
  assert 'kaggle' in names, names
  assert 'decisions' in names, names
  kaggle_spec = REGISTRY.get('kaggle')
  assert kaggle_spec.side_effect == 'SUBMISSION', kaggle_spec.side_effect
  print(f'PASS: {len(specs)} commands registered')
  for s in sorted(specs, key=lambda x: x.name):
      print(f'  {s.name:15} {s.side_effect:12} db={s.requires_db}')
  "

  # kca CLI must still work end-to-end after the refactor:
  python tools/kca/kca.py --help   → lists all subcommand groups
  python tools/kca/kca.py run list --json   → ok

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: registry list + CLI help + test results.
```

---

## Loop Prompt 3 — Tool registry (M7-T003)

```
Read:
1. tools/kca/agent/skill_loader.py   (SkillMeta.allowed_tools)
2. tools/kca/agent/command_registry.py   (CommandSpec.side_effect pattern)
3. docs/milestones/README.md   (M7 — Tool layer description + permission policy design)
4. docs/meeting-notes/2026-05-21-r1.md   (§2 tools/kca/agent/tool_executor.py sketch)
5. src/worker/worker.py   (existing tool call pattern in the agent loop)

Goal: implement tools/kca/agent/tool_registry.py.

@dataclass
class ToolSpec:
    name: str              # e.g. "bash", "read_file", "edit_file", "kaggle_submit"
    description: str
    side_effect: str       # READ_ONLY | LOCAL_WRITE | REMOTE_WRITE | SUBMISSION
    approval_label: str    # "allow" | "ask" | "deny" — default when no policy overrides
    timeout_s: int         # default execution timeout
    sandbox: str           # "sandboxed" | "unsandboxed" | "isolated_workspace"
    tags: list[str]        # e.g. ["filesystem", "network", "kaggle"]
    input_schema: dict     # minimal JSON Schema for the tool's input

TOOL_REGISTRY: dict[str, ToolSpec]

Populate TOOL_REGISTRY with at minimum these tools:
  bash              LOCAL_WRITE  ask     30s  unsandboxed
  read_file         READ_ONLY    allow   5s   sandboxed
  edit_file         LOCAL_WRITE  allow   10s  sandboxed
  write_file        LOCAL_WRITE  allow   10s  sandboxed
  web_fetch         READ_ONLY    allow   30s  sandboxed
  web_search        READ_ONLY    allow   30s  sandboxed
  git_commit        LOCAL_WRITE  allow   30s  sandboxed
  git_push          REMOTE_WRITE ask     30s  unsandboxed
  gh_pr_create      REMOTE_WRITE allow   30s  unsandboxed
  gh_pr_merge       REMOTE_WRITE ask     30s  unsandboxed
  kaggle_submit     SUBMISSION   ask     60s  unsandboxed
  kaggle_push       SUBMISSION   ask     60s  unsandboxed
  supabase_migrate  REMOTE_WRITE ask     60s  unsandboxed
  run_tests         LOCAL_WRITE  allow   120s sandboxed
  litellm_call      LOCAL_WRITE  allow   120s sandboxed
  create_artifact   LOCAL_WRITE  allow   10s  sandboxed

Helper functions:
  def get_tool(name: str) -> ToolSpec | None
  def list_tools(*, side_effect: str | None = None, tag: str | None = None) -> list[ToolSpec]
  def default_decision(tool_name: str) -> str   # returns approval_label or "ask" for unknowns

Verification:
  python -c "
  from tools.kca.agent.tool_registry import TOOL_REGISTRY, get_tool, default_decision
  assert get_tool('kaggle_submit').side_effect == 'SUBMISSION'
  assert get_tool('read_file').approval_label == 'allow'
  assert default_decision('kaggle_submit') == 'ask'
  assert default_decision('__unknown__') == 'ask'
  print(f'PASS: {len(TOOL_REGISTRY)} tools registered')
  "

  python -c "
  from tools.kca.agent.tool_registry import list_tools
  submissions = list_tools(side_effect='SUBMISSION')
  assert len(submissions) >= 2
  print(f'PASS: {[t.name for t in submissions]} are SUBMISSION tools')
  "

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: registry count, SUBMISSION tools, test results.
```

---

## Loop Prompt 4 — Permission policy layer (M7-T004)

```
Read:
1. tools/kca/agent/tool_registry.py   (ToolSpec.approval_label, TOOL_REGISTRY)
2. tools/kca/agent/skill_loader.py   (SkillMeta.approval_policy)
3. docs/milestones/README.md   (M7 — permission policy design block)
4. docs/meeting-notes/2026-05-21-r1.md   (§2 permissions/ layout, §11 policy JSON)
5. tools/kca/kg.py   (_check_approval_gate pattern for comparison)

Goal: implement tools/kca/agent/permission_policy.py.

PolicyRecord (maps to a JSON policy record per docs/milestones/README.md M7):
  operation: str
  default_decision: str      # "allow" | "ask" | "deny"
  reason: str
  allowed_in_modes: list[str]
  audit_required: bool

PermissionPolicy:
  Loaded from a YAML file (e.g. .kca/permissions/default.yaml).
  Each policy file is a list of PolicyRecord objects.
  resolve(operation, mode="default") -> str
    Returns "allow", "ask", or "deny". Priority:
      1. Explicit deny in policy → "deny" (never overridden by mode).
      2. operation in allowed_in_modes for the given mode → "allow".
      3. default_decision from matching PolicyRecord.
      4. ToolSpec.approval_label for the operation name (if registered).
      5. "ask" (safe default).

Also write three seed policy YAML files:

.kca/permissions/default.yaml:
  - All SUBMISSION operations: ask
  - git_push, gh_pr_create: allow
  - gh_pr_merge: ask
  - supabase_migrate: ask
  - bash: ask
  - All filesystem read/write within workspace: allow

.kca/permissions/permissive-dev.yaml:
  - kaggle_submit, kaggle_push: ask (still gated, even in dev)
  - supabase_migrate (remote): ask
  - gh_pr_merge: ask
  - Everything else normally covered by default: allow

.kca/permissions/competition-runner.yaml:
  - kaggle_submit in mode competition-finalization: allow
  - kaggle_submit in mode human-approved: allow
  - All other submission ops: ask
  - budget_exceeded: deny

Helpers:
  def load_policy(profile: str, *, permissions_root: Path | None = None) -> PermissionPolicy
  def resolve_for_skill(skill_meta: SkillMeta, operation: str, mode: str = "default") -> str

Verification:
  python -c "
  from tools.kca.agent.permission_policy import load_policy, resolve_for_skill
  from tools.kca.agent.skill_loader import load_skill

  # default policy
  p = load_policy('default')
  assert p.resolve('kaggle_submit') == 'ask', p.resolve('kaggle_submit')
  assert p.resolve('read_file') == 'allow', p.resolve('read_file')
  assert p.resolve('gh_pr_merge') == 'ask', p.resolve('gh_pr_merge')
  print('PASS default policy')

  # permissive-dev: bash allowed
  pd = load_policy('permissive-dev')
  assert pd.resolve('bash') == 'allow', pd.resolve('bash')
  assert pd.resolve('kaggle_submit') == 'ask'
  print('PASS permissive-dev policy')

  # competition-runner: submit allowed in competition-finalization mode
  cr = load_policy('competition-runner')
  assert cr.resolve('kaggle_submit', mode='competition-finalization') == 'allow'
  assert cr.resolve('kaggle_submit', mode='default') == 'ask'
  print('PASS competition-runner policy')
  "

  # resolve_for_skill reads the skill's approval-policy field:
  python -c "
  from tools.kca.agent.permission_policy import resolve_for_skill
  from tools.kca.agent.skill_loader import load_skill
  s = load_skill('_test_fixture')   # has approval-policy: permissive-dev
  assert resolve_for_skill(s.meta, 'bash') == 'allow'
  print('PASS resolve_for_skill')
  "

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: all policy assertions + test results.
```

---

## Loop Prompt 5 — `kca skill` CLI (M7-T005)

```
Read:
1. tools/kca/agent/skill_loader.py   (load_skill, list_skills, render_skill)
2. tools/kca/agent/permission_policy.py   (resolve_for_skill, load_policy)
3. tools/kca/agent/tool_registry.py   (list_tools, default_decision)
4. tools/kca/kca.py   (build_parser, add_parsers pattern)
5. tools/kca/decisions.py   (--json output style)

Goal: implement tools/kca/skill.py with `list`, `show`, and `run` subcommands;
register with kca.py.

kca skill list [--json] [--tag <tag>]
  Output: list of {name, description, version, approval_policy, tags} dicts.
  Human format: table with name | description | policy.

kca skill show <name> [--json]
  Output: full parsed metadata dict + rendered frontmatter fields + body
  (body not rendered — raw SKILL.md body).

kca skill run <name> [--arg key=value ...] [--mode <mode>] [--dry-run] [--json]
  Workflow:
  1. load_skill(name)
  2. Parse --arg pairs into a dict; validate all declared arguments are present.
     If a declared argument is missing: error, list required args.
  3. render_skill(skill, arg_dict) → rendered_body
  4. For each tool in SkillMeta.allowed_tools:
       decision = resolve_for_skill(skill.meta, tool, mode=args.mode)
       record: {tool, decision, reason}
  5. --dry-run output (--json):
     {
       "ok": true,
       "dry_run": true,
       "skill": <name>,
       "mode": <mode>,
       "args": <dict>,
       "tool_permissions": [{"tool": <t>, "decision": <d>, "reason": <r>}, ...],
       "rendered_prompt": <rendered_body>,
       "side_effect": "READ_ONLY"
     }
  6. Without --dry-run: print rendered_body and tool_permissions, then emit
     {"ok": true, "dry_run": false, "note": "actual execution not implemented in M7 — use kca job run"}
     (Actual job execution is M8 scope; M7 delivers the CLI surface only.)

Parsers:
  sub.add_parser("skill")  → skill_parser with subparsers: list / show / run

Register in kca.py:
  import skill as skill_mod
  skill_mod.add_parsers(sub)

Verification:
  python tools/kca/kca.py skill list
    → prints table with at least _test_fixture row (created in T001)

  python tools/kca/kca.py skill list --json
    → {"ok": true, "skills": [...], "side_effect": "READ_ONLY"}

  python tools/kca/kca.py skill show _test_fixture
    → prints name, description, allowed-tools, approval-policy, body

  python tools/kca/kca.py skill show _test_fixture --json
    → {"ok": true, "skill": {"name": "_test_fixture", ...}, "side_effect": "READ_ONLY"}

  python tools/kca/kca.py skill run _test_fixture \
    --arg task_path=docs/tasks/m7/M7-T001.md --dry-run --json
    → {
        "ok": true, "dry_run": true, "skill": "_test_fixture",
        "tool_permissions": [{"tool": "read_file", ...}, {"tool": "bash", ...}],
        "rendered_prompt": "Run task at docs/tasks/m7/M7-T001.md.\nCheck output.",
        "side_effect": "READ_ONLY"
      }

  # Missing required arg → error
  python tools/kca/kca.py skill run _test_fixture --dry-run --json
    → exit code != 0 or {"ok": false, "error": "missing argument: task_path"}

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: each verification, exit code behaviour.
```

---

## Loop Prompt 6 — Audit logging (M7-T006)

```
Read:
1. tools/kca/agent/permission_policy.py   (resolve, PolicyRecord)
2. tools/kca/agent/tool_registry.py   (ToolSpec.audit_required equivalent: approval_label != "allow")
3. tools/kca/db.py   (append_job_event pattern)
4. src/worker/telemetry.py   (OTEL span structure from M6)
5. tools/kca/agent/skill_loader.py   (SkillMeta.approval_policy)

Goal: implement tools/kca/agent/audit.py — records policy decisions for tool
executions, outside the worker agent loop (M7 scope: CLI-level audit).

AuditRecord:
  timestamp: str (ISO 8601)
  session_id: str (uuid4, stable per kca process invocation)
  skill_name: str | None
  tool_name: str
  operation: str
  decision: str   # allow | ask | deny
  mode: str
  policy_profile: str
  audit_required: bool
  args_hash: str  # sha256 of serialised args, not the args themselves

AuditLogger:
  backend: "file" | "db" | "both"
  file_path: Path (default: .agent/audit.jsonl)
  db_available: bool

  def record(self, rec: AuditRecord) -> None
    - Appends a JSON line to file_path (never raises; on error: stderr warning).
    - If db_available: append_job_event(job_id=None, event_type="tool_audit",
        event_data=rec.__dict__) — best-effort.

  def log_policy_decision(self, *, tool: str, operation: str, decision: str,
                           skill_name: str | None = None, mode: str = "default",
                           policy_profile: str = "default",
                           args: dict | None = None) -> AuditRecord

Wire into kca skill run (non-dry-run path only):
  For each tool in allowed_tools: log_policy_decision(...).
  Write .agent/audit.jsonl line.

Provide a CLI view:
  kca tool audit [--limit 20] [--json]
  Add "tool" group to kca.py:
    kca tool list [--tag <tag>] [--json]       → TOOL_REGISTRY contents
    kca tool audit [--limit 20] [--json]       → last N lines of .agent/audit.jsonl
    kca tool doctor [--json]                   → check all tools in TOOL_REGISTRY have
                                                  valid side_effect, timeout_s, sandbox

Verification:
  # Trigger a skill run (non-dry-run) to produce an audit record:
  python tools/kca/kca.py skill run _test_fixture \
    --arg task_path=docs/tasks/m7/M7-T001.md --json
    → ok + note about M7 non-execution

  # Audit log produced:
  test -f .agent/audit.jsonl && python -c "
  import json
  lines = open('.agent/audit.jsonl').readlines()
  assert len(lines) >= 1
  rec = json.loads(lines[-1])
  assert rec['tool_name'] in ('read_file', 'bash')
  assert rec['decision'] in ('allow', 'ask', 'deny')
  print('PASS audit record:', rec['tool_name'], rec['decision'])
  "

  python tools/kca/kca.py tool list --json
    → {"ok": true, "tools": [...], "side_effect": "READ_ONLY"}

  python tools/kca/kca.py tool doctor --json
    → {"ok": true, "tools_checked": <N>, "issues": []}

  python tools/kca/kca.py tool audit --json
    → {"ok": true, "records": [...], "side_effect": "READ_ONLY"}

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: audit.jsonl content + tool subcommands.
```

---

## Loop Prompt 7 — Seed skills (M7-T007)

```
Read:
1. tools/kca/agent/skill_loader.py   (SkillMeta fields)
2. tools/kca/agent/permission_policy.py   (profile names)
3. docs/meeting-notes/2026-05-21-r1.md   (§2 KCA skill example + four workflow recipes)
4. CLAUDE.md   (operating principles — untrusted data, one-change-at-a-time discipline)
5. docs/milestones/README.md   (M7 seed skills list)

Goal: create four SKILL.md files under .kca/skills/.

---  .kca/skills/run-milestone/SKILL.md  ---
---
name: run-milestone
description: Execute a milestone task end-to-end in an isolated workspace until acceptance criteria pass or blockers are documented.
version: "1.0"
argument-hint: "[task-md-path]"
arguments:
  - task_path
allowed-tools:
  - read_file
  - edit_file
  - write_file
  - bash
  - git_commit
  - gh_pr_create
  - run_tests
  - litellm_call
  - create_artifact
approval-policy: permissive-dev
tags:
  - platform-dev
  - milestone
---

Execute milestone task `$task_path`.

Workflow:
1. Read $task_path and CLAUDE.md.
2. Inspect the current architecture and test state.
3. Create or use an isolated workspace/branch.
4. Make the smallest coherent change that advances the acceptance criteria.
5. Run relevant tests, lint, type checks, and smoke tests.
6. Iterate until acceptance criteria pass or a decision gate is reached.

Produce on completion:
- Summary of changes made.
- List of changed files.
- Test results.
- Risks and known regressions.
- Unresolved blockers.
- Recommended next task.

Stop conditions:
- All acceptance criteria pass.
- A decision gate is reached (create a decision record instead of proceeding).
- Max turns, budget, or time is reached.
---

---  .kca/skills/triage-log/SKILL.md  ---
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
---

---  .kca/skills/prepare-submission/SKILL.md  ---
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
5. Create a decision record:
   `kca decision create --operation kaggle_submit --run-id <id> --reason "CV:<score>"`
6. Print the decision record ID. Do NOT submit — human must approve via
   `kca decision approve <id>`.

Stop if:
- submission.csv is missing or malformed → fail with clear error.
- cv_score is missing → warn and stop.
---

---  .kca/skills/review-pr/SKILL.md  ---
---
name: review-pr
description: Review a pull request for correctness, test coverage, and safety alignment with CLAUDE.md rules.
version: "1.0"
argument-hint: "[pr-number-or-branch]"
arguments:
  - pr_ref
allowed-tools:
  - read_file
  - bash
  - web_fetch
  - run_tests
  - litellm_call
approval-policy: permissive-dev
tags:
  - code-review
  - platform-dev
---

Review PR or branch `$pr_ref`.

Steps:
1. `gh pr diff $pr_ref` or `git diff main...$pr_ref` — collect the diff.
2. Read changed files in full.
3. Read CLAUDE.md safety boundaries.
4. Assess: correctness, test coverage, security, CLAUDE.md alignment.
5. Run tests: `python -m pytest tests/ -v -m "not db"`.
6. Produce a structured review:
   - Summary of changes.
   - Issues found (blocking / non-blocking).
   - Test results.
   - Security concerns.
   - Recommendation: approve / request-changes / needs-human-review.
---

Verification:
  python tools/kca/kca.py skill list --json
    → skills list includes run-milestone, triage-log, prepare-submission, review-pr

  for skill in run-milestone triage-log prepare-submission review-pr; do
    python tools/kca/kca.py skill show $skill | grep -q "name:" && echo "PASS $skill" || echo "FAIL $skill"
  done

  # dry-run each seed skill (only run-milestone and review-pr take args):
  python tools/kca/kca.py skill run run-milestone \
    --arg task_path=docs/tasks/m7/M7-T001.md --dry-run --json
    → ok=true, rendered_prompt contains "docs/tasks/m7/M7-T001.md"

  python tools/kca/kca.py skill run triage-log \
    --arg job_id=00000000-0000-0000-0000-000000000000 --dry-run --json
    → ok=true

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: skill list output + dry-run results.
```

---

## Loop Prompt 8 — M7 smoke tests (M7-T008)

```
Read:
1. tests/test_m6_smoke.py   (style, env-scrub helpers, skip pattern)
2. tools/kca/agent/skill_loader.py
3. tools/kca/agent/command_registry.py
4. tools/kca/agent/tool_registry.py
5. tools/kca/agent/permission_policy.py
6. tools/kca/agent/audit.py
7. tools/kca/skill.py

Goal: create tests/test_m7_smoke.py with 12–15 pytest tests; all pass
without ANTHROPIC_API_KEY, SUPABASE_DB_URL, KAGGLE_KEY, or GPU endpoints.

Required tests (use these names verbatim):
  1.  test_skill_load_fixture()
        load_skill('_test_fixture'); assert meta.name == '_test_fixture'
  2.  test_skill_load_missing()
        load_skill('__no_such__') raises FileNotFoundError
  3.  test_skill_render_substitution(tmp_path)
        write a SKILL.md with $foo in body; render_skill(s, {'foo':'bar'}) → 'bar' in body
  4.  test_skill_render_missing_arg(tmp_path)
        declared arg not provided → ValueError
  5.  test_skill_list_includes_seeds()
        list_skills() returns at least: run-milestone, triage-log,
        prepare-submission, review-pr, _test_fixture
  6.  test_command_registry_all_registered()
        REGISTRY.list_all() names ⊇ {'kaggle','decisions','skill','tool'}
  7.  test_command_registry_side_effects()
        REGISTRY.get('kaggle').side_effect == 'SUBMISSION'
        REGISTRY.get('nb').side_effect == 'READ_ONLY'
  8.  test_tool_registry_submission_tools()
        list_tools(side_effect='SUBMISSION') contains at least kaggle_submit, kaggle_push
  9.  test_tool_registry_unknown_default()
        default_decision('__unknown__') == 'ask'
  10. test_permission_policy_default()
        load_policy('default').resolve('kaggle_submit') == 'ask'
        load_policy('default').resolve('read_file') == 'allow'
  11. test_permission_policy_permissive_dev()
        load_policy('permissive-dev').resolve('bash') == 'allow'
        load_policy('permissive-dev').resolve('kaggle_submit') == 'ask'
  12. test_permission_policy_competition_runner_mode()
        load_policy('competition-runner').resolve('kaggle_submit',
            mode='competition-finalization') == 'allow'
        load_policy('competition-runner').resolve('kaggle_submit',
            mode='default') == 'ask'
  13. test_kca_skill_list_json(tmp_path)
        subprocess kca skill list --json → exit 0, valid JSON, 'skills' key present
  14. test_kca_skill_run_dry_run_json(tmp_path)
        subprocess kca skill run _test_fixture
          --arg task_path=x --dry-run --json
        → exit 0, ok=true, rendered_prompt contains 'x'
  15. test_audit_logger_writes_file(tmp_path)
        AuditLogger(backend='file', file_path=tmp_path/'audit.jsonl').log_policy_decision(
            tool='bash', operation='bash', decision='ask', mode='default',
            policy_profile='permissive-dev')
        → file exists, JSON line with decision='ask'

Verification:
  python -m pytest tests/test_m7_smoke.py -v   → all pass
  python -m pytest tests/ -v -m "not db"        → 0 failures

Do NOT git add or commit. Report: count + per-test status line.
```

---

## Loop Prompt 9 — Architecture documentation (M7-T009)

```
Read:
1. docs/milestones/README.md   (M7 section — full four-layer table + directory layout)
2. docs/meeting-notes/2026-05-21-r1.md   (§1–3)
3. tools/kca/agent/skill_loader.py   (SkillMeta fields)
4. tools/kca/agent/tool_registry.py   (ToolSpec fields)
5. tools/kca/agent/permission_policy.py   (PolicyRecord, PermissionPolicy)
6. .kca/skills/run-milestone/SKILL.md   (representative example)

Goal: write docs/architecture/kca-cli-architecture.md.

Required sections:

## Overview
One-paragraph product context. KCA CLI is the deterministic operator-facing
layer; skills are the agent-facing layer. Both share the same tool registry
and permission policy.

## Four layers

Table: Layer | Implemented in | Invocation | Side-effect control
- Command: tools/kca/*.py | kca <group> <cmd> | CommandSpec.side_effect
- Skill: .kca/skills/*/SKILL.md | kca skill run <name> | approval-policy profile
- Tool: tools/kca/agent/tool_registry.py | called by agent worker | ToolSpec.approval_label
- Job: src/worker/ + Supabase | kca job run | JobPolicy + budget tracker

## Skill format
Document all YAML frontmatter fields with their types and defaults.
Show a minimal example.

## Tool registry
List the fields of ToolSpec. Explain side_effect levels (READ_ONLY → SUBMISSION).
Note that SUBMISSION tools always default to "ask".

## Permission policy
Explain the policy resolution priority:
  deny > mode-specific allow > default_decision > ToolSpec.approval_label > "ask"
Show the PolicyRecord JSON example from docs/milestones/README.md M7.
Name the three shipped profiles: default, permissive-dev, competition-runner.

## Audit trail
Explain .agent/audit.jsonl and how it relates to agent_job_events.
Note: args_hash not args, to avoid logging sensitive data.

## Decision gate UI flow
Show the example from docs/milestones/README.md M7 / docs/meeting-notes/2026-05-21-r1.md §11:
  "Agent reached decision gate: Submit run kca-run-123..."

## Directory layout
Reproduce the layout table from docs/milestones/README.md M7.

## Adding a new command
Step-by-step: create module → add CommandSpec to REGISTRY → add_parsers → done.

## Adding a new skill
Step-by-step: mkdir .kca/skills/<name>/ → write SKILL.md → kca skill list shows it.

## Adding a new tool
Step-by-step: add ToolSpec to TOOL_REGISTRY → update permission policy if needed.

Verification:
  test -f docs/architecture/kca-cli-architecture.md
  wc -l docs/architecture/kca-cli-architecture.md   → at least 80 lines
  # All section headings present:
  for heading in "Overview" "Four layers" "Skill format" "Tool registry" \
                 "Permission policy" "Audit trail" "Decision gate" \
                 "Directory layout" "Adding a new command" "Adding a new skill" \
                 "Adding a new tool"; do
    grep -q "$heading" docs/architecture/kca-cli-architecture.md \
      && echo "PASS $heading" || echo "FAIL $heading"
  done

  python -m pytest tests/ -v -m "not db"   → 0 failures

Do NOT git add or commit. Report: line count, section headings PASS/FAIL.
```

---

## Loop Prompt 10 — M7 exit criteria (M7-T010)

```
Goal: verify ALL M7 exit criteria. Gate before M7 is declared complete.

Run each check and report PASS / FAIL / SKIP:

CI:
 1. python -m pytest tests/ -v -m "not db"   → 0 failures, 0 errors
 2. ruff check .                              → 0 issues
 3. ruff format --check .                     → 0 issues
 4. python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"
    → no exception; jobs no-db, live-db, lint all present

Skill loader:
 5. load_skill('run-milestone') → name == 'run-milestone'
 6. load_skill('triage-log')    → arguments == ['job_id']
 7. load_skill('prepare-submission') → approval_policy == 'default'
 8. load_skill('review-pr')    → 'bash' in allowed_tools (or equivalent)
 9. load_skill('__missing__') → FileNotFoundError
10. render_skill(s, {'task_path': 'x'}) → 'x' in rendered body

Command registry:
11. REGISTRY.list_all() includes skill, tool, kaggle, decisions
12. REGISTRY.get('kaggle').side_effect == 'SUBMISSION'

Tool registry:
13. list_tools(side_effect='SUBMISSION') ⊇ {kaggle_submit, kaggle_push}
14. default_decision('__unknown__') == 'ask'

Permission policy:
15. load_policy('default').resolve('kaggle_submit') == 'ask'
16. load_policy('permissive-dev').resolve('bash') == 'allow'
17. load_policy('competition-runner').resolve('kaggle_submit',
        mode='competition-finalization') == 'allow'

kca skill CLI:
18. kca skill list --json → ok=true, list includes the 4 seed skills
19. kca skill show run-milestone --json → ok=true, meta fields present
20. kca skill run run-milestone --arg task_path=docs/tasks/m7/M7-T001.md --dry-run --json
    → ok=true, rendered_prompt contains 'docs/tasks/m7/M7-T001.md',
      tool_permissions list non-empty
21. kca skill run _test_fixture --dry-run --json (missing --arg)
    → ok=false or exit != 0

kca tool CLI:
22. kca tool list --json → ok=true, ≥ 15 tools
23. kca tool doctor --json → ok=true, issues=[]
24. kca tool audit --json → ok=true (may be empty)

Audit:
25. Running kca skill run _test_fixture --arg task_path=x writes .agent/audit.jsonl
    with a record whose decision ∈ {allow, ask}

Architecture doc:
26. docs/architecture/kca-cli-architecture.md exists, ≥ 80 lines
27. Headings: Overview, Four layers, Skill format, Tool registry, Permission policy,
    Audit trail, Decision gate, Directory layout, Adding a new command,
    Adding a new skill, Adding a new tool — all present

Smoke tests:
28. python -m pytest tests/test_m7_smoke.py -v → 15/15 pass (or >= 12 + any extras)

Final document:
  Print full validation matrix (check | PASS/FAIL/SKIP | note).
  If all non-SKIP pass → output "M7 EXIT CRITERIA MET".
  Create docs/milestones/m7/final-review.md following the same structure as
  docs/milestones/m6/final-review.md with:
    - Validation matrix.
    - What landed (files created/modified).
    - DB access note (if any DB checks ran).
    - M8 follow-ups list.

Also update, in order:
  1. PROJECT_STATE.md — set current milestone to M8, summarise M7 deliverables,
     clear M7 open decisions.
  2. README.md — update "Current milestone" section from M7 to M8.
  3. docs/milestones/README.md — mark M7 ✓ done with one-line summary.
  4. docs/milestones/m7/handoff.md — write a per-milestone handoff prompt for the
     next AI tool / session that will start M8. Use docs/milestones/_templates/handoff-prompt.md as
     the canonical template and populate:
       - Read-first list (PROJECT_STATE.md, AGENTS.md, CLAUDE.md, the M8 section
         of docs/milestones/README.md, this docs/milestones/m7/final-review.md, latest ADRs,
         docs/architecture/kca-cli-architecture.md).
       - "State at M7 exit" (1–3 lines summarising what landed + the 28-check
         exit matrix outcome + the M8 follow-ups list).
       - "Current task" stub for the first M8 task (typically Prompt 0 of
         docs/milestones/m8/loop-prompts.md once that file exists).
     This step is required by docs/milestones/README.md § Milestone final-review
     protocol; do not skip it.

Do NOT git add or commit unless the human explicitly requests it.
Report: full matrix, final status.
```

---

## Running on Arch Linux (autonomous)

### One-time setup

```bash
# Ensure kca is installed and tests pass from M6
pip install -e .
python -m pytest tests/ -v -m "not db"   # should be 0 failures from M6

# Verify M7 base environment
python -c "from tools.kca.kca import build_parser; build_parser()"
python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"

# DB (carry over from M6 — only needed for T010 live-db check)
export SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
export KCA_DB_TARGET=local
# Refresh container IP if needed:
# docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

### Settings additions for autonomous M7 loop

These entries extend the M6 `.claude/settings.json` allow-list:

```json
"Bash(kca skill*)",
"Bash(kca tool*)",
"Bash(mkdir -p .kca*)",
"Bash(cat > .kca/skills*)",
"Bash(yamllint*)",
"Bash(for skill in*)"
```

### Sandbox notes

M7 is almost entirely local — no DB calls required for prompts 0–9. Only
Prompt 10 option 1 (live-db pytest) and the DB audit log path need
`dangerouslyDisableSandbox: true`. Everything else (file writes, imports,
kca skill CLI, ruff, pytest) runs within the normal sandbox.

### Full autonomous run

```bash
claude --bg \
  --name "M7" \
  --model opus \
  --effort high \
  "/goal Execute M7 Loop Prompts 0 through 10 from docs/milestones/m7/loop-prompts.md in sequence.
Each prompt's acceptance checks must pass before moving to the next.
On failure: fix the specific issue and retry that prompt only.
Do not git add, commit, or push unless Prompt 10 completes with M7 EXIT CRITERIA MET
and the human explicitly requests it.
Do not call the real Kaggle API or do any remote Supabase writes.
Use --dry-run for all kca skill run and kca job tests.
For DB validation (Prompt 10 only) use:
  SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres
  (container IP; refresh via docker inspect supabase-db if it changes)
DB calls require dangerouslyDisableSandbox=true.
Report PASS/FAIL for each prompt's verification step inline.
Stop at any FAIL that cannot be fixed within 3 attempts and report the blocker."
```

### Closeout checklist

After M7 EXIT CRITERIA MET, before moving to M8:

- [ ] docs/milestones/m7/final-review.md created with validation matrix.
- [ ] PROJECT_STATE.md updated: current milestone = M8.
- [ ] README.md current milestone updated to M8.
- [ ] docs/milestones/README.md M7 marked ✓ done.
- [ ] `.kca/skills/_test_fixture/` either removed or renamed to a real skill.
- [ ] Human reviews `docs/milestones/m7/final-review.md` and confirms M8 scope.
