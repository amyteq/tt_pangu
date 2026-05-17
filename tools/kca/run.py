from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect
from _util import REPO_ROOT

RUNS_ROOT = REPO_ROOT / "runs"
_TS_FMT = "%Y%m%d_%H%M%S"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(payload: dict, side_effect: SideEffect) -> None:
    out = {"side_effect": side_effect.value, **payload}
    print(json.dumps(out, ensure_ascii=False))


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def cmd_init(args: argparse.Namespace) -> int:
    competition = (args.competition or "").strip()
    if not competition:
        _emit({"ok": False, "error": "competition slug is required"}, SideEffect.LOCAL_WRITE)
        return EXIT_RUNTIME

    run_id = args.run_id or datetime.now(timezone.utc).strftime(_TS_FMT)
    run_dir = RUNS_ROOT / competition / run_id
    if run_dir.exists():
        _emit({"ok": False, "error": f"run_dir already exists: {_rel(run_dir)}"}, SideEffect.LOCAL_WRITE)
        return EXIT_RUNTIME

    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    meta = {
        "competition": competition,
        "run_id": run_id,
        "created_at": _now_iso(),
        "hypothesis": args.hypothesis or "",
        "tags": list(args.tag or []),
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (run_dir / "config.json").write_text("{}", encoding="utf-8")
    (run_dir / "metrics.json").write_text("{}", encoding="utf-8")

    _emit({
        "ok": True,
        "run_dir": _rel(run_dir),
        "run_id": run_id,
        "competition": competition,
    }, SideEffect.LOCAL_WRITE)
    return EXIT_OK


def cmd_record_metric(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_absolute():
        run_dir = (REPO_ROOT / run_dir).resolve()
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        _emit({"ok": False, "error": f"metrics.json not found in {_rel(run_dir)}"}, SideEffect.LOCAL_WRITE)
        return EXIT_RUNTIME

    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        metrics = {}

    metrics[args.key] = {
        "value": args.value,
        "recorded_at": _now_iso(),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _emit({
        "ok": True,
        "run_dir": _rel(run_dir),
        "key": args.key,
        "value": args.value,
    }, SideEffect.LOCAL_WRITE)
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    root = RUNS_ROOT
    if args.competition:
        competitions = [args.competition]
    else:
        competitions = sorted([p.name for p in root.glob("*") if p.is_dir()]) if root.exists() else []

    runs: list[dict] = []
    for comp in competitions:
        comp_dir = root / comp
        if not comp_dir.is_dir():
            continue
        for rd in sorted(comp_dir.iterdir()):
            if not rd.is_dir():
                continue
            meta: dict = {}
            mp = rd / "meta.json"
            if mp.exists():
                try:
                    meta = json.loads(mp.read_text(encoding="utf-8") or "{}")
                except json.JSONDecodeError:
                    meta = {"error": "invalid meta.json"}
            runs.append({
                "competition": comp,
                "run_id": rd.name,
                "run_dir": _rel(rd),
                "meta": meta,
            })

    _emit({"ok": True, "runs": runs, "count": len(runs)}, SideEffect.READ_ONLY)
    return EXIT_OK


def add_parsers(sub: argparse._SubParsersAction) -> None:
    run = sub.add_parser("run", help="Manage runs/<competition>/<run_id>/ artifact directories")
    run_sub = run.add_subparsers(dest="run_cmd", required=True)

    p_init = run_sub.add_parser("init", help="Create a new run artifact directory (LOCAL_WRITE)")
    p_init.add_argument("--competition", required=True)
    p_init.add_argument("--run-id", dest="run_id", default=None)
    p_init.add_argument("--hypothesis", default=None)
    p_init.add_argument("--tag", action="append", help="Repeatable")
    p_init.add_argument("--json", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_metric = run_sub.add_parser("record-metric", help="Append a metric to metrics.json (LOCAL_WRITE)")
    p_metric.add_argument("--run-dir", required=True)
    p_metric.add_argument("--key", required=True)
    p_metric.add_argument("--value", required=True, type=float)
    p_metric.add_argument("--json", action="store_true")
    p_metric.set_defaults(func=cmd_record_metric)

    p_list = run_sub.add_parser("list", help="List runs (READ_ONLY)")
    p_list.add_argument("--competition", default=None)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
