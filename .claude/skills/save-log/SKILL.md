---
name: save-log
description: Export a stopped or completed Claude Code background session transcript to logs/<session-name>.md using claude-code-log.
argument-hint: "<name|id>"
arguments:
  - session
allowed-tools:
  - Bash(python scripts/save_claude_session_log.py*)
disable-model-invocation: true
tags:
  - logging
  - handoff
  - claude-code
---

# save-log — export Claude Code session transcript to logs/

Use this skill to turn a **stopped** or **completed** Claude Code background-session transcript into a clean Markdown file under `logs/<session-name>.md`, ready for handoff packs or milestone evidence.

## Usage

```text
/save-log <name|id>
```

Examples:

```text
/save-log M7
/save-log 01F8ABC
/save-log 01F8ABCDEF1234567890
```

Prefer a Claude Code **agent name** or **short job id** for the selector. If the agent name has spaces, use an id; or rename the agent to a slug-like string (`M7`, `m9-2-impl`, …) first.

## How it works

The skill shells out to `python scripts/save_claude_session_log.py "$session"`, which:

1. Lists candidate sessions via `claude agents --json` and `~/.claude/jobs/*/state.json`.
2. Picks the best match for `<name|id>` (exact / prefix / substring scoring; ambiguous fuzzy matches fail loudly).
3. Refuses to export anything that is not `completed` or `stopped` unless `--allow-any-state` is set.
4. Locates the transcript JSONL under `~/.claude/projects/` (no fallback to `claude logs` terminal output — ANSI escape sequences would corrupt the export).
5. Calls `uvx claude-code-log@latest --detail low --format md --compact` to render clean Markdown.
6. Runs a configured secret-pattern scan on the rendered output and refuses to write if any pattern matches, unless `--allow-secret-like` is set.
7. Writes atomically to `logs/<safe-name>.md` (overwrites any previous export with the same name).

## Output

`logs/<safe-name>.md` with a small header block (Exported at, Session name, Job id, Session id, Status, Source transcript, Output) followed by the `claude-code-log --detail low --compact` body.

The script also prints a JSON closeout to stdout:

```json
{
  "ok": true,
  "output": "logs/m9_2-impl.md",
  "matched": {
    "name": "m9_2-impl",
    "job_id": "...",
    "session_id": "...",
    "status": "completed",
    "source": "claude agents --json"
  },
  "transcript": "/home/.../<session-id>.jsonl"
}
```

## Safety rules

- Reads only `~/.claude/projects/`, `~/.claude/jobs/`, and the stdout of `claude agents --json`. Does not read `.env*`, `~/.kaggle/kaggle.json`, `~/.ssh/**`, `~/.aws/**`, `~/.config/gcloud/**`, `~/.config/gh/**`, or `secrets/**` — even though the CLAUDE.md dev-phase carve-out allows some of those, this skill has no need for credentials.
- `disable-model-invocation: true` — only a human typing `/save-log` may trigger this skill. The model must not invoke it programmatically.
- Refuses to write if any of the configured secret patterns in `SECRET_PATTERNS` match the rendered transcript. Override with `--allow-secret-like` only after inspecting the transcript by hand.

## Out of scope

- Never commit exported transcripts. `logs/`, `worklogs/` and `.agent/` are local-only; masking known token shapes does not make a transcript safe to publish. Write a new sanitized evidence summary instead.
- No `claude logs` ANSI-strip fallback. If the transcript JSONL can't be located, the script fails loudly with the exact `find` hint.
- No `--all` mode. One session per invocation.

## Reference

Design rationale and the canonical reference implementation: `docs/meeting-notes/2026-05-26-r1.md`.
