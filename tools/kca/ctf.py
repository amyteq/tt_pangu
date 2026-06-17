"""kca ctf: authorized CTF / lab workflow CLI surface (M11-T003).

Subcommand surface:

  kca ctf event {register, list, info}
  kca ctf challenge {add, fetch, list, info}
  kca ctf scope {set, list, verify}
  kca ctf solver run
  kca ctf flag submit

Side-effect classification (see COMMANDS.md):

  - `event register|list|info`         LOCAL_WRITE / READ_ONLY
  - `challenge add|list|info`          LOCAL_WRITE / READ_ONLY
  - `challenge fetch`                  REMOTE_WRITE — KCA_ALLOW_REMOTE=1
                                       + dangerouslyDisableSandbox + scope match
  - `scope set|list|verify`            LOCAL_WRITE / READ_ONLY
  - `solver run`                       LOCAL_WRITE or SUBMISSION-class. The
                                       --reviewer-gate flag wires the worker's
                                       `challenge_run` target_op (see
                                       src/worker/worker.py::_TOOL_TO_TARGET_OP).
                                       --dry-run never fires the gate.
  - `flag submit`                      SUBMISSION. --dry-run never reads the
                                       flag value and never hits the network;
                                       without --dry-run the flag is read from
                                       --flag-file and is NEVER printed.

Credential / secret discipline (two-tier model — see ADR-0017):

  Tier 1 — **CTFtime.org platform account** (single account per user;
  used for events that accept CTFtime SSO and for the CTFtime calendar
  / event-registration flow). Stored in `~/.env` as
  `CTFTIME_USERNAME` and `CTFTIME_PASSWORD` (or `CTFTIME_TOKEN`).
  Loaded ONLY by `_load_ctftime_credentials()` — the single allow-listed
  call-site for the guard_tool deny exception on `~/.env`.

  Tier 2 — **Per-event credentials** (used when an event requires its
  own separate signup, distinct from the CTFtime account). Stored in
  `~/.ctf/<slug>.json` (object with `username`, `token`, optional
  `team_id`) OR `CTF_<EVENT>_USERNAME` + `CTF_<EVENT>_TOKEN` env vars.
  Loaded ONLY by `_load_event_credentials(event_slug)` — the single
  allow-listed call-site for the guard_tool deny exception on ~/.ctf/.

  Both helpers return a dict with boolean-presence flags only when
  used in stdout-bound paths; the raw values stay local to the
  POSTing function in `flag submit` and are dropped from memory
  immediately after.

  - The flag value is read from --flag-file. `cmd_flag_submit` opens
    the file, computes its length, and (in non-dry-run paths) hands
    the bytes directly to the request body builder. The flag is
    never logged, never `print()`ed, never added to a JSON envelope.
    Only `flag_length` and `accepted=true|false` + http status leave
    this function.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from _types import EXIT_BLOCKED, EXIT_OK, EXIT_RUNTIME, SideEffect

_GATE_ENV = "KCA_ALLOW_REMOTE"

# Cross-link: this module is the SINGLE intended caller of paths under
# ~/.ctf/ AND of ~/.env. Any other read site is denied at the hook layer
# (M11-T002 for ~/.ctf/, M11 follow-up for ~/.env CTFtime tier).
_CTF_CRED_DIR = Path.home() / ".ctf"
_CTFTIME_ENV_PATH = Path.home() / ".env"


# ---------------------------------------------------------------------------
# Small helpers (mirrors competition.py / kg.py emit pattern)
# ---------------------------------------------------------------------------


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _jsonable(vv) for k, vv in v.items()}
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v if (v is None or isinstance(v, (str, int, float, bool, list, dict))) else str(v)


def _emit(payload: dict) -> None:
    print(json.dumps({k: _jsonable(v) for k, v in payload.items()}, ensure_ascii=False))


def _load_db_ctf():
    # `src/db/ctf.py` adds its own sys.path entries so the inner `db`
    # module resolves the same way it does from any other kca subcommand.
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import src.db.ctf as _ctf  # noqa: E402

    return _ctf


def _load_db():
    import db as _db  # noqa: E402

    return _db


# ---------------------------------------------------------------------------
# Credential loading — the allow-listed call-site for ~/.ctf/<slug>.json
# ---------------------------------------------------------------------------


class CredentialsMissing(RuntimeError):
    """Raised when neither the file nor env-var path yields credentials."""


def _load_event_credentials(event_slug: str) -> dict[str, Any]:
    """Read CTF credentials for `event_slug`.

    Lookup order:
      1) ~/.ctf/<event_slug>.json — JSON object with at least
         `username` and `token`, optional `team_id`.
      2) CTF_<EVENT>_USERNAME + CTF_<EVENT>_TOKEN env vars,
         optional CTF_<EVENT>_TEAM_ID. `<EVENT>` is `event_slug`
         upper-cased with `-` → `_`.

    Returns a dict::

        {
          "source":   "file" | "env",
          "has_username": bool,
          "has_token":    bool,
          "has_team_id":  bool,
          "_username":    str,        # raw — never to be echoed
          "_token":       str,        # raw — never to be echoed
          "_team_id":     str | None, # raw — never to be echoed
        }

    Callers MUST only forward the boolean-presence fields to anything
    that could end up in stdout / stderr / an audit row / a JSON
    envelope. The underscored fields are intended for in-memory use
    inside the same function call and should be dropped immediately
    after the HTTP request body is built.
    """
    if not event_slug:
        raise CredentialsMissing("event_slug is required")

    # Path 1: file under ~/.ctf/
    cred_path = _CTF_CRED_DIR / f"{event_slug}.json"
    if cred_path.exists():
        try:
            data = json.loads(cred_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CredentialsMissing(f"~/.ctf/{event_slug}.json is not valid JSON: {type(exc).__name__}") from exc
        username = data.get("username")
        token = data.get("token")
        team_id = data.get("team_id")
        if not (username and token):
            raise CredentialsMissing(f"~/.ctf/{event_slug}.json missing 'username' or 'token' (team_id is optional)")
        return {
            "source": "file",
            "has_username": True,
            "has_token": True,
            "has_team_id": bool(team_id),
            "_username": username,
            "_token": token,
            "_team_id": team_id,
        }

    # Path 2: env vars
    env_key = event_slug.upper().replace("-", "_")
    u = os.environ.get(f"CTF_{env_key}_USERNAME")
    t = os.environ.get(f"CTF_{env_key}_TOKEN")
    team = os.environ.get(f"CTF_{env_key}_TEAM_ID")
    if u and t:
        return {
            "source": "env",
            "has_username": True,
            "has_token": True,
            "has_team_id": bool(team),
            "_username": u,
            "_token": t,
            "_team_id": team,
        }

    raise CredentialsMissing(
        f"no credentials for event '{event_slug}': expected "
        f"~/.ctf/{event_slug}.json OR CTF_{env_key}_USERNAME + "
        f"CTF_{env_key}_TOKEN env vars"
    )


def _safe_cred_presence(creds: dict[str, Any]) -> dict[str, Any]:
    """Return only the boolean-presence + source fields from a creds dict.

    Anything passed through this strip is safe to put in stdout / JSON
    envelopes / audit rows.
    """
    return {
        "source": creds.get("source"),
        "has_username": bool(creds.get("has_username")),
        "has_token": bool(creds.get("has_token")),
        "has_team_id": bool(creds.get("has_team_id")),
    }


def _parse_dotenv(text: str) -> dict[str, str]:
    """Tiny KEY=VALUE parser for ~/.env. Strips surrounding quotes; ignores
    blank lines and `#` comments. Does NOT execute shell expansion.

    Kept local to this module to avoid pulling in python-dotenv just for
    two keys.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if not k:
            continue
        v = v.strip()
        if (len(v) >= 2) and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        out[k] = v
    return out


