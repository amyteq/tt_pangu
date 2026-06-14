# M7-T008: `tests/test_m7_smoke.py`

## Milestone
M7: KCA CLI architecture — command / skill / tool / job / permission policy.

## Status
backfilled — original task spec was inlined into `docs/milestones/m7/loop-prompts.md` Loop Prompt 8; extracted here for the double-layer convention.

## Goal
Create `tests/test_m7_smoke.py` with 12–15 pytest tests; all pass without
ANTHROPIC_API_KEY, SUPABASE_DB_URL, KAGGLE_KEY, or GPU endpoints.

## Read first
1. `tests/test_m6_smoke.py`   (style, env-scrub helpers, skip pattern)
2. `tools/kca/agent/skill_loader.py`
3. `tools/kca/agent/command_registry.py`
4. `tools/kca/agent/tool_registry.py`
5. `tools/kca/agent/permission_policy.py`
6. `tools/kca/agent/audit.py`
7. `tools/kca/skill.py`

## Scope / Files / Implementation guidance

Required tests (use these names verbatim):

1. `test_skill_load_fixture()`
   `load_skill('_test_fixture')`; assert `meta.name == '_test_fixture'`
2. `test_skill_load_missing()`
   `load_skill('__no_such__')` raises `FileNotFoundError`
3. `test_skill_render_substitution(tmp_path)`
   Write a SKILL.md with `$foo` in body; `render_skill(s, {'foo':'bar'})` → `'bar'` in body
4. `test_skill_render_missing_arg(tmp_path)`
   Declared arg not provided → `ValueError`
5. `test_skill_list_includes_seeds()`
   `list_skills()` returns at least: run-milestone, triage-log, prepare-submission, review-pr, _test_fixture
6. `test_command_registry_all_registered()`
   `REGISTRY.list_all()` names ⊇ `{'kaggle','decisions','skill','tool'}`
7. `test_command_registry_side_effects()`
   `REGISTRY.get('kaggle').side_effect == 'SUBMISSION'`
   `REGISTRY.get('nb').side_effect == 'READ_ONLY'`
8. `test_tool_registry_submission_tools()`
   `list_tools(side_effect='SUBMISSION')` contains at least `kaggle_submit`, `kaggle_push`
9. `test_tool_registry_unknown_default()`
   `default_decision('__unknown__') == 'ask'`
10. `test_permission_policy_default()`
    `load_policy('default').resolve('kaggle_submit') == 'ask'`
    `load_policy('default').resolve('read_file') == 'allow'`
11. `test_permission_policy_permissive_dev()`
    `load_policy('permissive-dev').resolve('bash') == 'allow'`
    `load_policy('permissive-dev').resolve('kaggle_submit') == 'ask'`
12. `test_permission_policy_competition_runner_mode()`
    `load_policy('competition-runner').resolve('kaggle_submit', mode='competition-finalization') == 'allow'`
    `load_policy('competition-runner').resolve('kaggle_submit', mode='default') == 'ask'`
13. `test_kca_skill_list_json(tmp_path)`
    subprocess `kca skill list --json` → exit 0, valid JSON, `'skills'` key present
14. `test_kca_skill_run_dry_run_json(tmp_path)`
    subprocess `kca skill run _test_fixture --arg task_path=x --dry-run --json`
    → exit 0, `ok=true`, `rendered_prompt` contains `'x'`
15. `test_audit_logger_writes_file(tmp_path)`
    ```python
    AuditLogger(backend='file', file_path=tmp_path/'audit.jsonl').log_policy_decision(
        tool='bash', operation='bash', decision='ask', mode='default',
        policy_profile='permissive-dev')
    ```
    → file exists, JSON line with `decision='ask'`

## Acceptance criteria

```
python -m pytest tests/test_m7_smoke.py -v   → all pass
python -m pytest tests/ -v -m "not db"        → 0 failures
```

- Report: count + per-test status line.

## Stop condition
Stop after 30 turns.
