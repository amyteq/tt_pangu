# M8-T002: SKILL.md schema gate + retire `_test_fixture`

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 2; extracted here for the double-layer convention.

## Goal
Validate SKILL.md frontmatter against a JSON Schema at load time, and move
the test fixture out of `.kca/skills/` so it cannot be invoked from the
production CLI.

## Read first
1. `tools/kca/agent/skill_loader.py` (current SkillMeta + load_skill)
2. `.kca/skills/run-milestone/SKILL.md` (example of a real skill)
3. `.kca/skills/_test_fixture/SKILL.md` (fixture to retire)
4. `tests/test_m7_smoke.py` (assertions that still depend on `_test_fixture`)
5. `docs/milestones/m7/final-review.md` (§ M8 follow-up #3 and #5)

## Scope / Files / Implementation guidance

### Step 1 — Add `tools/kca/agent/skill_schema.py`
```python
SKILL_FRONTMATTER_SCHEMA = {
  "type": "object",
  "required": ["name", "description"],
  "additionalProperties": False,
  "properties": {
    "name":         {"type": "string", "pattern": "^[a-z0-9][a-z0-9-_]*$"},
    "description":  {"type": "string", "minLength": 1, "maxLength": 280},
    "version":      {"type": "string"},
    "argument-hint":{"type": "string"},
    "arguments":    {"type": "array", "items": {"type": "string"}},
    "allowed-tools":{"type": "array", "items": {"type": "string"}},
    "approval-policy": {"type": "string"},
    "disable-model-invocation": {"type": "boolean"},
    "tags":         {"type": "array", "items": {"type": "string"}},
  },
}
def validate_frontmatter(data: dict) -> None:
    """Raise SkillValidationError on schema mismatch."""

class SkillValidationError(ValueError): ...
```

### Step 2 — Wire into `skill_loader.load_skill`
- After YAML parse, call `validate_frontmatter(parsed)`.
- On error, raise `SkillValidationError` with the path included.
- Add a fast-fail when `allowed-tools` references a tool absent from
  `TOOL_REGISTRY` — raise with the offending tool name.

### Step 3 — Move the test fixture
```bash
mkdir -p tests/fixtures/skills/_test_fixture
git mv .kca/skills/_test_fixture/SKILL.md tests/fixtures/skills/_test_fixture/SKILL.md
rmdir .kca/skills/_test_fixture
# Update list_skills() to also accept an explicit skills_root (already supports it)
# Update tests/test_m7_smoke.py to point fixture-loading tests at
# tests/fixtures/skills as skills_root.
```

### Step 4 — Add CLI flag for invoking a fixture skill via the test root
In `tools/kca/skill.py`, add a hidden `--skills-root` flag (default `None`,
resolves to `.kca/skills`). Used only in tests; do NOT advertise in
`--help`.

## Acceptance criteria
- Schema rejection path:
  ```python
  from tools.kca.agent.skill_loader import load_skill, SkillValidationError
  import tempfile, pathlib, textwrap
  d = pathlib.Path(tempfile.mkdtemp()) / 'bad/SKILL.md'
  d.parent.mkdir(parents=True, exist_ok=True)
  d.write_text(textwrap.dedent('''---\nname: Bad Name With Spaces\ndescription: x\n---\nbody'''))
  try:
      load_skill('bad', skills_root=d.parent.parent)
      print('FAIL: should reject')
  except SkillValidationError as e:
      print('PASS:', e)
  ```
- Unknown tool in `allowed-tools` rejected (build a temp skill with
  `allowed-tools: [does_not_exist]`; expect `SkillValidationError`).
- All real skills still load:
  ```python
  from tools.kca.agent.skill_loader import list_skills
  names = {m.name for m in list_skills()}
  assert {'run-milestone','triage-log','prepare-submission','review-pr'} <= names
  assert '_test_fixture' not in names, 'fixture should no longer ship via .kca/skills/'
  print('PASS real skills present, fixture removed')
  ```
- `python -m pytest tests/test_m7_smoke.py -v` → all pass after fixture path update
- `python -m pytest tests/ -v -m "not db"` → 0 failures

Report: schema rejection path, fixture move, test suite still green.

## Stop condition
Stop after 30 turns.
