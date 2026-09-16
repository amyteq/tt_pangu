#!/usr/bin/env python3
"""Push a Claude Code or Codex harness event to Telegram via `kca notify`.

One script, two callers (#197 follow-up — "how can we enable telegram
notifications in claude and codex agents themselves?"):

* **Claude Code hook** — the harness pipes a JSON object on **stdin** with
  ``hook_event_name`` (``Notification`` / ``Stop`` / ``StopFailure`` /
  ``SubagentStop`` / ``SessionEnd`` …), ``session_id``, ``cwd`` and, for
  ``Notification``, ``message``. Verified against Claude Code 2.1.273.
* **Codex `notify`** — the harness execs the program with **one argv** holding
  a JSON object: ``type`` (``agent-turn-complete``), ``thread-id``,
  ``turn-id``, ``cwd``, ``input-messages``, ``last-assistant-message``.
  Verified against codex-cli 0.154.0.

This is the *push* half only. Replies still go through the GitHub record
(`/decide …`) or, for a live two-way session, the official Claude Code Telegram
channel plugin — see discussion #187, which owns that half.

Exit code is always 0: a notification failure must never break the harness turn
it is reporting on. Failures are printed to stderr for the hook log.

Usage (see docs/tooling/notification-channel.md for the settings snippets):

    # Claude Code hook
    scripts/agent_notify.py --source claude --level attention
    # Codex config.toml:  notify = ["/path/scripts/agent_notify.py", "--source", "codex"]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import notify  # noqa: E402

# Harness event -> level, when --level is not given. `Stop` is deliberately
# absent: it fires on every turn end, and #187 §4 warns against reporting each
# Stop as "task complete". Wire it explicitly if you want it.
CLAUDE_EVENT_LEVELS = {
    "Notification": "attention",  # the session is waiting on you
    "StopFailure": "attention",  # the turn ended in an API error
    "SubagentStop": "info",
    "SessionEnd": "info",
    "Stop": "info",
}
CODEX_EVENT_LEVELS = {"agent-turn-complete": "info"}

MAX_BODY_CHARS = 600


def read_payload(source: str, argv_rest: list[str]) -> dict:
    """Codex passes JSON as an argument; Claude Code pipes it on stdin."""
    if source == "codex":
        for arg in argv_rest:
            candidate = arg.strip()
            if candidate.startswith("{"):
                return json.loads(candidate)
        return {}
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    return json.loads(raw) if raw.strip() else {}


def _clip(text: str, limit: int = MAX_BODY_CHARS) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_message(source: str, payload: dict, label: str | None) -> tuple[str, str, str | None]:
    """Return (title, body, event_level). Never raises on a shape surprise."""
    tag = label or Path(str(payload.get("cwd") or REPO_ROOT)).name
    if source == "codex":
        event = str(payload.get("type") or "codex-event")
        inputs = payload.get("input-messages") or []
        prompt = _clip(inputs[0] if isinstance(inputs, list) and inputs else "", 160)
        title = f"Codex · {tag} · {event}"
        body = _clip(payload.get("last-assistant-message") or "")
        if prompt:
            body = f"↪ {prompt}\n\n{body}" if body else f"↪ {prompt}"
        thread = str(payload.get("thread-id") or "")
        if thread:
            body = f"{body}\n\nthread {thread[:12]}"
        return title, body or "(no message)", CODEX_EVENT_LEVELS.get(event)

    event = str(payload.get("hook_event_name") or "ClaudeEvent")
    title = f"Claude Code · {tag} · {event}"
    body = _clip(payload.get("message") or payload.get("reason") or "")
    session = str(payload.get("session_id") or "")
    if session:
        body = f"{body}\n\nsession {session[:12]}" if body else f"session {session[:12]}"
    return title, body or "(no message)", CLAUDE_EVENT_LEVELS.get(event)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=("claude", "codex"), required=True)
    parser.add_argument("--level", choices=notify.LEVELS, default=None, help="override the per-event default")
    parser.add_argument("--bot", default=None, help="bot key in .kca/notify.yml (one bot per agent entry, #187 §3)")
    parser.add_argument("--recipient", default=None)
    parser.add_argument("--label", default=None, help="short name for this entry, e.g. 'ayla1 · kaggle'")
    parser.add_argument("--config", default=None)
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args, rest = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    try:
        payload = read_payload(args.source, rest)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[agent_notify] unreadable {args.source} payload: {exc}", file=sys.stderr)
        return 0

    title, body, event_level = build_message(args.source, payload, args.label)
    level = args.level or event_level
    if level is None:
        # An event we do not have a rule for is not worth waking a phone over.
        print(f"[agent_notify] no level for this event; skipping: {title}", file=sys.stderr)
        return 0

    try:
        cfg = notify.load_config(args.config)
        result = notify.dispatch(
            cfg,
            level=level,
            title=title,
            body=body,
            recipient=args.recipient,
            bot=args.bot,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:  # never break the harness turn we are reporting on
        print(f"[agent_notify] send failed: {notify.redact(exc)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
