"""kca notify: long-run notification / HITL channel (issue #197).

Decision (#197, owner comment 5679417228): **the Telegram bot is the primary
push channel; GitHub stays the system of record.** A decision request writes the
GitHub comment first — that comment is the attributable, timestamped record
carrying `decision_id`, competition, plan summary, `plan_hash`, options and
expiry — and the Telegram card is a compact mirror linking back to it. If
Telegram is down the record still exists; if GitHub is down we do not pretend a
decision was recorded.

Phase 1a (this module) is the **send + parse** half:

* ``kca notify doctor``   — preflight the channel without printing any secret;
* ``kca notify send``     — push a levelled message (gate / digest / info);
* ``kca notify decision`` — open a decision request on both channels;
* :func:`parse_decision_reply` / :func:`resolve_reply` — the deterministic reply
  contract the phase-1b poller calls (an option id, never free-text inference).

Rules that bind every send (#185 §9 / §18):

* no secret, token or private competition payload in a notification body —
  everything transmitted goes through :func:`redact`;
* **no reply is never consent** — a lapsed decision resolves to ``EXPIRED``,
  never to "proceed";
* routine (non-gate) traffic is deduped, capped per day and deferred out of
  quiet hours; a ``gate`` may break quiet hours because work is blocked on it.

Secrets: the bot token and chat ids are read from the process environment, and
otherwise from the ``secrets_file`` named in ``.kca/notify.yml`` — of which only
``TELEGRAM_*`` keys are ever loaded, and no command ever prints a value.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from _types import EXIT_BLOCKED, EXIT_OK, EXIT_RUNTIME, SideEffect
from stuck import redact_escalation_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / ".kca" / "notify.yml"

LEVELS = ("gate", "digest", "info")
ROUTINE_LEVELS = ("digest", "info")
QUIET_HOURS_POLICIES = ("bypass", "defer")
ENV_PREFIX_ALLOWLIST = ("TELEGRAM_",)
CALLBACK_DATA_MAX_BYTES = 64  # Telegram Bot API hard limit on callback_data
RECORD_MARKER = "<!-- kca-decision:v1 -->"
REDACTED = "[REDACTED]"

# A Telegram bot token is `<bot_id>:<35-char secret>`. stuck.py's shared filter
# does not know that shape, so notify masks it first and then delegates.
_TELEGRAM_TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}")

# Deterministic reply contract. The answer is an option id on a `/decide` line;
# anything after it is recorded as context but never parsed as the decision.
_REPLY_RE = re.compile(
    r"^\s*/decide\s+(?P<decision_id>[A-Za-z0-9._:-]{1,64})\s+(?P<option_id>[A-Za-z0-9_-]{1,32})\s*(?P<note>.*)$"
)


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


def redact(text: Any) -> str:
    """Mask secret-shaped substrings in anything we are about to transmit."""
    scrubbed = _TELEGRAM_TOKEN_RE.sub(REDACTED, str(text))
    return str(redact_escalation_payload(scrubbed))


# ---------------------------------------------------------------------------
# Config + secrets
# ---------------------------------------------------------------------------


def _expand(path_str: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(path_str))))


def _parse_hhmm(text: str) -> dt.time:
    hh, _, mm = str(text).partition(":")
    return dt.time(hour=int(hh), minute=int(mm or 0))


def validate_config(cfg: dict[str, Any]) -> None:
    """Raise ValueError on a config that would fail at send time."""
    if int(cfg.get("version") or 0) != 1:
        raise ValueError("notify config: unsupported version (expected 1)")

    channels = cfg.get("channels") or {}
    if not channels:
        raise ValueError("notify config: no channels defined")

    levels = cfg.get("levels") or {}
    for level in LEVELS:
        spec = levels.get(level)
        if not spec:
            raise ValueError(f"notify config: levels.{level} is missing")
        names = list(spec.get("channels") or [])
        if not names:
            raise ValueError(f"notify config: levels.{level}.channels is empty")
        unknown = [n for n in names if n not in channels]
        if unknown:
            raise ValueError(f"notify config: levels.{level} references unknown channel(s) {unknown}")
        if spec.get("quiet_hours") not in QUIET_HOURS_POLICIES:
            raise ValueError(f"notify config: levels.{level}.quiet_hours must be one of {QUIET_HOURS_POLICIES}")

    telegram = channels.get("telegram") or {}
    if telegram.get("enabled") and not telegram.get("token_env"):
        raise ValueError("notify config: channels.telegram.token_env is required when telegram is enabled")
    if telegram.get("enabled") and not (telegram.get("recipients") or {}):
        raise ValueError("notify config: channels.telegram.recipients is empty")

    github = channels.get("github") or {}
    if github.get("enabled") and not github.get("repo"):
        raise ValueError("notify config: channels.github.repo is required when github is enabled")

    quiet = cfg.get("quiet_hours") or {}
    for key in ("timezone", "start", "end"):
        if key not in quiet:
            raise ValueError(f"notify config: quiet_hours.{key} is required")
    ZoneInfo(str(quiet["timezone"]))
    _parse_hhmm(quiet["start"])
    _parse_hhmm(quiet["end"])


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"notify config not found: {cfg_path}")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    validate_config(cfg)
    cfg["_path"] = str(cfg_path)
    return cfg


def load_env_file(path: Path, prefixes: tuple[str, ...] = ENV_PREFIX_ALLOWLIST) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines, keeping **only** allowlisted prefixes.

    The file named by ``secrets_file`` may hold unrelated credentials, so keys
    outside ``prefixes`` are never loaded, returned or logged. (The Claude Code
    guard hook separately denies the agent reading that file directly — this
    loader runs inside the notify process, which needs the value to send.)
    """
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key.startswith(prefixes):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def resolve_secret(name: str, cfg: dict[str, Any]) -> str | None:
    """Return a secret VALUE for internal use. Never print the result."""
    if not name:
        return None
    from_env = os.environ.get(name)
    if from_env:
        return from_env
    secrets_file = cfg.get("secrets_file")
    if not secrets_file:
        return None
    return load_env_file(_expand(str(secrets_file))).get(name) or None


