"""M7 smoke tests — skill loader / registries / permissions / audit / CLI.

All tests pass without ANTHROPIC_API_KEY, SUPABASE_DB_URL, KAGGLE_KEY, or
GPU endpoints.

Run with:
    python -m pytest tests/test_m7_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
KCA = [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py")]
FIXTURE_SKILLS_ROOT = REPO_ROOT / "tests" / "fixtures" / "skills"

# Ensure imports work for the agent package.
sys.path.insert(0, str(REPO_ROOT))


def _env_clean(**overrides) -> dict:
    env = os.environ.copy()
    for k in (
        "SUPABASE_DB_URL",
        "KCA_DB_TARGET",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
        "ANTHROPIC_API_KEY",
        "KCA_ALLOW_REMOTE",
    ):
        env.pop(k, None)
    env.update(overrides)
    return env


def _write_skill(tmp_path: Path, name: str, body: str, *, frontmatter: str | None = None) -> Path:
    root = tmp_path / "skills"
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = frontmatter or f"name: {name}\ndescription: test skill\n"
    (skill_dir / "SKILL.md").write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
    return root


def test_skill_load_fixture():
    from tools.kca.agent.skill_loader import load_skill

    s = load_skill("_test_fixture", skills_root=FIXTURE_SKILLS_ROOT)
    assert s.meta.name == "_test_fixture"
    assert "task_path" in s.meta.arguments
    assert "read_file" in s.meta.allowed_tools


def test_skill_load_missing():
    from tools.kca.agent.skill_loader import load_skill

    with pytest.raises(FileNotFoundError):
        load_skill("__no_such__")


def test_skill_render_substitution(tmp_path):
    from tools.kca.agent.skill_loader import load_skill, render_skill

    root = _write_skill(
        tmp_path,
        "foo_skill",
        "value=$foo",
        frontmatter="name: foo_skill\ndescription: t\narguments:\n  - foo\n",
    )
    s = load_skill("foo_skill", skills_root=root)
    out = render_skill(s, {"foo": "bar"})
    assert "value=bar" in out


def test_skill_render_missing_arg(tmp_path):
    from tools.kca.agent.skill_loader import load_skill, render_skill

    root = _write_skill(
        tmp_path,
        "bar_skill",
        "value=$foo",
        frontmatter="name: bar_skill\ndescription: t\narguments:\n  - foo\n",
    )
    s = load_skill("bar_skill", skills_root=root)
    with pytest.raises(ValueError):
        render_skill(s, {})


def test_skill_list_includes_seeds():
    from tools.kca.agent.skill_loader import list_skills

    names = {m.name for m in list_skills()}
    for required in (
        "run-milestone",
        "triage-log",
        "prepare-submission",
        "review-pr",
    ):
        assert required in names, f"missing seed skill: {required}"
    # The test fixture lives outside .kca/skills/ as of M8.
    assert "_test_fixture" not in names

    fixture_names = {m.name for m in list_skills(skills_root=FIXTURE_SKILLS_ROOT)}
    assert "_test_fixture" in fixture_names


def test_command_registry_all_registered():
    from tools.kca.agent.command_registry import REGISTRY

    names = {s.name for s in REGISTRY.list_all()}
    for required in ("kaggle", "decisions", "skill", "tool"):
        assert required in names, f"missing command: {required}"


def test_command_registry_side_effects():
    from tools.kca.agent.command_registry import REGISTRY

    assert REGISTRY.get("kaggle").side_effect == "SUBMISSION"
    assert REGISTRY.get("nb").side_effect == "READ_ONLY"


def test_tool_registry_submission_tools():
    from tools.kca.agent.tool_registry import list_tools

    names = {t.name for t in list_tools(side_effect="SUBMISSION")}
    assert {"kaggle_submit", "kaggle_push"}.issubset(names)


def test_tool_registry_unknown_default():
    from tools.kca.agent.tool_registry import default_decision

    assert default_decision("__unknown__") == "ask"


def test_permission_policy_default():
    from tools.kca.agent.permission_policy import load_policy

    p = load_policy("default")
    assert p.resolve("kaggle_submit") == "ask"
    assert p.resolve("read_file") == "allow"


def test_permission_policy_permissive_dev():
    from tools.kca.agent.permission_policy import load_policy

    p = load_policy("permissive-dev")
    assert p.resolve("bash") == "allow"
    assert p.resolve("kaggle_submit") == "ask"


def test_permission_policy_competition_runner_mode():
    from tools.kca.agent.permission_policy import load_policy

    p = load_policy("competition-runner")
    assert p.resolve("kaggle_submit", mode="competition-finalization") == "allow"
    assert p.resolve("kaggle_submit", mode="default") == "ask"


def test_kca_skill_list_json(tmp_path):
    proc = subprocess.run(
        KCA + ["skill", "list", "--json"],
        env=_env_clean(),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert "skills" in data


def test_kca_skill_run_dry_run_json(tmp_path):
    proc = subprocess.run(
        KCA
        + [
            "skill",
            "run",
            "_test_fixture",
            "--skills-root",
            str(FIXTURE_SKILLS_ROOT),
            "--arg",
            "task_path=x",
            "--dry-run",
            "--json",
        ],
        env=_env_clean(),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert "x" in data["rendered_prompt"]


def test_audit_logger_writes_file(tmp_path):
    from tools.kca.agent.audit import AuditLogger

    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(backend="file", file_path=path)
    rec = logger.log_policy_decision(
        tool="bash",
        operation="bash",
        decision="ask",
        mode="default",
        policy_profile="permissive-dev",
    )
    assert rec.decision == "ask"
    assert path.is_file()
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["decision"] == "ask"
    assert payload["tool_name"] == "bash"
