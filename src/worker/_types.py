from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobPolicy:
    max_turns: int = 60
    max_cost_usd: float = 20.0
    max_runtime_s: int = 7200
    allowed_tool_patterns: list[str] = field(
        default_factory=lambda: ["kca *", "python -m pytest *", "pytest *"]
    )
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.2
    top_p: float = 0.90
    min_p: float | None = None
    approval_gates: dict = field(default_factory=lambda: {
        "kaggle_submit":  False,
        "kernel_push":    False,
        "git_push":       False,
        "dataset_upload": True,
        "git_force_push": True,
    })
    max_side_effect: str = "SUBMISSION"


@dataclass
class WorkerResult:
    status: str          # done | failed | paused | budget_stop
    turns_used: int
    cost_usd: float
    duration_s: float
    final_message: str
    stop_reason: str     # end_turn | max_turns | max_cost_usd | max_runtime_s
                         # approval_required | tool_error | unexpected


@dataclass
class ToolCallRecord:
    tool_name: str
    tool_input: dict
    side_effect: str
    result_preview: str
