"""kca devpost: READ_ONLY register / fetch / info + gated submit for Devpost-style events.

Side-effect classification:
  - cmd_fetch  → READ_ONLY (anonymous HTTP GET; no cookies, no writes).
  - cmd_register → LOCAL_WRITE (UPSERT into the local `competitions` table).
  - cmd_info   → READ_ONLY (SELECT one row).
  - cmd_submit → SUBMISSION (M12-T007 only; gated behind reviewer + human
    approval; refuses without DEVPOST_USERNAME + DEVPOST_TOKEN env vars).

cmd_submit is the single Devpost write op the project supports. The
function exists so M12-T008's regression tests can assert the no-creds
refusal path; the real network call is performed only when both
credentials are present AND `dry_run=False`.

This adapter mirrors the shape of `tools/kca/competition.py` (Kaggle side)
and reuses the lightweight HTTP + readability fallback documented in
`tools/kca/research_fetch.py`. Playwright is opt-in only and is imported
lazily so `import tools.kca.devpost` stays cheap.

Untrusted-data principle: fetched HTML is treated as data, never as
instructions. Field extraction is purely structural (CSS selectors,
meta tags, regex over text).

Auth shape (decision for M12-T003):
  Anonymous HTTPS GET against the public hackathon page is sufficient
  for the four required fields on the picked target (h01). No cookie,
  API token, or session header is used. If a future candidate platform
  requires login for metadata, halt and ask before introducing a
  DEVPOST_* env var.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect

# Default user-agent advertises the project; matches research_fetch.py.
DEFAULT_USER_AGENT = "kca-devpost/0.1 (+https://example.invalid/kca)"
DEFAULT_TIMEOUT_S = 20

# ADR-0016 enum values that this adapter may write. Both route to the
# `hackathon-runner` profile per ADR-0016 §"Policy resolver shape" — the
# distinction is documentation-only in M12.
COMPETITION_TYPE_DEVPOST = "devpost"
COMPETITION_TYPE_HACKATHON_DEVPOST = "hackathon_devpost"


# ---------------------------------------------------------------------------
# JSON / output helpers
# ---------------------------------------------------------------------------


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _jsonable(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _emit(payload: dict) -> None:
    out = {k: _jsonable(v) for k, v in payload.items()}
    print(json.dumps(out, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# URL + extraction primitives
# ---------------------------------------------------------------------------


def _url_for_slug(slug: str) -> str:
    """Return the canonical public URL for a Devpost slug.

    Devpost hosts each event at `https://<slug>.devpost.com/`. The slug
    is treated as host-safe (alphanumeric + dash); refuse anything that
    would let a caller inject a different host.
    """
    if not slug or not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", slug):
        raise ValueError(f"invalid devpost slug: {slug!r}")
    return f"https://{slug}.devpost.com/"


def _extract_title(html: str) -> str | None:
    """Pull the canonical event title.

    Devpost's public page emits both an `<meta property=og:title>` and a
    `<title>` tag. og:title is the cleaner string ("H0: Hack the Zero
    Stack..." vs "...: Front-end in minutes... - Devpost"), so prefer it.
    """
    m = re.search(
        r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if m:
        return m.group(1).strip() or None
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    if m:
        # Strip the trailing " - Devpost" suffix when present.
        t = m.group(1).strip()
        t = re.sub(r"\s*-\s*Devpost\s*$", "", t)
        return t or None
    return None


def _extract_deadline_utc(html: str) -> str | None:
    """Pull the ISO8601 deadline; convert to UTC.

    Devpost renders the deadline inside a `<time>` element with a
    `data-iso-date="2026-06-29T20:00:00-04:00"` attribute. We normalise
    to UTC so the `competitions.deadline` column carries a single canonical
    representation.
    """
    m = re.search(r'data-iso-date=["\']([^"\']+)["\']', html, re.I)
    if not m:
        return None
    iso = m.group(1).strip()
    try:
        from datetime import datetime, timezone

        # Python 3.11+: datetime.fromisoformat accepts offsets. Normalise
        # to UTC and emit the ...Z suffix so the column is unambiguous.
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _extract_prize_summary(html: str) -> str | None:
    """Pull a short prize headline.

    Prefer the explicit `<p class="total-prizes">` block when present;
    otherwise fall back to a regex like '$80,000 in cash prizes'.
    The closeout SHOULD paraphrase rather than verbatim-quote the
    rules-page prize text (avoid copying competition rules verbatim into
    PR bodies).
    """
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(".total-prizes")
    if el:
        text = el.get_text(" ", strip=True)
        if text:
            return text
    m = re.search(
        r"\$[\d,]+\s+(?:USD\s+)?in\s+(?:total\s+)?(?:cash\s+)?prize(?:s)?",
        html,
        re.I,
    )
    if m:
        return m.group(0).strip()
    return None


def _extract_submission_format(html: str) -> list[str]:
    """Pull the list of required submission fields / artifacts.

    Devpost's public page commonly carries a "What to submit" heading
    followed by a `<ul>` of bullet items. We harvest those bullets and
    boil each one down to its 'key' (the first phrase before a colon /
    dash / period). Keys are emitted in source order; duplicates are
    de-duplicated case-insensitively.

    Returns a stable, JSON-safe list of strings — the shape the
    `competitions.submission_format` jsonb column carries.
    """
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    # Find the "What to submit" / "Submission Requirements" heading and
    # the next <ul> after it.
    candidate_uls: list[Any] = []
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        title = (h.get_text(strip=True) or "").lower()
        if "what to submit" in title or "submission requirements" in title:
            ul = h.find_next("ul")
            if ul is not None:
                candidate_uls.append(ul)
    items: list[str] = []
    seen: set[str] = set()
    for ul in candidate_uls:
        for li in ul.find_all("li", recursive=False):
            # Read only the li's own top-level text (not the nested
            # sub-bullets). A nested <ul> often expands "should ...", "must
            # ..." sub-clauses that aren't part of the field name.
            parts: list[str] = []
            for child in li.children:
                # Skip nested lists; their text is descriptive prose, not
                # a separate field requirement.
                if getattr(child, "name", None) in {"ul", "ol"}:
                    break
                if getattr(child, "name", None) is None:
                    # NavigableString
                    s = str(child).strip()
                    if s:
                        parts.append(s)
                else:
                    s = child.get_text(" ", strip=True)
                    if s:
                        parts.append(s)
            raw = " ".join(parts).strip()
            if not raw:
                continue
            # Reduce to the first 'key phrase'. Devpost bullets look like:
            #   "Text description - tell us which one of the AWS Databases ..."
            # We want "Text description". Split on the first " - ", " — ",
            # ": ", or ". " (sentence boundary).
            key = re.split(r"\s+[-–—:]\s+|\.\s+", raw, maxsplit=1)[0]
            key = key.strip().rstrip(".")
            # Cap the key at a sensible length so a missing sentence
            # boundary in a noisy bullet doesn't blow up the column.
            if len(key) > 80:
                key = key[:80].rsplit(" ", 1)[0]
            if not key:
                continue
            slug_key = re.sub(r"\s+", "_", key.lower())
            slug_key = re.sub(r"[^a-z0-9_]+", "", slug_key)
            if not slug_key or slug_key in seen:
                continue
            seen.add(slug_key)
            items.append(slug_key)
    return items


# ---------------------------------------------------------------------------
# HTTP fetch (anonymous; READ_ONLY)
# ---------------------------------------------------------------------------


def _fetch_html(
    url: str,
    *,
    playwright: bool = False,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Fetch raw HTML for the public Devpost page.

    Default path is anonymous `requests.get`. The Playwright path is
    opt-in and imported lazily; the import only happens when
    `playwright=True`. This keeps `import tools.kca.devpost` cheap and
    satisfies the M12-T003 acceptance check that importing the module
    does not eagerly import Playwright.
    """
    # SSRF / scheme guard via research_fetch._check_policy.
    from research_fetch import _check_policy

    policy_err = _check_policy(url)
    if policy_err is not None:
        warnings = policy_err.get("policy_warnings", [])
        raise RuntimeError(f"policy_blocked: {', '.join(warnings) or 'unknown'} (url={url})")

    if playwright:
        return _fetch_html_playwright(url, timeout_s=timeout_s)
    return _fetch_html_http(url, timeout_s=timeout_s)


def _fetch_html_http(url: str, *, timeout_s: int) -> str:
    import requests  # type: ignore

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,*/*;q=0.5",
    }
    resp = requests.get(url, timeout=timeout_s, headers=headers, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _fetch_html_playwright(url: str, *, timeout_s: int) -> str:
    # Imported lazily on purpose: the sanity test in
    # tests/test_m12_devpost_adapter.py asserts that the top-level
    # `import tools.kca.devpost` does NOT pull playwright in.
    from playwright.sync_api import sync_playwright  # type: ignore

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
            return page.content()
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Library-shaped API
#
# The CLI subcommands below are thin wrappers around these three pure
# functions. M12-T004 / M12-T006 may call these directly without going
# through argparse.
# ---------------------------------------------------------------------------


def fetch_metadata(slug: str, *, playwright: bool = False) -> dict[str, Any]:
    """READ_ONLY fetch + parse. Returns the four canonical fields.

    Shape:
      {
        "slug": str,
        "url": str,
        "title": str | None,
        "deadline_utc": str | None,   # ISO8601 with 'Z' suffix
        "prize_summary": str | None,
        "submission_format": list[str],
      }

    Raises:
      ValueError on invalid slug.
      RuntimeError when the SSRF / scheme guard refuses the URL.
      Network errors (`requests.HTTPError`, timeouts) propagate so the
      caller can decide whether to retry or surface to the user.
    """
    url = _url_for_slug(slug)
    html = _fetch_html(url, playwright=playwright)
    return {
        "slug": slug,
        "url": url,
        "title": _extract_title(html),
        "deadline_utc": _extract_deadline_utc(html),
        "prize_summary": _extract_prize_summary(html),
        "submission_format": _extract_submission_format(html),
    }


def register_competition(
    slug: str,
    name: str | None = None,
    *,
    competition_type: str = COMPETITION_TYPE_DEVPOST,
    playwright: bool = False,
) -> dict[str, Any]:
    """Idempotent UPSERT into `competitions` keyed by (platform, slug).

    The function fetches the public page to populate `deadline` and
    `submission_format`. If the slug is already registered, the existing
    row's id is reused; `title`, `deadline`, and `submission_format` are
    updated, and `competition_type` is set / overwritten to the value
    documented in this call.

    Returns a dict shaped like:
      {
        "id": str,
        "slug": str,
        "competition_type": str,
        "title": str,
        "deadline": str | None,
        "submission_format": list[str],
        "metadata": <fetch_metadata output>,
      }

    DB writes require KCA_DB_TARGET=local (default) or both
    KCA_DB_TARGET=remote + KCA_ALLOW_REMOTE=1 per `tools.kca.db`.
    """
    if competition_type not in {
        COMPETITION_TYPE_DEVPOST,
        COMPETITION_TYPE_HACKATHON_DEVPOST,
    }:
        raise ValueError(f"competition_type must be 'devpost' or 'hackathon_devpost', got {competition_type!r}")
    meta = fetch_metadata(slug, playwright=playwright)
    title = name or meta.get("title") or slug
    deadline = meta.get("deadline_utc")
    submission_format = meta.get("submission_format") or []

    import db as _db  # tools/kca/db.py

    # platform='devpost' so existing unique key (platform, slug) groups
    # the row cleanly under the Devpost adapter.
    competition_id = _db.ensure_competition(
        slug=slug,
        platform="devpost",
        title=title,
    )

    submission_format_json = json.dumps(submission_format)
    with _db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE competitions
                   SET competition_type  = %s::competition_type_enum,
                       deadline          = %s::timestamptz,
                       submission_format = %s::jsonb,
                       title             = COALESCE(%s, title)
                 WHERE id = %s::uuid
                """,
                (
                    competition_type,
                    deadline,
                    submission_format_json,
                    title,
                    competition_id,
                ),
            )
        conn.commit()

    return {
        "id": competition_id,
        "slug": slug,
        "competition_type": competition_type,
        "title": title,
        "deadline": deadline,
        "submission_format": submission_format,
        "metadata": meta,
    }


def get_competition_row(slug: str) -> dict[str, Any]:
    """READ_ONLY: return the local `competitions` row for `slug`.

    Raises KeyError when no such row exists.
    """
    import db as _db

    return _db.get_competition_by_slug(slug)


# ---------------------------------------------------------------------------
# M12-T007: gated submit (SUBMISSION side-effect)
# ---------------------------------------------------------------------------

# Documented env-var names for Devpost auth (decided in M12-T007). Both
# MUST be set for the submit path to touch the network; absence routes
# to a clean refusal that exits non-zero and does NOT make any HTTP
# call. Mirrors the KAGGLE_USERNAME / KAGGLE_KEY pattern from
# `tools/kca/kg.py::cmd_submit`. Never log / print the credential value.
DEVPOST_USERNAME_ENV = "DEVPOST_USERNAME"
DEVPOST_TOKEN_ENV = "DEVPOST_TOKEN"  # session cookie OR API token; auth_shape documented in the closing issue
DEVPOST_SUBMIT_ENDPOINT_TPL = "https://{slug}.devpost.com/submissions"


def _have_devpost_creds() -> bool:
    """Return True iff both DEVPOST_USERNAME and DEVPOST_TOKEN are set
    AND non-empty. Boolean only — never returns / logs the values."""
    import os as _os

    return bool(
        (_os.environ.get(DEVPOST_USERNAME_ENV) or "").strip() and (_os.environ.get(DEVPOST_TOKEN_ENV) or "").strip()
    )


def _load_submission_pack(slug: str, run_id: str) -> dict[str, Any]:
    """READ_ONLY: assemble the payload from runs/<slug>/<run_id>/submission_pack/.

    Returns the structured payload the Devpost submit endpoint will
    receive. Does NOT touch the network. Raises FileNotFoundError if the
    pack directory is missing. Pure / deterministic so M12-T008 can pin
    the templater output.
    """
    from pathlib import Path

    pack = (Path("runs") / slug / run_id / "submission_pack").resolve()
    if not pack.is_dir():
        raise FileNotFoundError(f"submission_pack not found at {pack}; run M12-T006 first")
    readme = pack / "README.md"
    demo_plan = pack / "demo-plan.md"
    checklist = pack / "submission-checklist.json"
    payload: dict[str, Any] = {
        "slug": slug,
        "run_id": run_id,
        "pack_dir": str(pack),
        "readme_present": readme.is_file(),
        "demo_plan_present": demo_plan.is_file(),
        "checklist_present": checklist.is_file(),
    }
    # Inline file contents only when small enough; never inline secrets.
    if readme.is_file():
        payload["readme_bytes"] = readme.stat().st_size
    if checklist.is_file():
        try:
            payload["checklist"] = json.loads(checklist.read_text(encoding="utf-8"))
        except Exception as exc:
            payload["checklist_error"] = f"{type(exc).__name__}: {exc}"
    return payload


def cmd_submit(
    slug: str,
    run_id: str,
    message: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Submit a Devpost-style hackathon entry. Single real-write op in M12.

    Behavior:
      - Reads runs/<slug>/<run_id>/submission_pack/ to assemble the
        payload (README, demo plan, checklist, source link). READ_ONLY.
      - If `dry_run=True` OR either of DEVPOST_USERNAME / DEVPOST_TOKEN
        is missing, returns a refusal dict with `ok=False` and
        `reason="credentials_missing"` (or `reason="dry_run"`) and
        DOES NOT touch the network. Callers should map this to a
        non-zero process exit.
      - If credentials are present AND not dry-run: POSTs the assembled
        payload to the Devpost submission endpoint, polls the response
        for the canonical submission URL, and returns
        `{"ok": True, "external_submission_id": <id>,
          "submission_url": <url>, ...}`.

    This function is the ONLY Devpost write op the project supports.
    The reviewer gate + human-decisions approval MUST fire before this
    is called in non-dry-run mode; see `src/worker/reviewer.py` +
    `tools/kca/decisions.py`.
    """
    if not slug or not isinstance(slug, str):
        return {"ok": False, "reason": "invalid_slug", "slug": slug}
    if not run_id or not isinstance(run_id, str):
        return {"ok": False, "reason": "invalid_run_id", "run_id": run_id}

    # Load pack first — failing here means M12-T006 has not run / is incomplete.
    try:
        payload = _load_submission_pack(slug, run_id)
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "reason": "submission_pack_missing",
            "error": str(exc),
            "slug": slug,
            "run_id": run_id,
            "side_effect": SideEffect.READ_ONLY.value,
        }

    creds_present = _have_devpost_creds()

    # Refusal branches — both fire BEFORE any network access.
    if dry_run:
        return {
            "ok": False,
            "reason": "dry_run",
            "message": "dry-run: payload assembled but not submitted",
            "slug": slug,
            "run_id": run_id,
            "payload_keys": sorted(payload.keys()),
            "creds_present": creds_present,  # boolean only, never the value
            "side_effect": SideEffect.READ_ONLY.value,
        }
    if not creds_present:
        return {
            "ok": False,
            "reason": "credentials_missing",
            "error": (
                f"{DEVPOST_USERNAME_ENV} and/or {DEVPOST_TOKEN_ENV} not set; "
                "cannot submit. Populate both in .env (read-for-use, not "
                "read-to-share) and re-run after human approval."
            ),
            "slug": slug,
            "run_id": run_id,
            "side_effect": SideEffect.SUBMISSION.value,
        }

    # ----- live submission branch (gated; only reachable with creds + not dry-run) -----
    # The two refusal branches above protect every test path M12-T008
    # exercises. The block below runs only when a human has explicitly
    # populated DEVPOST_* env vars AND opted out of dry-run; the
    # reviewer-gate + human-decisions approval is enforced upstream in
    # src/worker/reviewer.py + tools/kca/decisions.py.
    import os as _os
    import requests  # type: ignore

    endpoint = DEVPOST_SUBMIT_ENDPOINT_TPL.format(slug=slug)
    form = {
        "message": message,
        "slug": slug,
        "run_id": run_id,
        "readme_bytes": payload.get("readme_bytes", 0),
    }
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        # Token may be a session cookie OR an API token per the
        # auth_shape recorded on the closing issue. Both go in
        # Authorization to keep this module credential-shape agnostic.
        "Authorization": f"Bearer {_os.environ[DEVPOST_TOKEN_ENV]}",
    }
    try:
        resp = requests.post(endpoint, data=form, headers=headers, timeout=DEFAULT_TIMEOUT_S)
        resp.raise_for_status()
        body = resp.json() if "application/json" in resp.headers.get("Content-Type", "") else {}
    except Exception as exc:
        return {
            "ok": False,
            "reason": "http_error",
            "error": f"{type(exc).__name__}: {exc}",
            "slug": slug,
            "run_id": run_id,
            "side_effect": SideEffect.SUBMISSION.value,
        }

    external_id = str(body.get("id") or body.get("external_submission_id") or "").strip()
    submission_url = str(body.get("submission_url") or body.get("url") or "").strip()
    return {
        "ok": bool(external_id and submission_url),
        "external_submission_id": external_id,
        "submission_url": submission_url,
        "slug": slug,
        "run_id": run_id,
        "side_effect": SideEffect.SUBMISSION.value,
    }


def _cmd_submit_cli(args: argparse.Namespace) -> int:
    """argparse entry point for `kca devpost submit`."""
    result = cmd_submit(
        slug=args.slug,
        run_id=args.run_id,
        message=args.message,
        dry_run=bool(args.dry_run),
    )
    _emit(result)
    return EXIT_OK if result.get("ok") else EXIT_RUNTIME


# ---------------------------------------------------------------------------
# argparse entry points
# ---------------------------------------------------------------------------


def cmd_fetch(args: argparse.Namespace) -> int:
    slug = args.slug
    try:
        result = fetch_metadata(slug, playwright=bool(args.playwright))
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "slug": slug,
                "error": f"{type(exc).__name__}: {exc}",
                "side_effect": SideEffect.READ_ONLY.value,
            }
        )
        return EXIT_RUNTIME
    _emit(
        {
            "ok": True,
            "side_effect": SideEffect.READ_ONLY.value,
            **result,
        }
    )
    return EXIT_OK


def cmd_register(args: argparse.Namespace) -> int:
    slug = args.slug
    try:
        result = register_competition(
            slug,
            args.name,
            competition_type=args.competition_type,
            playwright=bool(args.playwright),
        )
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "slug": slug,
                "error": f"{type(exc).__name__}: {exc}",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            }
        )
        return EXIT_RUNTIME
    _emit(
        {
            "ok": True,
            "side_effect": SideEffect.LOCAL_WRITE.value,
            **result,
        }
    )
    return EXIT_OK


def cmd_info(args: argparse.Namespace) -> int:
    slug = args.slug
    try:
        row = get_competition_row(slug)
    except KeyError as exc:
        _emit(
            {
                "ok": False,
                "slug": slug,
                "error": f"{exc}",
                "side_effect": SideEffect.READ_ONLY.value,
            }
        )
        return EXIT_RUNTIME
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "slug": slug,
                "error": f"{type(exc).__name__}: {exc}",
                "side_effect": SideEffect.READ_ONLY.value,
            }
        )
        return EXIT_RUNTIME
    payload = {k: _jsonable(v) for k, v in row.items()}
    payload["id"] = str(row.get("id", ""))
    _emit(
        {
            "ok": True,
            "side_effect": SideEffect.READ_ONLY.value,
            "competition": payload,
        }
    )
    return EXIT_OK


def add_parsers(sub: argparse._SubParsersAction) -> None:
    devpost = sub.add_parser(
        "devpost",
        help="Devpost / hackathon adapter (READ_ONLY register / fetch / info; M12-T003)",
    )
    devpost_sub = devpost.add_subparsers(dest="devpost_cmd", required=True)

    p_reg = devpost_sub.add_parser(
        "register",
        help="UPSERT a Devpost competition row from the public page (LOCAL_WRITE).",
    )
    p_reg.add_argument("--slug", required=True)
    p_reg.add_argument(
        "--name",
        default=None,
        help="Override the title extracted from the public page.",
    )
    p_reg.add_argument(
        "--competition-type",
        dest="competition_type",
        choices=[COMPETITION_TYPE_DEVPOST, COMPETITION_TYPE_HACKATHON_DEVPOST],
        default=COMPETITION_TYPE_DEVPOST,
        help="ADR-0016 competition_type value (default: 'devpost').",
    )
    p_reg.add_argument(
        "--playwright",
        action="store_true",
        help="Use the headless-browser fallback for JS-rendered pages.",
    )
    p_reg.set_defaults(func=cmd_register)

    p_fetch = devpost_sub.add_parser(
        "fetch",
        help="Fetch + extract the four canonical metadata fields (READ_ONLY).",
    )
    p_fetch.add_argument("--slug", required=True)
    p_fetch.add_argument(
        "--playwright",
        action="store_true",
        help="Use the headless-browser fallback for JS-rendered pages.",
    )
    p_fetch.set_defaults(func=cmd_fetch)

    p_info = devpost_sub.add_parser(
        "info",
        help="Print the local competitions row for the slug (READ_ONLY).",
    )
    p_info.add_argument("--slug", required=True)
    p_info.set_defaults(func=cmd_info)

    p_submit = devpost_sub.add_parser(
        "submit",
        help=(
            "Submit a hackathon entry (SUBMISSION; M12-T007). Refuses "
            "without DEVPOST_USERNAME + DEVPOST_TOKEN set; use --dry-run "
            "to assemble payload without touching the network."
        ),
    )
    p_submit.add_argument("--slug", required=True)
    p_submit.add_argument(
        "--run-id",
        dest="run_id",
        required=True,
        help="The run id under runs/<slug>/<run_id>/submission_pack/",
    )
    p_submit.add_argument(
        "--message",
        required=True,
        help="Short submission message (visible on Devpost).",
    )
    p_submit.add_argument(
        "--dry-run",
        action="store_true",
        help="Assemble payload but DO NOT touch the network.",
    )
    p_submit.set_defaults(func=_cmd_submit_cli)


# Re-exported for tests / external callers.
__all__ = [
    "COMPETITION_TYPE_DEVPOST",
    "COMPETITION_TYPE_HACKATHON_DEVPOST",
    "DEVPOST_TOKEN_ENV",
    "DEVPOST_USERNAME_ENV",
    "add_parsers",
    "cmd_fetch",
    "cmd_info",
    "cmd_register",
    "cmd_submit",
    "fetch_metadata",
    "get_competition_row",
    "register_competition",
]
