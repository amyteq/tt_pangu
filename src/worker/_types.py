from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobPolicy:
    max_turns: int = 60
    max_cost_usd: float = 20.0
    max_runtime_s: int = 7200
    allowed_tool_patterns: list[str] = field(default_factory=lambda: ["kca *", "python -m pytest *", "pytest *"])
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.2
    top_p: float = 0.90
    min_p: float | None = None
    approval_gates: dict = field(
        default_factory=lambda: {
            "kaggle_submit": False,
            "kernel_push": False,
            "dataset_upload": True,
            "git_push": False,
            "git_force_push": True,
            "supabase_migrate": True,
            "delete_artifact": True,
            "external_fetch": False,
        }
    )
    max_side_effect: str = "SUBMISSION"
    # M8: skill metadata + per-tool decisions resolved from
    # tools.kca.agent.permission_policy.resolve_for_skill. Values are one of
    # "allow" / "ask" / "deny"; absent keys fall back to legacy gates.
    skill_name: str | None = None
    policy_profile: str = "default"
    mode: str = "default"
    tool_decisions: dict = field(default_factory=dict)
    # M12 / ADR-0016: route policy resolution on competition type.
    # Defaults to 'kaggle' for backwards-compatibility with M9 / M10 baseline
    # rows. The resolver in tools.kca.agent.permission_policy uses this to
    # pick a competition-type-specific profile when one is registered, then
    # falls back to the default profile (then to ToolSpec defaults).
    competition_type: str = "kaggle"


@dataclass
class WorkerResult:
    status: str  # done | failed | paused | budget_stop
    turns_used: int
    cost_usd: float
    duration_s: float
    final_message: str
    stop_reason: str  # end_turn | max_turns | max_cost_usd | max_runtime_s
    # approval_required | tool_error | unexpected


@dataclass
class ToolCallRecord:
    tool_name: str
    tool_input: dict
    side_effect: str
    result_preview: str