def _load_ctftime_credentials() -> dict[str, Any]:
    """Read the **CTFtime.org platform-level** account credentials.

    Lookup order:
      1) ~/.env file with `CTFTIME_USERNAME` and `CTFTIME_PASSWORD`
         (or `CTFTIME_TOKEN`).
      2) Process env vars with the same names (useful in CI).

    Returns a dict::

        {
          "source":   "home_env" | "process_env",
          "has_username": bool,
          "has_token":    bool,    # True if password OR token present
          "has_team_id":  False,   # not applicable to CTFtime account
          "_username":    str,     # raw — never to be echoed
          "_token":       str,     # raw — never to be echoed
        }

    Raises `CredentialsMissing` if neither path yields a complete
    (username, password|token) pair. Callers MUST only forward the
    `_safe_cred_presence(...)` result to stdout / JSON envelopes /
    audit rows. Underscored fields are intended for in-memory POST
    body construction only and should be dropped immediately after.
    """
    # Path 1: ~/.env
    if _CTFTIME_ENV_PATH.exists():
        try:
            parsed = _parse_dotenv(_CTFTIME_ENV_PATH.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CredentialsMissing(f"~/.env unreadable: {type(exc).__name__}") from exc
        username = parsed.get("CTFTIME_USERNAME")
        token = parsed.get("CTFTIME_PASSWORD") or parsed.get("CTFTIME_TOKEN")
        if username and token:
            return {
                "source": "home_env",
                "has_username": True,
                "has_token": True,
                "has_team_id": False,
                "_username": username,
                "_token": token,
            }

    # Path 2: process env vars (CI-friendly)
    username = os.environ.get("CTFTIME_USERNAME")
    token = os.environ.get("CTFTIME_PASSWORD") or os.environ.get("CTFTIME_TOKEN")
    if username and token:
        return {
            "source": "process_env",
            "has_username": True,
            "has_token": True,
            "has_team_id": False,
            "_username": username,
            "_token": token,
        }

    raise CredentialsMissing(
        "no CTFtime platform credentials: expected ~/.env with "
        "CTFTIME_USERNAME + CTFTIME_PASSWORD (or CTFTIME_TOKEN), "
        "OR the same as process env vars"
    )


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------


def _parse_target_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [u.strip() for u in raw.split(",") if u.strip()]


def _scope_covers_url(scope_row: dict, url: str) -> bool:
    """Return True iff `url`'s host matches any host in
    scope_row['target_urls'] AND the scope has not expired.

    `target_urls` is a JSONB list of fully-qualified URLs (with scheme).
    Match is on host equality (host-only; the path / query of the
    scope row's URL is ignored for the "covers" check so that
    a scope `https://event.example/api/submit` covers any path on
    event.example).
    """
    if not url:
        return False
    expires_at = scope_row.get("expires_at")
    if expires_at:
        now = _dt.datetime.now(_dt.timezone.utc)
        # tolerate naive datetimes by assuming UTC
        if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=_dt.timezone.utc)
        if now > expires_at:
            return False
    target_urls = scope_row.get("target_urls") or []
    if isinstance(target_urls, str):
        try:
            target_urls = json.loads(target_urls)
        except json.JSONDecodeError:
            return False
    target_hosts = set()
    for tu in target_urls:
        try:
            h = urlparse(tu).hostname
        except (ValueError, TypeError):
            h = None
        if h:
            target_hosts.add(h.lower())
    try:
        h = urlparse(url).hostname
    except (ValueError, TypeError):
        h = None
    if not h:
        return False
    return h.lower() in target_hosts


