#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INPUT = 2
EXIT_DEP = 3

TS_FORMAT = "%Y%m%d_%H%M%S"
DEFAULT_REMOTE_ROOT = ".jrun"
DEFAULT_LOCAL_ROOT = Path(".jrun")
DEFAULT_REGISTRY_ROOT = DEFAULT_LOCAL_ROOT / "registry"
DEFAULT_REMOTE_PYTHON = "python3"
DEFAULT_INTERVAL = 15
DEFAULT_BOOTSTRAP_TIMEOUT = 30
DEFAULT_HEARTBEAT_TIMEOUT = 90

_LOG_QUIET = False
_LOG_VERBOSE = 0

STATE_FIELDS = [
    "run_id",
    "status",
    "host",
    "pid",
    "submitted_at",
    "started_at",
    "updated_at",
    "last_heartbeat_at",
    "heartbeat_interval_sec",
    "finished_at",
    "notebook",
    "input_notebook",
    "output_notebook",
    "stdout_log",
    "stderr_log",
    "returncode",
    "message",
    "phase",
]
SUMMARY_FIELDS = (
    "run_id",
    "status",
    "phase",
    "host",
    "pid",
    "submitted_at",
    "started_at",
    "updated_at",
    "last_heartbeat_at",
    "heartbeat_interval_sec",
    "finished_at",
    "duration_sec",
    "notebook",
    "input_notebook",
    "output_notebook",
    "stdout_log",
    "stderr_log",
    "artifacts",
    "returncode",
    "message",
    "failure_reason",
)
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "timeout", "stalled"}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _set_log_mode(quiet: bool, verbose: int) -> None:
    global _LOG_QUIET, _LOG_VERBOSE
    _LOG_QUIET = quiet
    _LOG_VERBOSE = int(verbose or 0)


def _log(message: str, level: str = "INFO") -> None:
    if _LOG_QUIET and level != "ERROR":
        return
    if level == "DEBUG" and _LOG_VERBOSE <= 0:
        return
    print(f"{level}: {message}", file=sys.stderr)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=False))


def _emit_ok(args: argparse.Namespace, **payload: Any) -> int:
    data = {"ok": True, **payload}
    if getattr(args, "json", False):
        _print_json(data)
    else:
        fields = [
            ("action", data.get("action")),
            ("run_id", data.get("run_id")),
            ("status", data.get("status")),
            ("remote_run_dir", data.get("remote_run_dir")),
            ("fetched_to", data.get("fetched_to")),
        ]
        for key, value in fields:
            if value is not None:
                print(f"{key}: {value}")
    return EXIT_OK


def _emit_fail(
    args: argparse.Namespace,
    message: str,
    *,
    error: str,
    exit_code: int,
    **payload: Any,
) -> int:
    data = {"ok": False, "error": error, "message": message, **payload}
    if getattr(args, "json", False):
        _print_json(data)
    else:
        print(f"ERROR: {message}", file=sys.stderr)
    return exit_code