def resolve_recipient(cfg: dict[str, Any], name: str | None = None) -> tuple[str, dict[str, Any]]:
    recipients: dict[str, Any] = ((cfg.get("channels") or {}).get("telegram") or {}).get("recipients") or {}
    if name:
        if name not in recipients:
            raise KeyError(f"unknown telegram recipient {name!r}; known: {sorted(recipients)}")
        return name, recipients[name]
    for key, spec in recipients.items():
        if spec.get("default"):
            return key, spec
    if len(recipients) == 1:
        return next(iter(recipients.items()))
    raise KeyError("no default telegram recipient configured; pass --recipient")


# ---------------------------------------------------------------------------
# Quiet hours
# ---------------------------------------------------------------------------


def _tz(cfg: dict[str, Any]) -> ZoneInfo:
    return ZoneInfo(str((cfg.get("quiet_hours") or {}).get("timezone") or "UTC"))


def _now(cfg: dict[str, Any], now: dt.datetime | None = None) -> dt.datetime:
    tz = _tz(cfg)
    if now is None:
        return dt.datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def in_quiet_hours(cfg: dict[str, Any], now: dt.datetime | None = None) -> bool:
    quiet = cfg.get("quiet_hours") or {}
    start, end = _parse_hhmm(quiet["start"]), _parse_hhmm(quiet["end"])
    local = _now(cfg, now).timetz().replace(tzinfo=None)
    if start == end:
        return False
    if start < end:  # same-day window, e.g. 01:00-06:00
        return start <= local < end
    return local >= start or local < end  # wraps midnight, e.g. 22:00-08:00


def next_send_window(cfg: dict[str, Any], now: dt.datetime | None = None) -> dt.datetime:
    """The first instant at/after ``now`` that is outside quiet hours."""
    local = _now(cfg, now)
    if not in_quiet_hours(cfg, local):
        return local
    end = _parse_hhmm((cfg.get("quiet_hours") or {})["end"])
    candidate = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate <= local:
        candidate += dt.timedelta(days=1)
    return candidate


# ---------------------------------------------------------------------------
# Send ledger (dedupe + daily cap). Lives under a gitignored state dir.
# ---------------------------------------------------------------------------


def state_dir(cfg: dict[str, Any]) -> Path:
    raw = str(cfg.get("state_dir") or ".agent/notify")
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def ledger_path(cfg: dict[str, Any]) -> Path:
    return state_dir(cfg) / "sent.jsonl"


def dedupe_key(level: str, title: str, body: str) -> str:
    digest = hashlib.sha256(f"{level}\x00{title}\x00{body}".encode()).hexdigest()
    return digest[:16]


