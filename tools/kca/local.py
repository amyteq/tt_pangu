"""kca local: inspect, probe, and pick from KCA_LOCAL_ENDPOINT_* slots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _types import EXIT_OK, SideEffect

# Ensure repo root is on sys.path so we can import src.worker.local_model.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _emit_json(payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return exit_code


def _emit_text(lines: list[str]) -> int:
    for line in lines:
        print(line)
    return EXIT_OK


def _load_module():
    from src.worker import local_model as lm

    return lm


def cmd_list(args: argparse.Namespace) -> int:
    lm = _load_module()
    endpoints = lm.load_endpoints()
    rows = [
        {
            "name": ep.name,
            "url": ep.url,
            "model": ep.model,
            "backend": ep.backend,
        }
        for ep in endpoints
    ]
    if args.json:
        return _emit_json(
            {
                "ok": True,
                "endpoints": rows,
                "side_effect": SideEffect.READ_ONLY.value,
            }
        )
    if not rows:
        return _emit_text(["(no local endpoints configured)"])
    lines = [f"{r['name']:24s} {r['backend']:7s} {r['model']:40s} {r['url']}" for r in rows]
    return _emit_text(lines)


def cmd_probe(args: argparse.Namespace) -> int:
    lm = _load_module()
    endpoints = lm.load_endpoints()
    if args.name:
        endpoints = [ep for ep in endpoints if ep.name == args.name]
    results = []
    ok_count = 0
    for ep in endpoints:
        r = lm.probe(ep)
        results.append(
            {
                "name": ep.name,
                "url": ep.url,
                "backend": ep.backend,
                "ok": r["ok"],
                "models": r["models"],
                "latency_ms": r["latency_ms"],
                "error": r["error"],
            }
        )
        if r["ok"]:
            ok_count += 1
    if args.json:
        return _emit_json(
            {
                "ok": True,
                "ok_count": ok_count,
                "endpoints": results,
                "side_effect": SideEffect.READ_ONLY.value,
            }
        )
    lines = [f"{r['name']:24s} ok={r['ok']} latency_ms={r['latency_ms']} error={r['error']}" for r in results]
    if not lines:
        lines = ["(no local endpoints configured)"]
    return _emit_text(lines)


def cmd_triage(args: argparse.Namespace) -> int:
    from src.worker import triage, local_model as lm

    endpoint = None
    if args.endpoint:
        for ep in lm.load_endpoints():
            if ep.name == args.endpoint:
                endpoint = ep
                break
        if endpoint is None:
            payload = {"ok": False, "error": f"endpoint not found: {args.endpoint}"}
            if args.json:
                return _emit_json(payload, exit_code=1)
            print(payload)
            return 1
    result = triage.triage_job_events(args.job_id, endpoint=endpoint)
    exit_code = 0 if result.get("ok") else 1
    if args.json:
        return _emit_json(result, exit_code=exit_code)
    if result.get("ok"):
        print(f"endpoint={result.get('endpoint')} model={result.get('model')}")
        print(result.get("summary", ""))
    else:
        print(f"FAIL: {result.get('error')}")
    return exit_code


def cmd_summarise(args: argparse.Namespace) -> int:
    from src.worker import triage, local_model as lm

    p = Path(args.file)
    if not p.exists():
        payload = {"ok": False, "error": f"file not found: {args.file}"}
        if args.json:
            return _emit_json(payload, exit_code=1)
        print(payload)
        return 1
    text = p.read_text(errors="replace")
    endpoint = None
    if args.endpoint:
        for ep in lm.load_endpoints():
            if ep.name == args.endpoint:
                endpoint = ep
                break
    result = triage.summarise_text(text, endpoint=endpoint)
    exit_code = 0 if result.get("ok") else 1
    if args.json:
        return _emit_json(result, exit_code=exit_code)
    if result.get("ok"):
        print(f"endpoint={result.get('endpoint')} model={result.get('model')}")
        print(result.get("summary", ""))
    else:
        print(f"FAIL: {result.get('error')}")
    return exit_code


def cmd_pick(args: argparse.Namespace) -> int:
    lm = _load_module()
    ep = lm.pick_endpoint()
    if ep is None:
        payload = {
            "ok": False,
            "reason": "no endpoint available",
            "fallback": lm.fallback_model(),
            "side_effect": SideEffect.READ_ONLY.value,
        }
        if args.json:
            return _emit_json(payload)
        return _emit_text([f"(no endpoint) fallback={payload['fallback']}"])
    payload = {
        "ok": True,
        "name": ep.name,
        "url": ep.url,
        "model": ep.model,
        "backend": ep.backend,
        "side_effect": SideEffect.READ_ONLY.value,
    }
    if args.json:
        return _emit_json(payload)
    return _emit_text([f"{ep.name} {ep.backend} {ep.model} {ep.url}"])


def add_parsers(subparsers) -> None:
    p = subparsers.add_parser(
        "local",
        help="Inspect KCA_LOCAL_ENDPOINT_* configuration and probe availability.",
    )
    inner = p.add_subparsers(dest="local_cmd", required=True)

    p_list = inner.add_parser("list", help="List configured local endpoints.")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_probe = inner.add_parser("probe", help="Probe configured endpoints.")
    p_probe.add_argument("--name", default=None)
    p_probe.add_argument("--json", action="store_true")
    p_probe.set_defaults(func=cmd_probe)

    p_pick = inner.add_parser("pick", help="Pick the highest-priority reachable endpoint.")
    p_pick.add_argument("--json", action="store_true")
    p_pick.set_defaults(func=cmd_pick)

    p_triage = inner.add_parser("triage", help="Summarise a job's event trail with a local model.")
    p_triage.add_argument("--job-id", dest="job_id", required=True)
    p_triage.add_argument("--endpoint", default=None)
    p_triage.add_argument("--json", action="store_true")
    p_triage.set_defaults(func=cmd_triage)

    p_sum = inner.add_parser("summarise", help="Summarise a text file with a local model.")
    p_sum.add_argument("--file", required=True)
    p_sum.add_argument("--endpoint", default=None)
    p_sum.add_argument("--json", action="store_true")
    p_sum.set_defaults(func=cmd_summarise)
