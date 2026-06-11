from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from _types import EXIT_OK, EXIT_BLOCKED, EXIT_RUNTIME, SideEffect
from _util import warn

import db

_GATE_ENV = "KCA_ALLOW_REMOTE"


# ADR-0006 default policy: True = require approval, False = allow.
OPERATION_DEFAULTS = {
    "kaggle_submit": False,
    "kernel_push": False,
    "dataset_upload": True,
    "git_push": False,
    "git_force_push": True,
    "supabase_migrate": True,
    "delete_artifact": True,
    "external_fetch": False,
}


class ApprovalRequired(Exception):
    """Raised when a gated operation lacks approval under the active policy."""

    def __init__(self, operation: str, policy: dict):
        self.operation = operation
        self.policy = policy
        super().__init__(f"ApprovalRequired: {operation}")


def _check_approval_gate(operation: str, policy: dict) -> None:
    """Raise ApprovalRequired if `policy` (or defaults) gates `operation`.

    KCA_ALLOW_REMOTE=1 remains an emergency CI override.
    """
    gates = (policy or {}).get("approval_gates", {})
    requires = gates.get(operation, OPERATION_DEFAULTS.get(operation, True))
    if requires and not os.environ.get(_GATE_ENV):
        raise ApprovalRequired(operation, policy or {})


def _gate(side_effect: SideEffect, command_name: str) -> tuple[bool, str | None]:
    if side_effect in (SideEffect.READ_ONLY, SideEffect.LOCAL_WRITE):
        return True, None
    if os.environ.get(_GATE_ENV) == "1":
        warn(f"REMOTE OPERATION: kaggle {command_name} — {_GATE_ENV} is set")
        return True, None
    return False, f"remote operation requires {_GATE_ENV}=1 and human approval"


def _record_approval(command_name: str, options: dict) -> tuple[str | None, str | None]:
    """Insert a pending human_decisions row. Returns (approval_id, warning).

    Best-effort: DB failures never block the refusal path. Caller emits the
    blocked envelope regardless.
    """
    args_summary = ", ".join(f"{k}={v}" for k, v in options.items() if v is not None)
    prompt = f"Approve Kaggle {command_name} ({args_summary or 'no args'})"
    try:
        approval_id = db.insert_approval_request(
            decision_type=f"kaggle.{command_name}",
            prompt=prompt,
            options=options,
        )
        return approval_id, None
    except Exception as e:
        return None, f"approval recording failed: {type(e).__name__}: {e}"


def _emit_blocked(
    command_name: str,
    side_effect: SideEffect,
    reason: str,
    options: dict | None = None,
) -> int:
    payload = {
        "ok": False,
        "error": reason,
        "command": f"kaggle {command_name}",
        "side_effect": side_effect.value,
    }
    # Best-effort: record the attempt in human_decisions.
    if options is not None:
        approval_id, warning = _record_approval(command_name, options)
        if approval_id:
            payload["approval_request_id"] = approval_id
            payload["approval_recorded"] = True
        else:
            payload["approval_recorded"] = False
            if warning:
                payload["approval_warning"] = warning
                warn(warning)
    print(json.dumps(payload, ensure_ascii=False))
    return EXIT_BLOCKED


def _emit_stub(
    command_name: str, side_effect: SideEffect, extra: dict | None = None
) -> int:
    out = {
        "ok": True,
        "stub": True,
        "command": f"kaggle {command_name}",
        "side_effect": side_effect.value,
    }
    if extra:
        out.update(extra)
    print(json.dumps(out, ensure_ascii=False))
    return EXIT_OK


