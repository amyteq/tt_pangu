"""JSON-Schema-style validator for SKILL.md frontmatter.

We use a hand-rolled validator (no jsonschema dependency) keyed off
``SKILL_FRONTMATTER_SCHEMA``. The shape and field names match the existing
M7 ``SkillMeta`` so we can fail loudly on unknown keys, malformed types, or
bad slugs without changing the loader contract.
"""

from __future__ import annotations

import re
from typing import Any

SKILL_FRONTMATTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "description"],
    "additionalProperties": False,
    "properties": {
        "name": {
            "type": "string",
            # NOTE: leading underscore is allowed so test-only fixture skills
            # such as ``_test_fixture`` (now at tests/fixtures/skills/) can
            # round-trip. Spaces, uppercase, and slashes are still rejected.
            "pattern": r"^[a-z0-9_][a-z0-9_\-]*$",
        },
        "description": {"type": "string", "minLength": 1, "maxLength": 280},
        "version": {"type": "string"},
        "argument-hint": {"type": "string"},
        "arguments": {"type": "array", "items": {"type": "string"}},
        "allowed-tools": {"type": "array", "items": {"type": "string"}},
        "approval-policy": {"type": "string"},
        "disable-model-invocation": {"type": "boolean"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}


class SkillValidationError(ValueError):
    """Raised when a SKILL.md frontmatter does not match the schema."""


_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "number": (int, float),
}


def _matches_type(value: Any, type_name: str) -> bool:
    expected = _TYPE_MAP.get(type_name)
    if expected is None:
        return True
    # booleans are ints in Python; exclude bool when expecting number/int.
    if type_name == "number" and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def _validate_field(name: str, value: Any, spec: dict[str, Any]) -> None:
    type_name = spec.get("type")
    if type_name and not _matches_type(value, type_name):
        raise SkillValidationError(f"field {name!r}: expected type {type_name}, got {type(value).__name__}")
    if type_name == "string":
        if "minLength" in spec and len(value) < spec["minLength"]:
            raise SkillValidationError(f"field {name!r}: minLength {spec['minLength']} not met")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            raise SkillValidationError(f"field {name!r}: maxLength {spec['maxLength']} exceeded")
        pattern = spec.get("pattern")
        if pattern and not re.match(pattern, value):
            raise SkillValidationError(f"field {name!r}: value {value!r} does not match pattern {pattern}")
    if type_name == "array":
        item_spec = spec.get("items")
        if item_spec is None:
            return
        for i, item in enumerate(value):
            _validate_field(f"{name}[{i}]", item, item_spec)


def validate_frontmatter(data: dict[str, Any]) -> None:
    """Raise :class:`SkillValidationError` on schema mismatch."""
    if not isinstance(data, dict):
        raise SkillValidationError("frontmatter must be a YAML mapping")
    schema = SKILL_FRONTMATTER_SCHEMA

    for key in schema.get("required", []):
        if key not in data:
            raise SkillValidationError(f"required field missing: {key!r}")

    allowed = set(schema["properties"].keys())
    if not schema.get("additionalProperties", True):
        for key in data:
            if key not in allowed:
                raise SkillValidationError(f"unknown frontmatter key: {key!r}")

    for key, value in data.items():
        spec = schema["properties"].get(key)
        if spec is None:
            continue
        _validate_field(key, value, spec)


def validate_allowed_tools(allowed_tools: list[str], known_tools: set[str]) -> None:
    """Raise SkillValidationError when allowed_tools references unknown names."""
    for t in allowed_tools or []:
        if t not in known_tools:
            raise SkillValidationError(
                f"allowed-tools references unknown tool: {t!r} (must be one of {sorted(known_tools)[:6]}…)"
            )
