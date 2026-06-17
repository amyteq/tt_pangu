"""Skill loader: read `.kca/skills/<name>/SKILL.md`, parse YAML frontmatter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .skill_schema import (  # noqa: F401  (re-exported for callers)
    SkillValidationError,
    validate_allowed_tools,
    validate_frontmatter,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_skills_root() -> Path:
    return _repo_root() / ".kca" / "skills"


@dataclass
class SkillMeta:
    name: str
    description: str
    version: str = "1.0"
    argument_hint: str = ""
    arguments: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    approval_policy: str = "default"
    disable_model_invocation: bool = False
    tags: list[str] = field(default_factory=list)
    body: str = ""


@dataclass
class Skill:
    meta: SkillMeta
    path: Path
    rendered_body: str = ""


_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<fm>.*?)\r?\n---[ \t]*\r?\n?(?P<body>.*)\Z",
    re.DOTALL,
)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text = m.group("fm")
    body = m.group("body")
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return data, body


def _build_meta(data: dict, *, fallback_name: str) -> SkillMeta:
    name = data.get("name", fallback_name)
    description = data.get("description", "")
    if not isinstance(name, str) or not name:
        raise ValueError("skill `name` is required and must be a string")
    if not isinstance(description, str):
        raise ValueError("skill `description` must be a string")
    version = str(data.get("version", "1.0"))
    argument_hint = str(data.get("argument-hint", data.get("argument_hint", "")))
    arguments = list(data.get("arguments", []) or [])
    allowed_tools = list(data.get("allowed-tools", data.get("allowed_tools", [])) or [])
    approval_policy = str(data.get("approval-policy", data.get("approval_policy", "default")))
    disable_model_invocation = bool(
        data.get(
            "disable-model-invocation",
            data.get("disable_model_invocation", False),
        )
    )
    tags = list(data.get("tags", []) or [])
    return SkillMeta(
        name=name,
        description=description,
        version=version,
        argument_hint=argument_hint,
        arguments=[str(a) for a in arguments],
        allowed_tools=[str(t) for t in allowed_tools],
        approval_policy=approval_policy,
        disable_model_invocation=disable_model_invocation,
        tags=[str(t) for t in tags],
    )


def load_skill(name: str, *, skills_root: Path | None = None) -> Skill:
    root = skills_root or _default_skills_root()
    skill_dir = root / name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"skill {name!r} not found at {skill_md}")
    text = skill_md.read_text(encoding="utf-8")
    data, body = _parse_frontmatter(text)
    try:
        validate_frontmatter(data)
    except SkillValidationError as exc:
        raise SkillValidationError(f"{skill_md}: {exc}") from exc
    meta = _build_meta(data, fallback_name=name)
    # Cross-check allowed-tools against TOOL_REGISTRY so a typo fails loudly.
    try:
        from .tool_registry import TOOL_REGISTRY

        validate_allowed_tools(meta.allowed_tools, set(TOOL_REGISTRY.keys()))
    except SkillValidationError as exc:
        raise SkillValidationError(f"{skill_md}: {exc}") from exc
    meta.body = body
    return Skill(meta=meta, path=skill_md.resolve(), rendered_body=body)


def list_skills(*, skills_root: Path | None = None) -> list[SkillMeta]:
    root = skills_root or _default_skills_root()
    metas: list[SkillMeta] = []
    if not root.is_dir():
        return metas
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            skill = load_skill(entry.name, skills_root=root)
        except (ValueError, FileNotFoundError):
            continue
        metas.append(skill.meta)
    return metas


_ARG_TOKEN_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def render_skill(skill: Skill, args: dict[str, str]) -> str:
    body = skill.meta.body
    # Verify declared arguments present.
    missing = [a for a in skill.meta.arguments if a not in args]
    if missing:
        raise ValueError(f"missing skill argument(s): {', '.join(missing)}")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in args:
            return str(args[key])
        return match.group(0)

    rendered = _ARG_TOKEN_RE.sub(_sub, body)
    skill.rendered_body = rendered
    return rendered
