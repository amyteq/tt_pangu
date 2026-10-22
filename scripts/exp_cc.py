#!/usr/bin/env python3
"""Export Claude Code session transcripts to Markdown — batch or single.

Builds on the conventions of scripts/save_claude_session_log.py:
- Reads ~/.claude/projects/**/*.jsonl, ~/.claude/jobs/*/state.json, and
  `claude agents --json`. Does NOT read .env*, kaggle.json, ~/.ssh,
  ~/.aws, ~/.config/gcloud, ~/.config/gh, or secrets/.
- Renders through `uvx claude-code-log@latest --format md --compact`.
- Writes Markdown dumps to `.agent/worklogs/` under the repo root by default
  (override with --output-dir).
- Refuses to write transcripts containing secret-like patterns unless
  --allow-secret-like is passed; with that flag the matched secrets are
  masked (first/last 3 chars kept, the rest replaced with '*') so the
  matched values are obscured. This is not a complete privacy or secret scan;
  exported transcripts must remain local and must never be committed.

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
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


TERMINAL_STATUSES = {"completed", "complete", "stopped", "stop"}

# Number of leading/trailing characters of a secret body left in the clear
# when masking (everything between them becomes '*'). Keep small so that the
# masked value remains recognisable without disclosing the secret.
MASK_KEEP = 3

# Each rule is (regex, label, value_group). value_group selects the portion of
# the match that is the actual secret body to mask: 0 = mask the whole match;
# a positive index masks only that capturing group (so for `KEY=value` style
# assignments the variable name stays visible and only the value is masked).
SECRET_PATTERNS: list[tuple[str, str, int]] = [
    (
        r"(\b(?:postgres(?:ql)?|mysql|mongodb|redis)://[^\s/:@]+:)([^\s@]+)(@)",
        "database URL password",
        2,
    ),
    (r"(\bPGPASSWORD\s*=\s*['\"]?)([^\s'\";]{8,})", "Postgres env password", 2),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained PAT", 0),
    (r"\bgh[opsu]_[A-Za-z0-9_]{20,}", "GitHub token", 0),
    (r"\bsk-ant-[A-Za-z0-9_\-]{20,}", "Anthropic API key", 0),
    (r"\bsk-[A-Za-z0-9_\-]{32,}", "generic sk-* API key", 0),
    (r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY", "private key block", 0),
    (
        r"(\bANTHROPIC_API_KEY\s*=\s*['\"]?)([A-Za-z0-9_\-]{16,})",
        "Anthropic env key",
        2,
    ),
    (r"(\bOPENAI_API_KEY\s*=\s*['\"]?)([A-Za-z0-9_\-]{16,})", "OpenAI env key", 2),
    (r"(\bKAGGLE_KEY\s*=\s*['\"]?)([A-Za-z0-9_\-]{8,})", "Kaggle key", 2),
    (
        r"(\bSUPABASE_[A-Z0-9_]*KEY\s*=\s*['\"]?)([A-Za-z0-9_\-.]{16,})",
        "Supabase key",
        2,
    ),
    (
        r"(\b(?:password|passwd|secret|token)\s*[:=]\s*['\"]?)([A-Za-z0-9_\-.]{16,})",
        "generic secret assignment",
        2,
    ),
]

# Full `-----BEGIN ... PRIVATE KEY-----` ... `-----END ... PRIVATE KEY-----`
# block, masked in one shot so the base64 body never reaches the output.
PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----",
    flags=re.DOTALL,
)


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


def identity_key(c: Candidate) -> tuple[str, str]:
    """A stable identity for a session. The session id uniquely identifies a
    transcript, so it is the primary key; fall back to job id, then name. This
    matters because the SAME session surfaces from two sources with different
    completeness — `claude agents --json` reports the session id but no job id,
    while jobs/<id>/state.json reports both — and keying on all three fields
    would treat them as two sessions and dump the transcript twice."""
    if c.session_id:
        return ("sid", c.session_id)
    if c.job_id:
        return ("job", c.job_id)
    return ("name", c.name)


def merge_candidates(a: Candidate, b: Candidate) -> Candidate:
    """Combine two records for the same session into the richer one: prefer the
    record backed by a state.json file (it carries job id + status + the raw
    payload used for transcript resolution), then fill any blank fields from the
    other and prefer a terminal status."""
    primary, secondary = (a, b) if a.state_path else (b, a)
    status = primary.status
    if status not in TERMINAL_STATUSES and secondary.status in TERMINAL_STATUSES:
        status = secondary.status
    return Candidate(
        source=primary.source,
        job_id=primary.job_id or secondary.job_id,
        session_id=primary.session_id or secondary.session_id,
        name=primary.name or secondary.name,
        status=status or primary.status or secondary.status,
        cwd=primary.cwd or secondary.cwd,
        state_path=primary.state_path or secondary.state_path,
        raw=primary.raw or secondary.raw,
    )


def dedupe(candidates: list[Candidate]) -> list[Candidate]:
    by_key: dict[tuple[str, str], Candidate] = {}
    order: list[tuple[str, str]] = []
    for c in candidates:
        key = identity_key(c)
        if key in by_key:
            by_key[key] = merge_candidates(by_key[key], c)
        else:
            by_key[key] = c
            order.append(key)
    return [by_key[key] for key in order]


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


def select_candidate(target: str, candidates: list[Candidate], *, field: str | None = None) -> Candidate:
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
        raise RuntimeError(f"Ambiguous session selector {target!r}. Use an id instead.\n{choices}")

    return best[0]


def safe_glob(base: Path, pattern: str) -> list[Path]:
    """Recursive glob that tolerates unreadable siblings. Under a shared
    config dir (e.g. ~/.claude/projects with per-project 0700 dirs that a CI
    runner is only partially ACL'd into), a plain Path.glob can raise
    PermissionError mid-walk; swallow those and return what is reachable."""
    try:
        return list(base.glob(pattern))
    except (PermissionError, OSError):
        out: list[Path] = []
        try:
            children = list(base.iterdir())
        except (PermissionError, OSError):
            return out
        for child in children:
            if child.is_dir():
                try:
                    out.extend(child.rglob(pattern.removeprefix("**/")))
                except (PermissionError, OSError):
                    continue
        return out


def find_transcript_from_state(candidate: Candidate, config_dir: Path) -> Path | None:
    for path in collect_jsonl_paths(candidate.raw):
        if not path.is_absolute():
            path = (candidate.state_path.parent if candidate.state_path else config_dir) / path
        if path.exists():
            return path.resolve()

    if candidate.session_id:
        matches = safe_glob(config_dir / "projects", f"**/{candidate.session_id}.jsonl")
        if matches:
            return matches[0].resolve()

    if candidate.job_id:
        matches = safe_glob(config_dir / "projects", f"**/*{candidate.job_id}*.jsonl")
        if matches:
            return matches[0].resolve()

    return None


def safe_filename(name: str) -> str:
    text = name.strip() or "claude-session"
    text = re.sub(r"[^\w.\-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip(".-")
    return text[:120] or "claude-session"


def base_output_name(candidate: Candidate) -> str:
    return safe_filename(candidate.name or candidate.job_id or candidate.session_id or "claude-session")


def short_disambiguator(candidate: Candidate) -> str:
    """A short, stable suffix for a candidate. Prefer the session id, then the
    job id, so the same session keeps the same filename across runs (date-based
    suffixes would mint a new file every day and defeat byte-stability)."""
    raw = candidate.session_id or candidate.job_id
    return safe_filename(raw)[:8] if raw else ""


def assign_output_names(candidates: list[Candidate]) -> list[str]:
    """Return one filename stem per candidate, aligned by index, guaranteeing
    no two candidates share a stem. Names that are unique keep the clean
    `<name>` form; only colliding names get a `<name>_<short id>` suffix, so a
    second session sharing a name never silently overwrites the first."""
    bases = [base_output_name(c) for c in candidates]
    counts = Counter(bases)
    used: set[str] = set()
    names: list[str] = []
    for candidate, base in zip(candidates, bases):
        if counts[base] > 1:
            suffix = short_disambiguator(candidate)
            name = f"{base}_{suffix}" if suffix else base
        else:
            name = base
        # Final guard: if the disambiguated name still clashes (e.g. two
        # sessions with the same name and no usable id), append a counter.
        unique = name
        n = 2
        while unique in used:
            unique = f"{name}_{n}"
            n += 1
        used.add(unique)
        names.append(unique)
    return names


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


def redact_match(matched: str) -> str:
    """Withhold the entire match; diagnostics need a rule and location only."""
    return "[redacted]" if matched else ""


def scan_secret_like_lines(text: str) -> list[dict[str, Any]]:
    """Return per-line secret-like matches: {line, label, match_preview}.
    Each (line, label) pair is emitted at most once."""
    locations: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, label, _value_group in SECRET_PATTERNS:
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


def mask_secret_body(s: str, *, keep: int = MASK_KEEP) -> str:
    """Mask the middle of a secret, leaving `keep` chars at each end in the
    clear and replacing the rest with '*'. Secrets too short to keep both
    ends without overlap are masked in full."""
    if not s:
        return s
    if len(s) <= keep * 2:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep * 2) + s[-keep:]


def mask_secret_like_text(text: str) -> str:
    """Return `text` with every secret-like match masked in place.

    Private-key blocks are collapsed to a single redaction marker; every
    other rule masks only its secret body (the whole match, or the captured
    value group for `KEY=value` assignments) so the surrounding markdown and
    variable names stay readable. Idempotent: re-masking masked text is a
    no-op because the patterns no longer match the '*'-filled bodies."""
    text = PRIVATE_KEY_BLOCK_RE.sub("-----BEGIN PRIVATE KEY----- [REDACTED] -----END PRIVATE KEY-----", text)

    for pattern, _label, value_group in SECRET_PATTERNS:

        def repl(m: re.Match[str], vg: int = value_group) -> str:
            whole = m.group(0)
            if vg == 0 or m.group(vg) is None:
                return mask_secret_body(whole)
            start = m.start(vg) - m.start(0)
            end = m.end(vg) - m.start(0)
            return whole[:start] + mask_secret_body(m.group(vg)) + whole[end:]

        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text


def build_header(candidate: Candidate, transcript: Path) -> str:
    # The header must be a pure function of the session CONTENT so an unchanged
    # session re-exports to byte-identical Markdown and the daily worklogs
    # routine produces no commit. So: no "Exported at" wall-clock, and no
    # "Output" path — the output path varies per run (the routine renders into a
    # fresh temp worktree), which otherwise churned every file on every run.
    # The git commit time already records when a dump happened.
    title = candidate.name or candidate.job_id or candidate.session_id or "Claude session"
    return (
        f"# Claude session log: {title}\n\n"
        f"- Session name: `{candidate.name or ''}`\n"
        f"- Job id: `{candidate.job_id or ''}`\n"
        f"- Session id: `{candidate.session_id or ''}`\n"
        f"- Status: `{candidate.status or ''}`\n"
        f"- Source transcript: `{transcript}`\n\n"
        "---\n\n"
    )


def export_one(
    candidate: Candidate,
    *,
    root: Path,
    config_dir: Path,
    output_dir: Path,
    output_name: str,
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

    output_path = output_dir / f"{output_name}.md"

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
        final_text = build_header(candidate, transcript) + body.rstrip() + "\n"

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
                    "--allow-secret-like to write a masked copy."
                ),
                "transcript": str(transcript),
                "secret_labels": labels,
                "secret_locations": locations,
            }

        # When writing despite secret-like hits (--allow-secret-like), mask the
        # secret bodies first. This is not a complete privacy or secret scan;
        # exported transcripts must remain local and must never be committed.
        masked = bool(locations)
        if masked:
            final_text = mask_secret_like_text(final_text)

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
        "secret_masked": masked,
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
            "  python temp/export_claude_session_logs.py --json --output-dir .agent/worklogs\n"
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
        help="Export all discoverable sessions (default: on). Disabled automatically when --name or --id is given.",
    )
    parser.add_argument(
        "--allow-any-state",
        action="store_true",
        help="Skip the stopped/completed state check (include running sessions).",
    )
    parser.add_argument(
        "--allow-secret-like",
        action="store_true",
        help="Write even if secret-like patterns are found in the rendered "
        "transcript; matched secrets are masked (first/last "
        f"{MASK_KEEP} chars kept, the rest replaced with '*').",
    )
    parser.add_argument(
        "--detail",
        default="high",
        choices=["low", "medium", "high"],
        help="claude-code-log detail level (default: high — full content).",
    )
    parser.add_argument(
        "--output-dir",
        default=".agent/worklogs",
        help="Output directory, relative to repo root (default: .agent/worklogs).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the tool's own result in JSON.",
    )
    return parser


def emit_human(result: dict[str, Any]) -> None:
    matched = result.get("matched", {})
    label = matched.get("name") or matched.get("job_id") or matched.get("session_id") or "?"
    locations: list[dict[str, Any]] = result.get("secret_locations") or []

    if result.get("ok"):
        eprint(f"[ok]      {label} -> {result.get('output')}")
        if result.get("secret_override_applied") and locations:
            eprint(
                f"          WARN: --allow-secret-like override applied; "
                f"{len(locations)} secret-like line(s) masked and written:"
            )
            for loc in locations:
                eprint(f"            - line {loc['line']:>6}: {loc['label']} [{loc['match_preview']}]")
    elif result.get("skipped"):
        eprint(f"[skip:{result.get('reason')}] {label} (status={matched.get('status')}): {result.get('error')}")
        if result.get("reason") == "secret-like-detected" and locations:
            eprint(f"          {len(locations)} secret-like line(s) (rerun with --allow-secret-like to write anyway):")
            for loc in locations:
                eprint(f"            - line {loc['line']:>6}: {loc['label']} [{loc['match_preview']}]")
    else:
        eprint(f"[fail:{result.get('reason')}] {label}: {result.get('error')}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root = project_root()
    config_dir = claude_config_dir()

    candidates = dedupe(load_agents_from_cli(root) + load_agents_from_state_files(config_dir, root))

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

    output_names = assign_output_names(targets)

    results: list[dict[str, Any]] = []
    for c, output_name in zip(targets, output_names):
        result = export_one(
            c,
            root=root,
            config_dir=config_dir,
            output_dir=output_dir,
            output_name=output_name,
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
                "output_dir": str(output_dir.relative_to(root)) if output_dir.is_relative_to(root) else str(output_dir),
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        eprint(f"\nSummary: {exported} exported, {skipped} skipped, {failed} failed (of {len(results)} candidate(s)).")

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
