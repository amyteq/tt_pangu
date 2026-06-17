#!/usr/bin/env python3
"""Export a stopped/completed Claude Code background session to logs/<name>.md.

This script intentionally exports from Claude Code transcript JSONL via
`claude-code-log`, rather than from `claude logs`, because terminal output can
contain ANSI cursor/control sequences.

Read-list discipline: this script reads only ~/.claude/projects/**/*.jsonl,
~/.claude/jobs/*/state.json, and the stdout of `claude agents --json`. It does
NOT read .env*, ~/.kaggle/kaggle.json, ~/.ssh/**, ~/.aws/**,
~/.config/gcloud/**, ~/.config/gh/**, or secrets/**. The CLAUDE.md dev-phase
carve-out does not apply here — this script has no need for credentials.

Usage:
    python scripts/save_claude_session_log.py M7
    python scripts/save_claude_session_log.py <session-id>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TERMINAL_STATUSES = {"completed", "complete", "stopped", "stop"}

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained PAT"),
    (r"\bgh[opsu]_[A-Za-z0-9_]{20,}", "GitHub token"),
    (r"\bsk-ant-[A-Za-z0-9_\-]{20,}", "Anthropic API key"),
    (r"\bsk-[A-Za-z0-9_\-]{32,}", "generic sk-* API key"),
    (r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY", "private key block"),
    (r"\bANTHROPIC_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{16,}", "Anthropic env key"),
    (r"\bOPENAI_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{16,}", "OpenAI env key"),
    (r"\bKAGGLE_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}", "Kaggle key"),
    (r"\bSUPABASE_[A-Z0-9_]*KEY\s*=\s*['\"]?[A-Za-z0-9_\-.]{16,}", "Supabase key"),
    (
        r"\b(?:password|passwd|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-.]{16,}",
        "generic secret assignment",
    ),
]


@dataclass(frozen=True)
class Candidate:
    source: str
    job_id: str
    session_id: str
    name: str
    status: str
    cwd: str
    state_path: Path | None
    raw: dict[str, Any]


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def project_root() -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    proc = run(["git", "rev-parse", "--show-toplevel"], timeout=10)
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip()).resolve()

    return Path.cwd().resolve()


def claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser().resolve()


def walk_json(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from walk_json(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_json(value)


def first_value(obj: Any, keys: set[str]) -> str:
    if isinstance(obj, dict):
        for key in keys:
            value = obj.get(key)
            if value not in (None, ""):
                return str(value)

        for value in obj.values():
            found = first_value(value, keys)
            if found:
                return found

    elif isinstance(obj, list):
        for value in obj:
            found = first_value(value, keys)
            if found:
                return found

    return ""


def collect_jsonl_paths(obj: Any) -> list[Path]:
    paths: list[Path] = []
    for value in walk_json(obj):
        if isinstance(value, str) and value.endswith(".jsonl"):
            paths.append(Path(value).expanduser())
    return paths


def normalise_status(value: str) -> str:
    value = (value or "").strip().lower()
    if value in {"done", "success", "succeeded"}:
        return "completed"
    if value in {"cancelled", "canceled"}:
        return "stopped"
    return value


def related_to_project(cwd: str, root: Path) -> bool:
    if not cwd:
        return True

    try:
        p = Path(cwd).expanduser().resolve()
    except Exception:
        return True

    return p == root or root in p.parents or p in root.parents


def candidate_from_raw(
    raw: dict[str, Any],
    *,
    source: str,
    job_id: str = "",
    state_path: Path | None = None,
) -> Candidate:
    session_id = first_value(
        raw,
        {"sessionId", "session_id", "transcriptSessionId", "transcript_session_id"},
    )
    name = first_value(raw, {"name", "displayName", "display_name", "title"})
    status = first_value(raw, {"status", "state", "lifecycleState", "lifecycle_state"})
    cwd = first_value(raw, {"cwd", "workingDirectory", "working_dir", "projectDir", "project_dir"})

    if not job_id and state_path is not None:
        try:
            job_id = state_path.parent.name
        except Exception:
            job_id = ""

    return Candidate(
        source=source,
        job_id=job_id,
        session_id=session_id,
        name=name,
        status=normalise_status(status),
        cwd=cwd,
        state_path=state_path,
        raw=raw,
    )


def load_agents_from_cli(root: Path) -> list[Candidate]:
    proc = run(["claude", "agents", "--cwd", str(root), "--json"], cwd=root, timeout=20)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    out: list[Candidate] = []
    for item in data:
        if isinstance(item, dict):
            c = candidate_from_raw(item, source="claude agents --json")
            if related_to_project(c.cwd, root):
                out.append(c)
    return out


def load_agents_from_state_files(config_dir: Path, root: Path) -> list[Candidate]:
    jobs_dir = config_dir / "jobs"
    if not jobs_dir.exists():
        return []

    out: list[Candidate] = []
    for state_path in sorted(jobs_dir.glob("*/state.json")):
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(raw, dict):
            continue

        c = candidate_from_raw(raw, source="state.json", state_path=state_path)
        if related_to_project(c.cwd, root):
            out.append(c)

    return out


def dedupe(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Candidate] = []
    for c in candidates:
        key = (c.job_id, c.session_id, c.name)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def score_candidate(target: str, c: Candidate) -> int:
    t = target.strip()
    tl = t.lower()
    score = 0

    fields = [
        (c.job_id, 100),
        (c.session_id, 95),
        (c.name, 90),
    ]

    for value, exact_score in fields:
        if not value:
            continue
        vl = value.lower()
        if vl == tl:
            score = max(score, exact_score)
        elif vl.startswith(tl):
            score = max(score, exact_score - 10)
        elif tl in vl and exact_score == 90:
            score = max(score, 50)

    return score


def describe_candidate(c: Candidate) -> str:
    return (
        f"name={c.name or '-'} "
        f"job_id={c.job_id or '-'} "
        f"session_id={c.session_id or '-'} "
        f"status={c.status or '-'} "
        f"source={c.source}"
    )


def select_candidate(target: str, candidates: list[Candidate]) -> Candidate:
    scored = [(score_candidate(target, c), c) for c in candidates]
    scored = [(score, c) for score, c in scored if score > 0]

    if not scored:
        available = "\n".join(f"  - {describe_candidate(c)}" for c in candidates[:30])
        raise RuntimeError(
            f"No Claude background session matched {target!r}.\n"
            f"Available project sessions:\n{available or '  (none found)'}"
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    best = [c for score, c in scored if score == best_score]

    unique_keys = {(c.job_id, c.session_id, c.name) for c in best}
    if len(unique_keys) > 1 and best_score < 90:
        choices = "\n".join(f"  - {describe_candidate(c)}" for c in best)
        raise RuntimeError(f"Ambiguous session selector {target!r}. Use an id instead.\n{choices}")

    return best[0]


def find_transcript_from_state(candidate: Candidate, config_dir: Path) -> Path | None:
    for path in collect_jsonl_paths(candidate.raw):
        if not path.is_absolute():
            path = (candidate.state_path.parent if candidate.state_path else config_dir) / path
        if path.exists():
            return path.resolve()

    if candidate.session_id:
        matches = list((config_dir / "projects").glob(f"**/{candidate.session_id}.jsonl"))
        if matches:
            return matches[0].resolve()

    if candidate.job_id:
        matches = list((config_dir / "projects").glob(f"**/*{candidate.job_id}*.jsonl"))
        if matches:
            return matches[0].resolve()

    return None


def safe_filename(name: str) -> str:
    text = name.strip() or "claude-session"
    text = re.sub(r"[^\w.\-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip(".-")
    return text[:120] or "claude-session"


def run_claude_code_log(transcript: Path, tmp_md: Path, detail: str) -> None:
    uvx = shutil.which("uvx")
    if not uvx:
        raise RuntimeError("uvx not found. Install uv first, then run: uvx claude-code-log@latest --help")

    attempts: list[list[str]] = []
    for fmt in ("md", "markdown"):
        for output_flag in ("-o", "--output"):
            attempts.append(
                [
                    uvx,
                    "claude-code-log@latest",
                    str(transcript),
                    "--detail",
                    detail,
                    "--format",
                    fmt,
                    "--compact",
                    output_flag,
                    str(tmp_md),
                ]
            )
        attempts.append(
            [
                uvx,
                "claude-code-log@latest",
                str(transcript),
                "--detail",
                detail,
                "--format",
                fmt,
                "--compact",
            ]
        )

    errors: list[str] = []
    for cmd in attempts:
        proc = run(cmd, timeout=180)

        if cmd[-1] == str(tmp_md):
            if proc.returncode == 0 and tmp_md.exists() and tmp_md.stat().st_size > 0:
                return
        else:
            if proc.returncode == 0 and proc.stdout.strip():
                tmp_md.write_text(proc.stdout, encoding="utf-8")
                return

        errors.append("$ " + " ".join(cmd) + "\n" + f"returncode={proc.returncode}\n" + f"stderr={proc.stderr[-2000:]}")

    raise RuntimeError("claude-code-log failed.\n\n" + "\n\n---\n\n".join(errors[-3:]))


def scan_secret_like_text(text: str) -> list[str]:
    hits: list[str] = []
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(label)
    return hits


def build_header(candidate: Candidate, transcript: Path, output_path: Path) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = candidate.name or candidate.job_id or candidate.session_id or "Claude session"
    return (
        f"# Claude session log: {title}\n\n"
        f"- Exported at: `{now}`\n"
        f"- Session name: `{candidate.name or ''}`\n"
        f"- Job id: `{candidate.job_id or ''}`\n"
        f"- Session id: `{candidate.session_id or ''}`\n"
        f"- Status: `{candidate.status or ''}`\n"
        f"- Source transcript: `{transcript}`\n"
        f"- Output: `{output_path}`\n\n"
        "---\n\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "selector",
        help="Claude background session name, short job id, or session id",
    )
    parser.add_argument(
        "--allow-any-state",
        action="store_true",
        help="Export even if session is not completed/stopped",
    )
    parser.add_argument(
        "--allow-secret-like",
        action="store_true",
        help="Write even if secret-like patterns are found",
    )
    parser.add_argument(
        "--detail",
        default="low",
        choices=["low", "medium", "high"],
        help="claude-code-log detail level",
    )
    parser.add_argument(
        "--output-dir",
        default="logs",
        help="output directory, relative to repo root",
    )
    args = parser.parse_args()

    root = project_root()
    config_dir = claude_config_dir()

    candidates = dedupe(load_agents_from_cli(root) + load_agents_from_state_files(config_dir, root))

    candidate = select_candidate(args.selector, candidates)

    if not args.allow_any_state and candidate.status not in TERMINAL_STATUSES:
        raise RuntimeError(
            f"Matched session is not stopped/completed: {describe_candidate(candidate)}\n"
            f"Stop it first with `claude stop <id>` or rerun with --allow-any-state."
        )

    transcript = find_transcript_from_state(candidate, config_dir)
    if transcript is None:
        raise RuntimeError(
            f"Could not find transcript JSONL for session: {describe_candidate(candidate)}\n"
            f"Try `claude --resume` to locate the session, or search:\n"
            f"  find {config_dir}/projects -name '*.jsonl' | grep '<session-id>'"
        )

    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    out_name = safe_filename(candidate.name or candidate.job_id or candidate.session_id or args.selector)
    output_path = output_dir / f"{out_name}.md"

    with tempfile.TemporaryDirectory(prefix="save-claude-log-") as tmp_dir_s:
        tmp_dir = Path(tmp_dir_s)
        tmp_md = tmp_dir / "session.md"

        run_claude_code_log(transcript, tmp_md, args.detail)

        body = tmp_md.read_text(encoding="utf-8", errors="replace")
        final_text = build_header(candidate, transcript, output_path) + body.rstrip() + "\n"

        hits = scan_secret_like_text(final_text)
        if hits and not args.allow_secret_like:
            labels = ", ".join(sorted(set(hits)))
            raise RuntimeError(
                f"Refusing to write {output_path}: secret-like patterns detected: {labels}.\n"
                f"Manually inspect the transcript, redact sensitive content, or rerun with --allow-secret-like."
            )

        tmp_out = output_path.with_suffix(".tmp.md")
        tmp_out.write_text(final_text, encoding="utf-8")
        tmp_out.replace(output_path)

    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output_path.relative_to(root)),
                "matched": {
                    "name": candidate.name,
                    "job_id": candidate.job_id,
                    "session_id": candidate.session_id,
                    "status": candidate.status,
                    "source": candidate.source,
                },
                "transcript": str(transcript),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        eprint(f"ERROR: {exc}")
        raise SystemExit(1)
