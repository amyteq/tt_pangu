"""M12-T002 — permission policy resolver routes on competition_type.

ADR-0016 generalizes the policy layer beyond Kaggle. The resolver should:

1. Prefer a competition-type-specific profile when one exists
   (e.g. devpost -> hackathon-runner.yaml, ships in M12-T004).
2. Fall back to the skill's declared profile (or `default`) when the
   type-specific profile file is absent — guarantees M12-T002 lands
   without requiring T004's `hackathon-runner.yaml` to exist yet.
3. Treat an unknown `competition_type` as "no override" -> default profile.

These tests stub the permissions directory so they don't depend on the
real `.kca/permissions/` shipping any particular profile, and don't touch
the DB at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `tools/kca/agent/...` importable without installing as a package.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = _REPO_ROOT / "tools" / "kca"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from agent.permission_policy import (  # noqa: E402
    COMPETITION_TYPE_PROFILES,
    _resolve_profile_for_competition_type,
    resolve_for_skill,
)
from agent.skill_loader import SkillMeta  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_profile(root: Path, name: str, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.yaml").write_text(body, encoding="utf-8")


@pytest.fixture()
def perms_root(tmp_path: Path) -> Path:
    """Build a self-contained permissions directory for the test.

    - default.yaml: kaggle_submit=ask, devpost_submit=ask
    - competition-runner.yaml: kaggle_submit=allow in finalization mode
    - hackathon-runner.yaml: devpost_submit=ask + audit_required
    """
    root = tmp_path / "permissions"
    _write_profile(
        root,
        "default",
        """\
- operation: kaggle_submit
  default_decision: ask
- operation: devpost_submit
  default_decision: ask
- operation: read_file
  default_decision: allow
""",
    )
    _write_profile(
        root,
        "competition-runner",
        """\
- operation: kaggle_submit
  default_decision: ask
  allowed_in_modes:
    - competition-finalization
- operation: read_file
  default_decision: allow
""",
    )
    _write_profile(
        root,
        "hackathon-runner",
        """\
- operation: devpost_submit
  default_decision: ask
  audit_required: true
  allowed_in_modes:
    - hackathon-finalization
- operation: read_file
  default_decision: allow
""",
    )
    return root


@pytest.fixture()
def skill() -> SkillMeta:
    return SkillMeta(
        name="kaggle-experiment-loop",
        description="stub",
        approval_policy="default",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_kaggle_row_routes_to_competition_runner(perms_root: Path, skill: SkillMeta) -> None:
    """competition_type='kaggle' -> competition-runner profile.

    competition-runner allows kaggle_submit only in finalization mode;
    in default mode it must return 'ask'.
    """
    decision_default = resolve_for_skill(
        skill,
        "kaggle_submit",
        mode="default",
        permissions_root=perms_root,
        competition_type="kaggle",
    )
    decision_final = resolve_for_skill(
        skill,
        "kaggle_submit",
        mode="competition-finalization",
        permissions_root=perms_root,
        competition_type="kaggle",
    )
    assert decision_default == "ask"
    assert decision_final == "allow"


def test_devpost_row_routes_to_hackathon_runner(perms_root: Path, skill: SkillMeta) -> None:
    """competition_type='devpost' -> hackathon-runner profile.

    hackathon-runner declares devpost_submit -> ask + allowed_in_modes,
    so default mode returns 'ask' and hackathon-finalization returns 'allow'.
    This proves the resolver hits the type-specific profile instead of
    the skill's `default` profile.
    """
    decision_default = resolve_for_skill(
        skill,
        "devpost_submit",
        mode="default",
        permissions_root=perms_root,
        competition_type="devpost",
    )
    decision_final = resolve_for_skill(
        skill,
        "devpost_submit",
        mode="hackathon-finalization",
        permissions_root=perms_root,
        competition_type="devpost",
    )
    assert decision_default == "ask"
    assert decision_final == "allow"


def test_unknown_competition_type_falls_back_to_default(perms_root: Path, skill: SkillMeta) -> None:
    """Unknown competition_type -> resolver uses skill's default profile.

    'wildcard-platform' is not in COMPETITION_TYPE_PROFILES. The resolver
    must return what the default profile says for kaggle_submit ('ask'),
    not raise.
    """
    assert _resolve_profile_for_competition_type("wildcard-platform", permissions_root=perms_root) is None
    decision = resolve_for_skill(
        skill,
        "kaggle_submit",
        mode="default",
        permissions_root=perms_root,
        competition_type="wildcard-platform",
    )
    assert decision == "ask"


def test_missing_type_profile_falls_back_to_default(tmp_path: Path, skill: SkillMeta) -> None:
    """Type-specific profile is registered but file missing -> fallback.

    Guarantees M12-T002 ships green even though hackathon-runner.yaml
    only lands in M12-T004. With only default.yaml on disk, a
    competition_type='devpost' lookup must transparently fall back.
    """
    root = tmp_path / "permissions"
    _write_profile(
        root,
        "default",
        """\
- operation: devpost_submit
  default_decision: ask
""",
    )
    # Sanity: hackathon-runner is registered in the map...
    assert COMPETITION_TYPE_PROFILES.get("devpost") == "hackathon-runner"
    # ...but the file doesn't exist in this perms root.
    assert _resolve_profile_for_competition_type("devpost", permissions_root=root) is None
    decision = resolve_for_skill(
        skill,
        "devpost_submit",
        mode="default",
        permissions_root=root,
        competition_type="devpost",
    )
    assert decision == "ask"
