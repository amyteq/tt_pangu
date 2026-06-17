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


def _missing_kaggle_creds() -> str | None:
    """Return the cmd_submit-style error string for an absent credential, else None.

    Reads ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` for *presence only* — the values
    are never returned, logged, or printed (CLAUDE.md dev-phase secret policy).
    The message text mirrors ``cmd_submit`` verbatim so callers see one
    envelope shape across submit + push.
    """
    if not os.environ.get("KAGGLE_USERNAME"):
        return "KAGGLE_USERNAME not set; cannot submit"
    if not os.environ.get("KAGGLE_KEY"):
        return "KAGGLE_KEY not set; cannot submit"
    return None


def _utc_next_window_open() -> str:
    """ISO-8601 timestamp of the next UTC-midnight roll-over.

    The daily-budget window is the UTC calendar day (ADR-0020 §7); a refused
    push/submit backs off until this instant, when ``count_today_submissions``
    resets to 0.
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    tomorrow = (now + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.isoformat()


def _list_active_pushes(competition_id: str) -> list[dict]:
    """Return the active (non-terminal) latest-per-slug submissions KCA owns.

    Mirrors ``db._count_active_pushes`` (same "latest per file_path / slug
    proxy, status != terminal/stalled" rule, ADR-0020 §7) but returns the rows
    so the refusal envelope can name which runs hold the slots. READ_ONLY.
    """
    terminal = list(db._PUSH_TERMINAL_STATUSES)
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH latest AS (
                  SELECT DISTINCT ON (file_path)
                         file_path, status, created_at
                    FROM submissions
                   WHERE competition_id = %s::uuid
                   ORDER BY file_path, created_at DESC
                )
                SELECT file_path, status
                  FROM latest
                 WHERE status IS NULL
                    OR lower(status) <> ALL (%s)
                 ORDER BY created_at DESC
                """,
                (competition_id, terminal),
            )
            rows = cur.fetchall()
    return [{"file_path": r["file_path"], "status": r["status"]} for r in rows]


