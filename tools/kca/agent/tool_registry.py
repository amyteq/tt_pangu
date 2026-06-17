"""Tool registry: metadata for every agent-facing tool."""

from __future__ import annotations

from dataclasses import dataclass, field

SIDE_EFFECT_LEVELS = {"READ_ONLY", "LOCAL_WRITE", "REMOTE_WRITE", "SUBMISSION"}
APPROVAL_LABELS = {"allow", "ask", "deny"}
SANDBOX_LABELS = {"sandboxed", "unsandboxed", "isolated_workspace"}


@dataclass
class ToolSpec:
    name: str
    description: str
    side_effect: str
    approval_label: str
    timeout_s: int
    sandbox: str
    tags: list[str] = field(default_factory=list)
    input_schema: dict = field(default_factory=dict)


def _spec(
    name: str,
    description: str,
    side_effect: str,
    approval_label: str,
    timeout_s: int,
    sandbox: str,
    tags: list[str],
    input_schema: dict | None = None,
) -> ToolSpec:
    assert side_effect in SIDE_EFFECT_LEVELS, side_effect
    assert approval_label in APPROVAL_LABELS, approval_label
    assert sandbox in SANDBOX_LABELS, sandbox
    return ToolSpec(
        name=name,
        description=description,
        side_effect=side_effect,
        approval_label=approval_label,
        timeout_s=timeout_s,
        sandbox=sandbox,
        tags=tags,
        input_schema=input_schema or {"type": "object"},
    )


_TOOLS: list[ToolSpec] = [
    _spec(
        "bash",
        "Run a shell command.",
        "LOCAL_WRITE",
        "ask",
        30,
        "unsandboxed",
        ["shell"],
        {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    ),
    _spec(
        "read_file",
        "Read a file from the workspace.",
        "READ_ONLY",
        "allow",
        5,
        "sandboxed",
        ["filesystem"],
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    ),
    _spec(
        "edit_file",
        "Edit an existing file.",
        "LOCAL_WRITE",
        "allow",
        10,
        "sandboxed",
        ["filesystem"],
    ),
    _spec(
        "write_file",
        "Write a new file.",
        "LOCAL_WRITE",
        "allow",
        10,
        "sandboxed",
        ["filesystem"],
    ),
    _spec(
        "web_fetch",
        "Fetch a single URL.",
        "READ_ONLY",
        "allow",
        30,
        "sandboxed",
        ["network"],
    ),
    _spec(
        "web_search",
        "Run a web search query.",
        "READ_ONLY",
        "allow",
        30,
        "sandboxed",
        ["network"],
    ),
    _spec(
        "git_commit",
        "Create a git commit in the workspace.",
        "LOCAL_WRITE",
        "allow",
        30,
        "sandboxed",
        ["git"],
    ),
    _spec(
        "git_push",
        "Push commits to a remote.",
        "REMOTE_WRITE",
        "ask",
        30,
        "unsandboxed",
        ["git", "network"],
    ),
    _spec(
        "gh_pr_create",
        "Create a GitHub PR.",
        "REMOTE_WRITE",
        "allow",
        30,
        "unsandboxed",
        ["git", "github"],
    ),
    _spec(
        "gh_pr_merge",
        "Merge a GitHub PR.",
        "REMOTE_WRITE",
        "ask",
        30,
        "unsandboxed",
        ["git", "github"],
    ),
    _spec(
        "kaggle_submit",
        "Submit predictions to Kaggle.",
        "SUBMISSION",
        "ask",
        60,
        "unsandboxed",
        ["kaggle"],
    ),
    _spec(
        "kaggle_push",
        "Push a Kaggle kernel/notebook.",
        "SUBMISSION",
        "ask",
        60,
        "unsandboxed",
        ["kaggle"],
    ),
    _spec(
        "supabase_migrate",
        "Apply a Supabase migration to the remote DB.",
        "REMOTE_WRITE",
        "ask",
        60,
        "unsandboxed",
        ["db"],
    ),
    _spec(
        "run_tests",
        "Run the project test suite.",
        "LOCAL_WRITE",
        "allow",
        120,
        "sandboxed",
        ["tests"],
    ),
    _spec(
        "litellm_call",
        "Invoke a routed LLM endpoint.",
        "LOCAL_WRITE",
        "allow",
        120,
        "sandboxed",
        ["llm"],
    ),
    _spec(
        "create_artifact",
        "Create an artifact under the workspace artifacts directory.",
        "LOCAL_WRITE",
        "allow",
        10,
        "sandboxed",
        ["filesystem", "artifact"],
    ),
    # M12-T004 — read-only inspector for hackathon submission packs.
    # The hackathon-runner permission profile keeps this on `ask` even
    # though the tool itself is READ_ONLY, so the agent has a single
    # consistent surface to gate against.
    _spec(
        "submission_checklist",
        "Inspect a run's submission_pack and emit a per-item checklist.",
        "READ_ONLY",
        "ask",
        10,
        "sandboxed",
        ["hackathon", "submission-pack"],
        {
            "type": "object",
            "properties": {
                "competition_id": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["competition_id", "run_id"],
        },
    ),
    # M12-T004 — the gated external write op the hackathon-runner profile
    # references. The actual implementation ships in M12-T007. Registering
    # the ToolSpec here lets the permission resolver + the skill's
    # allowed-tools surface line up before T007 lands.
    _spec(
        "devpost_submit",
        "Submit a Devpost-style hackathon entry (gated; M12-T007).",
        "SUBMISSION",
        "ask",
        60,
        "unsandboxed",
        ["hackathon", "devpost"],
    ),
    _spec(
        "demo_upload",
        "Upload a demo asset for a hackathon entry (gated; follow-up).",
        "REMOTE_WRITE",
        "ask",
        60,
        "unsandboxed",
        ["hackathon", "devpost"],
    ),
    _spec(
        "team_invite",
        "Invite a teammate to a hackathon team (deny by default in M12).",
        "REMOTE_WRITE",
        "deny",
        30,
        "unsandboxed",
        ["hackathon", "teams"],
    ),
]

TOOL_REGISTRY: dict[str, ToolSpec] = {t.name: t for t in _TOOLS}


def get_tool(name: str) -> ToolSpec | None:
    return TOOL_REGISTRY.get(name)


def list_tools(*, side_effect: str | None = None, tag: str | None = None) -> list[ToolSpec]:
    items = list(TOOL_REGISTRY.values())
    if side_effect is not None:
        items = [t for t in items if t.side_effect == side_effect]
    if tag is not None:
        items = [t for t in items if tag in t.tags]
    return sorted(items, key=lambda t: t.name)


def default_decision(tool_name: str) -> str:
    tool = get_tool(tool_name)
    if tool is None:
        return "ask"
    return tool.approval_label