def _list_scopes(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM ctf_scopes ORDER BY created_at DESC LIMIT 200")
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def _get_scope_by_name(conn, name: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM ctf_scopes WHERE name = %s LIMIT 1",
            (name,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# event subcommands
# ---------------------------------------------------------------------------


def cmd_event_register(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    slug = args.slug
    name = args.name
    try:
        _db = _load_db()
        _ctf = _load_db_ctf()
        project_id = _db.ensure_default_project()
        event_id = _ctf.register_event(
            project_id=project_id,
            slug=slug,
            name=name,
            ctftime_event_id=args.ctftime_id,
            event_url=args.url,
            start_at=args.start_at,
            end_at=args.end_at,
            credentials_ref=args.credentials_ref,
        )
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf event register",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    _emit(
        {
            "ok": True,
            "command": "ctf event register",
            "side_effect": se.value,
            "event_id": event_id,
            "slug": slug,
            "name": name,
        }
    )
    return EXIT_OK


def cmd_event_list(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    events: list[dict] = []
    try:
        _ctf = _load_db_ctf()
        rows = _ctf.list_events()
        for r in rows:
            events.append(
                {
                    "id": str(r.get("id", "")),
                    "slug": r.get("slug"),
                    "name": r.get("name"),
                    "ctftime_event_id": r.get("ctftime_event_id"),
                    "event_url": r.get("event_url"),
                    "scoring": r.get("scoring"),
                    "credentials_ref": r.get("credentials_ref"),
                    "start_at": _jsonable(r.get("start_at")),
                    "end_at": _jsonable(r.get("end_at")),
                }
            )
    except Exception:
        # Graceful degrade — empty list when DB unavailable.
        events = []
    _emit(
        {
            "ok": True,
            "command": "ctf event list",
            "side_effect": se.value,
            "events": events,
        }
    )
    return EXIT_OK


def _get_event_by_slug(conn, slug: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM ctf_events WHERE slug = %s LIMIT 1", (slug,))
        row = cur.fetchone()
    return dict(row) if row else None


def cmd_event_info(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    try:
        _db = _load_db()
        conn = _db.get_conn()
        try:
            row = _get_event_by_slug(conn, args.slug)
        finally:
            conn.close()
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf event info",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    if row is None:
        _emit(
            {
                "ok": False,
                "error": f"no event with slug={args.slug!r}",
                "command": "ctf event info",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    payload = {k: _jsonable(v) for k, v in row.items()}
    payload["id"] = str(row.get("id", ""))
    _emit(
        {
            "ok": True,
            "command": "ctf event info",
            "side_effect": se.value,
            "event": payload,
        }
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# challenge subcommands
# ---------------------------------------------------------------------------


def cmd_challenge_add(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    try:
        _db = _load_db()
        _ctf = _load_db_ctf()
        conn = _db.get_conn()
        try:
            event = _get_event_by_slug(conn, args.event)
            if event is None:
                _emit(
                    {
                        "ok": False,
                        "error": f"no event with slug={args.event!r}; run `kca ctf event register` first",
                        "command": "ctf challenge add",
                        "side_effect": se.value,
                    }
                )
                return EXIT_RUNTIME
            scope_id = None
            if args.scope:
                scope = _get_scope_by_name(conn, args.scope)
                if scope is None:
                    _emit(
                        {
                            "ok": False,
                            "error": f"no scope with name={args.scope!r}; run `kca ctf scope set` first",
                            "command": "ctf challenge add",
                            "side_effect": se.value,
                        }
                    )
                    return EXIT_RUNTIME
                scope_id = str(scope["id"])
            challenge_id = _ctf.add_challenge(
                event_id=str(event["id"]),
                slug=args.slug,
                name=args.name,
                category=args.category,
                points=args.points,
                description=args.description,
                expected_flag_format=args.expected_flag_format,
                attachments_path=args.attachments_path,
                remote_endpoint=args.remote_endpoint,
                scope_id=scope_id,
                conn=conn,
            )
        finally:
            conn.close()
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf challenge add",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    _emit(
        {
            "ok": True,
            "command": "ctf challenge add",
            "side_effect": se.value,
            "challenge_id": challenge_id,
            "event_slug": args.event,
            "challenge_slug": args.slug,
            "category": args.category,
            "scope_attached": bool(args.scope),
        }
    )
    return EXIT_OK


def cmd_challenge_fetch(args: argparse.Namespace) -> int:
    """REMOTE_WRITE: fetch challenge attachments from the event endpoint.

    Stub in M11-T003 — the real network call belongs to T005 (in-scope
    local solve) and T007 (single approved live submission). This
    command exists to validate the gate: it refuses without
    KCA_ALLOW_REMOTE=1 and without a matching ctf_scopes row.
    """
    se = SideEffect.REMOTE_WRITE
    if os.environ.get(_GATE_ENV) != "1":
        _emit(
            {
                "ok": False,
                "error": f"remote operation requires {_GATE_ENV}=1 and human approval",
                "command": "ctf challenge fetch",
                "side_effect": se.value,
            }
        )
        return EXIT_BLOCKED

    # Scope check — look up the challenge's scope row, verify it covers
    # the challenge's remote_endpoint host.
    try:
        _db = _load_db()
        conn = _db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.remote_endpoint, c.scope_id, s.target_urls,
                           s.expires_at, s.name AS scope_name
                      FROM ctf_challenges c
                      JOIN ctf_events e ON e.id = c.event_id
                      LEFT JOIN ctf_scopes s ON s.id = c.scope_id
                     WHERE e.slug = %s AND c.slug = %s
                     LIMIT 1
                    """,
                    (args.event, args.slug),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf challenge fetch",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    if row is None:
        _emit(
            {
                "ok": False,
                "error": f"no challenge ({args.event!r}, {args.slug!r})",
                "command": "ctf challenge fetch",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    endpoint = row.get("remote_endpoint")
    if not endpoint:
        _emit(
            {
                "ok": False,
                "error": "challenge has no remote_endpoint; nothing to fetch",
                "command": "ctf challenge fetch",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    scope_row = dict(row) if row else {}
    if not _scope_covers_url(scope_row, endpoint):
        _emit(
            {
                "ok": False,
                "error": "scope does not cover remote_endpoint or has expired",
                "command": "ctf challenge fetch",
                "side_effect": se.value,
                "scope_name": scope_row.get("scope_name"),
                "endpoint_host": urlparse(endpoint).hostname,
            }
        )
        return EXIT_BLOCKED

    # M11-T003 stops here: the actual fetch lives in T005 (uses
    # research_fetch / playwright reuse path). Stub returns ok=True with
    # `dispatched=False` so the caller knows the gate passed but no
    # network call was made in this Loop Prompt.
    _emit(
        {
            "ok": True,
            "command": "ctf challenge fetch",
            "side_effect": se.value,
            "dispatched": False,
            "note": "T003 stub — actual fetch wired in T005",
            "via": args.via,
            "endpoint_host": urlparse(endpoint).hostname,
        }
    )
    return EXIT_OK


def cmd_challenge_list(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    challenges: list[dict] = []
    try:
        _db = _load_db()
        conn = _db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id::text AS id, c.slug, c.name, c.category,
                           c.points, c.remote_endpoint, c.scope_id::text AS scope_id
                      FROM ctf_challenges c
                      JOIN ctf_events e ON e.id = c.event_id
                     WHERE e.slug = %s
                     ORDER BY c.created_at DESC
                     LIMIT 200
                    """,
                    (args.event,),
                )
                rows = cur.fetchall()
            challenges = [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        challenges = []
    _emit(
        {
            "ok": True,
            "command": "ctf challenge list",
            "side_effect": se.value,
            "event_slug": args.event,
            "challenges": challenges,
        }
    )
    return EXIT_OK


def cmd_challenge_info(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    try:
        _ctf = _load_db_ctf()
        row = _ctf.get_challenge(args.event, args.slug)
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf challenge info",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    if row is None:
        _emit(
            {
                "ok": False,
                "error": f"no challenge ({args.event!r}, {args.slug!r})",
                "command": "ctf challenge info",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    payload = {k: _jsonable(v) for k, v in row.items()}
    payload["id"] = str(row.get("id", ""))
    _emit(
        {
            "ok": True,
            "command": "ctf challenge info",
            "side_effect": se.value,
            "challenge": payload,
        }
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# scope subcommands
# ---------------------------------------------------------------------------


def cmd_scope_set(args: argparse.Namespace) -> int:
    se = SideEffect.LOCAL_WRITE
    urls = _parse_target_urls(args.target_urls)
    try:
        _db = _load_db()
        project_id = _db.ensure_default_project()
        conn = _db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ctf_scopes
                      (project_id, name, authorized_scope, target_urls,
                       local_only, expires_at)
                    VALUES
                      (%s::uuid, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id::text
                    """,
                    (
                        project_id,
                        args.slug,
                        args.authorized,
                        json.dumps(urls),
                        bool(args.local_only),
                        args.expires_at,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    # ctf_scopes has no UNIQUE constraint on `name`; the
                    # ON CONFLICT DO NOTHING path won't fire for repeat
                    # names. Update the existing row by name instead.
                    cur.execute(
                        """
                        UPDATE ctf_scopes
                           SET authorized_scope = %s,
                               target_urls = %s::jsonb,
                               local_only = %s,
                               expires_at = %s
                         WHERE name = %s
                         RETURNING id::text
                        """,
                        (
                            args.authorized,
                            json.dumps(urls),
                            bool(args.local_only),
                            args.expires_at,
                            args.slug,
                        ),
                    )
                    row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """
                        INSERT INTO ctf_scopes
                          (project_id, name, authorized_scope, target_urls,
                           local_only, expires_at)
                        VALUES
                          (%s::uuid, %s, %s, %s::jsonb, %s, %s)
                        RETURNING id::text
                        """,
                        (
                            project_id,
                            args.slug,
                            args.authorized,
                            json.dumps(urls),
                            bool(args.local_only),
                            args.expires_at,
                        ),
                    )
                    row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf scope set",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    _emit(
        {
            "ok": True,
            "command": "ctf scope set",
            "side_effect": se.value,
            "scope_id": row["id"] if row else None,
            "name": args.slug,
            "target_urls": urls,
            "local_only": bool(args.local_only),
        }
    )
    return EXIT_OK


def cmd_scope_list(args: argparse.Namespace) -> int:
    se = SideEffect.READ_ONLY
    scopes: list[dict] = []
    try:
        _db = _load_db()
        conn = _db.get_conn()
        try:
            rows = _list_scopes(conn)
        finally:
            conn.close()
        for r in rows:
            scopes.append(
                {
                    "id": str(r.get("id", "")),
                    "name": r.get("name"),
                    "authorized_scope": r.get("authorized_scope"),
                    "target_urls": r.get("target_urls"),
                    "local_only": r.get("local_only"),
                    "expires_at": _jsonable(r.get("expires_at")),
                }
            )
    except Exception:
        scopes = []
    _emit(
        {
            "ok": True,
            "command": "ctf scope list",
            "side_effect": se.value,
            "scopes": scopes,
        }
    )
    return EXIT_OK


def cmd_scope_verify(args: argparse.Namespace) -> int:
    """Exit 0 iff `args.url` ∈ target_urls of `args.slug` AND not expired.

    Used by skills + the worker as a pre-flight check before any
    network_egress / challenge_run / flag_submit op.
    """
    se = SideEffect.READ_ONLY
    try:
        _db = _load_db()
        conn = _db.get_conn()
        try:
            scope = _get_scope_by_name(conn, args.slug)
        finally:
            conn.close()
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "command": "ctf scope verify",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    if scope is None:
        _emit(
            {
                "ok": False,
                "covered": False,
                "error": f"no scope with name={args.slug!r}",
                "command": "ctf scope verify",
                "side_effect": se.value,
            }
        )
        return EXIT_RUNTIME
    covered = _scope_covers_url(scope, args.url)
    _emit(
        {
            "ok": bool(covered),
            "covered": bool(covered),
            "scope_name": scope.get("name"),
            "url_host": urlparse(args.url).hostname,
            "command": "ctf scope verify",
            "side_effect": se.value,
        }
    )
    return EXIT_OK if covered else EXIT_BLOCKED


# ---------------------------------------------------------------------------
# solver run
# ---------------------------------------------------------------------------


def cmd_solver_run(args: argparse.Namespace) -> int:
    """Drive a solver against (event, challenge). M11-T003 stub.

    Side-effect:
      - --dry-run                 LOCAL_WRITE (no gate fires)
      - not --dry-run             SUBMISSION-class (gates via the
                                  worker's `challenge_run` target_op)

    The actual solver-loop body lives in T005 (web + crypto bundled
    challenges) and the reviewer gate exercises in T006. T003 only
    surfaces the CLI signature and the gate refusal path.
    """
    if args.dry_run:
        se = SideEffect.LOCAL_WRITE
        _emit(
            {
                "ok": True,
                "command": "ctf solver run",
                "side_effect": se.value,
                "dry_run": True,
                "event_slug": args.event,
                "challenge_slug": args.challenge,
                "reviewer_gate": False,
                "note": "T003 stub — solver body wired in T005",
            }
        )
        return EXIT_OK

    se = SideEffect.SUBMISSION
    if args.reviewer_gate and os.environ.get(_GATE_ENV) != "1":
        # Reviewer-gate ON without remote allowance: refuse cleanly.
        _emit(
            {
                "ok": False,
                "command": "ctf solver run",
                "side_effect": se.value,
                "error": f"ApprovalRequired: challenge_run (set {_GATE_ENV}=1 after human approval)",
                "target_op": "challenge_run",
            }
        )
        return EXIT_BLOCKED

    # T003 stub — actual solver dispatch lands in T005.
    _emit(
        {
            "ok": True,
            "command": "ctf solver run",
            "side_effect": se.value,
            "dispatched": False,
            "event_slug": args.event,
            "challenge_slug": args.challenge,
            "reviewer_gate": bool(args.reviewer_gate),
            "target_op": "challenge_run",
            "note": "T003 stub — solver body wired in T005",
        }
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# flag submit
# ---------------------------------------------------------------------------


def _read_flag_length(flag_file: Path) -> int:
    """Return only the integer length of the flag file's content.

    The bytes never escape this helper. The full flag bytes are read
    lazily by `cmd_flag_submit` ONLY in the non-dry-run path immediately
    before the (future) HTTP POST; T003 never performs the POST.
    """
    with flag_file.open("rb") as f:
        # 16KB cap is generous; flags are typically < 200 bytes.
        raw = f.read(16 * 1024)
    return len(raw.strip())


def cmd_flag_submit(args: argparse.Namespace) -> int:
    """Submit a flag for a challenge.

    --dry-run path (no remote allowance needed):
      - Open --flag-file with stat() only and read the header to compute
        flag_length. The flag VALUE is not retained beyond this stack
        frame and is never printed.
      - Echo the prospective request shape: event_slug, challenge_slug,
        flag_length, credential presence booleans, and side_effect.

    Non-dry-run path:
      - Refuse without KCA_ALLOW_REMOTE=1.
      - Refuse without a matching ctf_scopes row covering the event's
        submit URL (looked up from ctf_challenges.remote_endpoint).
      - T003 STOPS here. The real POST lives in T007 under the single
        approved live-event call.

    The flag value is NEVER printed, NEVER returned, NEVER added to any
    envelope. Only `flag_length`, `accepted=true|false`, and `http_status`
    leave this function.
    """
    se = SideEffect.SUBMISSION
    flag_path = Path(args.flag_file).expanduser()

    if not flag_path.exists():
        _emit(
            {
                "ok": False,
                "command": "ctf flag submit",
                "side_effect": se.value,
                "error": f"flag file not found: {flag_path}",
            }
        )
        return EXIT_RUNTIME

    # --dry-run: read only the length, never the value. No network. No
    # credential file is opened either — we just check presence.
    if args.dry_run:
        try:
            flag_length = _read_flag_length(flag_path)
        except OSError as exc:
            _emit(
                {
                    "ok": False,
                    "command": "ctf flag submit",
                    "side_effect": SideEffect.LOCAL_WRITE.value,
                    "error": f"read flag file: {type(exc).__name__}",
                    "dry_run": True,
                }
            )
            return EXIT_RUNTIME
        # Best-effort presence check — does NOT touch the file under
        # ~/.ctf/<slug>.json beyond loading + immediately discarding
        # the values from the returned dict.
        cred_presence: dict[str, Any] = {
            "source": None,
            "has_username": False,
            "has_token": False,
            "has_team_id": False,
        }
        try:
            raw = _load_event_credentials(args.event)
            cred_presence = _safe_cred_presence(raw)
            # Explicit drop. `raw` is GC'd at function return anyway,
            # but being explicit signals the contract to readers.
            raw.clear()
        except CredentialsMissing:
            pass
        _emit(
            {
                "ok": True,
                "command": "ctf flag submit",
                "side_effect": SideEffect.LOCAL_WRITE.value,
                "dry_run": True,
                "event_slug": args.event,
                "challenge_slug": args.challenge,
                "flag_length": flag_length,
                "credentials": cred_presence,
                "note": "T003 dry-run; T007 owns the single live submit",
            }
        )
        return EXIT_OK

    # Non-dry-run: enforce all four pre-conditions before T007 runs.
    if os.environ.get(_GATE_ENV) != "1":
        _emit(
            {
                "ok": False,
                "command": "ctf flag submit",
                "side_effect": se.value,
                "error": f"remote operation requires {_GATE_ENV}=1 and human approval",
                "target_op": "flag_submit",
            }
        )
        return EXIT_BLOCKED

    # Scope check: look up the challenge's remote_endpoint + scope row.
    try:
        _db = _load_db()
        conn = _db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.remote_endpoint, c.scope_id, s.target_urls,
                           s.expires_at, s.name AS scope_name
                      FROM ctf_challenges c
                      JOIN ctf_events e ON e.id = c.event_id
                      LEFT JOIN ctf_scopes s ON s.id = c.scope_id
                     WHERE e.slug = %s AND c.slug = %s
                     LIMIT 1
                    """,
                    (args.event, args.challenge),
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "command": "ctf flag submit",
                "side_effect": se.value,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return EXIT_RUNTIME

    if row is None:
        _emit(
            {
                "ok": False,
                "command": "ctf flag submit",
                "side_effect": se.value,
                "error": f"no challenge ({args.event!r}, {args.challenge!r})",
            }
        )
        return EXIT_RUNTIME

    endpoint = row.get("remote_endpoint")
    scope_row = dict(row)
    if not endpoint or not _scope_covers_url(scope_row, endpoint):
        _emit(
            {
                "ok": False,
                "command": "ctf flag submit",
                "side_effect": se.value,
                "error": "scope does not cover remote_endpoint or has expired",
                "scope_name": scope_row.get("scope_name"),
                "target_op": "flag_submit",
            }
        )
        return EXIT_BLOCKED

    # T003 STOPS HERE. The actual POST + ctf_attempts row write belongs
    # to T007's one-shot live submission. Surface the gate-passed
    # envelope so callers can confirm wiring without exfiltration.
    _emit(
        {
            "ok": True,
            "command": "ctf flag submit",
            "side_effect": se.value,
            "dispatched": False,
            "event_slug": args.event,
            "challenge_slug": args.challenge,
            "target_op": "flag_submit",
            "note": "T003 stub — live POST owned by T007",
        }
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Subparser registration
# ---------------------------------------------------------------------------


def add_parsers(sub: argparse._SubParsersAction) -> None:
    ctf = sub.add_parser(
        "ctf",
        help="Authorized CTF / lab workflow (event / challenge / scope / solver / flag). See COMMANDS.md.",
    )
    ctf_sub = ctf.add_subparsers(dest="ctf_cmd", required=True)

    # event ---------------------------------------------------------------
    p_event = ctf_sub.add_parser("event", help="Event (CTF round) lifecycle (LOCAL_WRITE / READ_ONLY)")
    event_sub = p_event.add_subparsers(dest="event_cmd", required=True)

    p_ev_reg = event_sub.add_parser(
        "register",
        help="Register a CTF event row (LOCAL_WRITE, idempotent on --slug).",
    )
    p_ev_reg.add_argument("--slug", required=True)
    p_ev_reg.add_argument("--name", required=True)
    p_ev_reg.add_argument("--ctftime-id", dest="ctftime_id", type=int, default=None)
    p_ev_reg.add_argument("--url", default=None, help="Event homepage URL")
    p_ev_reg.add_argument("--start-at", dest="start_at", default=None)
    p_ev_reg.add_argument("--end-at", dest="end_at", default=None)
    p_ev_reg.add_argument(
        "--credentials-ref",
        dest="credentials_ref",
        default=None,
        help="Path hint (e.g. ~/.ctf/<slug>.json) — never the credential value.",
    )
    p_ev_reg.add_argument("--json", action="store_true")
    p_ev_reg.set_defaults(func=cmd_event_register)

    p_ev_list = event_sub.add_parser("list", help="List registered CTF events (READ_ONLY).")
    p_ev_list.add_argument("--project", default=None)
    p_ev_list.add_argument("--json", action="store_true")
    p_ev_list.set_defaults(func=cmd_event_list)

    p_ev_info = event_sub.add_parser("info", help="Show one CTF event row (READ_ONLY).")
    p_ev_info.add_argument("--slug", required=True)
    p_ev_info.add_argument("--json", action="store_true")
    p_ev_info.set_defaults(func=cmd_event_info)

    # challenge -----------------------------------------------------------
    p_chal = ctf_sub.add_parser(
        "challenge",
        help="Challenge lifecycle (LOCAL_WRITE for add; REMOTE_WRITE for fetch).",
    )
    chal_sub = p_chal.add_subparsers(dest="challenge_cmd", required=True)

    p_chal_add = chal_sub.add_parser("add", help="Add a challenge to a registered event (LOCAL_WRITE).")
    p_chal_add.add_argument("--event", required=True)
    p_chal_add.add_argument("--slug", required=True)
    p_chal_add.add_argument("--name", required=True)
    p_chal_add.add_argument(
        "--category",
        required=True,
        choices=["web", "crypto", "rev", "pwn", "forensics", "osint", "misc"],
    )
    p_chal_add.add_argument("--points", type=int, default=None)
    p_chal_add.add_argument("--description", default=None)
    p_chal_add.add_argument("--expected-flag-format", dest="expected_flag_format", default=None)
    p_chal_add.add_argument("--attachments-path", dest="attachments_path", default=None)
    p_chal_add.add_argument("--remote-endpoint", dest="remote_endpoint", default=None)
    p_chal_add.add_argument(
        "--scope",
        default=None,
        help="Name of an existing ctf_scopes row to attach.",
    )
    p_chal_add.add_argument("--json", action="store_true")
    p_chal_add.set_defaults(func=cmd_challenge_add)

    p_chal_fetch = chal_sub.add_parser(
        "fetch",
        help="Fetch challenge attachments / endpoint snapshot "
        "(REMOTE_WRITE; requires KCA_ALLOW_REMOTE=1 + scope match).",
    )
    p_chal_fetch.add_argument("--event", required=True)
    p_chal_fetch.add_argument("--slug", required=True)
    p_chal_fetch.add_argument("--via", choices=["http", "playwright"], default="http")
    p_chal_fetch.add_argument("--json", action="store_true")
    p_chal_fetch.set_defaults(func=cmd_challenge_fetch)

    p_chal_list = chal_sub.add_parser("list", help="List challenges for an event (READ_ONLY).")
    p_chal_list.add_argument("--event", required=True)
    p_chal_list.add_argument("--json", action="store_true")
    p_chal_list.set_defaults(func=cmd_challenge_list)

    p_chal_info = chal_sub.add_parser("info", help="Show one challenge row (READ_ONLY).")
    p_chal_info.add_argument("--event", required=True)
    p_chal_info.add_argument("--slug", required=True)
    p_chal_info.add_argument("--json", action="store_true")
    p_chal_info.set_defaults(func=cmd_challenge_info)

    # scope ---------------------------------------------------------------
    p_scope = ctf_sub.add_parser(
        "scope",
        help="ctf_scopes authorization rows (LOCAL_WRITE / READ_ONLY).",
    )
    scope_sub = p_scope.add_subparsers(dest="scope_cmd", required=True)

    p_scope_set = scope_sub.add_parser("set", help="Insert or update a ctf_scopes row (LOCAL_WRITE).")
    p_scope_set.add_argument("--slug", required=True, help="Scope name (unique-ish).")
    p_scope_set.add_argument("--authorized", required=True)
    p_scope_set.add_argument(
        "--target-urls",
        dest="target_urls",
        required=True,
        help="Comma-separated list of fully-qualified URLs.",
    )
    p_scope_set.add_argument("--local-only", action="store_true", dest="local_only")
    p_scope_set.add_argument("--expires-at", dest="expires_at", default=None)
    p_scope_set.add_argument("--json", action="store_true")
    p_scope_set.set_defaults(func=cmd_scope_set)

    p_scope_list = scope_sub.add_parser("list", help="List ctf_scopes rows (READ_ONLY).")
    p_scope_list.add_argument("--json", action="store_true")
    p_scope_list.set_defaults(func=cmd_scope_list)

    p_scope_verify = scope_sub.add_parser(
        "verify",
        help="Exit 0 iff URL ∈ target_urls AND scope not expired (READ_ONLY).",
    )
    p_scope_verify.add_argument("--slug", required=True)
    p_scope_verify.add_argument("--url", required=True)
    p_scope_verify.add_argument("--json", action="store_true")
    p_scope_verify.set_defaults(func=cmd_scope_verify)

    # solver --------------------------------------------------------------
    p_solver = ctf_sub.add_parser(
        "solver",
        help="Solver lifecycle. --dry-run is LOCAL_WRITE; otherwise "
        "SUBMISSION-class via the worker's challenge_run target_op.",
    )
    solver_sub = p_solver.add_subparsers(dest="solver_cmd", required=True)

    p_solver_run = solver_sub.add_parser(
        "run",
        help="Run a solver against (event, challenge). --dry-run skips the "
        "reviewer gate; --reviewer-gate makes the challenge_run gate fire.",
    )
    p_solver_run.add_argument("--event", required=True)
    p_solver_run.add_argument("--challenge", required=True)
    p_solver_run.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_solver_run.add_argument(
        "--reviewer-gate",
        dest="reviewer_gate",
        action="store_true",
        help="Force the challenge_run reviewer gate (T006 wiring).",
    )
    p_solver_run.add_argument("--json", action="store_true")
    p_solver_run.set_defaults(func=cmd_solver_run)

    # flag ----------------------------------------------------------------
    p_flag = ctf_sub.add_parser(
        "flag",
        help="Flag submission. --dry-run is LOCAL_WRITE; otherwise SUBMISSION.",
    )
    flag_sub = p_flag.add_subparsers(dest="flag_cmd", required=True)

    p_flag_submit = flag_sub.add_parser(
        "submit",
        help="Submit a flag for a challenge. Flag is read from --flag-file "
        "and NEVER echoed. --dry-run skips the network call.",
    )
    p_flag_submit.add_argument("--event", required=True)
    p_flag_submit.add_argument("--challenge", required=True)
    p_flag_submit.add_argument(
        "--flag-file",
        dest="flag_file",
        required=True,
        help="Path to a file containing the flag string. Never echoed.",
    )
    p_flag_submit.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_flag_submit.add_argument("--json", action="store_true")
    p_flag_submit.set_defaults(func=cmd_flag_submit)


__all__ = [
    "add_parsers",
    "cmd_event_register",
    "cmd_event_list",
    "cmd_event_info",
    "cmd_challenge_add",
    "cmd_challenge_fetch",
    "cmd_challenge_list",
    "cmd_challenge_info",
    "cmd_scope_set",
    "cmd_scope_list",
    "cmd_scope_verify",
    "cmd_solver_run",
    "cmd_flag_submit",
    "_load_event_credentials",
    "_safe_cred_presence",
    "_scope_covers_url",
    "CredentialsMissing",
]
