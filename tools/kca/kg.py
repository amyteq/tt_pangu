from __future__ import annotations

import argparse
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
    "kaggle_submit":    False,
    "kernel_push":      False,
    "dataset_upload":   True,
    "git_push":         False,
    "git_force_push":   True,
    "supabase_migrate": True,
    "delete_artifact":  True,
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


def _emit_stub(command_name: str, side_effect: SideEffect, extra: dict | None = None) -> int:
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
        return _emit_json({
            "ok": False,
            "error": "KAGGLE_USERNAME not set; cannot submit",
            "competition": competition,
            "side_effect": se.value,
        })
    if not os.environ.get("KAGGLE_KEY"):
        return _emit_json({
            "ok": False,
            "error": "KAGGLE_KEY not set; cannot submit",
            "competition": competition,
            "side_effect": se.value,
        })

    try:
        _check_approval_gate("kaggle_submit", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked("submit", se, f"ApprovalRequired: kaggle_submit",
                             options={"competition": competition, "file": file_path,
                                      "message": message})

    proc = subprocess.run(
        ["kaggle", "competitions", "submit", "-c", competition,
         "-f", file_path, "-m", message],
        capture_output=True, text=True,
    )
    return _emit_json({
        "ok": proc.returncode == 0,
        "competition": competition,
        "file": file_path,
        "side_effect": se.value,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    })


def cmd_push(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    kernel_dir = args.kernel_dir

    try:
        _check_approval_gate("kernel_push", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked("push", se, "ApprovalRequired: kernel_push",
                             options={"kernel_dir": kernel_dir})

    if args.dry_run:
        meta = Path(kernel_dir) / "kernel-metadata.json"
        if not meta.exists():
            return _emit_json({
                "ok": False,
                "error": f"kernel-metadata.json not found in {kernel_dir}",
                "kernel_dir": kernel_dir,
                "side_effect": SideEffect.READ_ONLY.value,
                "dry_run": True,
            })
        return _emit_json({
            "ok": True,
            "dry_run": True,
            "kernel_dir": kernel_dir,
            "side_effect": SideEffect.READ_ONLY.value,
        })

    proc = subprocess.run(
        ["kaggle", "kernels", "push", "-p", kernel_dir],
        capture_output=True, text=True,
    )
    return _emit_json({
        "ok": proc.returncode == 0,
        "kernel_dir": kernel_dir,
        "side_effect": se.value,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    })


def cmd_upload(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    options = {"path": args.path}
    try:
        _check_approval_gate("dataset_upload", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked("upload", se, "ApprovalRequired: dataset_upload",
                             options=options)
    proc = subprocess.run(
        ["kaggle", "datasets", "version", "-p", args.path, "-m", "kca upload"],
        capture_output=True, text=True,
    )
    return _emit_json({
        "ok": proc.returncode == 0,
        "path": args.path,
        "side_effect": se.value,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    })


def cmd_download(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    competition = args.competition
    path = args.path or str(Path.cwd() / "data" / competition)
    Path(path).mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["kaggle", "competitions", "download", "-c", competition, "-p", path],
        capture_output=True, text=True,
    )
    return _emit_json({
        "ok": proc.returncode == 0,
        "competition": competition,
        "path": path,
        "side_effect": se.value,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    })


def cmd_watch(args: argparse.Namespace) -> int:
    kernel_ref = getattr(args, "kernel", None) or args.run
    poll_seconds = getattr(args, "poll_seconds", 30)
    max_iterations = getattr(args, "max_iterations", 1)
    final_status = "unknown"
    last_stdout = ""
    for _ in range(max_iterations):
        proc = subprocess.run(
            ["kaggle", "kernels", "status", kernel_ref],
            capture_output=True, text=True,
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
    return _emit_json({
        "ok": final_status == "complete",
        "kernel": kernel_ref,
        "status": final_status,
        "side_effect": SideEffect.READ_ONLY.value,
        "stdout": last_stdout,
    })


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
    p_push.add_argument("--kernel-dir", dest="kernel_dir", required=True,
                        help="Directory containing kernel-metadata.json")
    p_push.add_argument("--dry-run", action="store_true",
                        help="Validate kernel-metadata.json without uploading")
    p_push.add_argument("--json", action="store_true")
    p_push.set_defaults(func=cmd_push)

    p_upload = kg_sub.add_parser("upload", help="Upload dataset (REMOTE_WRITE)")
    p_upload.add_argument("--path", required=True)
    p_upload.add_argument("--json", action="store_true")
    p_upload.set_defaults(func=cmd_upload)

    p_download = kg_sub.add_parser("download",
                                   help="Download competition data (LOCAL_WRITE)")
    p_download.add_argument("--competition", required=True)
    p_download.add_argument("--path", default=None,
                            help="Destination dir (default ./data/<competition>)")
    p_download.add_argument("--json", action="store_true")
    p_download.set_defaults(func=cmd_download)

    p_watch = kg_sub.add_parser("watch", help="Watch a kernel run (READ_ONLY)")
    p_watch.add_argument("--run", default=None, help="Legacy alias for --kernel")
    p_watch.add_argument("--kernel", default=None,
                        help="Kernel ref (user/slug) to poll status for")
    p_watch.add_argument("--poll-seconds", dest="poll_seconds", type=int, default=30)
    p_watch.add_argument("--max-iterations", dest="max_iterations", type=int,
                         default=1)
    p_watch.add_argument("--json", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    p_fetch = kg_sub.add_parser("fetch", help="Fetch run artifacts (READ_ONLY)")
    p_fetch.add_argument("--run", required=True)
    p_fetch.add_argument("--json", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_list = kg_sub.add_parser("list", help="List Kaggle runs (READ_ONLY)")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
