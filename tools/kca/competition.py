"""kca competition: register, clone, list, info for competition repos (M4-T003)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect


def _emit(payload: dict) -> None:
    # JSON-safe: stringify uuid/datetime values shallowly.
    out = {}
    for k, v in payload.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [_jsonable(x) for x in v]
        else:
            out[k] = _jsonable(v)
    print(json.dumps(out, ensure_ascii=False, default=str))


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(vv) for k, vv in v.items()}
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v if (v is None or isinstance(v, (str, int, float, bool, list, dict))) else str(v)


def _default_clone_path(slug: str) -> str:
    return str(Path.home() / "competitions" / f"kaggle-{slug}")


def _load_db():
    import db as _db
    return _db


def cmd_register(args: argparse.Namespace) -> int:
    slug = args.slug
    repo_url = args.repo_url
    branch = args.branch or "main"
    clone_path = args.clone_path or _default_clone_path(slug)
    try:
        _db = _load_db()
        comp = _db.get_competition_by_slug(slug)
        _db.update_competition(
            comp["id"],
            repo_url=repo_url,
            default_branch=branch,
            local_clone_path=clone_path,
        )
    except Exception as exc:
        _emit({"ok": False, "error": str(exc), "side_effect": SideEffect.LOCAL_WRITE.value})
        return EXIT_RUNTIME
    _emit({
        "ok": True,
        "slug": slug,
        "repo_url": repo_url,
        "default_branch": branch,
        "local_clone_path": clone_path,
        "side_effect": SideEffect.LOCAL_WRITE.value,
    })
    return EXIT_OK


def cmd_clone(args: argparse.Namespace) -> int:
    slug = args.slug
    try:
        _db = _load_db()
        comp = _db.get_competition_by_slug(slug)
    except Exception as exc:
        _emit({"ok": False, "error": str(exc)})
        return EXIT_RUNTIME

    repo_url = comp.get("repo_url")
    if not repo_url:
        _emit({"ok": False, "error": f"competition '{slug}' has no repo_url; run register first"})
        return EXIT_RUNTIME
    clone_path = args.path or comp.get("local_clone_path") or _default_clone_path(slug)

    if Path(clone_path).exists():
        _emit({
            "ok": True,
            "cloned": False,
            "path": clone_path,
            "side_effect": SideEffect.READ_ONLY.value,
        })
        return EXIT_OK

    try:
        Path(clone_path).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", repo_url, clone_path], check=True,
                       capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        _emit({"ok": False, "error": f"git clone failed: {exc.stderr or exc.stdout}"})
        return EXIT_RUNTIME

    _emit({
        "ok": True,
        "cloned": True,
        "path": clone_path,
        "side_effect": SideEffect.LOCAL_WRITE.value,
    })
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    competitions: list[dict] = []
    try:
        _db = _load_db()
        rows = _db.list_competitions()
        for r in rows:
            competitions.append({
                "id": str(r.get("id", "")),
                "slug": r.get("slug"),
                "platform": r.get("platform"),
                "title": r.get("title"),
                "repo_url": r.get("repo_url"),
                "default_branch": r.get("default_branch"),
                "local_clone_path": r.get("local_clone_path"),
            })
    except Exception:
        # Graceful degradation: empty list when DB unavailable.
        competitions = []
    _emit({
        "ok": True,
        "competitions": competitions,
        "side_effect": SideEffect.READ_ONLY.value,
    })
    return EXIT_OK


def cmd_info(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        comp = _db.get_competition_by_slug(args.slug)
    except Exception as exc:
        _emit({"ok": False, "error": str(exc)})
        return EXIT_RUNTIME
    out = {k: _jsonable(v) for k, v in comp.items()}
    out["id"] = str(comp.get("id", ""))
    _emit({
        "ok": True,
        "competition": out,
        "side_effect": SideEffect.READ_ONLY.value,
    })
    return EXIT_OK


def add_parsers(sub: argparse._SubParsersAction) -> None:
    comp = sub.add_parser("competition", help="Register and inspect competition repos (M4)")
    comp_sub = comp.add_subparsers(dest="competition_cmd", required=True)

    p_reg = comp_sub.add_parser("register", help="Register a competition repo (LOCAL_WRITE)")
    p_reg.add_argument("--slug", required=True)
    p_reg.add_argument("--repo-url", dest="repo_url", required=True)
    p_reg.add_argument("--branch", default="main")
    p_reg.add_argument("--clone-path", dest="clone_path", default=None)
    p_reg.add_argument("--json", action="store_true")
    p_reg.set_defaults(func=cmd_register)

    p_clone = comp_sub.add_parser("clone", help="Clone competition repo locally (LOCAL_WRITE)")
    p_clone.add_argument("--slug", required=True)
    p_clone.add_argument("--path", default=None, help="Override local clone path")
    p_clone.add_argument("--json", action="store_true")
    p_clone.set_defaults(func=cmd_clone)

    p_list = comp_sub.add_parser("list", help="List registered competitions (READ_ONLY)")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_info = comp_sub.add_parser("info", help="Show competition row (READ_ONLY)")
    p_info.add_argument("--slug", required=True)
    p_info.add_argument("--json", action="store_true")
    p_info.set_defaults(func=cmd_info)