def read_ledger(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = ledger_path(cfg)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def append_ledger(cfg: dict[str, Any], entry: dict[str, Any]) -> None:
    path = ledger_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _parse_ts(value: Any) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def recent_duplicate(
    entries: list[dict[str, Any]], key: str, window_minutes: int, now: dt.datetime
) -> dict[str, Any] | None:
    if window_minutes <= 0:
        return None
    cutoff = now - dt.timedelta(minutes=window_minutes)
    for entry in reversed(entries):
        if entry.get("key") != key or entry.get("status") != "sent":
            continue
        ts = _parse_ts(entry.get("ts"))
        if ts and ts >= cutoff:
            return entry
    return None


def routine_sends_today(cfg: dict[str, Any], entries: list[dict[str, Any]], now: dt.datetime) -> int:
    today = _now(cfg, now).date()
    count = 0
    for entry in entries:
        if entry.get("level") not in ROUTINE_LEVELS or entry.get("status") != "sent":
            continue
        ts = _parse_ts(entry.get("ts"))
        if ts and ts.astimezone(_tz(cfg)).date() == today:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Decision request rendering
# ---------------------------------------------------------------------------


@dataclass
class DecisionRequest:
    """A blocking question for the human, in the #197 record format."""

    decision_id: str
    competition: str
    summary: str
    options: list[tuple[str, str]]
    expires_at: str
    plan_hash: str = ""
    issue: int | None = None
    account: str = ""
    links: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id is required")
        if len(self.options) < 2:
            raise ValueError("a decision request needs at least 2 options")
        ids = [opt_id for opt_id, _ in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate option ids: {ids}")
        if not self.plan_hash:
            self.plan_hash = hashlib.sha256(self.summary.encode()).hexdigest()[:12]
        if _parse_ts(self.expires_at) is None:
            raise ValueError(f"expires_at is not ISO-8601: {self.expires_at!r}")
        for opt_id in ids:
            data = callback_data(self.decision_id, opt_id)
            if len(data.encode()) > CALLBACK_DATA_MAX_BYTES:
                raise ValueError(f"callback_data too long for Telegram ({data!r} > {CALLBACK_DATA_MAX_BYTES}B)")

    def issue_url(self, cfg: dict[str, Any]) -> str:
        repo = ((cfg.get("channels") or {}).get("github") or {}).get("repo") or ""
        return f"https://github.com/{repo}/issues/{self.issue}" if (repo and self.issue) else ""


def callback_data(decision_id: str, option_id: str) -> str:
    return f"kca:{decision_id}:{option_id}"


def render_github_comment(req: DecisionRequest) -> str:
    """The durable record. Everything a reader needs to attribute the answer."""
    rows = [
        ("competition", req.competition or "—"),
        ("decision_id", f"`{req.decision_id}`"),
        ("plan_hash", f"`{req.plan_hash}`"),
        ("account", req.account or "—"),
        ("expires_at", req.expires_at),
    ]
    table = "\n".join(f"| {name} | {redact(value)} |" for name, value in rows)
    options = "\n".join(f"- `{opt_id}` — {redact(label)}" for opt_id, label in req.options)
    links = "\n".join(f"- {redact(link)}" for link in req.links)
    machine = yaml.safe_dump(
        {
            "decision_id": req.decision_id,
            "competition": req.competition,
            "plan_hash": req.plan_hash,
            "expires_at": req.expires_at,
            "options": [opt_id for opt_id, _ in req.options],
        },
        sort_keys=False,
        allow_unicode=True,
    ).strip()

    body = [
        RECORD_MARKER,
        f"## 🔔 Decision request — `{req.decision_id}`",
        "",
        "| field | value |",
        "| --- | --- |",
        table,
        "",
        "**Plan summary**",
        "",
        redact(req.summary),
        "",
        "**Options**",
        "",
        options,
        "",
        "**How to answer** — deterministic, an option id (never free-text inference):",
        "",
        "```",
        f"/decide {req.decision_id} <option_id>",
        "```",
        "",
        "Put that on its own line in a comment on this issue; anything after the option id is "
        "recorded as context but is never parsed as the answer. Tapping a button in the Telegram "
        "card posts the same line back here.",
        "",
        f"⏳ **No reply is not consent.** After `{req.expires_at}` this request lapses to "
        "`WAIT_HUMAN` — it never auto-approves.",
    ]
    if links:
        body += ["", "**Links**", "", links]
    body += ["", "```yaml", machine, "```"]
    return "\n".join(body)


def _tg_escape(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_telegram_text(req: DecisionRequest, cfg: dict[str, Any]) -> str:
    """The compact push card. Detail lives in the GitHub record it links to."""
    summary = redact(req.summary)
    if len(summary) > 500:
        summary = summary[:497] + "…"
    lines = [
        f"🔔 <b>Decision</b> — <code>{_tg_escape(req.decision_id)}</code>",
        f"🏁 {_tg_escape(redact(req.competition) or '—')}",
        f"#️⃣ plan <code>{_tg_escape(req.plan_hash)}</code>",
        "",
        _tg_escape(summary),
        "",
        "".join(["⏳ expires ", _tg_escape(req.expires_at), " — no reply ≠ approval"]),
    ]
    url = req.issue_url(cfg)
    if url:
        lines += ["", f'📎 <a href="{_tg_escape(url)}">record on GitHub</a>']
    return "\n".join(lines)


def build_keyboard(req: DecisionRequest, cfg: dict[str, Any]) -> dict[str, Any]:
    buttons = [
        [{"text": label, "callback_data": callback_data(req.decision_id, opt_id)}] for opt_id, label in req.options
    ]
    url = req.issue_url(cfg)
    if url:
        buttons.append([{"text": "Open issue", "url": url}])
    return {"inline_keyboard": buttons}


# ---------------------------------------------------------------------------
# Reply contract (used by the phase-1b poller and by `kca notify resolve`)
# ---------------------------------------------------------------------------


def parse_decision_reply(text: str) -> dict[str, str] | None:
    """Parse the first ``/decide <decision_id> <option_id>`` line, or None.

    Deterministic by construction: prose that merely *sounds* like approval
    ("yes", "go ahead", "A") never parses. Absence of a match means WAIT_HUMAN.
    """
    for line in (text or "").splitlines():
        match = _REPLY_RE.match(line)
        if match:
            return {
                "decision_id": match.group("decision_id"),
                "option_id": match.group("option_id"),
                "note": match.group("note").strip(),
            }
    return None


def resolve_reply(
    req: DecisionRequest | dict[str, Any],
    reply_text: str,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Decide what a reply means. ``approved`` is true only for ANSWERED.

    Statuses: ANSWERED | EXPIRED | INVALID_OPTION | MISMATCHED_DECISION |
    WAIT_HUMAN (no parsable reply). Expiry is checked before the option, so a
    late answer never resolves a lapsed request.
    """
    if isinstance(req, DecisionRequest):
        decision_id, expires_at = req.decision_id, req.expires_at
        option_ids = [opt_id for opt_id, _ in req.options]
    else:
        decision_id = str(req.get("decision_id") or "")
        expires_at = str(req.get("expires_at") or "")
        option_ids = [str(o) for o in (req.get("options") or [])]

    parsed = parse_decision_reply(reply_text)
    moment = now or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    deadline = _parse_ts(expires_at)
    expired = bool(deadline and moment > deadline)

    if parsed is None:
        status = "EXPIRED" if expired else "WAIT_HUMAN"
        return {"status": status, "approved": False, "option_id": None, "decision_id": decision_id, "note": ""}
    if expired:
        return {
            "status": "EXPIRED",
            "approved": False,
            "option_id": None,
            "decision_id": decision_id,
            "note": parsed["note"],
        }
    if parsed["decision_id"] != decision_id:
        return {
            "status": "MISMATCHED_DECISION",
            "approved": False,
            "option_id": None,
            "decision_id": parsed["decision_id"],
            "note": parsed["note"],
        }
    if parsed["option_id"] not in option_ids:
        return {
            "status": "INVALID_OPTION",
            "approved": False,
            "option_id": parsed["option_id"],
            "decision_id": decision_id,
            "note": parsed["note"],
        }
    return {
        "status": "ANSWERED",
        "approved": True,
        "option_id": parsed["option_id"],
        "decision_id": decision_id,
        "note": parsed["note"],
    }


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------


def _telegram_api(cfg: dict[str, Any], method: str) -> tuple[str, str]:
    telegram = (cfg.get("channels") or {}).get("telegram") or {}
    token = resolve_secret(str(telegram.get("token_env") or ""), cfg)
    if not token:
        raise RuntimeError(f"{telegram.get('token_env')} is not set (see docs/tooling/notification-channel.md)")
    base = str(telegram.get("api_base") or "https://api.telegram.org").rstrip("/")
    return f"{base}/bot{token}/{method}", token


def telegram_call(cfg: dict[str, Any], method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST to the Bot API. The token never appears in the returned payload."""
    import requests

    url, token = _telegram_api(cfg, method)
    timeout = int(((cfg.get("channels") or {}).get("telegram") or {}).get("timeout_s") or 15)
    try:
        response = requests.post(url, json=payload or {}, timeout=timeout)
        data = response.json()
    except Exception as exc:  # network error, non-JSON body
        return {"ok": False, "error": redact(str(exc).replace(token, REDACTED))}
    if not data.get("ok"):
        return {"ok": False, "error": redact(str(data.get("description") or data))}
    return {"ok": True, "result": data.get("result")}


def send_telegram(
    cfg: dict[str, Any],
    *,
    text: str,
    keyboard: dict[str, Any] | None = None,
    recipient: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    name, spec = resolve_recipient(cfg, recipient)
    chat_env = str(spec.get("chat_id_env") or "")
    chat_id = resolve_secret(chat_env, cfg)
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = keyboard
    if dry_run:
        # A dry run renders the card without credentials on purpose — it is how
        # a message is reviewed before the bot exists. `chat_id_configured`
        # still reports whether a real send would have found a chat id.
        preview = dict(payload, chat_id=f"<{chat_env}>")
        return {
            "ok": True,
            "channel": "telegram",
            "recipient": name,
            "dry_run": True,
            "chat_id_configured": bool(chat_id),
            "payload": preview,
        }
    if not chat_id:
        return {"ok": False, "channel": "telegram", "recipient": name, "error": f"{chat_env} is not set"}
    result = telegram_call(cfg, "sendMessage", payload)
    if not result.get("ok"):
        return {"ok": False, "channel": "telegram", "recipient": name, "error": result.get("error")}
    return {
        "ok": True,
        "channel": "telegram",
        "recipient": name,
        "message_id": (result.get("result") or {}).get("message_id"),
    }


def post_github_comment(cfg: dict[str, Any], *, issue: int, body: str, dry_run: bool = False) -> dict[str, Any]:
    repo = ((cfg.get("channels") or {}).get("github") or {}).get("repo") or ""
    if dry_run:
        return {"ok": True, "channel": "github", "dry_run": True, "issue": issue, "repo": repo, "body": body}
    cmd = ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"]
    try:
        proc = subprocess.run(cmd, input=body, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "channel": "github", "error": redact(str(exc))}
    if proc.returncode != 0:
        return {"ok": False, "channel": "github", "error": redact((proc.stderr or proc.stdout).strip())}
    return {"ok": True, "channel": "github", "issue": issue, "url": (proc.stdout or "").strip()}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch(
    cfg: dict[str, Any],
    *,
    level: str,
    title: str,
    body: str,
    issue: int | None = None,
    recipient: str | None = None,
    github_body: str | None = None,
    telegram_text: str | None = None,
    telegram_keyboard: dict[str, Any] | None = None,
    dry_run: bool = False,
    force: bool = False,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Route one message. Returns ``{"ok", "status", "channels", ...}``.

    ``status`` is ``sent`` | ``deduped`` | ``deferred`` | ``rate_limited`` |
    ``failed``. Suppression is a *successful* outcome — it is the #185 §18
    intervention budget working, not an error.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {LEVELS}")
    spec = (cfg.get("levels") or {})[level]
    moment = _now(cfg, now)
    title, body = redact(title), redact(body)
    key = dedupe_key(level, title, body)
    entries = read_ledger(cfg)

    def _record(status: str, detail: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "ts": moment.isoformat(),
            "level": level,
            "key": key,
            "title": title[:120],
            "status": status,
            "issue": issue,
            "dry_run": dry_run,
        }
        if not dry_run:
            append_ledger(cfg, entry)
        return {"ok": status != "failed", "status": status, "level": level, "key": key, **detail}

    if not force:
        duplicate = recent_duplicate(entries, key, int(spec.get("dedupe_minutes") or 0), moment)
        if duplicate:
            return _record("deduped", {"reason": f"identical {level} sent at {duplicate.get('ts')}", "channels": []})

        if level in ROUTINE_LEVELS:
            cap = int((cfg.get("limits") or {}).get("routine_pushes_per_day") or 0)
            used = routine_sends_today(cfg, entries, moment)
            if cap and used >= cap:
                return _record(
                    "rate_limited",
                    {"reason": f"routine push budget spent ({used}/{cap} today)", "channels": []},
                )

        if spec.get("quiet_hours") == "defer" and in_quiet_hours(cfg, moment):
            return _record(
                "deferred",
                {
                    "reason": "quiet hours",
                    "retry_after": next_send_window(cfg, moment).isoformat(),
                    "channels": [],
                },
            )

    results: list[dict[str, Any]] = []
    for channel in spec.get("channels") or []:
        channel_cfg = (cfg.get("channels") or {}).get(channel) or {}
        if not channel_cfg.get("enabled"):
            results.append({"ok": True, "channel": channel, "skipped": "disabled"})
            continue
        if channel == "github":
            if not issue:
                results.append({"ok": False, "channel": "github", "error": "no --issue given; record not written"})
                continue
            record = github_body or f"**{title}**\n\n{body}"
            results.append(post_github_comment(cfg, issue=issue, body=record, dry_run=dry_run))
        elif channel == "telegram":
            text = telegram_text or f"<b>{_tg_escape(title)}</b>\n\n{_tg_escape(body)}"
            results.append(
                send_telegram(cfg, text=text, keyboard=telegram_keyboard, recipient=recipient, dry_run=dry_run)
            )
        else:
            results.append({"ok": False, "channel": channel, "error": "no transport implemented"})

    status = "sent" if any(r.get("ok") for r in results) else "failed"
    return _record(status, {"channels": results})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def exit_code_for(result: dict[str, Any]) -> int:
    """`sent` -> 0, suppressed (deduped / deferred / rate_limited) -> 2, failed -> 1.

    Suppression is a policy decision, not a fault: a caller retrying on exit 2
    would be fighting the intervention budget, whereas exit 1 means the message
    genuinely did not get out and is worth retrying.
    """
    status = result.get("status")
    if status == "sent":
        return EXIT_OK
    return EXIT_RUNTIME if status == "failed" else EXIT_BLOCKED


def _emit(
    payload: dict[str, Any],
    exit_code: int = EXIT_OK,
    side_effect: SideEffect = SideEffect.REMOTE_WRITE,
) -> int:
    """Emit one JSON object. The group registers as REMOTE_WRITE (its ceiling);
    each command reports what it actually did, so `doctor` says READ_ONLY."""
    print(json.dumps({"side_effect": side_effect.value, **payload}, ensure_ascii=False, indent=2))
    return exit_code


def cmd_doctor(args: argparse.Namespace) -> int:
    """Preflight every prerequisite. Reports presence, never values."""
    checks: list[dict[str, Any]] = []
    try:
        cfg = load_config(args.config)
    except Exception as exc:
        return _emit(
            {"ok": False, "checks": [{"name": "config", "ok": False, "detail": str(exc)}]},
            EXIT_RUNTIME,
            SideEffect.READ_ONLY,
        )
    checks.append({"name": "config", "ok": True, "detail": cfg["_path"]})

    telegram = (cfg.get("channels") or {}).get("telegram") or {}
    token_env = str(telegram.get("token_env") or "")
    token = resolve_secret(token_env, cfg)
    checks.append({"name": f"{token_env} present", "ok": bool(token), "detail": "set" if token else "MISSING"})

    for name, spec in (telegram.get("recipients") or {}).items():
        chat_env = str(spec.get("chat_id_env") or "")
        chat_id = resolve_secret(chat_env, cfg)
        checks.append(
            {
                "name": f"recipient {name}: {chat_env}",
                "ok": bool(chat_id),
                "detail": "set" if chat_id else "MISSING",
            }
        )

    if token and not args.offline:
        me = telegram_call(cfg, "getMe")
        username = (me.get("result") or {}).get("username") if me.get("ok") else None
        checks.append(
            {
                "name": "telegram getMe",
                "ok": bool(me.get("ok")),
                "detail": f"@{username}" if username else str(me.get("error")),
            }
        )

    if ((cfg.get("channels") or {}).get("github") or {}).get("enabled"):
        try:
            proc = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=30, check=False)
            checks.append(
                {
                    "name": "gh auth",
                    "ok": proc.returncode == 0,
                    "detail": "logged in" if proc.returncode == 0 else "not logged in",
                }
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append({"name": "gh auth", "ok": False, "detail": redact(str(exc))})

    moment = _now(cfg)
    entries = read_ledger(cfg)
    cap = int((cfg.get("limits") or {}).get("routine_pushes_per_day") or 0)
    ok = all(c["ok"] for c in checks)
    return _emit(
        {
            "ok": ok,
            "checks": checks,
            "quiet_hours_now": in_quiet_hours(cfg, moment),
            "local_time": moment.isoformat(),
            "routine_budget": f"{routine_sends_today(cfg, entries, moment)}/{cap} used today",
        },
        EXIT_OK if ok else EXIT_RUNTIME,
        SideEffect.READ_ONLY,
    )


def cmd_send(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
        result = dispatch(
            cfg,
            level=args.level,
            title=args.title,
            body=args.body,
            issue=args.issue,
            recipient=args.recipient,
            dry_run=args.dry_run,
            force=args.force,
        )
    except Exception as exc:
        return _emit({"ok": False, "error": redact(str(exc))}, EXIT_RUNTIME)
    return _emit(result, exit_code_for(result))


def cmd_decision(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
        options = []
        for raw in args.option:
            opt_id, _, label = str(raw).partition("=")
            options.append((opt_id.strip(), (label or opt_id).strip()))
        req = DecisionRequest(
            decision_id=args.decision_id,
            competition=args.competition,
            summary=args.summary,
            options=options,
            expires_at=args.expires_at,
            plan_hash=args.plan_hash or "",
            issue=args.issue,
            account=args.account or "",
            links=list(args.link or []),
        )
        result = dispatch(
            cfg,
            level="gate",
            title=f"Decision {req.decision_id} — {req.competition}",
            body=req.summary,
            issue=args.issue,
            recipient=args.recipient,
            github_body=render_github_comment(req),
            telegram_text=render_telegram_text(req, cfg),
            telegram_keyboard=build_keyboard(req, cfg),
            dry_run=args.dry_run,
            force=args.force,
        )
        payload = {**result, "decision_id": req.decision_id, "plan_hash": req.plan_hash}
        return _emit(payload, exit_code_for(result))
    except Exception as exc:
        return _emit({"ok": False, "error": redact(str(exc))}, EXIT_RUNTIME)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    group = sub.add_parser("notify", help="Long-run notification / HITL channel (Telegram push + GitHub record)")
    group_sub = group.add_subparsers(dest="notify_cmd", required=True)

    def _common(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--config", default=None, help=f"notify config (default: {DEFAULT_CONFIG_PATH})")

    p_doctor = group_sub.add_parser("doctor", help="Preflight the channel; reports presence, never secret values")
    _common(p_doctor)
    p_doctor.add_argument("--offline", action="store_true", help="skip the Telegram getMe round-trip")
    p_doctor.set_defaults(func=cmd_doctor)

    p_send = group_sub.add_parser("send", help="Send a levelled notification")
    _common(p_send)
    p_send.add_argument("--level", choices=LEVELS, default="info")
    p_send.add_argument("--title", required=True)
    p_send.add_argument("--body", required=True)
    p_send.add_argument("--issue", type=int, default=None, help="GitHub issue for the record leg")
    p_send.add_argument("--recipient", default=None)
    p_send.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_send.add_argument("--force", action="store_true", help="ignore dedupe / daily cap / quiet hours")
    p_send.set_defaults(func=cmd_send)

    p_dec = group_sub.add_parser("decision", help="Open a decision request (GitHub record + Telegram card)")
    _common(p_dec)
    p_dec.add_argument("--decision-id", dest="decision_id", required=True)
    p_dec.add_argument("--competition", required=True)
    p_dec.add_argument("--summary", required=True)
    p_dec.add_argument("--option", action="append", required=True, help="id=label (repeat; >= 2 required)")
    p_dec.add_argument("--expires-at", dest="expires_at", required=True, help="ISO-8601 deadline")
    p_dec.add_argument("--plan-hash", dest="plan_hash", default=None)
    p_dec.add_argument("--issue", type=int, required=True, help="tracking issue that holds the record")
    p_dec.add_argument("--account", default=None, help="which agent/Kaggle account this decision is for")
    p_dec.add_argument("--link", action="append", default=[])
    p_dec.add_argument("--recipient", default=None)
    p_dec.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_dec.add_argument("--force", action="store_true")
    p_dec.set_defaults(func=cmd_decision)
