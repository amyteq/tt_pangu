"""kca research: record cited, trust-labeled web research items.

Subcommands:
  fetch  — pull a URL via http or playwright, store artifacts, insert row.
  add    — register a research_items row by URL (no fetch).
  list   — list research items, optionally by competition.
  show   — show one research item by id.
  cite   — link a research_item to a run/experiment/job with optional quote.

Untrusted-data principle: fetched bytes are saved verbatim and never
executed; we extract structural text only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from _types import EXIT_OK, EXIT_BLOCKED, EXIT_RUNTIME, SideEffect
from _util import REPO_ROOT


VALID_TRUSTS = {"official", "trusted_public", "community", "untrusted", "unknown"}


def _emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return EXIT_OK if payload.get("ok") else EXIT_RUNTIME


def _db_or_warn():
    """Return (db_module, warning_or_none). warning_or_none is set when DB
    connection info / driver isn't available; callers may still degrade."""
    try:
        import db as _db
        _db.get_conn().close()
        return _db, None
    except Exception as e:
        try:
            import db as _db
            return _db, f"db_unavailable: {type(e).__name__}: {e}"
        except Exception as e2:
            return None, f"db_import_failed: {e2}"


def _allowed_domains() -> list[str] | None:
    raw = os.environ.get("KCA_RESEARCH_ALLOW_DOMAINS")
    if not raw:
        return None
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _domain_allowed(url: str) -> bool:
    allow = _allowed_domains()
    if allow is None:
        return False  # gate required by default
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allow)


def _resolve_competition_id(slug: str | None):
    """Look up competition id by slug. Returns (id_or_none, warning_or_none)."""
    if not slug:
        return None, None
    try:
        import db as _db
        row = _db.get_competition_by_slug(slug)
        return row.get("id"), None
    except Exception as e:
        return None, f"competition_lookup_failed: {type(e).__name__}: {e}"


def cmd_fetch(args: argparse.Namespace) -> int:
    from research_fetch import fetch_page
    from kg import _check_approval_gate, ApprovalRequired

    se = SideEffect.LOCAL_WRITE
    url = args.url
    trust = args.trust or "untrusted"
    if trust not in VALID_TRUSTS:
        return _emit({"ok": False, "error": f"invalid trust: {trust}",
                      "side_effect": se.value})

    # SSRF / scheme check first (independent of approval gate).
    from research_fetch import _check_policy
    policy_err = _check_policy(url)
    if policy_err is not None:
        payload = dict(policy_err)
        warnings = payload.get("policy_warnings", [])
        payload["error"] = ", ".join(warnings) if warnings else "policy_blocked"
        payload.setdefault("side_effect", se.value)
        return _emit(payload)

    # Approval gate when domain isn't in allow-list.
    policy_gates = {"external_fetch": True} if not _domain_allowed(url) else {}
    try:
        _check_approval_gate("external_fetch",
                             {"approval_gates": policy_gates})
    except ApprovalRequired:
        return _emit({
            "ok": False,
            "error": "ApprovalRequired: external_fetch",
            "operation": "external_fetch",
            "url": url,
            "side_effect": se.value,
        })

    # Stage artifact dir under repo: artifacts/research/<hash[:12]>/ -- but
    # we don't know the hash yet, so use a tmp staging dir and move.
    staging = REPO_ROOT / "artifacts" / "research" / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    result = fetch_page(url, out_dir=staging,
                        fetcher=args.fetcher or "http",
                        timeout_s=args.timeout or 20)
    if not result.get("ok"):
        # Surface policy_warnings as part of the response.
        payload = dict(result)
        payload.setdefault("side_effect", se.value)
        return _emit(payload)

    content_hash = result["content_hash"]
    short = content_hash.split(":", 1)[-1][:12]
    final_dir = REPO_ROOT / "artifacts" / "research" / short
    final_dir.mkdir(parents=True, exist_ok=True)
    raw_final = final_dir / "raw.html"
    text_final = final_dir / "main.txt"
    Path(result["raw_path"]).replace(raw_final)
    Path(result["text_path"]).replace(text_final)
    shot_path = result.get("screenshot_path")
    shot_final = None
    if shot_path:
        shot_final = final_dir / "screenshot.png"
        Path(shot_path).replace(shot_final)

    payload: dict[str, Any] = {
        "ok": True,
        "url": url,
        "fetcher": result.get("fetcher"),
        "http_status": result.get("http_status"),
        "content_hash": content_hash,
        "raw_path": str(raw_final),
        "text_path": str(text_final),
        "screenshot_path": str(shot_final) if shot_final else None,
        "bytes": result.get("bytes"),
        "trust": trust,
        "side_effect": se.value,
    }

    # Insert DB rows if available.
    _db, warn_msg = _db_or_warn()
    if _db is None or warn_msg:
        payload["db_warning"] = warn_msg or "no db module"
        return _emit(payload)

    try:
        comp_id, comp_warn = _resolve_competition_id(args.competition)
        html_art = _db.attach_artifact(
            "research_html", str(raw_final),
            content_hash=content_hash,
            byte_size=result.get("bytes"),
        )
        text_art = _db.attach_artifact(
            "research_text", str(text_final),
            content_hash=content_hash,
        )
        item_id = _db.create_research_item(
            url=url,
            title=args.title,
            source_kind=args.source_kind,
            trust=trust,
            summary=args.summary,
            competition_id=comp_id,
            fetcher=result.get("fetcher"),
            http_status=result.get("http_status"),
            content_hash=content_hash,
            html_artifact_id=html_art,
            text_artifact_id=text_art,
            source_policy={"fetcher": result.get("fetcher")},
        )
        payload["research_item_id"] = item_id
        payload["html_artifact_id"] = html_art
        payload["text_artifact_id"] = text_art
        if comp_warn:
            payload["competition_warning"] = comp_warn
    except Exception as e:
        payload["db_warning"] = f"{type(e).__name__}: {e}"

    return _emit(payload)


