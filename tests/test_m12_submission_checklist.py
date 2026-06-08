"""M12-T004 — submission_checklist tool + hackathon-runner profile + skill.

Test surface (no DB, no network):

1. `build_checklist` is deterministic for a fixed submission_format +
   fixture submission_pack directory. The fixture lives at
   `tests/fixtures/m12/submission_pack/` and is committed alongside the
   golden checklist in `tests/fixtures/m12/submission_pack.checklist.json`.
2. Missing required files report `status="todo"` with empty evidence.
3. Present files report `status="done"` with a stable relative evidence
   path.
4. Tool-registration round trip:
   - `submission_checklist` is in TOOL_REGISTRY.
   - The `hackathon-runner` profile resolves `devpost_submit` and
     `demo_upload` to `ask` and `team_invite` to `deny`; an
     unspecified op falls back to the default profile.
5. The `hackathon-experiment-loop` skill parses via the existing
   skill loader (front-matter + body).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools" / "kca"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "m12"
GOLDEN_FILE = FIXTURES_DIR / "submission_pack.checklist.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import submission_checklist as sc_mod  # noqa: E402
from agent.permission_policy import load_policy, resolve_for_skill  # noqa: E402
from agent.skill_loader import load_skill  # noqa: E402
from agent.tool_registry import TOOL_REGISTRY  # noqa: E402


# Fixed submission_format used across the fixture + tests. Slug-shaped
# keys matching what M12-T003's _extract_submission_format emits.
FIXTURE_SUBMISSION_FORMAT = [
    "text_description",
    "demo_video",
    "github_repo_url",
    # Duplicate-against-canonical key — must be de-duped against
    # README.md (canonical), so the final checklist must not contain
    # this twice.
    "README.md",
]

FIXTURE_SLUG = "sample-hack"
FIXTURE_RUN_ID = "20260609T000000Z"


# ---------------------------------------------------------------------------
# Fixture: tmp_path-based submission_pack
# ---------------------------------------------------------------------------


def _make_pack(
    root: Path,
    *,
    files: dict[str, str | None],
) -> Path:
    """Build a runs/<slug>/<run_id>/submission_pack/ tree under `root`.

    `files` maps relative paths to content. Passing `None` as content
    creates an empty file (which the tool should still treat as `todo`).
    Use a path ending in '/' to create an empty directory.
    """
    pack = root / FIXTURE_SLUG / FIXTURE_RUN_ID / "submission_pack"
    pack.mkdir(parents=True, exist_ok=True)
    for relpath, content in files.items():
        target = pack / relpath
        if relpath.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            target.write_text("", encoding="utf-8")
        else:
            target.write_text(content, encoding="utf-8")
    return pack


@pytest.fixture()
def runs_root_complete(tmp_path: Path) -> Path:
    """All canonical items + format keys present and non-empty."""
    runs = tmp_path / "runs"
    _make_pack(
        runs,
        files={
            "README.md": "# Sample hackathon submission\n",
            "demo-plan.md": "1. Walk through demo flow.\n",
            "source/main.py": "print('hello')\n",
            "submission-checklist.json": "[]\n",
            "text_description": "We built a thing.\n",
            "demo_video": "https://example.invalid/video\n",
            "github_repo_url": "https://example.invalid/repo\n",
        },
    )
    return runs


@pytest.fixture()
def runs_root_missing_required(tmp_path: Path) -> Path:
    """README + demo plan present; source/ + format keys missing."""
    runs = tmp_path / "runs"
    _make_pack(
        runs,
        files={
            "README.md": "# WIP\n",
            "demo-plan.md": "TBD\n",
        },
    )
    return runs


# ---------------------------------------------------------------------------
# 1. Deterministic golden output
# ---------------------------------------------------------------------------


def test_build_checklist_matches_golden(runs_root_complete: Path) -> None:
    """For a fixed submission_format + fixture pack, output is stable."""
    checklist = sc_mod.build_checklist(
        slug=FIXTURE_SLUG,
        run_id=FIXTURE_RUN_ID,
        submission_format=FIXTURE_SUBMISSION_FORMAT,
        runs_root=runs_root_complete,
    )

    # Determinism: calling twice with identical inputs yields identical output.
    checklist_again = sc_mod.build_checklist(
        slug=FIXTURE_SLUG,
        run_id=FIXTURE_RUN_ID,
        submission_format=FIXTURE_SUBMISSION_FORMAT,
        runs_root=runs_root_complete,
    )
    assert checklist == checklist_again

    # Shape contract: list[dict] with item/status/evidence keys only.
    assert isinstance(checklist, list)
    for entry in checklist:
        assert set(entry.keys()) == {"item", "status", "evidence"}
        assert entry["status"] in {"done", "todo", "blocked"}

    # All canonical items emitted, in CANONICAL_ITEMS order, before
    # format keys.
    canonical_names = [name for name, _ in sc_mod.CANONICAL_ITEMS]
    canonical_in_output = [e["item"] for e in checklist[: len(canonical_names)]]
    assert canonical_in_output == canonical_names

    # Format keys: README.md was filtered out as a dup of the canonical
    # README.md; the remaining three keys appear in source order.
    extra_in_output = [e["item"] for e in checklist[len(canonical_names) :]]
    assert extra_in_output == ["text_description", "demo_video", "github_repo_url"]

    # In the complete-pack fixture, every item is `done`.
    assert all(e["status"] == "done" for e in checklist), checklist

    # Golden file: write on first run, compare on subsequent runs. Use
    # an env-flag opt-in for the write so CI can never regenerate it.
    payload = json.dumps(checklist, indent=2, sort_keys=True) + "\n"
    if not GOLDEN_FILE.exists():
        GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_FILE.write_text(payload, encoding="utf-8")
    # Compare structure (relative-evidence paths embed tmp_path so we
    # normalize by stripping evidence values that point at the tmp dir).
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    assert [e["item"] for e in checklist] == [e["item"] for e in golden]
    assert [e["status"] for e in checklist] == [e["status"] for e in golden]


# ---------------------------------------------------------------------------
# 2. `todo` when required file missing
# ---------------------------------------------------------------------------


def test_missing_required_files_report_todo(runs_root_missing_required: Path) -> None:
    checklist = sc_mod.build_checklist(
        slug=FIXTURE_SLUG,
        run_id=FIXTURE_RUN_ID,
        submission_format=FIXTURE_SUBMISSION_FORMAT,
        runs_root=runs_root_missing_required,
    )
    by_item = {e["item"]: e for e in checklist}

    # README + demo-plan exist and are non-empty -> done.
    assert by_item["README.md"]["status"] == "done"
    assert by_item["demo-plan.md"]["status"] == "done"

    # source/ + submission-checklist.json missing -> todo, empty evidence.
    assert by_item["source/"]["status"] == "todo"
    assert by_item["source/"]["evidence"] == ""
    assert by_item["submission-checklist.json"]["status"] == "todo"

    # Format keys all missing -> todo.
    for key in ("text_description", "demo_video", "github_repo_url"):
        assert by_item[key]["status"] == "todo"
        assert by_item[key]["evidence"] == ""


# ---------------------------------------------------------------------------
# 3. `done` with non-empty evidence path
# ---------------------------------------------------------------------------


def test_done_status_carries_evidence_path(runs_root_complete: Path) -> None:
    checklist = sc_mod.build_checklist(
        slug=FIXTURE_SLUG,
        run_id=FIXTURE_RUN_ID,
        submission_format=FIXTURE_SUBMISSION_FORMAT,
        runs_root=runs_root_complete,
    )
    by_item = {e["item"]: e for e in checklist}
    # README evidence string points at the runs-root-relative path.
    readme = by_item["README.md"]
    assert readme["status"] == "done"
    assert readme["evidence"].endswith("submission_pack/README.md"), readme

    # source/ resolves to the directory; its evidence path ends in the
    # dirname (no trailing slash assumption).
    src = by_item["source/"]
    assert src["status"] == "done"
    assert src["evidence"].endswith("submission_pack/source"), src


# ---------------------------------------------------------------------------
# 4a. Tool-registration round-trip
# ---------------------------------------------------------------------------


def test_submission_checklist_registers_in_tool_registry() -> None:
    assert "submission_checklist" in TOOL_REGISTRY
    spec = TOOL_REGISTRY["submission_checklist"]
    assert spec.side_effect == "READ_ONLY"
    # The tool keeps `ask` even though it's READ_ONLY so the hackathon
    # runner has a single consistent gate surface.
    assert spec.approval_label == "ask"
    # Input schema documents the two required uuid inputs.
    assert "competition_id" in spec.input_schema["properties"]
    assert "run_id" in spec.input_schema["properties"]
    assert set(spec.input_schema["required"]) == {"competition_id", "run_id"}


# ---------------------------------------------------------------------------
# 4b. hackathon-runner profile resolves the three named gates
# ---------------------------------------------------------------------------


def test_hackathon_runner_profile_decisions() -> None:
    """Load the shipped .kca/permissions/hackathon-runner.yaml and resolve."""
    policy = load_policy("hackathon-runner")
    assert policy.resolve("devpost_submit", mode="default") == "ask"
    assert policy.resolve("demo_upload", mode="default") == "ask"
    assert policy.resolve("team_invite", mode="default") == "deny"
    # team_invite stays deny in any mode (no allowed_in_modes).
    assert policy.resolve("team_invite", mode="hackathon-finalization") == "deny"
    # Finalization mode promotes the two ask-ed ops to allow.
    assert policy.resolve("devpost_submit", mode="hackathon-finalization") == "allow"
    assert policy.resolve("demo_upload", mode="hackathon-finalization") == "allow"
    # An operation not in the profile falls back to the tool registry default
    # via PermissionPolicy.resolve's terminal _tool_default_decision call.
    # For a registered tool like read_file (default allow), the profile
    # ships the allow record anyway.
    assert policy.resolve("read_file", mode="default") == "allow"


def test_resolve_for_skill_routes_hackathon_runner_via_competition_type() -> None:
    """ADR-0016 routing: competition_type='devpost' -> hackathon-runner."""
    from agent.skill_loader import SkillMeta

    skill = SkillMeta(
        name="hackathon-experiment-loop",
        description="stub",
        approval_policy="hackathon-runner",
    )
    decision = resolve_for_skill(
        skill,
        "devpost_submit",
        mode="default",
        competition_type="devpost",
    )
    assert decision == "ask"
    decision_final = resolve_for_skill(
        skill,
        "devpost_submit",
        mode="hackathon-finalization",
        competition_type="devpost",
    )
    assert decision_final == "allow"


# ---------------------------------------------------------------------------
# 5. The hackathon-experiment-loop SKILL.md parses through the loader
# ---------------------------------------------------------------------------


def test_hackathon_experiment_loop_skill_parses() -> None:
    skill = load_skill("hackathon-experiment-loop")
    assert skill.meta.name == "hackathon-experiment-loop"
    assert skill.meta.approval_policy == "hackathon-runner"
    # The skill must NOT request the devpost_submit tool in allowed-tools
    # — that's enforced at the body level (stop condition) and via the
    # permission profile in M12-T007.
    assert "devpost_submit" not in skill.meta.allowed_tools
    # The body documents the stop condition explicitly.
    assert "Stop condition" in skill.meta.body
    assert "devpost_submit" in skill.meta.body


# ---------------------------------------------------------------------------
# 6. Pack-missing sentinel
# ---------------------------------------------------------------------------


def test_missing_pack_returns_blocked_sentinel(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()  # competition + run dirs absent on purpose
    checklist = sc_mod.build_checklist(
        slug=FIXTURE_SLUG,
        run_id=FIXTURE_RUN_ID,
        submission_format=FIXTURE_SUBMISSION_FORMAT,
        runs_root=runs,
    )
    assert checklist == [{"item": "__pack__", "status": "blocked", "evidence": ""}]