def _emit_json(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return EXIT_OK if payload.get("ok") else EXIT_RUNTIME


def _policy_from_env() -> dict:
    """Load a JSON policy blob from KCA_POLICY env if present; else empty."""
    raw = os.environ.get("KCA_POLICY")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def cmd_submit(args: argparse.Namespace) -> int:
    se = SideEffect.SUBMISSION
    competition = args.competition
    file_path = args.file
    message = args.message or "kca agent submission"

    if not os.environ.get("KAGGLE_USERNAME"):
        return _emit_json(
            {
                "ok": False,
                "error": "KAGGLE_USERNAME not set; cannot submit",
                "competition": competition,
                "side_effect": se.value,
            }
        )
    if not os.environ.get("KAGGLE_KEY"):
        return _emit_json(
            {
                "ok": False,
                "error": "KAGGLE_KEY not set; cannot submit",
                "competition": competition,
                "side_effect": se.value,
            }
        )

    try:
        _check_approval_gate("kaggle_submit", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked(
            "submit",
            se,
            "ApprovalRequired: kaggle_submit",
            options={"competition": competition, "file": file_path, "message": message},
        )

    proc = subprocess.run(
        [
            "kaggle",
            "competitions",
            "submit",
            "-c",
            competition,
            "-f",
            file_path,
            "-m",
            message,
        ],
        capture_output=True,
        text=True,
    )
    return _emit_json(
        {
            "ok": proc.returncode == 0,
            "competition": competition,
            "file": file_path,
            "side_effect": se.value,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    )


def _lint_kernel(kernel_dir: str) -> tuple[bool, str | None]:
    """Static pre-push lint of a kernel's code: catch undefined-name / pyflakes
    errors in seconds, before a multi-hour GPU run wastes them.

    Assembles a notebook's code cells (or reads a .py code_file) and runs
    `ruff check --select E9,F821,F811,F841` (syntax + undefined/redef/unused).
    Graceful-degrade: returns (True, None)
    if ruff is missing, metadata/code is absent, or anything errors — the gate
    must never block a push for infrastructure reasons (mirrors format_gate).
    Returns (ok, ruff_output_on_failure).
    """
    import shutil
    import sys
    import tempfile

    try:
        meta_path = Path(kernel_dir) / "kernel-metadata.json"
        if not meta_path.exists():
            return True, None
        code_file = json.loads(meta_path.read_text()).get("code_file")
        if not code_file:
            return True, None
        src_path = Path(kernel_dir) / code_file
        if not src_path.exists():
            return True, None

        if src_path.suffix == ".ipynb":
            nb = json.loads(src_path.read_text())
            code = "\n".join(
                "".join(c.get("source", []))
                for c in nb.get("cells", [])
                if c.get("cell_type") == "code"
            )
        elif src_path.suffix == ".py":
            code = src_path.read_text()
        else:
            return True, None

        # Find ruff on PATH, or next to the running interpreter (the env bin,
        # where `kca`'s python lives even when PATH doesn't include it).
        ruff = shutil.which("ruff")
        if not ruff:
            cand = Path(sys.executable).with_name("ruff")
            ruff = str(cand) if cand.exists() else None
        if not ruff:
            return True, None

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "_kernel_assembled.py"
            tmp.write_text(code)
            proc = subprocess.run(
                [
                    ruff,
                    "check",
                    "--select",
                    "E9,F821,F811,F841",
                    "--no-cache",
                    str(tmp),
                ],
                capture_output=True,
                text=True,
            )
        if proc.returncode == 0:
            return True, None
        return False, (proc.stdout or proc.stderr or "ruff reported errors")
    except Exception:
        return True, None


def cmd_push(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    kernel_dir = args.kernel_dir

    try:
        _check_approval_gate("kernel_push", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked(
            "push",
            se,
            "ApprovalRequired: kernel_push",
            options={"kernel_dir": kernel_dir},
        )

    # Static lint gate: refuse to push a kernel whose code has undefined-name /
    # pyflakes errors (caught in seconds, before any GPU time). Runs for both
    # --dry-run and real push. Override: --skip-lint or KCA_SKIP_KERNEL_LINT=1.
    if not (
        getattr(args, "skip_lint", False)
        or os.environ.get("KCA_SKIP_KERNEL_LINT") == "1"
    ):
        lint_ok, lint_out = _lint_kernel(kernel_dir)
        if not lint_ok:
            return _emit_json(
                {
                    "ok": False,
                    "error": (
                        "kernel lint failed (undefined names / pyflakes) — fix "
                        "before pushing, or pass --skip-lint / KCA_SKIP_KERNEL_LINT=1"
                    ),
                    "kernel_dir": kernel_dir,
                    "lint": lint_out,
                    "side_effect": SideEffect.READ_ONLY.value,
                }
            )

    if args.dry_run:
        meta = Path(kernel_dir) / "kernel-metadata.json"
        if not meta.exists():
            return _emit_json(
                {
                    "ok": False,
                    "error": f"kernel-metadata.json not found in {kernel_dir}",
                    "kernel_dir": kernel_dir,
                    "side_effect": SideEffect.READ_ONLY.value,
                    "dry_run": True,
                }
            )
        return _emit_json(
            {
                "ok": True,
                "dry_run": True,
                "kernel_dir": kernel_dir,
                "side_effect": SideEffect.READ_ONLY.value,
            }
        )

    proc = subprocess.run(
        ["kaggle", "kernels", "push", "-p", kernel_dir],
        capture_output=True,
        text=True,
    )
    push_ok = proc.returncode == 0
    response: dict = {
        "ok": push_ok,
        "kernel_dir": kernel_dir,
        "side_effect": se.value,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

    # Extract kernel ref + version from the push response and metadata, so we
    # can auto-watch the resulting run.
    kernel_ref = None
    pushed_version = None
    try:
        meta = json.loads((Path(kernel_dir) / "kernel-metadata.json").read_text())
        kernel_ref = meta.get("id")
    except Exception:
        pass
    import re as _re

    m = _re.search(r"[Kk]ernel version (\d+) successfully pushed", proc.stdout or "")
    if m:
        pushed_version = int(m.group(1))
    response["kernel_ref"] = kernel_ref
    response["pushed_version"] = pushed_version

    # Auto-watch the kernel run until terminal (default). --no-watch opts out.
    if push_ok and getattr(args, "watch", True) and kernel_ref:
        watch_result = _watch_kernel_until_terminal(
            kernel_ref,
            poll_seconds=getattr(args, "poll_seconds", 60),
            max_minutes=getattr(args, "max_poll_minutes", 60),
        )
        response["watch"] = watch_result
        response["ok"] = push_ok and watch_result.get("terminal", False)

    return _emit_json(response)


def _watch_kernel_until_terminal(
    kernel_ref: str, *, poll_seconds: int = 60, max_minutes: int = 60
) -> dict:
    """Poll a kernel run until it produces a downloadable output log.

    Returns a dict with: terminal (bool), polls, runtime_seconds, log_path,
    error_excerpt (if a Python traceback is detected in stderr). The Kaggle
    `kernels status` API has been observed to 500 for newly-pushed kernels;
    this watcher uses `kernels output` instead, which only succeeds once the
    run is terminal.

    READ_ONLY against Kaggle.
    """
    import tempfile
    import time as _time

    tmp_dir = tempfile.mkdtemp(prefix="kca-watch-")
    log_path = Path(tmp_dir) / f"{kernel_ref.split('/')[-1]}.log"
    polls = 0
    started = _time.monotonic()
    max_polls = max(1, (max_minutes * 60) // poll_seconds)
    while polls < max_polls:
        polls += 1
        try:
            if log_path.exists():
                log_path.unlink()
        except OSError:
            pass
        # `kaggle kernels output` exits 1 + writes nothing while running;
        # exits 0 + writes log file once terminal.
        subprocess.run(
            ["kaggle", "kernels", "output", kernel_ref, "-p", tmp_dir],
            capture_output=True,
            text=True,
        )
        if log_path.exists() and log_path.stat().st_size > 100:
            break
        if polls < max_polls:
            _time.sleep(poll_seconds)

    runtime = _time.monotonic() - started
    terminal = log_path.exists() and log_path.stat().st_size > 100
    result: dict = {
        "terminal": terminal,
        "polls": polls,
        "runtime_seconds": round(runtime, 1),
        "log_path": str(log_path) if terminal else None,
    }

    if terminal:
        # Extract any "Exception encountered" / Traceback excerpt so the caller
        # (auto-fix loop or human) can see the failure mode without re-reading
        # the full multi-MB log.
        try:
            entries = json.loads(log_path.read_text())
            stderr_lines = [
                r["data"]
                for r in entries
                if r.get("stream_name") == "stderr" and "Traceback" in r.get("data", "")
            ]
            error_window = []
            if stderr_lines:
                # Capture the last ~30 stderr lines starting from the traceback
                tail_start = next(
                    (
                        i
                        for i, r in enumerate(entries)
                        if "Traceback" in r.get("data", "")
                    ),
                    -1,
                )
                if tail_start >= 0:
                    error_window = [
                        r["data"].rstrip()
                        for r in entries[tail_start : tail_start + 60]
                        if r.get("stream_name") == "stderr"
                    ]
            result["error_excerpt"] = (
                "\n".join(error_window[-30:]) if error_window else None
            )
        except Exception as exc:
            result["error_excerpt"] = f"<log parse failed: {exc!r}>"

    return result


def cmd_upload(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    options = {"path": args.path}
    try:
        _check_approval_gate("dataset_upload", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked(
            "upload", se, "ApprovalRequired: dataset_upload", options=options
        )
    proc = subprocess.run(
        ["kaggle", "datasets", "version", "-p", args.path, "-m", "kca upload"],
        capture_output=True,
        text=True,
    )
    return _emit_json(
        {
            "ok": proc.returncode == 0,
            "path": args.path,
            "side_effect": se.value,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    )


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for child in sorted(root.rglob("*")):
        if child.is_file() and child.name != "manifest.json":
            out.append(child)
    return out


def cmd_download(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    competition = args.competition
    path_str = args.path or str(Path.cwd() / "data" / competition)
    path = Path(path_str)
    path.mkdir(parents=True, exist_ok=True)
    manifest_path = path / "manifest.json"

    existing: dict = {"files": []}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            existing = {"files": []}

    skipped = 0
    if args.resume and existing.get("files"):
        # Walk existing manifest; if file on disk matches sha256, skip its
        # re-download by removing it from a "to download" list. Since the
        # kaggle CLI fetches the whole bundle, we cannot truly skip per-file
        # — but we record how many files matched so the caller knows the
        # resume comparison ran. The actual download is still invoked unless
        # every file matched.
        all_matched = True
        for entry in existing.get("files", []):
            target = path / entry["name"]
            if target.exists() and _sha256_file(target) == entry.get("sha256"):
                skipped += 1
            else:
                all_matched = False
        if all_matched and skipped > 0:
            # Nothing left to fetch; just refresh manifest and return.
            return _refresh_manifest_and_emit(
                competition=competition,
                path=path,
                manifest_path=manifest_path,
                skipped=skipped,
                rc=0,
                stdout="",
                stderr="",
                ran_kaggle=False,
                side_effect=se,
            )

    # Run kaggle CLI; if it isn't installed or creds missing, surface a
    # graceful error and still build/refresh the manifest from whatever is
    # already on disk (useful for tests and --resume scenarios).
    rc = 0
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            ["kaggle", "competitions", "download", "-c", competition, "-p", str(path)],
            capture_output=True,
            text=True,
        )
        rc = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except FileNotFoundError as e:
        rc = 127
        stderr = f"kaggle CLI not found: {e}"

    return _refresh_manifest_and_emit(
        competition=competition,
        path=path,
        manifest_path=manifest_path,
        skipped=skipped,
        rc=rc,
        stdout=stdout,
        stderr=stderr,
        ran_kaggle=True,
        side_effect=se,
    )


def _refresh_manifest_and_emit(
    *,
    competition: str,
    path: Path,
    manifest_path: Path,
    skipped: int,
    rc: int,
    stdout: str,
    stderr: str,
    ran_kaggle: bool,
    side_effect: SideEffect,
) -> int:
    files = _walk_files(path)
    entries = []
    for f in files:
        rel = f.relative_to(path).as_posix()
        entries.append(
            {
                "name": rel,
                "sha256": _sha256_file(f),
                "bytes": f.stat().st_size,
            }
        )
    manifest = {
        "competition": competition,
        "fetched_at": _dt.datetime.utcnow().isoformat() + "Z",
        "files": entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    payload = {
        "ok": rc == 0,
        "competition": competition,
        "path": str(path),
        "files": len(entries),
        "skipped": skipped,
        "manifest": str(manifest_path),
        "side_effect": side_effect.value,
    }
    if not ran_kaggle:
        payload["all_matched"] = True
    if stdout:
        payload["stdout"] = stdout
    if stderr:
        payload["stderr"] = stderr
    return _emit_json(payload)


def cmd_verify(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    path = Path(args.path)
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return _emit_json(
            {
                "ok": False,
                "error": f"manifest not found: {manifest_path}",
                "path": str(path),
                "side_effect": se.value,
            }
        )
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        return _emit_json(
            {
                "ok": False,
                "error": f"manifest parse error: {e}",
                "path": str(path),
                "side_effect": se.value,
            }
        )
    ok_count = 0
    missing: list[str] = []
    mismatched: list[str] = []
    for entry in manifest.get("files", []):
        name = entry["name"]
        target = path / name
        if not target.exists():
            missing.append(name)
            continue
        if _sha256_file(target) != entry.get("sha256"):
            mismatched.append(name)
            continue
        ok_count += 1
    return _emit_json(
        {
            "ok": (not missing) and (not mismatched),
            "ok_count": ok_count,
            "missing": missing,
            "mismatched": mismatched,
            "path": str(path),
            "side_effect": se.value,
        }
    )


def cmd_watch(args: argparse.Namespace) -> int:
    kernel_ref = getattr(args, "kernel", None) or args.run
    poll_seconds = getattr(args, "poll_seconds", 30)
    max_iterations = getattr(args, "max_iterations", 1)
    final_status = "unknown"
    last_stdout = ""
    for _ in range(max_iterations):
        proc = subprocess.run(
            ["kaggle", "kernels", "status", kernel_ref],
            capture_output=True,
            text=True,
        )
        last_stdout = proc.stdout
        text = (proc.stdout or "").lower()
        if "complete" in text:
            final_status = "complete"
            break
        if "error" in text:
            final_status = "error"
            break
        if max_iterations > 1:
            time.sleep(poll_seconds)
    return _emit_json(
        {
            "ok": final_status == "complete",
            "kernel": kernel_ref,
            "status": final_status,
            "side_effect": SideEffect.READ_ONLY.value,
            "stdout": last_stdout,
        }
    )


def _fetch_kaggle_submissions(competition: str) -> list[dict]:
    """Call the Kaggle Python API and return submissions as plain dicts.

    Each dict has: file_name, date, description, status, public_score (float|None),
    private_score (float|None), ref.

    Kaggle's library prints version warnings to stdout, which corrupts our JSON
    envelope — capture and discard that chatter.
    """
    import contextlib
    import io as _io

    from kaggle import api

    with contextlib.redirect_stdout(_io.StringIO()):
        api.authenticate()
        raw = list(api.competition_submissions(competition))
    rows = []
    for s in raw:
        rows.append(
            {
                "file_name": getattr(s, "file_name", None),
                "date": str(getattr(s, "date", "") or ""),
                "description": getattr(s, "description", "") or "",
                "status": str(getattr(s, "status", "") or ""),
                "public_score": (
                    float(s.public_score)
                    if getattr(s, "public_score", None) not in (None, "")
                    else None
                ),
                "private_score": (
                    float(s.private_score)
                    if getattr(s, "private_score", None) not in (None, "")
                    else None
                ),
                "ref": getattr(s, "ref", None),
            }
        )
    return rows


def cmd_score(args: argparse.Namespace) -> int:
    """Read public LB scores for a competition and optionally write the matched
    row's public_score back to a `submissions` row.

    READ_ONLY against Kaggle (Python API call to `competition_submissions`).
    LOCAL_WRITE against the DB when --update-db is given.
    """
    competition = args.competition
    se = SideEffect.READ_ONLY

    try:
        submissions = _fetch_kaggle_submissions(competition)
    except Exception as exc:
        return _emit_json(
            {
                "ok": False,
                "side_effect": se.value,
                "competition": competition,
                "error": f"kaggle competition_submissions failed: {exc!s}",
            }
        )

    matched = submissions
    if args.kernel_ref:
        slug_part = args.kernel_ref.split("/")[-1].lower()
        matched = [r for r in matched if slug_part in r["description"].lower()]
    if args.message_filter:
        needle = args.message_filter.lower()
        matched = [r for r in matched if needle in r["description"].lower()]

    payload = {
        "ok": True,
        "side_effect": se.value,
        "competition": competition,
        "match_count": len(matched),
        "submissions": matched[: args.limit] if args.limit else matched,
    }

    if args.update_db and args.submission_id:
        if not matched:
            payload["ok"] = False
            payload["error"] = (
                f"no Kaggle submissions row matched filters for "
                f"competition={competition!r}; refusing to update DB"
            )
            return _emit_json(payload)
        top = matched[0]
        public_score = top["public_score"]
        status = top["status"] or None
        try:
            db.update_submission(
                args.submission_id,
                public_lb_score=public_score,
                status=status,
            )
            # M10 schema accumulated both columns; the test fixture reads
            # `public_score` (migration 0004) so mirror the value there too.
            with db.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE submissions SET public_score = %s WHERE id = %s::uuid",
                        (public_score, args.submission_id),
                    )
                conn.commit()
        except Exception as exc:
            payload["ok"] = False
            payload["error"] = f"DB update failed: {exc!s}"
            return _emit_json(payload)
        payload["updated_submission_id"] = args.submission_id
        payload["public_score"] = public_score
        payload["matched_description"] = top["description"]
        payload["side_effect"] = SideEffect.LOCAL_WRITE.value

    return _emit_json(payload)


def cmd_fetch(args: argparse.Namespace) -> int:
    return _emit_stub("fetch", SideEffect.READ_ONLY, {"run": args.run})


def cmd_list(args: argparse.Namespace) -> int:
    return _emit_stub("list", SideEffect.READ_ONLY)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    kg = sub.add_parser("kaggle", help="Kaggle remote operations (gated)")
    kg_sub = kg.add_subparsers(dest="kaggle_cmd", required=True)

    p_submit = kg_sub.add_parser("submit", help="Submit to a competition (SUBMISSION)")
    p_submit.add_argument("--competition", required=True)
    p_submit.add_argument("--file", required=True)
    p_submit.add_argument("--message", required=True)
    p_submit.add_argument("--json", action="store_true")
    p_submit.set_defaults(func=cmd_submit)

    p_push = kg_sub.add_parser("push", help="Push a kernel (REMOTE_WRITE)")
    p_push.add_argument(
        "--kernel-dir",
        dest="kernel_dir",
        required=True,
        help="Directory containing kernel-metadata.json",
    )
    p_push.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate kernel-metadata.json without uploading",
    )
    p_push.add_argument(
        "--skip-lint",
        dest="skip_lint",
        action="store_true",
        help="Skip the pre-push static lint (undefined-name / pyflakes) check",
    )
    p_push.add_argument(
        "--no-watch",
        dest="watch",
        action="store_false",
        default=True,
        help="Skip auto-watching the kernel run after a successful push",
    )
    p_push.add_argument(
        "--poll-seconds",
        dest="poll_seconds",
        type=int,
        default=60,
        help="Seconds between watcher polls (default 60)",
    )
    p_push.add_argument(
        "--max-poll-minutes",
        dest="max_poll_minutes",
        type=int,
        default=60,
        help="Watcher cap in minutes (default 60)",
    )
    p_push.add_argument("--json", action="store_true")
    p_push.set_defaults(func=cmd_push)

    p_upload = kg_sub.add_parser("upload", help="Upload dataset (REMOTE_WRITE)")
    p_upload.add_argument("--path", required=True)
    p_upload.add_argument("--json", action="store_true")
    p_upload.set_defaults(func=cmd_upload)

    p_download = kg_sub.add_parser(
        "download", help="Download competition data (LOCAL_WRITE)"
    )
    p_download.add_argument("--competition", required=True)
    p_download.add_argument(
        "--path", default=None, help="Destination dir (default ./data/<competition>)"
    )
    p_download.add_argument(
        "--resume",
        action="store_true",
        help="Skip files whose sha256 matches manifest entry",
    )
    p_download.add_argument("--json", action="store_true")
    p_download.set_defaults(func=cmd_download)

    p_verify = kg_sub.add_parser(
        "verify", help="Verify a downloaded dataset against manifest.json"
    )
    p_verify.add_argument(
        "--path", required=True, help="Directory holding manifest.json"
    )
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    p_watch = kg_sub.add_parser("watch", help="Watch a kernel run (READ_ONLY)")
    p_watch.add_argument("--run", default=None, help="Legacy alias for --kernel")
    p_watch.add_argument(
        "--kernel", default=None, help="Kernel ref (user/slug) to poll status for"
    )
    p_watch.add_argument("--poll-seconds", dest="poll_seconds", type=int, default=30)
    p_watch.add_argument("--max-iterations", dest="max_iterations", type=int, default=1)
    p_watch.add_argument("--json", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    p_score = kg_sub.add_parser(
        "score",
        help="Read public LB score from `kaggle competitions submissions` and "
        "optionally write it to a submissions row (READ_ONLY / LOCAL_WRITE)",
    )
    p_score.add_argument("--competition", required=True)
    p_score.add_argument(
        "--kernel-ref",
        dest="kernel_ref",
        default=None,
        help="Match the submission row whose description contains this kernel "
        "slug (user/slug or just slug)",
    )
    p_score.add_argument(
        "--message-filter",
        dest="message_filter",
        default=None,
        help="Substring match against the submission description",
    )
    p_score.add_argument(
        "--submission-id",
        dest="submission_id",
        default=None,
        help="`submissions.id` to update (with --update-db)",
    )
    p_score.add_argument(
        "--update-db",
        dest="update_db",
        action="store_true",
        help="Write the matched row's publicScore + status to submissions",
    )
    p_score.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max rows to return (default 10; 0 disables the cap)",
    )
    p_score.add_argument("--json", action="store_true")
    p_score.set_defaults(func=cmd_score)

    p_fetch = kg_sub.add_parser("fetch", help="Fetch run artifacts (READ_ONLY)")
    p_fetch.add_argument("--run", required=True)
    p_fetch.add_argument("--json", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_list = kg_sub.add_parser("list", help="List Kaggle runs (READ_ONLY)")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