def _die(message: str, exit_code: int) -> None:
    raise SystemExit(message, exit_code)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_by_fields(
    data: dict[str, Any], fields: list[str], extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    out = {key: data.get(key) for key in fields}
    if extra:
        out.update(extra)
    return out


def _normalize_state(data: dict[str, Any], *, remote_run_dir: str | None = None) -> dict[str, Any]:
    return _normalize_by_fields(data, STATE_FIELDS, {"remote_run_dir": remote_run_dir})


def _normalize_summary(data: dict[str, Any], *, remote_run_dir: str | None = None) -> dict[str, Any]:
    return _normalize_by_fields(data, SUMMARY_FIELDS, {"remote_run_dir": remote_run_dir})


def _ensure_dependency(exe: str) -> None:
    if shutil.which(exe) is None:
        _die(f"missing dependency: {exe}", EXIT_DEP)


def _make_run_id(notebook: Path) -> str:
    return f"{datetime.now().strftime(TS_FORMAT)}_{notebook.stem.replace(' ', '_')}_{uuid.uuid4().hex[:8]}"


def _remote_spec(target: str, user: str | None) -> str:
    return f"{user}@{target}" if user else target


def _remote_python_cmd(remote_python: str | None) -> str:
    value = (remote_python or DEFAULT_REMOTE_PYTHON).strip()
    local_home = str(Path.home())
    if value == local_home:
        return "$HOME"
    if value.startswith(local_home + "/"):
        return "$HOME/" + value[len(local_home) + 1 :]
    if value.startswith("~/"):
        return "$HOME/" + value[2:]
    return value


def _ssh_base_args(args: argparse.Namespace) -> list[str]:
    cmd = ["ssh"]
    if getattr(args, "port", None):
        cmd += ["-p", str(args.port)]
    if getattr(args, "identity", None):
        cmd += ["-i", args.identity]
    return cmd


def _scp_base_args(args: argparse.Namespace) -> list[str]:
    cmd = ["scp"]
    if getattr(args, "port", None):
        cmd += ["-P", str(args.port)]
    if getattr(args, "identity", None):
        cmd += ["-i", args.identity]
    return cmd


def _run_cmd(cmd: list[str], *, capture_output: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    if _LOG_VERBOSE:
        _log(" ".join(shlex.quote(str(part)) for part in cmd), "DEBUG")
    proc = subprocess.run(cmd, text=True, capture_output=capture_output)
    if check and proc.returncode != 0:
        detail = (
            (proc.stderr or "").strip() or (proc.stdout or "").strip() or f"command failed: {' '.join(map(str, cmd))}"
        )
        _die(detail, EXIT_RUNTIME)
    return proc


def _ssh_run(
    args: argparse.Namespace,
    remote_cmd: str,
    *,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if not getattr(args, "target", None):
        _die("--target is required or run_id must exist in local registry", EXIT_INPUT)
    cmd = _ssh_base_args(args) + [
        _remote_spec(args.target, getattr(args, "user", None)),
        remote_cmd,
    ]
    return _run_cmd(cmd, capture_output=capture_output, check=check)


def _ssh_bash(
    args: argparse.Namespace,
    script: str,
    *,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _ssh_run(
        args,
        f"bash -lc {shlex.quote(script)}",
        capture_output=capture_output,
        check=check,
    )


def _scp_to(args: argparse.Namespace, sources: list[Path], remote_dir: str) -> None:
    cmd = (
        _scp_base_args(args)
        + [str(path) for path in sources]
        + [f"{_remote_spec(args.target, getattr(args, 'user', None))}:{remote_dir}"]
    )
    _run_cmd(cmd)


def _scp_from(args: argparse.Namespace, remote_dir: str, local_parent: Path) -> None:
    _ensure_dir(local_parent)
    cmd = _scp_base_args(args) + [
        "-r",
        f"{_remote_spec(args.target, getattr(args, 'user', None))}:{remote_dir}",
        str(local_parent),
    ]
    _run_cmd(cmd)


def _remote_mkdirs(args: argparse.Namespace, *paths: str) -> None:
    wanted = [path for path in paths if path]
    if not wanted:
        _die("no remote paths specified for mkdir", EXIT_INPUT)
    script = "set -e; " + " && ".join(f"mkdir -p -- {shlex.quote(path)}" for path in wanted)
    _ssh_bash(args, script)


def _registry_path(run_id: str) -> Path:
    return DEFAULT_REGISTRY_ROOT / f"{run_id}.json"


def _save_registry(data: dict[str, Any]) -> None:
    _write_json(_registry_path(data["run_id"]), data)


def _load_registry(run_id: str) -> dict[str, Any]:
    path = _registry_path(run_id)
    if not path.exists():
        _die(f"run_id not found in local registry: {run_id}", EXIT_INPUT)
    return _read_json(path)


def _context_from_registry_or_args(args: argparse.Namespace, run_id: str) -> dict[str, Any]:
    if getattr(args, "target", None):
        remote_root = args.remote_root or DEFAULT_REMOTE_ROOT
        return {
            "run_id": run_id,
            "target": args.target,
            "user": args.user,
            "port": args.port,
            "identity": args.identity,
            "remote_root": remote_root,
            "remote_run_dir": f"{remote_root.rstrip('/')}/{run_id}",
            "remote_python": _remote_python_cmd(args.remote_python),
        }
    data = _load_registry(run_id)
    data.setdefault("remote_python", _remote_python_cmd(DEFAULT_REMOTE_PYTHON))
    return data


def _ssh_args_from_ctx(args: argparse.Namespace, ctx: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        target=ctx.get("target"),
        user=ctx.get("user"),
        port=ctx.get("port"),
        identity=ctx.get("identity"),
        remote_root=ctx.get("remote_root"),
        remote_python=ctx.get("remote_python"),
        json=getattr(args, "json", False),
        dry_run=getattr(args, "dry_run", False),
        quiet=getattr(args, "quiet", False),
        verbose=getattr(args, "verbose", 0),
    )


def _read_remote_text(ssh_args: argparse.Namespace, remote_path: str) -> str:
    proc = _ssh_bash(
        ssh_args,
        f"if [ -f {shlex.quote(remote_path)} ]; then cat {shlex.quote(remote_path)}; fi",
        capture_output=True,
        check=True,
    )
    return proc.stdout


def _read_remote_json(ssh_args: argparse.Namespace, remote_path: str) -> dict[str, Any] | None:
    text = _read_remote_text(ssh_args, remote_path).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _die(f"invalid remote json: {remote_path}: {exc}", EXIT_RUNTIME)
        return None


def _tail_text(text: str, lines: int = 20) -> str:
    rows = [line for line in text.splitlines() if line.strip()]
    return "\n".join(rows[-lines:]) if rows else ""


def _read_remote_launch_hint(ssh_args: argparse.Namespace, remote_run_dir: str) -> str:
    return _tail_text(_read_remote_text(ssh_args, f"{remote_run_dir}/launch.log"))


def _remote_pid_alive(ssh_args: argparse.Namespace, pid: int | str | None) -> bool:
    if not pid:
        return False
    proc = _ssh_bash(
        ssh_args,
        f"kill -0 {shlex.quote(str(pid))} >/dev/null 2>&1",
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _build_manifest(args: argparse.Namespace, notebook: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": ctx["run_id"],
        "target": ctx["target"],
        "user": ctx.get("user"),
        "port": ctx.get("port"),
        "identity": ctx.get("identity"),
        "remote_root": ctx["remote_root"],
        "remote_run_dir": ctx["remote_run_dir"],
        "remote_python": ctx["remote_python"],
        "worker_name": "jrun_worker.py",
        "notebook": notebook.name,
        "timeout": args.execute_timeout,
        "submitted_at": _now_iso(),
        "artifact_globs": list(getattr(args, "artifact_glob", None) or []),
    }


def _build_submit_state(notebook: Path, run_id: str, target: str) -> dict[str, Any]:
    return _normalize_state(
        {
            "run_id": run_id,
            "status": "submitted",
            "host": target,
            "pid": None,
            "submitted_at": _now_iso(),
            "started_at": None,
            "updated_at": _now_iso(),
            "last_heartbeat_at": None,
            "heartbeat_interval_sec": None,
            "finished_at": None,
            "notebook": notebook.name,
            "input_notebook": f"input/{notebook.name}",
            "output_notebook": f"work/{notebook.stem}.out.ipynb",
            "stdout_log": "work/stdout.log",
            "stderr_log": "work/stderr.log",
            "returncode": None,
            "message": "submitted",
            "phase": "queued",
        }
    )


def _local_run_dir(run_id: str) -> Path:
    return DEFAULT_LOCAL_ROOT / run_id


def _stage_submit_bundle(notebook: Path, manifest: dict[str, Any], state: dict[str, Any]) -> Path:
    run_root = _local_run_dir(manifest["run_id"])
    input_dir = run_root / "input"
    work_dir = run_root / "work"
    artifacts_dir = run_root / "artifacts"
    _ensure_dir(input_dir)
    _ensure_dir(work_dir)
    _ensure_dir(artifacts_dir)
    worker_src = Path(__file__).resolve().with_name("jrun_worker.py")
    if not worker_src.exists():
        _die(f"worker file not found: {worker_src}", EXIT_DEP)
    shutil.copy2(notebook, input_dir / notebook.name)
    shutil.copy2(worker_src, input_dir / "jrun_worker.py")
    _write_json(input_dir / "manifest.json", manifest)
    _write_json(run_root / "state.json", state)
    return run_root


def _status_payload(ssh_args: argparse.Namespace, ctx: dict[str, Any]) -> dict[str, Any]:
    remote_run_dir = ctx["remote_run_dir"]
    summary = _read_remote_json(ssh_args, f"{remote_run_dir}/summary.json")
    if summary:
        payload = _normalize_summary(summary, remote_run_dir=remote_run_dir)
        payload["status"] = payload.get("status") or "unknown"
        return payload
    state = _read_remote_json(ssh_args, f"{remote_run_dir}/state.json")
    if state:
        return _normalize_state(state, remote_run_dir=remote_run_dir)
    return _normalize_state(
        {
            "run_id": ctx["run_id"],
            "status": "missing",
            "message": "remote state not found",
        },
        remote_run_dir=remote_run_dir,
    )


def _submit(args: argparse.Namespace) -> int:
    notebook = Path(args.notebook).expanduser().resolve()
    if not notebook.exists() or notebook.suffix.lower() != ".ipynb":
        return _emit_fail(
            args,
            "input notebook must exist and end with .ipynb",
            error="invalid_input",
            exit_code=EXIT_INPUT,
        )
    if not args.target:
        return _emit_fail(
            args,
            "--target is required for submit",
            error="invalid_input",
            exit_code=EXIT_INPUT,
        )

    run_id = _make_run_id(notebook)
    ctx = _context_from_registry_or_args(args, run_id)
    ssh_args = _ssh_args_from_ctx(args, ctx)
    manifest = _build_manifest(args, notebook, ctx)
    state = _build_submit_state(notebook, run_id, ctx["target"])

    if args.dry_run:
        return _emit_ok(
            args,
            action="submit",
            run_id=run_id,
            target=ctx["target"],
            remote_run_dir=ctx["remote_run_dir"],
            remote_python=ctx["remote_python"],
            notebook=str(notebook),
            wait=bool(args.wait),
            dry_run=True,
            artifact_globs=manifest["artifact_globs"],
        )

    _ensure_dependency("ssh")
    _ensure_dependency("scp")

    run_root = _stage_submit_bundle(notebook, manifest, state)
    remote_run_dir = ctx["remote_run_dir"]
    remote_input_dir = f"{remote_run_dir}/input"
    _remote_mkdirs(
        ssh_args,
        remote_run_dir,
        remote_input_dir,
        f"{remote_run_dir}/work",
        f"{remote_run_dir}/artifacts",
    )
    _scp_to(ssh_args, [run_root / "state.json"], remote_run_dir)
    _scp_to(
        ssh_args,
        [
            run_root / "input" / notebook.name,
            run_root / "input" / "manifest.json",
            run_root / "input" / "jrun_worker.py",
        ],
        remote_input_dir,
    )

    preflight = _ssh_bash(
        ssh_args,
        f"set -e; cd {shlex.quote(remote_run_dir)}; {ctx['remote_python']} -V >/dev/null 2>&1",
        check=False,
    )
    if preflight.returncode != 0:
        return _emit_fail(
            args,
            f"remote python is not available: {ctx['remote_python']}",
            error="missing_dependency",
            exit_code=EXIT_DEP,
            run_id=run_id,
            target=ctx["target"],
        )

    launch_script = (
        f"set -e; cd {shlex.quote(remote_run_dir)}; "
        "mkdir -p -- work artifacts; "
        ": > launch.log; "
        f"printf '%s\\n' 'launcher_started_at={_now_iso()}' 'remote_python={ctx['remote_python']}' >> launch.log; "
        f"nohup {ctx['remote_python']} input/jrun_worker.py --run-dir . >> launch.log 2>&1 < /dev/null & echo $!"
    )
    launched = _ssh_bash(ssh_args, launch_script, capture_output=True)
    launcher_pid = (launched.stdout or "").strip()
    _save_registry(ctx)
    _log(f"submitted run_id={run_id} target={ctx['target']} launcher_pid={launcher_pid or 'unknown'}")

    if not args.wait:
        return _emit_ok(
            args,
            action="submit",
            run_id=run_id,
            status="submitted",
            target=ctx["target"],
            remote_run_dir=ctx["remote_run_dir"],
        )

    rc = _watch(args, run_id=run_id, from_submit=True)
    if rc != EXIT_OK:
        return rc
    return _fetch(args, run_id=run_id, from_submit=True)


def _status(args: argparse.Namespace) -> int:
    ctx = _context_from_registry_or_args(args, args.run_id)
    ssh_args = _ssh_args_from_ctx(args, ctx)
    payload = _status_payload(ssh_args, ctx)
    launch_hint = (
        _read_remote_launch_hint(ssh_args, ctx["remote_run_dir"]) if payload.get("status") == "submitted" else None
    )
    if args.json:
        return _emit_ok(
            args,
            action="status",
            run_id=ctx["run_id"],
            status=payload.get("status", "unknown"),
            remote_run_dir=ctx["remote_run_dir"],
            summary=payload,
            launch_hint=launch_hint or None,
        )
    return _emit_ok(
        args,
        action="status",
        run_id=ctx["run_id"],
        status=payload.get("status", "unknown"),
        remote_run_dir=ctx["remote_run_dir"],
    )


def _watch(args: argparse.Namespace, *, run_id: str | None = None, from_submit: bool = False) -> int:
    actual_run_id = run_id or args.run_id
    ctx = _context_from_registry_or_args(args, actual_run_id)
    ssh_args = _ssh_args_from_ctx(args, ctx)
    if args.dry_run and not from_submit:
        return _emit_ok(
            args,
            action="watch",
            run_id=ctx["run_id"],
            status="planned",
            remote_run_dir=ctx["remote_run_dir"],
            dry_run=True,
        )

    deadline = None if args.timeout is None or args.timeout <= 0 else time.time() + args.timeout
    submitted_since = None
    running_since = None
    last_status = None
    while True:
        payload = _status_payload(ssh_args, ctx)
        status = str(payload.get("status") or "unknown")
        now = time.time()
        if status != last_status:
            _log(f"run_id={ctx['run_id']} status={status}")
            last_status = status
        else:
            _log(f"run_id={ctx['run_id']} status={status}", "DEBUG")

        if status in TERMINAL_STATUSES:
            if status == "succeeded":
                return _emit_ok(
                    args,
                    action="watch",
                    run_id=ctx["run_id"],
                    status=status,
                    remote_run_dir=ctx["remote_run_dir"],
                )
            return _emit_fail(
                args,
                str(payload.get("message") or f"remote status={status}"),
                error="remote_failed",
                exit_code=EXIT_RUNTIME,
                run_id=ctx["run_id"],
                status=status,
            )

        if status == "submitted":
            submitted_since = submitted_since or now
            if now - submitted_since >= max(1, int(args.bootstrap_timeout)):
                launch_hint = _read_remote_launch_hint(ssh_args, ctx["remote_run_dir"])
                if not launch_hint:
                    return _emit_fail(
                        args,
                        "remote worker did not bootstrap; launch.log is still missing",
                        error="remote_bootstrap_failed",
                        exit_code=EXIT_RUNTIME,
                        run_id=ctx["run_id"],
                        status=status,
                    )
                lower = launch_hint.lower()
                if any(
                    token in lower
                    for token in (
                        "no such file",
                        "not found",
                        "traceback",
                        "permission denied",
                        "command not found",
                    )
                ):
                    return _emit_fail(
                        args,
                        f"remote worker bootstrap failed; launch.log tail:\n{launch_hint}",
                        error="remote_bootstrap_failed",
                        exit_code=EXIT_RUNTIME,
                        run_id=ctx["run_id"],
                        status=status,
                    )
        else:
            submitted_since = None

        if status == "running":
            running_since = running_since or now
            hb = payload.get("last_heartbeat_at") or payload.get("updated_at")
            if hb:
                try:
                    hb_dt = datetime.fromisoformat(str(hb))
                    age = now - hb_dt.timestamp()
                except Exception:
                    age = 0
            else:
                age = now - running_since
            if age >= max(1, int(args.heartbeat_timeout)):
                pid_alive = _remote_pid_alive(ssh_args, payload.get("pid"))
                if not pid_alive:
                    hint = _read_remote_launch_hint(ssh_args, ctx["remote_run_dir"])
                    return _emit_fail(
                        args,
                        f"remote worker stopped sending heartbeats and pid is not alive; launch.log tail:\n{hint}"
                        if hint
                        else "remote worker stopped sending heartbeats and pid is not alive",
                        error="heartbeat_timeout",
                        exit_code=EXIT_RUNTIME,
                        run_id=ctx["run_id"],
                        status=status,
                    )
        else:
            running_since = None

        if deadline is not None and now >= deadline:
            hint = _read_remote_launch_hint(ssh_args, ctx["remote_run_dir"])
            message = f"watch timed out; launch.log tail:\n{hint}" if hint else "watch timed out"
            return _emit_fail(
                args,
                message,
                error="timeout",
                exit_code=EXIT_RUNTIME,
                run_id=ctx["run_id"],
            )
        time.sleep(max(1, int(args.interval)))


def _fetch(args: argparse.Namespace, *, run_id: str | None = None, from_submit: bool = False) -> int:
    actual_run_id = run_id or args.run_id
    ctx = _context_from_registry_or_args(args, actual_run_id)
    ssh_args = _ssh_args_from_ctx(args, ctx)
    base = Path(args.output_dir).expanduser().resolve() if args.output_dir else DEFAULT_LOCAL_ROOT.resolve()
    local_parent = base if base.name != ctx["run_id"] else base.parent
    fetched_to = local_parent / ctx["run_id"]
    if args.dry_run and not from_submit:
        return _emit_ok(
            args,
            action="fetch",
            run_id=ctx["run_id"],
            remote_run_dir=ctx["remote_run_dir"],
            fetched_to=str(fetched_to),
            dry_run=True,
        )
    _ensure_dependency("scp")
    _scp_from(ssh_args, ctx["remote_run_dir"], local_parent)
    return _emit_ok(
        args,
        action="fetch",
        run_id=ctx["run_id"],
        fetched_to=str(fetched_to),
        remote_run_dir=ctx["remote_run_dir"],
    )


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print minimal JSON to stdout")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned side effects without executing them",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quiet", action="store_true", help="Suppress non-error stderr logs")
    group.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Increase stderr log detail; repeat for more detail",
    )


def _add_ssh_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", help="Remote host or SSH alias")
    parser.add_argument("--user", help="Remote SSH user")
    parser.add_argument("--port", type=int, help="Remote SSH port")
    parser.add_argument("--identity", help="SSH private key path")
    parser.add_argument("--remote-root", default=None, help="Remote root directory for run folders")
    parser.add_argument(
        "--remote-python",
        default=None,
        help=f"Remote Python used to launch the worker; default: {DEFAULT_REMOTE_PYTHON}",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jrun.py",
        description="Run notebooks on a remote host via SSH with polling.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit", prog="jrun.py submit", help="Upload a notebook and start a remote run")
    _add_common_args(submit)
    submit.add_argument("notebook", help="Local .ipynb file")
    _add_ssh_args(submit)
    submit.add_argument(
        "--wait",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Wait for completion and fetch artifacts",
    )
    submit.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds when waiting",
    )
    submit.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Overall max seconds for local watch mode when --wait is enabled; 0 disables",
    )
    submit.add_argument(
        "--bootstrap-timeout",
        type=int,
        default=DEFAULT_BOOTSTRAP_TIMEOUT,
        help="Max seconds to wait for worker bootstrap",
    )
    submit.add_argument(
        "--heartbeat-timeout",
        type=int,
        default=DEFAULT_HEARTBEAT_TIMEOUT,
        help="Max seconds without heartbeat while running",
    )
    submit.add_argument(
        "--execute-timeout",
        type=int,
        default=-1,
        help="Remote ExecutePreprocessor timeout; -1 disables per-cell timeout",
    )
    submit.add_argument("--output-dir", help="Local destination root used when --wait fetches artifacts")
    submit.add_argument(
        "--artifact-glob",
        action="append",
        default=[],
        help="Extra remote glob to copy into artifacts/ after execution; repeatable",
    )

    status = sub.add_parser(
        "status",
        prog="jrun.py status",
        help="Read state.json or summary.json for a run",
    )
    _add_common_args(status)
    status.add_argument("run_id", help="Run id returned by submit")
    _add_ssh_args(status)

    watch = sub.add_parser(
        "watch",
        prog="jrun.py watch",
        help="Poll a run until it reaches a terminal state",
    )
    _add_common_args(watch)
    watch.add_argument("run_id", help="Run id returned by submit")
    _add_ssh_args(watch)
    watch.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds",
    )
    watch.add_argument(
        "--bootstrap-timeout",
        type=int,
        default=DEFAULT_BOOTSTRAP_TIMEOUT,
        help="Max seconds to wait for worker bootstrap",
    )
    watch.add_argument(
        "--heartbeat-timeout",
        type=int,
        default=DEFAULT_HEARTBEAT_TIMEOUT,
        help="Max seconds without heartbeat while running",
    )
    watch.add_argument("--timeout", type=int, default=0, help="Overall max seconds to wait; 0 disables")

    fetch = sub.add_parser(
        "fetch",
        prog="jrun.py fetch",
        help="Copy a remote run directory to local output",
    )
    _add_common_args(fetch)
    fetch.add_argument("run_id", help="Run id returned by submit")
    _add_ssh_args(fetch)
    fetch.add_argument("--output-dir", help="Local destination root; default is .jrun")
    return parser


def _error_name(exit_code: int) -> str:
    if exit_code == EXIT_INPUT:
        return "invalid_input"
    if exit_code == EXIT_DEP:
        return "missing_dependency"
    return "runtime_error"


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:])
    if not getattr(args, "remote_root", None):
        args.remote_root = DEFAULT_REMOTE_ROOT
    if not getattr(args, "remote_python", None):
        args.remote_python = DEFAULT_REMOTE_PYTHON
    _set_log_mode(getattr(args, "quiet", False), getattr(args, "verbose", 0))
    try:
        if args.command == "submit":
            return _submit(args)
        if args.command == "status":
            return _status(args)
        if args.command == "watch":
            return _watch(args)
        if args.command == "fetch":
            return _fetch(args)
        return _emit_fail(
            args,
            f"unsupported command: {args.command}",
            error="invalid_input",
            exit_code=EXIT_INPUT,
        )
    except SystemExit as exc:
        if len(exc.args) == 2 and isinstance(exc.args[0], str) and isinstance(exc.args[1], int):
            message, exit_code = exc.args
            return _emit_fail(args, message, error=_error_name(exit_code), exit_code=exit_code)
        raise
    except KeyboardInterrupt:
        return _emit_fail(args, "interrupted", error="interrupted", exit_code=EXIT_RUNTIME)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
