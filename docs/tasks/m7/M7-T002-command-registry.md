# M7-T002: Command registry

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 2; extracted here for the double-layer convention.

## Goal
Implement `tools/kca/agent/command_registry.py` — a central registry that
records metadata about every kca subcommand group.

## Read first
1. `tools/kca/kca.py`   (build_parser, current add_parsers pattern)
2. `tools/kca/agent/skill_loader.py`   (from Prompt 1)
3. `docs/milestones/README.md`   (M7 — Command vs Skill distinction)
4. `docs/meeting-notes/2026-05-21-r1.md`   (§2: KCA CLI command suggestions)

## Scope / Files / Implementation guidance

```python
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
```

Populate REGISTRY at import time by registering all existing kca subcommand
groups with accurate side_effect and requires_db values:
```
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
```

Update `kca.py` to `build_parser()` using `REGISTRY.list_all()` instead of the
current hardcoded imports, so new commands auto-register.

## Acceptance criteria

```python
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
```

kca CLI must still work end-to-end after the refactor:
```
python tools/kca/kca.py --help   → lists all subcommand groups
python tools/kca/kca.py run list --json   → ok
```

- `python -m pytest tests/ -v -m "not db"` → 0 failures.
- Report: registry list + CLI help + test results.

## Stop condition
Stop after 30 turns.
