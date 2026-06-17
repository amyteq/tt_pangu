"""Permission policy resolver: allow / ask / deny for (operation, mode) pairs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .skill_loader import SkillMeta
from .tool_registry import default_decision as _tool_default_decision

DECISIONS = {"allow", "ask", "deny"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_permissions_root() -> Path:
    return _repo_root() / ".kca" / "permissions"


@dataclass
class PolicyRecord:
    operation: str
    default_decision: str
    reason: str = ""
    allowed_in_modes: list[str] = field(default_factory=list)
    audit_required: bool = False


@dataclass
class PermissionPolicy:
    profile: str
    records: dict[str, PolicyRecord] = field(default_factory=dict)

    def get_record(self, operation: str) -> PolicyRecord | None:
        return self.records.get(operation)

    def resolve(self, operation: str, mode: str = "default") -> str:
        rec = self.records.get(operation)
        if rec is not None:
            if rec.default_decision == "deny":
                return "deny"
            if mode in rec.allowed_in_modes:
                return "allow"
            if rec.default_decision in DECISIONS:
                return rec.default_decision
        # Fall back to ToolSpec.approval_label (returns "ask" for unknowns).
        return _tool_default_decision(operation)


def _records_from_yaml(profile: str, data) -> dict[str, PolicyRecord]:
    if not isinstance(data, list):
        raise ValueError(f"permission policy {profile!r} must be a YAML list of records")
    out: dict[str, PolicyRecord] = {}
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"policy record must be a mapping, got {type(item)}")
        op = item.get("operation")
        decision = item.get("default_decision", "ask")
        if not isinstance(op, str) or not op:
            raise ValueError(f"policy record missing operation: {item}")
        if decision not in DECISIONS:
            raise ValueError(f"invalid default_decision {decision!r} for {op!r}")
        out[op] = PolicyRecord(
            operation=op,
            default_decision=decision,
            reason=str(item.get("reason", "")),
            allowed_in_modes=list(item.get("allowed_in_modes", []) or []),
            audit_required=bool(item.get("audit_required", False)),
        )
    return out


def load_policy(profile: str, *, permissions_root: Path | None = None) -> PermissionPolicy:
    root = permissions_root or _default_permissions_root()
    path = root / f"{profile}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"policy profile {profile!r} not found at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    records = _records_from_yaml(profile, data)
    return PermissionPolicy(profile=profile, records=records)


# M12 / ADR-0016: registry of competition_type -> policy profile filename
# (without the .yaml extension). Order matters only for documentation: this
# is a flat dict. Profiles that don't exist yet (e.g. hackathon-runner ships
# in M12-T004, ctf-runner in M11) fall back to `default` at resolve time so
# this map stays additive and forward-compatible.
COMPETITION_TYPE_PROFILES: dict[str, str] = {
    "kaggle": "competition-runner",
    "devpost": "hackathon-runner",
    "hackathon_devpost": "hackathon-runner",
    "ctf": "ctf-runner",
    "generic": "default",
}


def _resolve_profile_for_competition_type(
    competition_type: str | None,
    *,
    permissions_root: Path | None = None,
) -> str | None:
    """Return the profile name to load for a given competition_type.

    Routing rules (ADR-0016 + ADR-0006 four-level hierarchy):
      1. Look up the type-specific profile in COMPETITION_TYPE_PROFILES.
      2. If that profile file does not exist on disk, fall back to None
         so the caller can use its skill-derived or default profile.
      3. Unknown competition_type -> None (fall back to default).
    """
    if not competition_type:
        return None
    profile = COMPETITION_TYPE_PROFILES.get(competition_type)
    if profile is None:
        return None
    root = permissions_root or _default_permissions_root()
    if not (root / f"{profile}.yaml").is_file():
        return None
    return profile


def resolve_for_skill(
    skill_meta: SkillMeta,
    operation: str,
    mode: str = "default",
    *,
    permissions_root: Path | None = None,
    competition_type: str | None = None,
) -> str:
    """Resolve allow / ask / deny for an operation.

    Resolution order (ADR-0006 four-level hierarchy, generalized in ADR-0016):
      1. If `competition_type` is provided AND a matching profile file
         exists, load that profile first and return its decision if the
         operation is recorded there.
      2. Otherwise (or if the type-specific profile has no record for
         the operation), fall back to the skill's declared profile
         (`skill_meta.approval_policy`) or `default`.
      3. `ToolSpec.approval_label` is the final fallback inside
         `PermissionPolicy.resolve`.

    Backwards compatibility: callers that omit `competition_type` get the
    pre-M12 behaviour byte-for-byte (skill profile only).
    """
    type_profile = _resolve_profile_for_competition_type(competition_type, permissions_root=permissions_root)
    if type_profile is not None:
        policy = load_policy(type_profile, permissions_root=permissions_root)
        if policy.get_record(operation) is not None:
            return policy.resolve(operation, mode=mode)
    fallback_profile = skill_meta.approval_policy or "default"
    policy = load_policy(fallback_profile, permissions_root=permissions_root)
    return policy.resolve(operation, mode=mode)