def cmd_add(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    trust = args.trust or "unknown"
    if trust not in VALID_TRUSTS:
        return _emit({"ok": False, "error": f"invalid trust: {trust}",
                      "side_effect": se.value})

    _db, warn_msg = _db_or_warn()
    payload: dict[str, Any] = {
        "ok": True,
        "url": args.url,
        "title": args.title,
        "trust": trust,
        "side_effect": se.value,
    }
    if _db is None or warn_msg:
        payload["db_warning"] = warn_msg or "no db module"
        return _emit(payload)

    try:
        comp_id, comp_warn = _resolve_competition_id(args.competition)
        item_id = _db.create_research_item(
            url=args.url,
            title=args.title,
            trust=trust,
            summary=args.summary,
            competition_id=comp_id,
        )
        payload["research_item_id"] = item_id
        if comp_warn:
            payload["competition_warning"] = comp_warn
    except Exception as e:
        payload["ok"] = False
        payload["error"] = f"{type(e).__name__}: {e}"
        return _emit(payload)

    return _emit(payload)


def cmd_list(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    _db, warn_msg = _db_or_warn()
    if _db is None or warn_msg:
        return _emit({
            "ok": True,
            "items": [],
            "db_warning": warn_msg or "no db module",
            "side_effect": se.value,
        })
    try:
        comp_id, _ = _resolve_competition_id(args.competition)
        items = _db.list_research_items(competition_id=comp_id, limit=args.limit)
        return _emit({
            "ok": True,
            "items": [_jsonable(r) for r in items],
            "side_effect": se.value,
        })
    except Exception as e:
        return _emit({"ok": False, "error": f"{type(e).__name__}: {e}",
                      "side_effect": se.value})


def cmd_show(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    _db, warn_msg = _db_or_warn()
    if _db is None or warn_msg:
        return _emit({"ok": False, "error": warn_msg or "no db",
                      "side_effect": se.value})
    try:
        item = _db.get_research_item(args.id)
        return _emit({"ok": True, "item": _jsonable(item),
                      "side_effect": se.value})
    except Exception as e:
        return _emit({"ok": False, "error": f"{type(e).__name__}: {e}",
                      "side_effect": se.value})


def cmd_cite(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    _db, warn_msg = _db_or_warn()
    if _db is None or warn_msg:
        return _emit({"ok": False, "error": warn_msg or "no db",
                      "side_effect": se.value})
    try:
        cid = _db.cite_research(
            args.id,
            run_id=args.run_id,
            experiment_id=args.experiment_id,
            quote=args.quote,
        )
        return _emit({"ok": True, "citation_id": cid,
                      "side_effect": se.value})
    except Exception as e:
        return _emit({"ok": False, "error": f"{type(e).__name__}: {e}",
                      "side_effect": se.value})


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    rs = sub.add_parser("research",
                        help="Cited, trust-labeled web research items")
    rs_sub = rs.add_subparsers(dest="research_cmd", required=True)

    p_fetch = rs_sub.add_parser("fetch",
                                help="Fetch a URL and record a research_items row")
    p_fetch.add_argument("--url", required=True)
    p_fetch.add_argument("--competition", default=None)
    p_fetch.add_argument("--fetcher", choices=("http", "playwright"),
                         default="http")
    p_fetch.add_argument("--trust", choices=sorted(VALID_TRUSTS),
                         default="untrusted")
    p_fetch.add_argument("--title", default=None)
    p_fetch.add_argument("--summary", default=None)
    p_fetch.add_argument("--source-kind", dest="source_kind", default="page")
    p_fetch.add_argument("--timeout", type=int, default=20)
    p_fetch.add_argument("--json", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_add = rs_sub.add_parser("add", help="Register a research_items row by URL")
    p_add.add_argument("--url", required=True)
    p_add.add_argument("--title", default=None)
    p_add.add_argument("--summary", default=None)
    p_add.add_argument("--trust", choices=sorted(VALID_TRUSTS),
                       default="unknown")
    p_add.add_argument("--competition", default=None)
    p_add.add_argument("--json", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_list = rs_sub.add_parser("list", help="List research_items")
    p_list.add_argument("--competition", default=None)
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = rs_sub.add_parser("show", help="Show a research_item by id")
    p_show.add_argument("--id", required=True)
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_cite = rs_sub.add_parser("cite", help="Link a research_item to a run/experiment")
    p_cite.add_argument("--id", required=True)
    p_cite.add_argument("--run-id", dest="run_id", default=None)
    p_cite.add_argument("--experiment-id", dest="experiment_id", default=None)
    p_cite.add_argument("--quote", default=None)
    p_cite.add_argument("--json", action="store_true")
    p_cite.set_defaults(func=cmd_cite)
