"""M9.4 Discovery / Debate Gate — smoke tests.

No DB, no creds, no network. Verifies:
- the three .claude/agents/*.md files parse with required front-matter;
- docs/architecture/discovery-debate-gate.md exists and contains the
  union of all three agents' canonical acceptance lines as substrings;
- docs/milestone-loop-protocol.md has an additive §7 heading;
- at least one M9.4-T005 evidence transcript names the multi-account /
  owner / env mapping the legacy kkr migration originally missed.

The .claude/skills/design-archaeology/SKILL.md skill resolves are
*optional* at M9.4 close-time — M9.3-T001 owns shipping that file. The
test skips that assertion if the skill is not present, marking it
xfail-like to surface the dependency without failing the M9.4 milestone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

AGENT_FILES = [
    REPO_ROOT / ".claude" / "agents" / "requirements-skeptic.md",
    REPO_ROOT / ".claude" / "agents" / "legacy-archaeologist.md",
    REPO_ROOT / ".claude" / "agents" / "design-red-team.md",
]

REQUIRED_FRONTMATTER_KEYS = {"name", "description", "tools", "model", "permissionMode"}

ACCEPTANCE_LINES = {
    "requirements-skeptic": (
        "Output MUST contain ≥5 questions spread across ≥3 categories, and "
        "an `explicit_unknowns:` section listing things the agent could not "
        "answer without human input."
    ),
    "legacy-archaeologist": (
        "Output MUST cover all 10 sections; ≥5 distinct legacy behavior "
        "dimensions must be named explicitly, including any multi-account / "
        "owner / env mapping the legacy artefact encodes."
    ),
    "design-red-team": (
        "Output MUST include ≥3 alternatives, ≥1 dropped capability with "
        "file:line evidence, all four long-term-cost axes, and ≥1 "
        "actionable `open_disagreements` entry."
    ),
}

EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence" / "m9_4-kkr-replay"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    parts = text.split("---", 2)
    assert len(parts) >= 3, "missing YAML front-matter delimiters"
    meta = yaml.safe_load(parts[1])
    assert isinstance(meta, dict), "front-matter is not a YAML mapping"
    return meta, parts[2]


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
def test_agent_frontmatter_parses(path: Path) -> None:
    assert path.exists(), f"missing agent file: {path}"
    meta, _ = _split_frontmatter(path.read_text())
    missing = REQUIRED_FRONTMATTER_KEYS - set(meta)
    assert not missing, f"{path.name} missing front-matter keys: {missing}"
    assert meta["permissionMode"] == "plan", f"{path.name} must declare permissionMode: plan (read-only role)"


def _normalise_blockquote(text: str) -> str:
    """Collapse blockquote line-wraps so a multi-line acceptance line
    can be matched as a single substring."""
    return re.sub(r"\n> ?", " ", text)


@pytest.mark.parametrize(
    "path,key",
    [(p, p.stem) for p in AGENT_FILES],
    ids=lambda v: v.name if isinstance(v, Path) else v,
)
def test_agent_has_canonical_acceptance_line(path: Path, key: str) -> None:
    expected = ACCEPTANCE_LINES[key]
    haystack = _normalise_blockquote(path.read_text())
    assert expected in haystack, f"{path.name} is missing its canonical acceptance line"


def test_discovery_debate_gate_doc_present() -> None:
    doc = REPO_ROOT / "docs" / "architecture" / "discovery-debate-gate.md"
    assert doc.exists(), "missing docs/architecture/discovery-debate-gate.md"
    text = _normalise_blockquote(doc.read_text())
    for key, line in ACCEPTANCE_LINES.items():
        assert line in text, f"discovery-debate-gate.md missing {key}'s acceptance line"
    assert "arch:" in text and "legacy-migration:" in text, "discovery-debate-gate.md must document both task tags"
    assert "docs/evidence/<milestone>/<task>/discovery/" in text, (
        "discovery-debate-gate.md must document the evidence path"
    )


def test_protocol_section_7_present() -> None:
    proto = REPO_ROOT / "docs" / "milestone-loop-protocol.md"
    text = proto.read_text()
    assert "\n## 7. Discovery / Debate Gate\n" in text, "milestone-loop-protocol.md must have an additive §7 heading"


def test_kkr_replay_evidence_present() -> None:
    for name in (
        "legacy-archaeologist.md",
        "requirements-skeptic.md",
        "design-red-team.md",
    ):
        p = EVIDENCE_DIR / name
        assert p.exists(), f"missing M9.4-T005 replay evidence: {p}"
        assert "Source:" in p.read_text().splitlines()[2] or any(
            line.startswith("Source:") for line in p.read_text().splitlines()[:5]
        ), f"{name} missing provenance header"


def test_legacy_archaeologist_evidence_names_multi_account() -> None:
    """The load-bearing M9.4-T005 gate: the replay must surface the
    multi-Kaggle-account / owner / env mapping the original kkr migration
    missed (docs/meeting-notes/2026-05-24-r3.md §6).
    """
    evidence = (EVIDENCE_DIR / "legacy-archaeologist.md").read_text()
    for needle in ("harrysun2006", "firefly2006", ".env.{owner}", "owner"):
        assert needle in evidence, (
            f"legacy-archaeologist evidence must name '{needle}' (multi-account / owner / env mapping)"
        )


def test_design_archaeology_skill_present_or_skipped() -> None:
    """M9.3-T001 owns shipping .claude/skills/design-archaeology/SKILL.md;
    until that lands, this assertion is a soft skip so M9.4 can close
    on its own merits. When M9.3 lands, this becomes a hard PASS."""
    skill = REPO_ROOT / ".claude" / "skills" / "design-archaeology" / "SKILL.md"
    if not skill.exists():
        pytest.skip(
            "design-archaeology skill not yet on disk — owned by M9.3-T001; "
            "M9.4 references it via docs/architecture/discovery-debate-gate.md "
            "without requiring its presence."
        )
    meta, _ = _split_frontmatter(skill.read_text())
    assert meta.get("name") == "design-archaeology"
