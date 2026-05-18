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
import sys
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
        (run_dir / "metrics.json").write_text(
            json.dumps(metrics_snapshot or {}, indent=2), encoding="utf-8"
        )
        return None
    except OSError as e:
        return f"cache write failed: {e}"


def cmd_init(args: argparse.Namespace) -> int:
    competition = (args.competition or "").strip()
    if not competition:
        _emit({"ok": False, "error": "competition slug is required"})
        return EXIT_RUNTIME

    external_run_id = args.run_id or datetime.now(timezone.utc).strftime(_TS_FMT)
    run_dir = RUNS_ROOT / competition / external_run_id
    run_dir_str = _rel(run_dir)

    # DB writes: project → competition → experiment → experiment_run. One
    # connection, one transaction context. Fail closed if anything errors.
    try:
        conn = db.get_conn()
    except (db.RemoteOperationBlocked, db.DBNotConfigured) as e:
        return _emit_db_error(e, "DB unavailable")
    except Exception as e:  # psycopg.OperationalError etc.
        return _emit_db_error(e, "DB connection failed")

    try:
        project_id = db.ensure_default_project(conn=conn)
        competition_id = db.ensure_competition(competition, conn=conn)
        experiment_id = db.create_experiment(
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
    except Exception as e:
        conn.close()
        return _emit_db_error(e, "DB write failed")
    finally:
        # _with_conn handled per-call commits; close the explicit conn here.
        try:
            conn.close()
        except Exception:
            pass

    # DB committed — now write cache files.
    meta = {
        "competition": competition,
        "competition_id": competition_id,
        "experiment_id": experiment_id,
        "experiment_run_id": experiment_run_id,
        "run_id": external_run_id,
        "created_at": _now_iso(),
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
    _emit(payload)
    return EXIT_OK


def cmd_record_metric(args: argparse.Namespace) -> int:
    # Resolve the experiment_run via --experiment-run-id or --run-dir.
    if args.experiment_run_id:
        experiment_run_id = args.experiment_run_id
        run_dir = None
    else:
        run_dir = Path(args.run_dir).expanduser() if args.run_dir else None
        if run_dir is None:
            _emit({"ok": False, "error": "either --experiment-run-id or --run-dir is required"})
            return EXIT_RUNTIME

    try:
        conn = db.get_conn()
    except (db.RemoteOperationBlocked, db.DBNotConfigured) as e:
        return _emit_db_error(e, "DB unavailable")
    except Exception as e:
        return _emit_db_error(e, "DB connection failed")

    try:
        if not args.experiment_run_id:
            assert run_dir is not None
            found = db.find_run_by_dir(_rel(run_dir), conn=conn)
            if not found:
                _emit({"ok": False, "error": f"no run found in DB for run_dir={_rel(run_dir)}"})
                return EXIT_RUNTIME
            experiment_run_id = found["experiment_run_id"]
            db_run_dir = found["run_dir"]
        else:
            db_run_dir = None
        event = db.record_metric(experiment_run_id, args.key, args.value, conn=conn)
    except Exception as e:
        return _emit_db_error(e, "DB write failed")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Refresh metrics.json cache from DB state if we have a run_dir.
    cache_warning: str | None = None
    target_dir: Path | None = None
    if db_run_dir:
        target_dir = (REPO_ROOT / db_run_dir).resolve()
    elif run_dir:
        target_dir = run_dir

    if target_dir and target_dir.exists():
        # Refresh metrics.json by re-reading the snapshot from the DB.
        try:
            with db.get_conn() as conn2, conn2.cursor() as cur:
                cur.execute(
                    "select metrics from experiment_runs where id = %s::uuid",
                    (experiment_run_id,),
                )
                row = cur.fetchone()
                snapshot = (row or {}).get("metrics") or {}
            (target_dir / "metrics.json").write_text(
                json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
            )
        except Exception as e:
            cache_warning = f"metrics.json refresh failed: {e}"
            warn(cache_warning)

    payload = {
        "ok": True,
        "experiment_run_id": experiment_run_id,
        "key": args.key,
        "value": args.value,
        "recorded_at": event["recorded_at"].isoformat()
            if hasattr(event["recorded_at"], "isoformat")
            else str(event["recorded_at"]),
    }
    if target_dir:
        payload["run_dir"] = _rel(target_dir)
    if cache_warning:
        payload["cache_warning"] = cache_warning
    _emit(payload)
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    try:
        conn = db.get_conn()
    except (db.RemoteOperationBlocked, db.DBNotConfigured) as e:
        return _emit_db_error(e, "DB unavailable")
    except Exception as e:
        return _emit_db_error(e, "DB connection failed")

    try:
        rows = db.list_runs(competition_slug=args.competition, limit=args.limit, conn=conn)
    except Exception as e:
        return _emit_db_error(e, "DB read failed")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # JSON-safe: convert datetimes to iso strings.
    out_rows = []
    for r in rows:
        rr = dict(r)
        for k, v in list(rr.items()):
            if hasattr(v, "isoformat"):
                rr[k] = v.isoformat()
        out_rows.append(rr)

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
    p_metric.add_argument("--experiment-run-id", dest="experiment_run_id", default=None,
                          help="UUID; alternative to --run-dir")
    p_metric.add_argument("--key", required=True)
    p_metric.add_argument("--value", required=True, type=float)
    p_metric.add_argument("--json", action="store_true")
    p_metric.set_defaults(func=cmd_record_metric)

    p_list = run_sub.add_parser(
        "list", help="List runs from the DB (READ_ONLY)"
    )
    p_list.add_argument("--competition", default=None)
    p_list.add_argument("--limit", type=int, default=100)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
