#!/usr/bin/env python3
"""Export Claude Code session transcripts to Markdown — batch or single.

Builds on the conventions of scripts/save_claude_session_log.py:
- Reads ~/.claude/projects/**/*.jsonl, ~/.claude/jobs/*/state.json, and
  `claude agents --json`. Does NOT read .env*, kaggle.json, ~/.ssh,
  ~/.aws, ~/.config/gcloud, ~/.config/gh, or secrets/.
- Renders through `uvx claude-code-log@latest --format md --compact`.
- Refuses to write transcripts containing secret-like patterns unless
  --allow-secret-like is passed.

Differences from scripts/save_claude_session_log.py:
- `--all` (default) exports every session discoverable for the project.
- `--name` / `--id` narrow to a single session (mutually exclusive with
  each other; either disables `--all`).
- `--detail` defaults to `high` so the full content is rendered.
- `--json` toggles structured output (single object for one session,
  array under "results" for batch); without --json, prints
  human-readable progress + a one-line summary.
- In batch mode, per-session failures (missing transcript, non-terminal
  state, secret hit) are recorded and the run continues. The exit code
  is 0 if at least one session exported; non-zero only if every
  candidate failed.

Usage:
    python temp/export_claude_session_logs.py
    python temp/export_claude_session_logs.py --name M7
    python temp/export_claude_session_logs.py --id 01F8ABC...
    python temp/export_claude_session_logs.py --all --json
    python temp/export_claude_session_logs.py --allow-any-state --detail high
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


def run(
    cmd: list[str], *, cwd: Path | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
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
    cwd = first_value(
        raw, {"cwd", "workingDirectory", "working_dir", "projectDir", "project_dir"}
    )

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


def score_candidate(target: str, c: Candidate, *, field: str | None = None) -> int:
    """Score a candidate. If `field` is 'name' or 'id', restrict matching
    to that surface (id covers both job_id and session_id). When None,
    matches any of the three (original behavior)."""
    t = target.strip()
    tl = t.lower()
    score = 0

    if field == "name":
        fields = [(c.name, 90)]
    elif field == "id":
        fields = [(c.job_id, 100), (c.session_id, 95)]
    else:
        fields = [(c.job_id, 100), (c.session_id, 95), (c.name, 90)]

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


def select_candidate(
    target: str, candidates: list[Candidate], *, field: str | None = None
) -> Candidate:
    scored = [(score_candidate(target, c, field=field), c) for c in candidates]
    scored = [(score, c) for score, c in scored if score > 0]

    if not scored:
        available = "\n".join(f"  - {describe_candidate(c)}" for c in candidates[:30])
        raise RuntimeError(
            f"No Claude background session matched {target!r}"
            f"{' on ' + field if field else ''}.\n"
            f"Available project sessions:\n{available or '  (none found)'}"
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    best = [c for score, c in scored if score == best_score]

    unique_keys = {(c.job_id, c.session_id, c.name) for c in best}
    if len(unique_keys) > 1 and best_score < 90:
        choices = "\n".join(f"  - {describe_candidate(c)}" for c in best)
        raise RuntimeError(
            f"Ambiguous session selector {target!r}. Use an id instead.\n{choices}"
        )

    return best[0]


def find_transcript_from_state(candidate: Candidate, config_dir: Path) -> Path | None:
    for path in collect_jsonl_paths(candidate.raw):
        if not path.is_absolute():
            path = (
                candidate.state_path.parent if candidate.state_path else config_dir
            ) / path
        if path.exists():
            return path.resolve()

    if candidate.session_id:
        matches = list(
            (config_dir / "projects").glob(f"**/{candidate.session_id}.jsonl")
        )
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
        raise RuntimeError(
            "uvx not found. Install uv first, then run: uvx claude-code-log@latest --help"
        )

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

        errors.append(
            "$ "
            + " ".join(cmd)
            + "\n"
            + f"returncode={proc.returncode}\n"
            + f"stderr={proc.stderr[-2000:]}"
        )

    raise RuntimeError("claude-code-log failed.\n\n" + "\n\n---\n\n".join(errors[-3:]))


def redact_match(matched: str) -> str:
    """Mask the middle of a matched secret-like substring so the caller
    can recognise what tripped the scan without echoing the secret."""
    if not matched:
        return ""
    if "PRIVATE KEY" in matched.upper():
        return "[private key block]"
    s = matched.strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}...{s[-4:]} (len={len(s)})"


def scan_secret_like_lines(text: str) -> list[dict[str, Any]]:
    """Return per-line secret-like matches: {line, label, match_preview}.
    Each (line, label) pair is emitted at most once."""
    locations: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, label in SECRET_PATTERNS:
            m = re.search(pattern, line, flags=re.IGNORECASE)
            if not m:
                continue
            key = (lineno, label)
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                {
                    "line": lineno,
                    "label": label,
                    "match_preview": redact_match(m.group(0)),
                }
            )
    return locations


def build_header(candidate: Candidate, transcript: Path, output_path: Path) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    title = (
        candidate.name or candidate.job_id or candidate.session_id or "Claude session"
    )
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


def export_one(
    candidate: Candidate,
    *,
    root: Path,
    config_dir: Path,
    output_dir: Path,
    detail: str,
    allow_any_state: bool,
    allow_secret_like: bool,
) -> dict[str, Any]:
    """Export a single session. Returns a result record; never raises
    for per-session failures — those land in the record's `error`."""
    base: dict[str, Any] = {
        "matched": {
            "name": candidate.name,
            "job_id": candidate.job_id,
            "session_id": candidate.session_id,
            "status": candidate.status,
            "source": candidate.source,
        },
    }

    if not allow_any_state and candidate.status not in TERMINAL_STATUSES:
        return {
            **base,
            "ok": False,
            "skipped": True,
            "reason": "non-terminal-state",
            "error": (
                f"Session not stopped/completed (status={candidate.status!r}); "
                "rerun with --allow-any-state to include it."
            ),
        }

    transcript = find_transcript_from_state(candidate, config_dir)
    if transcript is None:
        return {
            **base,
            "ok": False,
            "skipped": True,
            "reason": "transcript-not-found",
            "error": (
                f"Could not find transcript JSONL for session. "
                f"Hint: find {config_dir}/projects -name '*.jsonl' | "
                f"grep '{candidate.session_id or candidate.job_id or candidate.name}'"
            ),
        }

    out_name = safe_filename(
        candidate.name or candidate.job_id or candidate.session_id or "claude-session"
    )
    output_path = output_dir / f"{out_name}.md"

    with tempfile.TemporaryDirectory(prefix="export-claude-log-") as tmp_dir_s:
        tmp_dir = Path(tmp_dir_s)
        tmp_md = tmp_dir / "session.md"

        try:
            run_claude_code_log(transcript, tmp_md, detail)
        except Exception as exc:
            return {
                **base,
                "ok": False,
                "skipped": False,
                "reason": "render-failed",
                "error": str(exc),
                "transcript": str(transcript),
            }

        body = tmp_md.read_text(encoding="utf-8", errors="replace")
        final_text = (
            build_header(candidate, transcript, output_path) + body.rstrip() + "\n"
        )

        locations = scan_secret_like_lines(final_text)
        labels = sorted({loc["label"] for loc in locations})
        if locations and not allow_secret_like:
            return {
                **base,
                "ok": False,
                "skipped": True,
                "reason": "secret-like-detected",
                "error": (
                    f"Refused to write {output_path}: secret-like patterns "
                    f"detected on {len(locations)} line(s): "
                    f"{', '.join(labels)}. Inspect manually and rerun with "
                    "--allow-secret-like to override."
                ),
                "transcript": str(transcript),
                "secret_labels": labels,
                "secret_locations": locations,
            }

        tmp_out = output_path.with_suffix(".tmp.md")
        tmp_out.write_text(final_text, encoding="utf-8")
        tmp_out.replace(output_path)

    try:
        out_rel = str(output_path.relative_to(root))
    except ValueError:
        out_rel = str(output_path)

    return {
        **base,
        "ok": True,
        "skipped": False,
        "output": out_rel,
        "transcript": str(transcript),
        "secret_labels": labels,
        "secret_locations": locations,
        "secret_override_applied": bool(locations and allow_secret_like),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_claude_session_logs.py",
        description=(
            "Export Claude Code session transcripts to Markdown. Defaults "
            "to exporting every session discoverable for the current "
            "project. Use --name or --id to target one session."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python temp/export_claude_session_logs.py\n"
            "  python temp/export_claude_session_logs.py --name M7\n"
            "  python temp/export_claude_session_logs.py --id 01F8ABC\n"
            "  python temp/export_claude_session_logs.py --json --output-dir logs\n"
            "  python temp/export_claude_session_logs.py --allow-any-state --detail high\n"
        ),
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--name",
        default=None,
        help="Find the transcript JSONL by session name (exact / prefix / substring).",
    )
    selector.add_argument(
        "--id",
        dest="id",
        default=None,
        help="Find the transcript JSONL by job id or session id.",
    )
    parser.add_argument(
        "--all",
        dest="all",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export all discoverable sessions (default: on). Disabled "
        "automatically when --name or --id is given.",
    )
    parser.add_argument(
        "--allow-any-state",
        action="store_true",
        help="Skip the stopped/completed state check (include running sessions).",
    )
    parser.add_argument(
        "--allow-secret-like",
        action="store_true",
        help="Write even if secret-like patterns are found in the rendered transcript.",
    )
    parser.add_argument(
        "--detail",
        default="high",
        choices=["low", "medium", "high"],
        help="claude-code-log detail level (default: high — full content).",
    )
    parser.add_argument(
        "--output-dir",
        default="logs",
        help="Output directory, relative to repo root (default: logs).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the tool's own result in JSON.",
    )
    return parser


