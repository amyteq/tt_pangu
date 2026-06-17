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

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect
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
        return _emit({"ok": False, "error": f"invalid trust: {trust}", "side_effect": se.value})

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
        _check_approval_gate("external_fetch", {"approval_gates": policy_gates})
    except ApprovalRequired:
        return _emit(
            {
                "ok": False,
                "error": "ApprovalRequired: external_fetch",
                "operation": "external_fetch",
                "url": url,
                "side_effect": se.value,
            }
        )

    # Stage artifact dir under repo: artifacts/research/<hash[:12]>/ -- but
    # we don't know the hash yet, so use a tmp staging dir and move.
    staging = REPO_ROOT / "artifacts" / "research" / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    result = fetch_page(
        url,
        out_dir=staging,
        fetcher=args.fetcher or "http",
        timeout_s=args.timeout or 20,
    )
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
            "research_html",
            str(raw_final),
            content_hash=content_hash,
            byte_size=result.get("bytes"),
        )
        text_art = _db.attach_artifact(
            "research_text",
            str(text_final),
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
        return _emit({"ok": False, "error": f"invalid trust: {trust}", "side_effect": se.value})

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
        return _emit(
            {
                "ok": True,
                "items": [],
                "db_warning": warn_msg or "no db module",
                "side_effect": se.value,
            }
        )
    try:
        comp_id, _ = _resolve_competition_id(args.competition)
        items = _db.list_research_items(competition_id=comp_id, limit=args.limit)
        return _emit(
            {
                "ok": True,
                "items": [_jsonable(r) for r in items],
                "side_effect": se.value,
            }
        )
    except Exception as e:
        return _emit({"ok": False, "error": f"{type(e).__name__}: {e}", "side_effect": se.value})


def cmd_show(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    _db, warn_msg = _db_or_warn()
    if _db is None or warn_msg:
        return _emit({"ok": False, "error": warn_msg or "no db", "side_effect": se.value})
    try:
        item = _db.get_research_item(args.id)
        return _emit({"ok": True, "item": _jsonable(item), "side_effect": se.value})
    except Exception as e:
        return _emit({"ok": False, "error": f"{type(e).__name__}: {e}", "side_effect": se.value})


def cmd_cite(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    _db, warn_msg = _db_or_warn()
    if _db is None or warn_msg:
        return _emit({"ok": False, "error": warn_msg or "no db", "side_effect": se.value})
    try:
        cid = _db.cite_research(
            args.id,
            run_id=args.run_id,
            experiment_id=args.experiment_id,
            quote=args.quote,
        )
        return _emit({"ok": True, "citation_id": cid, "side_effect": se.value})
    except Exception as e:
        return _emit({"ok": False, "error": f"{type(e).__name__}: {e}", "side_effect": se.value})


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


# ===========================================================================
# Idea-sourcing (M14-T006) — untrusted-data filter + source readers.
#
# These power `kca explore propose-next`. Every fetched string (public-kernel
# titles, forum-thread bodies, arxiv abstracts) is treated as UNTRUSTED DATA
# per CLAUDE.md operating principle 1 / ADR-0020: it is captured as quoted
# data with a trust_label and is NEVER interpreted as an instruction, command,
# or search-space directive. The three reader functions are *injectable* so
# tests drive them with fixtures; the defaults make NO network call unless an
# explicit live reader is supplied by the caller.
# ===========================================================================

# Phrases that, in untrusted source text, look like an attempt to redirect the
# agent. We do NOT act on them; we only *flag* their presence so the proposal
# carries a low trust_label and the operator can see the source was adversarial.
_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "disregard the above",
    "run this command",
    "run the following",
    "execute the following",
    "rm -rf",
    "curl ",
    "wget ",
    "system(",
    "subprocess",
    "os.system",
    "eval(",
    "exec(",
    "import os",
    "kaggle competitions submit",
    "kaggle kernels push",
    "you are now",
    "new instructions",
    "override your",
)

# A sentinel that MUST never appear in any executed code path. Tests inject a
# fixture containing this token inside an "instruction"; if propose-next ever
# treated the source as code, the token would surface as a side effect. We
# assert it only ever lands inside a quoted data field.
NOEXEC_SENTINEL = "__KCA_NOEXEC_SENTINEL__"


def detect_injection(text: str) -> list[str]:
    """Return the injection markers found in untrusted ``text`` (lower-cased).

    Pure string scan — it never executes anything. The returned list is recorded
    as evidence so a proposal sourced from adversarial text is down-trusted.
    """
    if not text:
        return []
    low = text.lower()
    return [m for m in _INJECTION_MARKERS if m in low]


def sanitize_untrusted(text: str, *, max_len: int = 280) -> str:
    """Collapse untrusted source text into a single quoted-data line.

    Strips control chars / newlines (so it cannot break out of a YAML scalar or
    a log line), truncates, and returns a plain string. The result is only ever
    written into a *data* field (rationale / quote), never evaluated.
    """
    if not text:
        return ""
    flat = " ".join(str(text).split())
    flat = "".join(ch for ch in flat if ch == " " or (32 <= ord(ch) < 0x110000 and ch.isprintable()))
    if len(flat) > max_len:
        flat = flat[: max_len - 1].rstrip() + "…"
    return flat


def classify_trust(source_kind: str, injection_markers: list[str]) -> str:
    """Map (source_kind, injection findings) -> a research-brief trust label.

    Any source carrying an injection marker is forced to ``untrusted`` no matter
    its origin — an adversarial payload is never promoted to community/public.
    """
    if injection_markers:
        return "untrusted"
    return {
        "kernel": "community",
        "forum": "community",
        "arxiv": "trusted_public",
    }.get(source_kind, "unknown")


def _kernel_keywords(title: str) -> list[str]:
    """Extract candidate axis hints from a kernel/paper title (data, not code)."""
    low = title.lower()
    hits: list[str] = []
    for backbone in (
        "efficientnet",
        "efficientnetv2",
        "resnet",
        "resnet101",
        "densenet",
        "convnext",
        "vit",
        "swin",
        "xception",
        "regnet",
        "nfnet",
    ):
        if backbone in low:
            hits.append(backbone)
    return hits


# --- Injectable source readers --------------------------------------------
#
# Default behavior: NO network. A live reader (a callable hitting the Kaggle /
# arxiv APIs under the research-brief trust model) is passed in by the caller
# only when --live is requested with prior approval; tests pass fixture-backed
# readers. Each returns a list of dicts: {source_kind, source_url, title, text}.


def default_kernels_reader(slug: str, limit: int) -> list[dict]:
    """Default kernels reader — NO network. Returns []. Tests inject a fixture.

    A live implementation would call ``kaggle.api.kernels_list(competition=slug,
    sort_by='hotness')`` (READ_ONLY) and map each kernel to a source dict. We do
    NOT call it by default so the test path and the dry-run default never touch
    the network.
    """
    return []


def default_forum_reader(slug: str, limit: int) -> list[dict]:
    """Default forum reader — NO network (best-effort scrape is opt-in)."""
    return []


def default_arxiv_reader(keywords: list[str], limit: int) -> list[dict]:
    """Default arxiv reader — NO network. Tests inject a fixture."""
    return []


def gather_sources(
    slug: str,
    *,
    budget: int,
    kernels_reader=None,
    forum_reader=None,
    arxiv_reader=None,
    keywords: list[str] | None = None,
) -> list[dict]:
    """Collect + sanitize source records from the three injectable readers.

    Every record is run through the untrusted-data filter:
      - ``injection_markers`` records any adversarial phrase found (evidence);
      - ``trust_label`` is forced to ``untrusted`` when markers are present;
      - ``quote`` is the sanitized single-line data form (never executed).
    Returns the list of sanitized source dicts (raw text discarded after scan).
    """
    kernels_reader = kernels_reader or default_kernels_reader
    forum_reader = forum_reader or default_forum_reader
    arxiv_reader = arxiv_reader or default_arxiv_reader
    keywords = keywords or [slug]

    raw: list[dict] = []
    raw.extend(kernels_reader(slug, budget) or [])
    raw.extend(forum_reader(slug, budget) or [])
    raw.extend(arxiv_reader(keywords, budget) or [])

    out: list[dict] = []
    for rec in raw:
        kind = str(rec.get("source_kind", "unknown"))
        url = str(rec.get("source_url", "")) or None
        title = sanitize_untrusted(rec.get("title", ""), max_len=200)
        body = str(rec.get("text", "") or "")
        markers = detect_injection(title + "\n" + body)
        trust = classify_trust(kind, markers)
        out.append(
            {
                "source_kind": kind,
                "source_url": url,
                "title": title,
                "quote": sanitize_untrusted(body or title),
                "trust_label": trust,
                "injection_markers": markers,
                "keyword_hits": _kernel_keywords(title + " " + body),
            }
        )
    return out


def add_parsers(sub: argparse._SubParsersAction) -> None:
    rs = sub.add_parser("research", help="Cited, trust-labeled web research items")
    rs_sub = rs.add_subparsers(dest="research_cmd", required=True)

    p_fetch = rs_sub.add_parser("fetch", help="Fetch a URL and record a research_items row")
    p_fetch.add_argument("--url", required=True)
    p_fetch.add_argument("--competition", default=None)
    p_fetch.add_argument("--fetcher", choices=("http", "playwright"), default="http")
    p_fetch.add_argument("--trust", choices=sorted(VALID_TRUSTS), default="untrusted")
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
    p_add.add_argument("--trust", choices=sorted(VALID_TRUSTS), default="unknown")
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