def _check_budget_gates(
    command_name: str,
    competition: str | None,
    se: SideEffect,
    *,
    check_concurrency: bool,
) -> int | None:
    """Run the concurrency + daily-budget courtesy gates (ADR-0020 §7).

    Returns an EXIT_* code if a gate refuses (after emitting the JSON
    envelope); ``None`` to proceed. Best-effort: a missing competition slug or
    an unreachable DB is non-fatal — the gate is a courtesy guard, and
    Kaggle's own 429/400 remains the hard authority (the loop HALTS on that,
    it does not retry here). No real Kaggle call happens on any path.
    """
    if not competition:
        return None
    try:
        comp = db.get_competition_by_slug(competition)
    except Exception:
        # Unknown comp / DB unreachable: skip the courtesy gate, let the
        # downstream path (or Kaggle itself) be the authority.
        return None

    competition_id = str(comp["id"])

    # 1. Concurrency gate (cmd_push only).
    if check_concurrency:
        max_concurrent = comp.get("max_concurrent_pushes")
        if max_concurrent is not None:
            try:
                active = db.count_active_pushes(competition_id)
            except Exception:
                active = None
            if active is not None and active >= int(max_concurrent):
                try:
                    active_runs = _list_active_pushes(competition_id)
                except Exception:
                    active_runs = []
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": (f"max_concurrent_pushes reached ({active}/{max_concurrent}); refusing to push"),
                            "competition": competition,
                            "command": f"kaggle {command_name}",
                            "side_effect": se.value,
                            "active_pushes": active,
                            "max_concurrent_pushes": int(max_concurrent),
                            "active_runs": active_runs,
                        },
                        ensure_ascii=False,
                    )
                )
                return EXIT_BLOCKED

    # 2. Daily-budget gate (cmd_push + cmd_submit).
    max_daily = comp.get("max_daily_submissions")
    if max_daily is not None:
        try:
            today = db.count_today_submissions(competition_id)
        except Exception:
            today = None
        if today is not None and today >= int(max_daily):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            f"max_daily_submissions reached "
                            f"({today}/{max_daily}); backing off until the "
                            f"UTC-day window reopens"
                        ),
                        "competition": competition,
                        "command": f"kaggle {command_name}",
                        "side_effect": se.value,
                        "today_submissions": today,
                        "max_daily_submissions": int(max_daily),
                        "next_window_open_utc": _utc_next_window_open(),
                    },
                    ensure_ascii=False,
                )
            )
            return EXIT_BLOCKED

    return None


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

    # Daily-budget gate (ADR-0020 §7) — refuse past max_daily_submissions for
    # the UTC calendar day, BEFORE the approval gate. Courtesy guard only.
    budget_block = _check_budget_gates("submit", competition, se, check_concurrency=False)
    if budget_block is not None:
        return budget_block

    try:
        _check_approval_gate("kaggle_submit", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked(
            "submit",
            se,
            "ApprovalRequired: kaggle_submit",
            options={"competition": competition, "file": file_path, "message": message},
        )

    # Code-competition submission: when --kernel is given, submit the kernel's
    # OUTPUT file straight from Kaggle storage (-k/-v) instead of uploading a
    # local file. --file is then the output filename (e.g. submission.zip), so
    # large adapters never round-trip through the local disk.
    #
    # NOTE on versions: the Kaggle API is latest-run-centric — `kaggle kernels
    # output/status` only expose the LATEST run, so an older version's artifact
    # cannot be downloaded/inspected via API. Submit therefore reliably targets
    # the just-pushed (latest) version; omit --version for that. To keep an
    # earlier candidate retrievable, push it as its own kernel (one kernel per
    # candidate) rather than relying on stale version numbers.
    kernel = getattr(args, "kernel", None)
    version = getattr(args, "version", None)
    cmd = [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        competition,
        "-f",
        file_path,
        "-m",
        message,
    ]
    if kernel:
        cmd += ["-k", kernel]
    if version is not None:
        cmd += ["-v", str(version)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    return _emit_json(
        {
            "ok": proc.returncode == 0,
            "competition": competition,
            "file": file_path,
            "kernel": kernel,
            "version": version,
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
            code = "\n".join("".join(c.get("source", [])) for c in nb.get("cells", []) if c.get("cell_type") == "code")
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
    competition = getattr(args, "competition", None)

    # The pre-flight gates guard a REAL push only. `--dry-run` is a READ_ONLY
    # metadata validation that never reaches Kaggle, so it does not require
    # credentials or consume a concurrency / daily-budget slot.
    if not args.dry_run:
        # 1. Credentials pre-check (issue #62) — mirror cmd_submit's envelope
        #    shape, BEFORE the approval gate fires. Reads env for presence only.
        creds_error = _missing_kaggle_creds()
        if creds_error:
            return _emit_json(
                {
                    "ok": False,
                    "error": creds_error,
                    "competition": competition,
                    "side_effect": se.value,
                }
            )

        # 2. Concurrency + 3. daily-budget courtesy gates (ADR-0020 §7), BEFORE
        #    the approval gate. No real Kaggle call on any refusal path.
        gate_block = _check_budget_gates("push", competition, se, check_concurrency=True)
        if gate_block is not None:
            return gate_block

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
    if not (getattr(args, "skip_lint", False) or os.environ.get("KCA_SKIP_KERNEL_LINT") == "1"):
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
            competition=competition,
            run_id=getattr(args, "run_id", None),
        )
        response["watch"] = watch_result
        response["ok"] = push_ok and watch_result.get("terminal", False)

    return _emit_json(response)


# Watcher states (ADR-0020 §6).
_STATE_QUEUED = "queued"
_STATE_RUNNING = "running"
_STATE_TERMINAL = "terminal"

# Default estimated queue time when this competition/accelerator has no
# history (ADR-0020 §6: default 15 min).
_DEFAULT_EST_QUEUE_SECONDS = 15 * 60

# Stable RUNNING cadence (ADR-0020 §6).
_RUNNING_CADENCE_SECONDS = 300

# Substrings classifying a `kaggle kernels status` 200 body.
_STATUS_QUEUED_TOKENS = ("queued", "not started", "notstarted", "pending")
_STATUS_RUNNING_TOKENS = ("running",)
_STATUS_TERMINAL_TOKENS = ("complete", "error", "cancel", "failed")


def _fibonacci_queued_cadence(cap_seconds: float):
    """Yield the QUEUED Fibonacci backoff `[60, 90, 150, 240, …]`, capped.

    The ramp is `a, b = 60, 90` then `a, b = b, a + b`; every value is clamped
    to ``cap_seconds`` (⅓ × estimated_queue_time) so a short queue never waits
    longer than a third of its own estimate. Once the cap is hit the cadence
    holds there. ``cap_seconds`` is floored at 60 so the ramp always emits a
    sane first wait even for tiny estimates.
    """
    cap = max(60.0, float(cap_seconds))
    a, b = 60, 90
    while True:
        yield min(a, cap)
        a, b = b, a + b


def _estimate_queue_seconds(competition: str | None) -> float:
    """Median of the last 5 same-accelerator queue times for this comp.

    Best-effort DB read of ``analysis_jsonb.queue_time_seconds``; any failure
    (no DB, no history, unknown comp) falls back to the 15-min default. The
    estimator never raises into the poller.
    """
    if not competition:
        return float(_DEFAULT_EST_QUEUE_SECONDS)
    try:
        comp = db.get_competition_by_slug(competition)
        if not comp:
            return float(_DEFAULT_EST_QUEUE_SECONDS)
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT (er.analysis_jsonb ->> 'queue_time_seconds')::float AS q
                      FROM experiment_runs er
                      JOIN experiments e ON e.id = er.experiment_id
                     WHERE e.competition_id = %s::uuid
                       AND er.analysis_jsonb ? 'queue_time_seconds'
                     ORDER BY er.created_at DESC NULLS LAST
                     LIMIT 5
                    """,
                    (str(comp["id"]),),
                )
                samples = [r["q"] for r in cur.fetchall()]
    except Exception:
        samples = None
    if not samples:
        return float(_DEFAULT_EST_QUEUE_SECONDS)
    ordered = sorted(float(s) for s in samples if s is not None)
    if not ordered:
        return float(_DEFAULT_EST_QUEUE_SECONDS)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _classify_status(stdout: str) -> str | None:
    """Map a `kaggle kernels status` 200 body to a watcher state.

    Returns ``_STATE_QUEUED`` / ``_STATE_RUNNING`` / ``_STATE_TERMINAL`` or
    ``None`` when the body is unrecognised (treated as no-change by the caller).
    The authoritative TERMINAL oracle stays the `kernels output` size>100 check;
    this is only the QUEUED-vs-RUNNING cadence classifier (plus an early
    terminal hint when status clearly says complete/error).
    """
    text = (stdout or "").lower()
    if not text:
        return None
    if any(tok in text for tok in _STATUS_TERMINAL_TOKENS):
        return _STATE_TERMINAL
    if any(tok in text for tok in _STATUS_RUNNING_TOKENS):
        return _STATE_RUNNING
    if any(tok in text for tok in _STATUS_QUEUED_TOKENS):
        return _STATE_QUEUED
    return None


def _default_status_fetch(kernel_ref: str) -> tuple[int, str]:
    """Call `kaggle kernels status`; return (http_status_guess, stdout).

    The CLI does not surface the raw HTTP code, so we infer 500/503 from the
    stderr text the M10 runs emitted ("500 - Internal Server Error" /
    "503 ..."). A 500/503 is reported so the poller can treat it as
    non-terminal, no-state-change (ADR-0020 §6). Any other invocation reports
    200 with the stdout body for classification.
    """
    proc = subprocess.run(
        ["kaggle", "kernels", "status", kernel_ref],
        capture_output=True,
        text=True,
    )
    blob = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
    if "500" in blob and "server error" in blob:
        return 500, proc.stdout or ""
    if "503" in blob and ("unavailable" in blob or "service" in blob):
        return 503, proc.stdout or ""
    return 200, proc.stdout or ""


def _default_output_fetch(kernel_ref: str, tmp_dir: str) -> Path:
    """Call `kaggle kernels output`; return the local log path (may not exist).

    `kaggle kernels output` exits 1 + writes nothing while the run is QUEUED or
    RUNNING; exits 0 + writes the log file once the run is terminal. The
    size>100 check on the returned path is the authoritative TERMINAL oracle
    (M10-discovered, preserved per ADR-0020 §6).
    """
    log_path = Path(tmp_dir) / f"{kernel_ref.split('/')[-1]}.log"
    try:
        if log_path.exists():
            log_path.unlink()
    except OSError:
        pass
    subprocess.run(
        ["kaggle", "kernels", "output", kernel_ref, "-p", tmp_dir],
        capture_output=True,
        text=True,
    )
    return log_path


def _watch_kernel_until_terminal(
    kernel_ref: str,
    *,
    poll_seconds: int = 60,
    max_minutes: int = 60,
    competition: str | None = None,
    run_id: str | None = None,
    sleep_fn=None,
    now_fn=None,
    status_fetch=None,
    output_fetch=None,
    est_queue_seconds: float | None = None,
) -> dict:
    """Poll a kernel run with the ADR-0020 §6 three-state cadence machine.

    States:
      QUEUED   → Fibonacci ramp `[60, 90, 150, 240, …]` capped at
                 ⅓ × estimated_queue_time.
      RUNNING  → stable 300 s cadence.
      TERMINAL → exit (authoritative oracle = `kernels output` log size>100).
      STALLED  → still QUEUED past ``max_minutes`` → exit non-terminal, mark
                 the submission ``stalled`` (frees the concurrency slot).

    State is classified from `kaggle kernels status` when it returns 200; a
    500/503 is treated as **non-terminal, no state change** (the M10 fresh-push
    500 bug must not be read as terminal or as an error). The `kernels output`
    size>100 check remains the authoritative TERMINAL detector even when status
    never returns 200.

    All time + I/O seams are injectable so tests drive the machine with a
    mocked clock and mocked CLI responses (no real sleeps, no real Kaggle):
      - ``sleep_fn(seconds)``  — defaults to ``time.sleep``.
      - ``now_fn()``           — monotonic seconds; defaults to ``time.monotonic``.
      - ``status_fetch(ref)``  — returns ``(http_status, stdout)``.
      - ``output_fetch(ref, tmp_dir)`` — returns a ``Path`` (may not exist).

    Returns a dict with: terminal, stalled, polls, state, cadence (the cadence
    sequence actually slept, for assertion), runtime_seconds, queue_time_seconds,
    running_time_seconds, log_path, error_excerpt.

    READ_ONLY against Kaggle.
    """
    import tempfile
    import time as _time

    sleep_fn = sleep_fn or _time.sleep
    now_fn = now_fn or _time.monotonic
    status_fetch = status_fetch or _default_status_fetch
    output_fetch = output_fetch or _default_output_fetch

    if est_queue_seconds is None:
        est_queue_seconds = _estimate_queue_seconds(competition)
    queued_cap = est_queue_seconds / 3.0
    queued_cadence = _fibonacci_queued_cadence(queued_cap)

    tmp_dir = tempfile.mkdtemp(prefix="kca-watch-")
    log_path = Path(tmp_dir) / f"{kernel_ref.split('/')[-1]}.log"

    polls = 0
    cadence: list[float] = []
    started = now_fn()
    deadline = started + max_minutes * 60
    state = _STATE_QUEUED
    # Monotonic timestamp at which the run was first observed RUNNING, so we can
    # split queue time from running time. None until the first RUNNING tick.
    running_since: float | None = None
    queue_time_seconds: float | None = None
    running_time_seconds: float | None = None
    terminal = False
    stalled = False

    while True:
        polls += 1

        # 1. Authoritative TERMINAL oracle: `kernels output` size > 100.
        log_path = output_fetch(kernel_ref, tmp_dir)
        if log_path.exists() and log_path.stat().st_size > 100:
            terminal = True
            if running_since is not None:
                running_time_seconds = now_fn() - running_since
            elif queue_time_seconds is None:
                queue_time_seconds = now_fn() - started
            break

        # 2. Classify cadence state from `kernels status` (200 only). A
        #    500/503 is non-terminal, no state change (ADR-0020 §6).
        http_status, stdout = status_fetch(kernel_ref)
        if http_status == 200:
            classified = _classify_status(stdout)
            if classified == _STATE_RUNNING and state != _STATE_RUNNING:
                state = _STATE_RUNNING
                running_since = now_fn()
                queue_time_seconds = running_since - started
            elif classified == _STATE_QUEUED:
                state = _STATE_QUEUED
            # A status-200 "terminal" hint is advisory only; the size>100 oracle
            # on the next tick is authoritative, so we do not exit here.

        # 3. STALLED: still QUEUED past the cap → exit non-terminal, free slot.
        if now_fn() >= deadline:
            if state == _STATE_QUEUED:
                stalled = True
                if queue_time_seconds is None:
                    queue_time_seconds = now_fn() - started
            break

        # 4. Sleep one cadence step for the current state.
        if state == _STATE_RUNNING:
            wait = float(_RUNNING_CADENCE_SECONDS)
        else:
            wait = next(queued_cadence)
        # Never overshoot the deadline.
        remaining = deadline - now_fn()
        if remaining <= 0:
            if state == _STATE_QUEUED:
                stalled = True
                if queue_time_seconds is None:
                    queue_time_seconds = now_fn() - started
            break
        wait = min(wait, remaining)
        cadence.append(wait)
        sleep_fn(wait)

    runtime = now_fn() - started
    if stalled:
        state = "stalled"
        _mark_submission_stalled(kernel_ref, competition)
    elif terminal:
        state = _STATE_TERMINAL

    result: dict = {
        "terminal": terminal,
        "stalled": stalled,
        "state": state,
        "polls": polls,
        "cadence": cadence,
        "runtime_seconds": round(runtime, 1),
        "queue_time_seconds": (round(queue_time_seconds, 1) if queue_time_seconds is not None else None),
        "running_time_seconds": (round(running_time_seconds, 1) if running_time_seconds is not None else None),
        "log_path": str(log_path) if terminal else None,
    }

    # Telemetry: record queue/running time separately so the estimator has data.
    if run_id and (queue_time_seconds is not None or running_time_seconds is not None):
        try:
            db.set_run_analysis_jsonb(
                run_id,
                queue_time_seconds=(round(queue_time_seconds, 1) if queue_time_seconds is not None else None),
                running_time_seconds=(round(running_time_seconds, 1) if running_time_seconds is not None else None),
            )
        except Exception as exc:  # best-effort; telemetry never blocks the watch
            result["telemetry_warning"] = f"{type(exc).__name__}: {exc}"

    if terminal:
        # Extract any "Exception encountered" / Traceback excerpt so the caller
        # (auto-fix loop or human) can see the failure mode without re-reading
        # the full multi-MB log.
        try:
            entries = json.loads(log_path.read_text())
            stderr_lines = [
                r["data"] for r in entries if r.get("stream_name") == "stderr" and "Traceback" in r.get("data", "")
            ]
            error_window = []
            if stderr_lines:
                # Capture the last ~30 stderr lines starting from the traceback
                tail_start = next(
                    (i for i, r in enumerate(entries) if "Traceback" in r.get("data", "")),
                    -1,
                )
                if tail_start >= 0:
                    error_window = [
                        r["data"].rstrip()
                        for r in entries[tail_start : tail_start + 60]
                        if r.get("stream_name") == "stderr"
                    ]
            result["error_excerpt"] = "\n".join(error_window[-30:]) if error_window else None
        except Exception as exc:
            result["error_excerpt"] = f"<log parse failed: {exc!r}>"

    return result


def _mark_submission_stalled(kernel_ref: str, competition: str | None) -> None:
    """Mark a QUEUED-too-long submission ``stalled`` to release its slot.

    Best-effort: a missing competition / DB-unreachable path is a no-op (the
    watcher already exited non-terminal). ``stalled`` is in
    ``db._PUSH_TERMINAL_STATUSES`` so ``count_active_pushes`` stops counting the
    slug, freeing the concurrency slot the loop was holding (ADR-0020 §6).
    """
    if not competition:
        return
    try:
        comp = db.get_competition_by_slug(competition)
        if not comp:
            return
        slug = kernel_ref.split("/")[-1]
        # Mark the latest submission for this slug stalled; ``stalled`` is in
        # db._PUSH_TERMINAL_STATUSES so count_active_pushes stops counting it.
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE submissions
                       SET status = 'stalled'
                     WHERE id = (
                       SELECT id FROM submissions
                        WHERE competition_id = %s::uuid
                          AND file_path LIKE %s
                        ORDER BY created_at DESC
                        LIMIT 1
                     )
                    """,
                    (str(comp["id"]), f"%{slug}%"),
                )
            conn.commit()
    except Exception:
        # Telemetry / slot release is best-effort; never raise into the watcher.
        return


def _watch_many(
    kernel_refs: list[str],
    *,
    max_minutes: int = 60,
    competition: str | None = None,
    run_ids: dict[str, str] | None = None,
    sleep_fn=None,
    now_fn=None,
    list_fetch=None,
    est_queue_seconds: float | None = None,
) -> dict:
    """Watch ≥ 2 kernel slugs with ONE `kaggle kernels list` read per tick.

    Each tick issues a single ``kaggle kernels list -m --page-size 100`` and
    parses the per-slug status out of that one response, instead of N
    per-slug status calls. Slugs that reach a terminal status drop out; the
    loop ends when every slug is terminal or ``max_minutes`` elapses (remaining
    slugs are marked ``stalled``). The QUEUED Fibonacci cadence governs the
    shared tick interval until any slug is RUNNING, then the 300 s RUNNING
    cadence applies (the slowest-state-wins rule keeps the single shared tick).

    Single-slug watching is **not** routed here — ``cmd_push`` calls
    ``_watch_kernel_until_terminal`` directly for one slug (ADR-0020 §6). This
    function activates only at ≥ 2 tracked slugs and asserts that contract.

    Injectable seams mirror ``_watch_kernel_until_terminal`` so tests drive it
    with a mocked clock and a mocked list response (no real Kaggle, no sleeps):
      - ``list_fetch()`` returns ``{slug: status_text}`` for the one list call.

    Returns ``{"slugs": {slug: {state, terminal, polls}}, "list_calls": int,
    "polls": int}`` — ``list_calls == polls`` proves ONE list per tick.
    """
    import time as _time

    if len(kernel_refs) < 2:
        raise ValueError("_watch_many requires >= 2 slugs; use the 1-slug watcher")

    sleep_fn = sleep_fn or _time.sleep
    now_fn = now_fn or _time.monotonic
    list_fetch = list_fetch or _default_list_fetch

    if est_queue_seconds is None:
        est_queue_seconds = _estimate_queue_seconds(competition)
    queued_cadence = _fibonacci_queued_cadence(est_queue_seconds / 3.0)

    slugs = {ref.split("/")[-1]: ref for ref in kernel_refs}
    per_slug: dict[str, dict] = {s: {"state": _STATE_QUEUED, "terminal": False, "polls": 0} for s in slugs}
    started = now_fn()
    deadline = started + max_minutes * 60
    polls = 0
    list_calls = 0

    while True:
        polls += 1
        # ONE list read per tick, parsed per-slug.
        statuses = list_fetch()
        list_calls += 1
        any_running = False
        for slug, info in per_slug.items():
            if info["terminal"]:
                continue
            info["polls"] += 1
            classified = _classify_status(statuses.get(slug, ""))
            if classified == _STATE_TERMINAL:
                info["state"] = _STATE_TERMINAL
                info["terminal"] = True
            elif classified == _STATE_RUNNING:
                info["state"] = _STATE_RUNNING
                any_running = True
            elif classified == _STATE_QUEUED:
                info["state"] = _STATE_QUEUED

        if all(info["terminal"] for info in per_slug.values()):
            break
        if now_fn() >= deadline:
            for slug, info in per_slug.items():
                if not info["terminal"]:
                    info["state"] = "stalled"
                    _mark_submission_stalled(slugs[slug], competition)
            break

        wait = float(_RUNNING_CADENCE_SECONDS) if any_running else next(queued_cadence)
        remaining = deadline - now_fn()
        if remaining <= 0:
            for slug, info in per_slug.items():
                if not info["terminal"]:
                    info["state"] = "stalled"
                    _mark_submission_stalled(slugs[slug], competition)
            break
        sleep_fn(min(wait, remaining))

    return {"slugs": per_slug, "list_calls": list_calls, "polls": polls}


def _default_list_fetch() -> dict[str, str]:
    """Call `kaggle kernels list -m --page-size 100`; return {slug: status}.

    ONE real Kaggle list read; parses the table/JSON the CLI emits into a
    per-slug status map. Best-effort parsing — an unparsable row is dropped
    (the per-slug classifier then sees an empty status = no state change).
    """
    proc = subprocess.run(
        ["kaggle", "kernels", "list", "-m", "--page-size", "100", "--csv"],
        capture_output=True,
        text=True,
    )
    out: dict[str, str] = {}
    lines = (proc.stdout or "").splitlines()
    for line in lines[1:]:  # skip header
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        ref = parts[0]
        slug = ref.split("/")[-1]
        # The status column position varies by CLI version; join the rest so
        # the substring classifier can still pick up running/complete/error.
        out[slug] = " ".join(parts[1:])
    return out


def cmd_upload(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    options = {"path": args.path}
    try:
        _check_approval_gate("dataset_upload", _policy_from_env())
    except ApprovalRequired:
        return _emit_blocked("upload", se, "ApprovalRequired: dataset_upload", options=options)
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
                "public_score": (float(s.public_score) if getattr(s, "public_score", None) not in (None, "") else None),
                "private_score": (
                    float(s.private_score) if getattr(s, "private_score", None) not in (None, "") else None
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
                f"no Kaggle submissions row matched filters for competition={competition!r}; refusing to update DB"
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
    p_submit.add_argument(
        "--file",
        required=True,
        help="Local file path, OR (with --kernel) the kernel output filename",
    )
    p_submit.add_argument("--message", required=True)
    p_submit.add_argument(
        "--kernel",
        default=None,
        help="Code competition: submit this kernel's output from Kaggle storage "
        "(no local download/upload), e.g. user/kernel-slug",
    )
    p_submit.add_argument(
        "--version",
        default=None,
        help="Kernel version to submit (used with --kernel). Omit to submit the "
        "latest run — recommended, since the API only retrieves the latest run's "
        "output (`kaggle kernels output/status` have no version selector)",
    )
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
        "--competition",
        default=None,
        help="Competition slug — enables the concurrency + daily-budget "
        "courtesy gates (ADR-0020 §7). Omit to skip the DB-backed gates.",
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
    p_push.add_argument(
        "--run-id",
        dest="run_id",
        default=None,
        help="experiment_runs.id to record queue_time_seconds / running_time_seconds on (analysis_jsonb telemetry)",
    )
    p_push.add_argument("--json", action="store_true")
    p_push.set_defaults(func=cmd_push)

    p_upload = kg_sub.add_parser("upload", help="Upload dataset (REMOTE_WRITE)")
    p_upload.add_argument("--path", required=True)
    p_upload.add_argument("--json", action="store_true")
    p_upload.set_defaults(func=cmd_upload)

    p_download = kg_sub.add_parser("download", help="Download competition data (LOCAL_WRITE)")
    p_download.add_argument("--competition", required=True)
    p_download.add_argument("--path", default=None, help="Destination dir (default ./data/<competition>)")
    p_download.add_argument(
        "--resume",
        action="store_true",
        help="Skip files whose sha256 matches manifest entry",
    )
    p_download.add_argument("--json", action="store_true")
    p_download.set_defaults(func=cmd_download)

    p_verify = kg_sub.add_parser("verify", help="Verify a downloaded dataset against manifest.json")
    p_verify.add_argument("--path", required=True, help="Directory holding manifest.json")
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    p_watch = kg_sub.add_parser("watch", help="Watch a kernel run (READ_ONLY)")
    p_watch.add_argument("--run", default=None, help="Legacy alias for --kernel")
    p_watch.add_argument("--kernel", default=None, help="Kernel ref (user/slug) to poll status for")
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
        help="Match the submission row whose description contains this kernel slug (user/slug or just slug)",
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