def emit_human(result: dict[str, Any]) -> None:
    matched = result.get("matched", {})
    label = (
        matched.get("name")
        or matched.get("job_id")
        or matched.get("session_id")
        or "?"
    )
    locations: list[dict[str, Any]] = result.get("secret_locations") or []

    if result.get("ok"):
        eprint(f"[ok]      {label} -> {result.get('output')}")
        if result.get("secret_override_applied") and locations:
            eprint(
                f"          WARN: --allow-secret-like override applied; "
                f"{len(locations)} secret-like line(s) written:"
            )
            for loc in locations:
                eprint(
                    f"            - line {loc['line']:>6}: "
                    f"{loc['label']} [{loc['match_preview']}]"
                )
    elif result.get("skipped"):
        eprint(
            f"[skip:{result.get('reason')}] {label} "
            f"(status={matched.get('status')}): {result.get('error')}"
        )
        if result.get("reason") == "secret-like-detected" and locations:
            eprint(
                f"          {len(locations)} secret-like line(s) "
                "(rerun with --allow-secret-like to write anyway):"
            )
            for loc in locations:
                eprint(
                    f"            - line {loc['line']:>6}: "
                    f"{loc['label']} [{loc['match_preview']}]"
                )
    else:
        eprint(f"[fail:{result.get('reason')}] {label}: {result.get('error')}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root = project_root()
    config_dir = claude_config_dir()

    candidates = dedupe(
        load_agents_from_cli(root) + load_agents_from_state_files(config_dir, root)
    )

    if not candidates:
        payload = {
            "ok": False,
            "results": [],
            "summary": {"total": 0, "exported": 0, "skipped": 0, "failed": 0},
            "error": (
                "No Claude background sessions discoverable for this project. "
                f"Checked `claude agents --json` and {config_dir}/jobs/*/state.json."
            ),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            eprint(payload["error"])
        return 2

    if args.name is not None:
        targets = [select_candidate(args.name, candidates, field="name")]
        single = True
    elif args.id is not None:
        targets = [select_candidate(args.id, candidates, field="id")]
        single = True
    elif args.all:
        targets = candidates
        single = False
    else:
        eprint("Nothing to do: pass --name, --id, or --all (default).")
        return 2

    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for c in targets:
        result = export_one(
            c,
            root=root,
            config_dir=config_dir,
            output_dir=output_dir,
            detail=args.detail,
            allow_any_state=args.allow_any_state,
            allow_secret_like=args.allow_secret_like,
        )
        results.append(result)
        if not args.json:
            emit_human(result)

    exported = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if not r.get("ok") and r.get("skipped"))
    failed = sum(1 for r in results if not r.get("ok") and not r.get("skipped"))

    summary = {
        "total": len(results),
        "exported": exported,
        "skipped": skipped,
        "failed": failed,
    }

    if args.json:
        if single:
            payload = {**results[0], "summary": summary}
        else:
            payload = {
                "ok": exported > 0,
                "results": results,
                "summary": summary,
                "output_dir": str(output_dir.relative_to(root))
                if output_dir.is_relative_to(root)
                else str(output_dir),
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        eprint(
            f"\nSummary: {exported} exported, {skipped} skipped, "
            f"{failed} failed (of {len(results)} candidate(s))."
        )

    if exported == 0:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        eprint("Interrupted.")
        raise SystemExit(130)
    except Exception as exc:
        eprint(f"ERROR: {exc}")
        raise SystemExit(1)
