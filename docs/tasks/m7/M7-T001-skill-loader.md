# M7-T001: Skill loader

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 1; extracted here for the double-layer convention.

## Goal
Implement `tools/kca/agent/skill_loader.py` — reads `.kca/skills/<name>/SKILL.md`,
parses YAML frontmatter, performs `$arg` substitution.

## Read first
1. `docs/milestones/README.md`   (M7 section — four-layer model + skill format)
2. `docs/meeting-notes/2026-05-21-r1.md`   (§1–3: skill YAML frontmatter design)
3. `tools/kca/kca.py`   (current subcommand registration pattern)
4. `src/worker/_types.py`   (JobPolicy shape, for approval-policy integration)

## Scope / Files / Implementation guidance

Directory: `.kca/skills/<name>/SKILL.md`

YAML frontmatter fields (all optional except `name` and `description`):
```
name: str
description: str
version: str (default "1.0")
argument-hint: str
arguments: list[str]   # positional arg names for $arg substitution
allowed-tools: list[str]
approval-policy: str   # profile name in .kca/permissions/<profile>.yaml
disable-model-invocation: bool (default false)
tags: list[str]
```

Implementation:
```python
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
```

Rules:
- Parse frontmatter between the first and second `---` separators only.
- Body begins on the line after the closing `---`.
- If no frontmatter delimiters: entire content is body, meta is defaults.
- Never import or execute the skill body.

## Acceptance criteria

Create a minimal fixture skill:
```bash
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
```

Run:
```python
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
```

```python
from tools.kca.agent.skill_loader import load_skill
try:
    load_skill('__nonexistent__')
    print('FAIL: should raise')
except FileNotFoundError:
    print('PASS FileNotFoundError on missing skill')
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: each verification + fixture skill created.

## Stop condition
Stop after 30 turns.
