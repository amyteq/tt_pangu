"""Central registry for kca subcommand groups."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SIDE_EFFECT_LEVELS = {"READ_ONLY", "LOCAL_WRITE", "REMOTE_WRITE", "SUBMISSION"}


@dataclass
class CommandSpec:
    name: str
    description: str
    side_effect: str
    requires_db: bool
    add_parsers_fn: Callable[[object], None]


@dataclass
class CommandRegistry:
    _specs: dict[str, CommandSpec] = field(default_factory=dict)

    def register(self, spec: CommandSpec) -> None:
        if spec.side_effect not in SIDE_EFFECT_LEVELS:
            raise ValueError(f"unknown side_effect {spec.side_effect!r} for command {spec.name!r}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> CommandSpec | None:
        return self._specs.get(name)

    def list_all(self) -> list[CommandSpec]:
        return sorted(self._specs.values(), key=lambda s: s.name)


REGISTRY = CommandRegistry()


def _seed_registry() -> None:
    import competition as competition_mod
    import contracts as contracts_mod
    import ctf as ctf_mod
    import decisions as decisions_mod
    import devpost as devpost_mod
    import eval as eval_mod
    import explore as explore_mod
    import goal as goal_mod
    import submission_checklist as submission_checklist_mod
    import kg as kg_mod
    import local as local_mod
    import nb as nb_mod
    import notify as notify_mod
    import research as research_mod
    import review as review_mod
    import run as run_mod
    import workspace as workspace_mod

    REGISTRY.register(
        CommandSpec(
            "nb",
            "Notebook <-> percent-py conversion.",
            "READ_ONLY",
            False,
            nb_mod.add_parsers,
        )
    )
    REGISTRY.register(CommandSpec("run", "Experiment run lifecycle.", "LOCAL_WRITE", True, run_mod.add_parsers))
    REGISTRY.register(
        CommandSpec(
            "kaggle",
            "Kaggle submission / kernel push.",
            "SUBMISSION",
            True,
            kg_mod.add_parsers,
        )
    )
    REGISTRY.register(CommandSpec("eval", "Evaluation harness.", "READ_ONLY", False, eval_mod.add_parsers))
    REGISTRY.register(
        CommandSpec(
            "workspace",
            "Workspace lifecycle.",
            "LOCAL_WRITE",
            True,
            workspace_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "decisions",
            "Decision records.",
            "LOCAL_WRITE",
            True,
            decisions_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "competition",
            "Competition workspace + manifest.",
            "LOCAL_WRITE",
            True,
            competition_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "contracts",
            "Ledger contract validation (ADR-0023).",
            "READ_ONLY",
            False,
            contracts_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "goal",
            "Goal-driven Kaggle loop: declare / inspect / update a goal (M14-T002).",
            "LOCAL_WRITE",
            True,
            goal_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "explore",
            "Goal-driven Kaggle loop: exploration-batch init / run / rank / prune (M14-T003).",
            "LOCAL_WRITE",
            True,
            explore_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "ctf",
            "Authorized CTF / lab workflow (event/challenge/scope/solver/flag).",
            "LOCAL_WRITE",
            True,
            ctf_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "devpost",
            "Devpost / hackathon adapter (register / fetch / info + gated submit; M12-T007).",
            "SUBMISSION",
            True,
            devpost_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "submission",
            "Submission-pack inspector (READ_ONLY checklist; M12-T004).",
            "READ_ONLY",
            False,
            submission_checklist_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "research",
            "Research fetch / index.",
            "LOCAL_WRITE",
            True,
            research_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "notify",
            "Long-run notification / HITL channel: Telegram push + GitHub record (#197).",
            "REMOTE_WRITE",
            False,
            notify_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "local",
            "Local LLM endpoint probing.",
            "READ_ONLY",
            False,
            local_mod.add_parsers,
        )
    )
    REGISTRY.register(
        CommandSpec(
            "review",
            "Multi-agent review.",
            "READ_ONLY",
            True,
            review_mod.add_parsers,
        )
    )

    # New M7 commands — registered lazily to avoid circular imports if missing.
    try:
        import skill as skill_mod  # type: ignore

        REGISTRY.register(
            CommandSpec(
                "skill",
                "Skill loader CLI.",
                "READ_ONLY",
                False,
                skill_mod.add_parsers,
            )
        )
    except ImportError:
        pass

    try:
        import tool as tool_mod  # type: ignore

        REGISTRY.register(
            CommandSpec(
                "tool",
                "Tool registry / audit CLI.",
                "READ_ONLY",
                False,
                tool_mod.add_parsers,
            )
        )
    except ImportError:
        pass


_seed_registry()
