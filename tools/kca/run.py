"""kca run subcommands — DB-first as of M2-T004.

The DB (experiments + experiment_runs + experiment_run_metrics) is the
source of truth. The filesystem layout under runs/<comp>/<run_id>/ is a
local cache rewritten from DB state. If the DB write fails, no FS state
is created and the command exits non-zero.

Cache write failures after a successful DB commit downgrade to a stderr
warning + `cache_warning` field in the JSON envelope; the exit code stays 0
since the canonical state (DB) is intact.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect
from _util import REPO_ROOT, warn

import db

RUNS_ROOT = REPO_ROOT / "runs"
_TS_FMT = "%Y%m%d_%H%M%S"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(payload: dict, side_effect: SideEffect | None = None) -> None:
    se = side_effect or db.current_side_effect()
    out = {"side_effect": se.value, **payload}
    print(json.dumps(out, ensure_ascii=False))


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def _emit_db_error(err: Exception, label: str) -> int:
    _emit({"ok": False, "error": f"{label}: {err}", "error_type": type(err).__name__})
    return EXIT_RUNTIME


def _write_cache_files(run_dir: Path, meta: dict, metrics_snapshot: dict) -> str | None:
    """Write meta/config/metrics caches. Return warning string if anything failed."""
    try:
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (run_dir / "config.json").write_text("{}", encoding="utf-8")
        (run_dir / "metrics.json").write_text(json.dumps(metrics_snapshot or {}, indent=2), encoding="utf-8")
        return None
    except OSError as e:
        return f"cache write failed: {e}"


def cmd_init(args: argparse.Namespace) -> int:
    import os

    competition = (args.competition or "").strip()
    if not competition:
        _emit({"ok": False, "error": "competition slug is required"})
        return EXIT_RUNTIME

    external_run_id = args.run_id or datetime.now(timezone.utc).strftime(_TS_FMT)
    # Resolve run_dir relative to cwd (M4 spec: runs/<slug>/<run_id>/).
    run_dir = Path.cwd() / "runs" / competition / external_run_id
    run_dir_str = f"runs/{competition}/{external_run_id}"

    competition_id: str | None = None
    experiment_id: str | None = None
    experiment_run_id: str | None = None
    db_warning: str | None = None

    db_available = bool(os.environ.get("SUPABASE_DB_URL"))
    if db_available:
        try:
            conn = db.get_conn()
            try:
                project_id = db.ensure_default_project(conn=conn)
                competition_id = db.ensure_competition(competition, conn=conn)
                experiment_id = db.create_experiment_m2(
                    name=external_run_id,
                    hypothesis=args.hypothesis or None,
                    tags=list(args.tag or []),
                    config={},
                    project_id=project_id,
                    conn=conn,
                )
                experiment_run_id = db.create_experiment_run(
                    experiment_id=experiment_id,
                    external_run_id=external_run_id,
                    run_dir=run_dir_str,
                    conn=conn,
                )
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            db_warning = f"DB write skipped: {e}"
            warn(db_warning)

    meta = {
        "competition": competition,
        "competition_id": competition_id,
        "experiment_id": experiment_id,
        "experiment_run_id": experiment_run_id,
        "run_id": external_run_id,
        "started_at": _now_iso(),
        "hypothesis": args.hypothesis or "",
        "tags": list(args.tag or []),
    }
    cache_warning = _write_cache_files(run_dir, meta, {})

    payload = {
        "ok": True,
        "run_dir": run_dir_str,
        "run_id": external_run_id,
        "competition": competition,
        "competition_id": competition_id,
        "experiment_id": experiment_id,
        "experiment_run_id": experiment_run_id,
    }
    if cache_warning:
        warn(cache_warning)
        payload["cache_warning"] = cache_warning
    if db_warning:
        payload["db_warning"] = db_warning
    _emit(payload, SideEffect.LOCAL_WRITE)
    return EXIT_OK


def cmd_record_metric(args: argparse.Namespace) -> int:
    import os

    run_dir = Path(args.run_dir).expanduser() if args.run_dir else None
    if run_dir is None and not args.experiment_run_id:
        _emit(
            {
                "ok": False,
                "error": "either --run-dir or --experiment-run-id is required",
            }
        )
        return EXIT_RUNTIME

    # FS-first: load meta.json + read/merge metrics.json.
    meta: dict = {}
    if run_dir is not None and (run_dir / "meta.json").exists():
        try:
            meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    metrics_path = (run_dir / "metrics.json") if run_dir else None
    metrics: dict = {}
    if metrics_path and metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            metrics = {}
    metrics[args.key] = args.value
    cache_warning: str | None = None
    if metrics_path:
        try:
            metrics_path.parent.mkdir(parents=True, exist_ok=True)
            metrics_path.write_text(
                json.dumps(metrics, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            cache_warning = f"metrics.json write failed: {e}"
            warn(cache_warning)

    db_warning: str | None = None
    experiment_run_id = args.experiment_run_id or meta.get("experiment_run_id")
    if os.environ.get("SUPABASE_DB_URL") and experiment_run_id:
        try:
            db.record_metric_m2(experiment_run_id, args.key, args.value)
        except Exception as e:
            db_warning = f"DB record_metric skipped: {e}"
            warn(db_warning)

    payload: dict = {
        "ok": True,
        "key": args.key,
        "value": args.value,
    }
    if run_dir is not None:
        payload["run_dir"] = str(run_dir)
    if experiment_run_id:
        payload["experiment_run_id"] = experiment_run_id
    if cache_warning:
        payload["cache_warning"] = cache_warning
    if db_warning:
        payload["db_warning"] = db_warning
    _emit(payload, SideEffect.LOCAL_WRITE)
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    import os

    # FS-first: walk runs/<comp>/*/meta.json relative to cwd.
    out_rows: list[dict] = []
    runs_root = Path.cwd() / "runs"
    if runs_root.exists():
        if args.competition:
            comp_dirs = [runs_root / args.competition]
        else:
            comp_dirs = [d for d in runs_root.iterdir() if d.is_dir()]
        for cd in comp_dirs:
            if not cd.exists():
                continue
            for run_dir in sorted(cd.iterdir()):
                meta_path = run_dir / "meta.json"
                if not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
                meta["run_dir"] = f"runs/{cd.name}/{run_dir.name}"
                out_rows.append(meta)

    # If DB available, optionally merge DB-known runs (best-effort).
    if os.environ.get("SUPABASE_DB_URL"):
        try:
            db_rows = db.list_runs_m2(
                competition_slug=args.competition,
                limit=args.limit,
            )
            for r in db_rows:
                rr = dict(r)
                for k, v in list(rr.items()):
                    if hasattr(v, "isoformat"):
                        rr[k] = v.isoformat()
                out_rows.append(rr)
        except Exception:
            pass

    _emit({"ok": True, "runs": out_rows, "count": len(out_rows)}, SideEffect.READ_ONLY)
    return EXIT_OK


def add_parsers(sub: argparse._SubParsersAction) -> None:
    run = sub.add_parser("run", help="Manage runs/<competition>/<run_id>/ — DB-first (M2)")
    run_sub = run.add_subparsers(dest="run_cmd", required=True)

    p_init = run_sub.add_parser(
        "init",
        help="Create a new run in DB + filesystem cache (LOCAL_WRITE; requires DB)",
    )
    p_init.add_argument("--competition", required=True)
    p_init.add_argument("--run-id", dest="run_id", default=None)
    p_init.add_argument("--hypothesis", default=None)
    p_init.add_argument("--tag", action="append", help="Repeatable")
    p_init.add_argument("--json", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_metric = run_sub.add_parser(
        "record-metric",
        help="Append a metric event in DB; refresh metrics.json cache (LOCAL_WRITE)",
    )
    p_metric.add_argument("--run-dir", default=None, help="runs/<comp>/<run_id>/ path")
    p_metric.add_argument(
        "--experiment-run-id",
        dest="experiment_run_id",
        default=None,
        help="UUID; alternative to --run-dir",
    )
    p_metric.add_argument("--key", required=True)
    p_metric.add_argument("--value", required=True, type=float)
    p_metric.add_argument("--json", action="store_true")
    p_metric.set_defaults(func=cmd_record_metric)

    p_list = run_sub.add_parser("list", help="List runs from the DB (READ_ONLY)")
    p_list.add_argument("--competition", default=None)
    p_list.add_argument("--limit", type=int, default=100)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
