"""kca notify: long-run notification / HITL channel (issue #197).

Decision (#197, owner comment 5679417228): **the Telegram bot is the primary
push channel; GitHub stays the system of record.** A decision request writes the
GitHub comment first — that comment is the attributable, timestamped record
carrying `decision_id`, competition, plan summary, `plan_hash`, options and
expiry — and the Telegram card is a compact mirror linking back to it. If
Telegram is down the record still exists; if GitHub is down we do not pretend a
decision was recorded.

Phase 1a (this module) is the **send + parse** half:

* ``kca notify doctor``   — preflight every bot without printing any secret;
* ``kca notify send``     — push a levelled message
  (gate / attention / digest / info);
* ``kca notify decision`` — open a decision request on both channels;
* :func:`parse_decision_reply` / :func:`resolve_reply` — the deterministic reply
  contract the phase-1b poller calls (an option id, never free-text inference).

The Telegram card is deliberately **read-only** in phase 1a: nothing consumes
`getUpdates` or callback queries yet, so a tappable option button would look
like an answer and resolve nothing. The card spells out the `/decide` line for
each option and links to the record, which is where the answer is given.

Rules that bind every send (#185 §9 / §18):

* no secret, token or private competition payload in a notification body —
  everything transmitted goes through :func:`redact` and is length-bounded;
* **no reply is never consent** — a lapsed decision resolves to ``EXPIRED``,
  never to "proceed";
* routine traffic (``digest`` / ``info``) is deduped, capped per day and
  deferred out of quiet hours; ``gate`` and ``attention`` break quiet hours and
  are never capped, because a human is blocked on them;
* a send is ``sent`` only when *every* configured channel took it — one failed
  leg is ``partial``, which exits non-zero, because a decision with no GitHub
  record is not a decision that was filed.

Bots: one bot per agent entry (discussion #187 §3) — a token has exactly one
active *receiving* process, so Claude Code entry A and entry B cannot share
one. Sending is unaffected, so ``kca notify`` may push through a bot whose
update stream a Claude Code Telegram channel is holding.

Secrets: bot tokens and chat ids are read from the process environment, and
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
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

import yaml

from _types import EXIT_BLOCKED, EXIT_OK, EXIT_RUNTIME, SideEffect
from stuck import redact_escalation_payload

try:  # POSIX only; the ledger lock degrades to best-effort without it.
    import fcntl
except ImportError:  # pragma: no cover - not reachable on Linux/macOS
    fcntl = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / ".kca" / "notify.yml"

LEVELS = ("gate", "attention", "digest", "info")
# Only these count against the daily intervention budget (#185 §18). A `gate`
# or an `attention` ping is a block, not routine traffic.
ROUTINE_LEVELS = ("digest", "info")
# Levels whose contract includes the system-of-record comment: a `gate` is the
# decision record, so its record channel is required rather than optional
# (#206 F002). The others are push-only by design.
RECORD_REQUIRED_LEVELS = ("gate",)
QUIET_HOURS_POLICIES = ("bypass", "defer")
ENV_PREFIX_ALLOWLIST = ("TELEGRAM_",)
CALLBACK_DATA_MAX_BYTES = 64  # Telegram Bot API hard limit on callback_data
RECORD_MARKER = "<!-- kca-decision:v1 -->"
REDACTED = "[REDACTED]"

# Bounded length is part of the no-leak contract: a harness event carries
# whatever the session said, so a runaway body is clipped before it is rendered
# into a push or a record.
MAX_TITLE_CHARS = 200
MAX_BODY_CHARS = 2000
# Telegram rejects a `sendMessage` body over 4096 characters. A decision card is
# assembled from validated ids plus free-text labels, so every free-text part is
# bounded *after HTML escaping* and the card degrades by whole lines — an
# over-long label must not turn a gate into a failed push (#206 F011).
TELEGRAM_MAX_CHARS = 4096
MAX_CARD_FIELD_CHARS = 120
MAX_OPTION_LABEL_CHARS = 120
MAX_CARD_SUMMARY_CHARS = 500
MAX_CARD_URL_CHARS = 400
MAX_RENDERED_OPTIONS = 10
# Any configured secret shorter than this is not masked by value — masking a
# 2-character value would blank out unrelated text for no security gain.
MIN_MASKABLE_SECRET_CHARS = 6

# A `sent` outcome means every attempted channel accepted the message; a
# `partial` means at least one did not, and the caller must treat it as a
# failure (the record leg is not optional — see :func:`dispatch`).
FAILED_STATUSES = ("failed", "partial")
SUPPRESSED_STATUSES = ("deduped", "deferred", "rate_limited")

# Ledger housekeeping. The lock makes the read → decide → append sequence atomic
# across processes and worktrees; the size bound keeps a file that is appended
# to for the life of the project from growing without limit.
LOCK_POLL_S = 0.05
# The lock is held across the transports it serialises, so a ceiling shorter
# than the worst case hold makes the unlocked fallback the *normal* path and the
# daily cap stops being enforced (#206 F003). The default is therefore derived
# from the configured transport timeouts rather than being a flat 10 s;
# `limits.lock_wait_s` overrides it for an operator who knows better.
LOCK_WAIT_MARGIN_S = 10.0
DEFAULT_TELEGRAM_TIMEOUT_S = 15
GITHUB_TIMEOUT_S = 90
LEDGER_MAX_BYTES = 512_000
LEDGER_KEEP_ENTRIES = 1000
# A suppressed send is recorded once per hour per message, not once per hook
# invocation: a spent budget must not turn every later event into a new line.
SUPPRESSION_LOG_MINUTES = 60


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# A Telegram bot token is `<bot_id>:<35-char secret>`. stuck.py's shared filter
# does not know that shape, so notify masks it first and then delegates.
_TELEGRAM_TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}")

# Credential shapes stuck.py does not cover. Every one of them is anchored on a
# vendor prefix or an explicit assignment, never on "this looks like a number":
# silencing a gate or eating the operator's own sentence is a worse outcome than
# the leak it would prevent.
_SECRET_VALUE_RES = (
    _TELEGRAM_TOKEN_RE,
    # OpenAI-style keys, including the project form `sk-proj-…`. `sk-ant-…` is
    # already handled by stuck.py; this generalises it. The long run is
    # deliberately hyphen-free and ≥16 chars: `sk-learn-baseline` is a branch
    # name an operator may well put in a gate, and masking it would eat the
    # reason out of the message (#206 F010).
    re.compile(r"\bsk-(?:[A-Za-z0-9]{1,12}-){0,4}[A-Za-z0-9_]{16,}"),
    # GitHub PATs / OAuth tokens.
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}"),  # Google API key
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),  # Slack
    re.compile(r"\bhf_[A-Za-z0-9]{16,}"),  # Hugging Face
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}"),  # GitLab
    # A JWT / signed session cookie.
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # HTTP auth schemes. `Bearer` alone is not enough: `Basic <base64>` carries
    # user:password, and masking only the scheme word left the payload in the
    # clear (#206 F001).
    re.compile(r"(?i)\b(?:bearer|basic|digest|negotiate|apikey)\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)

# `NAME=value` / `NAME: value` where the NAME itself says "this is a secret".
# The name is kept — it is the half of the message a human needs — and only the
# value is masked, which is how `OPENAI_API_KEY=…` and `CHAT_ID=…` are caught
# without redacting every digit in the body.
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_KEY|CREDENTIAL"
    r"|PRIVATE_KEY|SESSION_KEY|CHAT_ID)[A-Z0-9_]*)(\s*[:=]\s*)"
    r"(\"[^\"\n]*\"|'[^'\n]*'|\S+)"
)

# Names that are ordinary operator reporting rather than credentials.
# `tokens: 1500 remaining` and `max_tokens: 4096` are budget fields, and masking
# them removes the number the human needs (#206 F010). The exemption is an
# *exact* name list, not a "contains a `tokens` component" rule: the component
# rule also exempted `TOKENS_SECRET=…`, `API_TOKENS=…` and `max_tokens_secret=…`,
# which read as credentials and now mask again (#206 F010, round 3).
_OPERATOR_FIELD_NAMES = frozenset(
    {
        "tokens",
        "max_tokens",
        "min_tokens",
        "num_tokens",
        "n_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "max_output_tokens",
        "max_input_tokens",
        "tokens_used",
        "tokens_left",
        "tokens_remaining",
    }
)

# …and the exemption only applies to a value that *is* a budget number. A count
# cannot be an opaque credential, so `max_tokens=4096` survives while
# `max_tokens=sk-live-abcdef` does not (#206 F010, round 3).
_COUNT_VALUE_RE = re.compile(r"""\A["']?[+-]?\d[\d,_]*(?:\.\d+)?["']?\Z""")

# An `Authorization` header value is a credential *in its entirety* — scheme,
# payload and any continuation — so unlike a named assignment it is masked to
# the end of the line rather than one whitespace-delimited token (#206 F001).
_AUTH_HEADER_RE = re.compile(r"(?im)^(.*?\b(?:proxy-)?authorization)(\s*[:=]\s*)(\S.*)$")

# Deterministic reply contract. The answer is an option id on a `/decide` line;
# anything after it is recorded as context but never parsed as the decision.
# The id grammars are shared with :class:`DecisionRequest` validation so a
# decision can never be published in a form its own reply parser rejects.
# The validators anchor with `\A…\Z`, not `^…$`: Python's `$` also matches the
# position before a final newline, so `^…$` accepted `"approval-v2\n"` at
# creation while the line-oriented reply parser split the newline away and could
# never answer it (#206 F005). `\Z` makes creation and parsing one grammar.
DECISION_ID_PATTERN = r"[A-Za-z0-9._:-]{1,64}"
OPTION_ID_PATTERN = r"[A-Za-z0-9_-]{1,32}"
_DECISION_ID_RE = re.compile(rf"\A{DECISION_ID_PATTERN}\Z")
_OPTION_ID_RE = re.compile(rf"\A{OPTION_ID_PATTERN}\Z")
_REPLY_RE = re.compile(
    rf"^\s*/decide\s+(?P<decision_id>{DECISION_ID_PATTERN})\s+(?P<option_id>{OPTION_ID_PATTERN})\s*(?P<note>.*)$"
)


def _configured_secret_values(cfg: dict[str, Any] | None) -> tuple[str, ...]:
    """Our own resolved bot tokens / chat ids, so a body cannot echo one back.

    Shape rules cannot recognise a bare chat id, but we know ours: if the text
    we are about to transmit contains a value this config resolves to, it is
    masked. Values are used, never returned to a caller or printed.
    """
    if not cfg:
        return ()
    telegram = (cfg.get("channels") or {}).get("telegram") or {}
    names = [str((spec or {}).get("token_env") or "") for spec in (telegram.get("bots") or {}).values()]
    names += [str((spec or {}).get("chat_id_env") or "") for spec in (telegram.get("recipients") or {}).values()]
    values = {resolve_secret(name, cfg) or "" for name in names if name}
    return tuple(v for v in values if len(v) >= MIN_MASKABLE_SECRET_CHARS)


def _mask_assignment(match: re.Match[str]) -> str:
    """Mask the value of `SECRET_NAME=value`, unless it is a budget count.

    Both halves of the exemption are required: an exact operator field name *and*
    a numeric value. Either one alone let a credential through (#206 F010).
    """
    name = match.group(1)
    if name.casefold() in _OPERATOR_FIELD_NAMES and _COUNT_VALUE_RE.match(match.group(3)):
        return match.group(0)
    return f"{name}{match.group(2)}{REDACTED}"


def redact(text: Any, cfg: dict[str, Any] | None = None) -> str:
    """Mask secret-shaped substrings in anything we are about to transmit.

    Four layers, cheapest first: known credential shapes, `Authorization:` header
    lines (masked whole), `SECRET_NAME=value` assignments (name kept, value
    masked), and — when ``cfg`` is given — the literal values this config
    resolves to. Everything then goes through the shared
    ``stuck.redact_escalation_payload`` filter (DSNs, AWS ids, flags).

    It masks *credential shapes and credential-named fields*, not "text that
    might be private": arbitrary private competition data has no shape, so the
    defence against that is not this function but the rule that session text is
    never forwarded unless asked for — ``scripts/agent_notify.py`` pushes
    metadata only until ``--content`` is passed (#206 F001/F010).
    """
    scrubbed = str(text)
    for pattern in _SECRET_VALUE_RES:
        scrubbed = pattern.sub(REDACTED, scrubbed)
    scrubbed = _AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", scrubbed)
    scrubbed = _SECRET_ASSIGNMENT_RE.sub(_mask_assignment, scrubbed)
    for value in _configured_secret_values(cfg):
        scrubbed = scrubbed.replace(value, REDACTED)
    return str(redact_escalation_payload(scrubbed))


def clip(text: Any, limit: int) -> str:
    """Bound a transmitted field; an elision is visible, not silent."""
    out = str(text)
    return out if len(out) <= limit else out[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Config + secrets
# ---------------------------------------------------------------------------


def _expand(path_str: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(path_str))))


def _parse_hhmm(text: str) -> dt.time:
    hh, _, mm = str(text).partition(":")
    return dt.time(hour=int(hh), minute=int(mm or 0))


def is_required_channel(level: str, channel: str, cfg: dict[str, Any]) -> bool:
    """Is ``channel`` load-bearing for ``level``, rather than one of its outlets?

    A `gate` is *defined* by its GitHub record — the attributable, timestamped
    comment is the system of record (#197), so the record channel is required
    and turning it off is a configuration error, not a way to send gates over
    Telegram alone. `attention` / `digest` / `info` are push-only by design and
    keep working with any single outlet disabled.
    """
    if level not in RECORD_REQUIRED_LEVELS:
        return False
    channel_cfg = (cfg.get("channels") or {}).get(channel) or {}
    return str(channel_cfg.get("role") or ("record" if channel == "github" else "")) == "record"


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
        # Catch the F002 shape at load time as well as at send time: a level
        # that needs a record cannot route it through a disabled channel.
        off = [n for n in names if is_required_channel(level, n, cfg) and not (channels.get(n) or {}).get("enabled")]
        if off:
            raise ValueError(
                f"notify config: levels.{level} needs its record channel(s) {off}, but they are disabled — "
                f"a {level} without a record is not a decision that was filed"
            )
        if spec.get("quiet_hours") not in QUIET_HOURS_POLICIES:
            raise ValueError(f"notify config: levels.{level}.quiet_hours must be one of {QUIET_HOURS_POLICIES}")
        if "suppress_unchanged" in spec and not isinstance(spec["suppress_unchanged"], bool):
            raise ValueError(f"notify config: levels.{level}.suppress_unchanged must be true or false")

    telegram = channels.get("telegram") or {}
    if telegram.get("enabled"):
        if telegram.get("token_env"):
            raise ValueError(
                "notify config: channels.telegram.token_env is no longer supported — declare each bot under "
                "channels.telegram.bots.<name>.token_env and pick one with default_bot (discussion #187 §3)"
            )
        bots = telegram.get("bots") or {}
        if not bots:
            raise ValueError("notify config: channels.telegram.bots is empty")
        for bot_name, bot_spec in bots.items():
            if not (bot_spec or {}).get("token_env"):
                raise ValueError(f"notify config: channels.telegram.bots.{bot_name}.token_env is required")
        default_bot = telegram.get("default_bot")
        if default_bot and default_bot not in bots:
            raise ValueError(f"notify config: channels.telegram.default_bot {default_bot!r} is not in bots")
        if not default_bot and len(bots) > 1:
            raise ValueError("notify config: channels.telegram.default_bot is required when several bots exist")
        recipients = telegram.get("recipients") or {}
        if not recipients:
            raise ValueError("notify config: channels.telegram.recipients is empty")
        for rcpt_name, rcpt in recipients.items():
            bot_ref = (rcpt or {}).get("bot")
            if bot_ref and bot_ref not in bots:
                raise ValueError(f"notify config: recipient {rcpt_name} references unknown bot {bot_ref!r}")

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


def resolve_bot(
    cfg: dict[str, Any], name: str | None = None, recipient: dict[str, Any] | None = None
) -> tuple[str, dict[str, Any]]:
    """Pick a bot: explicit name, else the recipient's, else `default_bot`.

    Each agent entry gets its own bot (#187 §3) because a token has exactly one
    active *receiving* process. Sending is unaffected, so kca may push through a
    bot whose update stream a Claude Code Telegram channel is holding.
    """
    telegram = (cfg.get("channels") or {}).get("telegram") or {}
    bots: dict[str, Any] = telegram.get("bots") or {}
    wanted = name or (recipient or {}).get("bot") or telegram.get("default_bot")
    if wanted:
        if wanted not in bots:
            raise KeyError(f"unknown telegram bot {wanted!r}; known: {sorted(bots)}")
        return str(wanted), bots[wanted]
    if len(bots) == 1:
        return next(iter(bots.items()))
    raise KeyError("no default telegram bot configured; pass --bot")


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


def primary_checkout_root(start: Path) -> Path:
    """The primary checkout of ``start``'s repository.

    A linked worktree has a ``.git`` *file* pointing at
    ``<primary>/.git/worktrees/<name>``. Without this, relative state resolves
    under each checkout, so every worktree would keep its own send ledger and
    hand itself a fresh daily budget — the cap is a property of the human's
    phone, not of a directory.
    """
    marker = start / ".git"
    try:
        if not marker.is_file():
            return start
        line = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return start
    if not line.startswith("gitdir:"):
        return start
    gitdir = Path(line.partition(":")[2].strip())
    if not gitdir.is_absolute():
        gitdir = (start / gitdir).resolve()
    commondir = gitdir / "commondir"
    try:
        common = (gitdir / commondir.read_text(encoding="utf-8").strip()).resolve()
    except OSError:
        return start
    return common.parent if common.name == ".git" else start


def state_dir(cfg: dict[str, Any]) -> Path:
    raw = str(cfg.get("state_dir") or ".agent/notify")
    path = Path(raw)
    return path if path.is_absolute() else primary_checkout_root(REPO_ROOT) / path


def ledger_path(cfg: dict[str, Any]) -> Path:
    return state_dir(cfg) / "sent.jsonl"


def dedupe_key(level: str, title: str, body: str) -> str:
    digest = hashlib.sha256(f"{level}\x00{title}\x00{body}".encode()).hexdigest()
    return digest[:16]


def lock_wait_s(cfg: dict[str, Any]) -> float:
    """How long to wait for the ledger lock, in seconds.

    Long enough to outlast a lock holder that is mid-transport: the holder keeps
    the lock until its Telegram POST *and* its `gh` subprocess return, so a
    ceiling below ``telegram.timeout_s + GITHUB_TIMEOUT_S`` would time out on an
    ordinary slow send rather than on a wedged process (#206 F003).
    """
    override = (cfg.get("limits") or {}).get("lock_wait_s")
    if override is not None:
        return max(float(override), 0.0)
    telegram = (cfg.get("channels") or {}).get("telegram") or {}
    return float(telegram.get("timeout_s") or DEFAULT_TELEGRAM_TIMEOUT_S) + GITHUB_TIMEOUT_S + LOCK_WAIT_MARGIN_S


@contextmanager
def ledger_lock(cfg: dict[str, Any], timeout_s: float | None = None, *, create: bool = True) -> Iterator[bool]:
    """Serialise read → decide → append → send across processes and worktrees.

    Without it two agents can both read a spent-but-not-yet-recorded budget and
    both send. The lock is held across the transport too, because the ledger
    entry that spends the budget is only written once the transport returns.

    **Best effort by design**: it yields ``False`` after ``timeout_s`` instead of
    raising, because a `gate` must never be dropped just because another process
    was wedged holding the lock. What the caller does with an unserialised
    dispatch differs by level — :func:`dispatch` sends a `gate`/`attention`
    anyway and defers a routine `digest`/`info` (#206 F003) — and the wait
    itself comes from :func:`lock_wait_s`, which outlasts the transports.

    ``create=False`` skips locking entirely and creates nothing. A dry run
    appends no ledger entry, so it has nothing to serialise, and it is the
    command an operator rehearses with — including from a hook — so it must not
    leave a state directory or a `ledger.lock` behind (#206 F012).
    """
    if fcntl is None or not create:  # pragma: no branch - fcntl exists on Linux/macOS
        yield False
        return
    path = state_dir(cfg) / "ledger.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
    except OSError:
        yield False
        return
    acquired = False
    wait_s = lock_wait_s(cfg) if timeout_s is None else float(timeout_s)
    deadline = time.monotonic() + max(wait_s, 0.0)
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(LOCK_POLL_S)
        yield acquired
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def read_ledger(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Every well-formed entry. A damaged line is skipped, never fatal.

    "Well-formed" means a JSON *object*: a stray `null` or `[]` line is valid
    JSON but has no `.get`, and letting one through would take the whole channel
    down — including the `doctor` command you would run to diagnose it.
    """
    path = ledger_path(cfg)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def append_ledger(cfg: dict[str, Any], entry: dict[str, Any]) -> None:
    path = ledger_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    compact_ledger(cfg)


def compact_ledger(cfg: dict[str, Any]) -> int:
    """Trim the ledger to its newest entries once it crosses the size bound.

    This file is appended to for the life of the project, and every dispatch
    reads it whole, so an unbounded ledger makes notifications progressively
    slower. The current day (the budget) and the longest dedupe window are both
    far inside ``LEDGER_KEEP_ENTRIES`` at a two-routine-pushes-per-day cap. The
    last `sent` entry per level is *not*: ``suppress_unchanged`` compares against
    it however old it is, so a newest-N window on its own silently re-enables
    the digest it was meant to hold back (#206 F004). Those few entries are
    therefore pinned, in place and in order, whatever their age.

    Returns the number of lines dropped.
    """
    path = ledger_path(cfg)
    try:
        if path.stat().st_size <= LEDGER_MAX_BYTES:
            return 0
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        if len(lines) <= LEDGER_KEEP_ENTRIES:
            return 0
        keep = set(range(len(lines) - LEDGER_KEEP_ENTRIES, len(lines)))
        pinned: dict[str, int] = {}
        for index, line in enumerate(lines):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("status") == "sent" and parsed.get("level"):
                pinned[str(parsed["level"])] = index
        keep.update(pinned.values())
        kept = [lines[i] for i in sorted(keep)]
        # A unique temp name: a process that is writing without the lock (a
        # `gate` that could not take it) must not clobber another rewrite.
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text("\n".join(kept) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return 0
    return len(lines) - len(kept)


def _parse_ts(value: Any) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def recent_duplicate(
    entries: list[dict[str, Any]],
    key: str,
    window_minutes: int,
    now: dt.datetime,
    status: str = "sent",
) -> dict[str, Any] | None:
    if window_minutes <= 0:
        return None
    cutoff = now - dt.timedelta(minutes=window_minutes)
    for entry in reversed(entries):
        if entry.get("key") != key or entry.get("status") != status:
            continue
        ts = _parse_ts(entry.get("ts"))
        if ts and ts >= cutoff:
            return entry
    return None


def last_sent(entries: list[dict[str, Any]], level: str) -> dict[str, Any] | None:
    """The most recent message actually sent at ``level``, whenever that was."""
    for entry in reversed(entries):
        if entry.get("level") == level and entry.get("status") == "sent":
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
        # A published decision must be answerable. The reply parser is the only
        # supported answer path, so an id it cannot parse would strand the gate
        # until it expires — reject it here, before anything is transmitted.
        if not _DECISION_ID_RE.match(self.decision_id):
            raise ValueError(
                f"decision_id {self.decision_id!r} is not answerable: "
                f"`/decide` accepts {DECISION_ID_PATTERN} (see parse_decision_reply)"
            )
        if len(self.options) < 2:
            raise ValueError("a decision request needs at least 2 options")
        ids = [opt_id for opt_id, _ in self.options]
        for opt_id in ids:
            if not _OPTION_ID_RE.match(opt_id):
                raise ValueError(
                    f"option id {opt_id!r} is not answerable: "
                    f"`/decide` accepts {OPTION_ID_PATTERN} (see parse_decision_reply)"
                )
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate option ids: {ids}")
        # Ids are rendered verbatim (they must round-trip through `/decide`), so
        # they are the one field redaction cannot clean up after the fact.
        for value in [self.decision_id, *ids]:
            if redact(value) != value:
                raise ValueError(f"decision/option id looks secret-shaped and must not be published: {value!r}")
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
    """The phase-1b callback contract.

    No button carries it yet (nothing consumes `getUpdates`), but every id is
    still validated against the 64-byte limit at construction so a decision
    opened today stays answerable by a tap once the poller exists.
    """
    return f"kca:{decision_id}:{option_id}"


def render_github_comment(req: DecisionRequest, cfg: dict[str, Any] | None = None) -> str:
    """The durable record. Everything a reader needs to attribute the answer."""
    rows = [
        ("competition", req.competition or "—"),
        ("decision_id", f"`{req.decision_id}`"),
        ("plan_hash", f"`{req.plan_hash}`"),
        ("account", req.account or "—"),
        ("expires_at", req.expires_at),
    ]
    table = "\n".join(f"| {name} | {redact(value, cfg)} |" for name, value in rows)
    options = "\n".join(f"- `{opt_id}` — {redact(label, cfg)}" for opt_id, label in req.options)
    links = "\n".join(f"- {redact(link, cfg)}" for link in req.links)
    # Ids are grammar-checked and secret-shape-checked at construction; every
    # other field is free text, so it is scrubbed here too — the machine block
    # is transmitted exactly like the prose above it.
    machine = yaml.safe_dump(
        {
            "decision_id": req.decision_id,
            "competition": redact(req.competition, cfg),
            "plan_hash": redact(req.plan_hash, cfg),
            "expires_at": redact(req.expires_at, cfg),
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
        redact(req.summary, cfg),
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
        "recorded as context but is never parsed as the answer. **This comment is the only way "
        "to answer**: the Telegram card is a read-only mirror of this record, and phase 1a has "
        "nothing consuming button taps.",
        "",
        f"⏳ **No reply is not consent.** After `{redact(req.expires_at, cfg)}` this request lapses to "
        "`EXPIRED` — it never auto-approves, and a late answer does not revive it.",
    ]
    if links:
        body += ["", "**Links**", "", links]
    body += ["", "```yaml", machine, "```"]
    return "\n".join(body)


def _tg_escape(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tg_escape_clip(text: Any, limit: int) -> str:
    """Escape for `parse_mode=HTML` and bound the **escaped** length.

    Escaping expands — 500 characters of `&` become 2500 of `&amp;` — so a field
    bounded in source characters could still push an assembled card past
    Telegram's limit (#206 F011). Entities are appended whole, so the bound can
    never land inside an `&amp;`.
    """
    escaped = _tg_escape(text)
    if len(escaped) <= limit:
        return escaped
    out: list[str] = []
    used = 0
    for char in str(text):
        piece = _tg_escape(char)
        if used + len(piece) > limit - 1:
            break
        out.append(piece)
        used += len(piece)
    return "".join(out) + "…"


def _fit_html_lines(lines: list[str], limit: int) -> str:
    """Bound an assembled card by dropping **whole rendered lines**.

    Slicing the joined string is what broke here: a cut after `<code>` but before
    `</code>` leaves unbalanced markup, Telegram rejects the message outright and
    the whole gate is lost (#206 F011). Every line this module renders opens and
    closes its own tags, so dropping trailing lines cannot unbalance anything —
    the card degrades instead of failing.
    """
    if len("\n".join(lines)) <= limit:
        return "\n".join(lines)
    kept = list(lines)
    while kept and len("\n".join(kept)) + 2 > limit:  # +2 leaves room for the "…" line
        kept.pop()
    kept.append("…")
    return "\n".join(kept)


def _card_lines(req: DecisionRequest, cfg: dict[str, Any], keep: int) -> list[str]:
    """One rendered card at a given option count — each line self-contained HTML."""
    answers = [
        f"<code>/decide {_tg_escape_clip(req.decision_id, MAX_CARD_FIELD_CHARS)} "
        f"{_tg_escape_clip(opt_id, MAX_CARD_FIELD_CHARS)}</code> — "
        f"{_tg_escape_clip(redact(label, cfg), MAX_OPTION_LABEL_CHARS)}"
        for opt_id, label in req.options[:keep]
    ]
    hidden = len(req.options) - keep
    if hidden > 0:
        answers.append(f"… {hidden} more option(s) — see the record on GitHub")
    lines = [
        f"🔔 <b>Decision</b> — <code>{_tg_escape_clip(req.decision_id, MAX_CARD_FIELD_CHARS)}</code>",
        f"🏁 {_tg_escape_clip(redact(req.competition, cfg), MAX_CARD_FIELD_CHARS) or '—'}",
        f"#️⃣ plan <code>{_tg_escape_clip(redact(req.plan_hash, cfg), MAX_CARD_FIELD_CHARS)}</code>",
        "",
        _tg_escape_clip(redact(req.summary, cfg), MAX_CARD_SUMMARY_CHARS),
        "",
        "✍️ <b>Answer by commenting on the record</b> (this card has no buttons to tap):",
        *answers,
        "",
        "".join(
            [
                "⏳ expires ",
                _tg_escape_clip(redact(req.expires_at, cfg), MAX_CARD_FIELD_CHARS),
                " — no reply ≠ approval",
            ]
        ),
    ]
    url = req.issue_url(cfg)
    if url and len(_tg_escape(url)) <= MAX_CARD_URL_CHARS:
        # An href is clipped by dropping the line, never mid-URL: half a link is
        # a link to somewhere else.
        lines += ["", f'📎 <a href="{_tg_escape(url)}">record on GitHub</a>']
    return lines


def render_telegram_text(req: DecisionRequest, cfg: dict[str, Any]) -> str:
    """The compact push card. Detail lives in the GitHub record it links to.

    It spells out the `/decide` line for every option because that comment is
    the answer path in phase 1a — the card itself is read-only.

    Over-long input degrades in two safe steps, never by cutting the assembled
    HTML: re-render with fewer options first, then drop whole trailing lines
    (#206 F011).
    """
    keep = min(len(req.options), MAX_RENDERED_OPTIONS)
    while True:
        lines = _card_lines(req, cfg, keep)
        if len("\n".join(lines)) <= TELEGRAM_MAX_CHARS or keep == 0:
            return _fit_html_lines(lines, TELEGRAM_MAX_CHARS)
        keep -= 1


def build_keyboard(req: DecisionRequest, cfg: dict[str, Any]) -> dict[str, Any]:
    """A link to the record — and deliberately nothing tappable per option.

    Phase 1a has no process consuming `getUpdates` / callback queries, so an
    option button would look like an answer, silently resolve nothing, and leave
    the human believing an unanswered gate was handled. The card carries the
    `/decide` lines instead; :func:`callback_data` stays reserved for phase 1b.
    """
    url = req.issue_url(cfg)
    return {"inline_keyboard": [[{"text": "📋 Answer on GitHub", "url": url}]]} if url else {}


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


def _telegram_api(cfg: dict[str, Any], method: str, bot: str | None = None) -> tuple[str, str]:
    telegram = (cfg.get("channels") or {}).get("telegram") or {}
    bot_name, bot_spec = resolve_bot(cfg, bot)
    token_env = str(bot_spec.get("token_env") or "")
    token = resolve_secret(token_env, cfg)
    if not token:
        raise RuntimeError(f"{token_env} (bot {bot_name}) is not set (see docs/tooling/notification-channel.md)")
    base = str(telegram.get("api_base") or "https://api.telegram.org").rstrip("/")
    return f"{base}/bot{token}/{method}", token


def telegram_call(
    cfg: dict[str, Any], method: str, payload: dict[str, Any] | None = None, bot: str | None = None
) -> dict[str, Any]:
    """POST to the Bot API. The token never appears in the returned payload."""
    import requests

    url, token = _telegram_api(cfg, method, bot)
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
    bot: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    name, spec = resolve_recipient(cfg, recipient)
    bot_name, _bot_spec = resolve_bot(cfg, bot, spec)
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
            "bot": bot_name,
            "dry_run": True,
            "chat_id_configured": bool(chat_id),
            "payload": preview,
        }
    if not chat_id:
        return {
            "ok": False,
            "channel": "telegram",
            "recipient": name,
            "bot": bot_name,
            "error": f"{chat_env} is not set",
        }
    result = telegram_call(cfg, "sendMessage", payload, bot=bot_name)
    if not result.get("ok"):
        return {"ok": False, "channel": "telegram", "recipient": name, "bot": bot_name, "error": result.get("error")}
    return {
        "ok": True,
        "channel": "telegram",
        "recipient": name,
        "bot": bot_name,
        "message_id": (result.get("result") or {}).get("message_id"),
    }


def post_github_comment(cfg: dict[str, Any], *, issue: int, body: str, dry_run: bool = False) -> dict[str, Any]:
    repo = ((cfg.get("channels") or {}).get("github") or {}).get("repo") or ""
    if dry_run:
        return {"ok": True, "channel": "github", "dry_run": True, "issue": issue, "repo": repo, "body": body}
    cmd = ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"]
    try:
        proc = subprocess.run(cmd, input=body, capture_output=True, text=True, timeout=GITHUB_TIMEOUT_S, check=False)
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
    bot: str | None = None,
    github_body: str | None = None,
    telegram_text: str | None = None,
    telegram_keyboard: dict[str, Any] | None = None,
    dry_run: bool = False,
    force: bool = False,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Route one message. Returns ``{"ok", "status", "channels", ...}``.

    ``status`` is ``sent`` | ``deduped`` | ``deferred`` | ``rate_limited`` |
    ``partial`` | ``failed``. Suppression is a *successful* outcome — it is the
    #185 §18 intervention budget working, not an error — while ``partial`` is
    not: it means at least one configured channel did not take the message, so
    a `gate` whose GitHub record failed reports failure even though the Telegram
    push landed. The whole read → decide → send → append sequence runs under
    :func:`ledger_lock` so two agents cannot both spend the last of the budget.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {LEVELS}")
    spec = (cfg.get("levels") or {})[level]
    moment = _now(cfg, now)
    title = clip(redact(title, cfg), MAX_TITLE_CHARS)
    body = clip(redact(body, cfg), MAX_BODY_CHARS)
    key = dedupe_key(level, title, body)

    with ledger_lock(cfg, create=not dry_run) as locked:
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
            # A suppressed outcome is logged once per hour per message: with the
            # budget spent, every later hook invocation hits the same branch and
            # would otherwise add a line for as long as the agent runs.
            repeat = status in SUPPRESSED_STATUSES and recent_duplicate(
                entries, key, SUPPRESSION_LOG_MINUTES, moment, status=status
            )
            if not dry_run and not repeat:
                append_ledger(cfg, entry)
            return {
                "ok": status not in FAILED_STATUSES,
                "status": status,
                "level": level,
                "key": key,
                "serialized": bool(locked),
                **detail,
            }

        if not force:
            # A routine push fails closed when the read → decide → append
            # sequence could not be serialised: sending anyway would spend the
            # daily budget against a stale count, which is exactly how two
            # processes both take the last slot (#206 F003). A `gate` or an
            # `attention` still goes out unserialised — never dropped for a lock
            # — and a dry run takes no lock because it appends nothing.
            if level in ROUTINE_LEVELS and not locked and not dry_run and fcntl is not None:
                return _record(
                    "deferred",
                    {
                        "reason": "ledger lock busy; a routine push is not spent against a stale budget",
                        "retry_after": (moment + dt.timedelta(seconds=lock_wait_s(cfg))).isoformat(),
                        "channels": [],
                    },
                )

            # "Nothing changed since the last one" is time-independent on
            # purpose: a once-daily digest repeats outside any rolling window,
            # and #197 asks for it to be suppressed while it says the same thing.
            if spec.get("suppress_unchanged"):
                previous = last_sent(entries, level)
                if previous and previous.get("key") == key:
                    return _record(
                        "deduped",
                        {"reason": f"unchanged since the {level} sent at {previous.get('ts')}", "channels": []},
                    )

            duplicate = recent_duplicate(entries, key, int(spec.get("dedupe_minutes") or 0), moment)
            if duplicate:
                return _record(
                    "deduped", {"reason": f"identical {level} sent at {duplicate.get('ts')}", "channels": []}
                )

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
                # "Off by configuration" is a successful skip for a push channel
                # — but a `gate` *is* its GitHub record, so a disabled record
                # channel is a missing system-of-record entry, not a skip, and
                # must not let the dispatch report `sent` (#206 F002).
                if is_required_channel(level, channel, cfg):
                    results.append(
                        {
                            "ok": False,
                            "channel": channel,
                            "error": f"channel disabled in config; a {level} cannot be filed without its record",
                        }
                    )
                else:
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
                    send_telegram(
                        cfg,
                        text=text,
                        keyboard=telegram_keyboard,
                        recipient=recipient,
                        bot=bot,
                        dry_run=dry_run,
                    )
                )
            else:
                results.append({"ok": False, "channel": channel, "error": "no transport implemented"})

        # Every configured channel has to take it. Reporting `sent` because one
        # leg worked is how a decision ends up with no record on GitHub while
        # the caller believes it was filed.
        delivered = [bool(r.get("ok")) for r in results]
        if not delivered or not any(delivered):
            status = "failed"
        elif all(delivered):
            status = "sent"
        else:
            status = "partial"
        detail: dict[str, Any] = {"channels": results}
        if status == "partial":
            failed = [str(r.get("channel")) for r in results if not r.get("ok")]
            detail["reason"] = f"channel(s) did not take the message: {', '.join(failed)}"
        return _record(status, detail)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def exit_code_for(result: dict[str, Any]) -> int:
    """`sent` -> 0, suppressed (deduped / deferred / rate_limited) -> 2, else 1.

    Suppression is a policy decision, not a fault: a caller retrying on exit 2
    would be fighting the intervention budget, whereas exit 1 means the message
    genuinely did not get out and is worth retrying. A `partial` counts as exit
    1 — one missing leg is a message that did not fully get out.
    """
    status = str(result.get("status"))
    if status == "sent":
        return EXIT_OK
    return EXIT_BLOCKED if status in SUPPRESSED_STATUSES else EXIT_RUNTIME


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
    bots: dict[str, Any] = telegram.get("bots") or {}
    identities: dict[str, str] = {}
    for bot_name, bot_spec in bots.items():
        token_env = str((bot_spec or {}).get("token_env") or "")
        token = resolve_secret(token_env, cfg)
        checks.append(
            {
                "name": f"bot {bot_name}: {token_env}",
                "ok": bool(token),
                "detail": "set" if token else "MISSING",
            }
        )
        if not token or args.offline:
            continue
        # getMe is how a token is checked without ever printing it — the reply
        # names the bot, which is also how you confirm which env var is which.
        me = telegram_call(cfg, "getMe", bot=bot_name)
        username = (me.get("result") or {}).get("username") if me.get("ok") else None
        if username:
            identities[bot_name] = f"@{username}"
        checks.append(
            {
                "name": f"bot {bot_name}: getMe",
                "ok": bool(me.get("ok")),
                "detail": f"@{username}" if username else str(me.get("error")),
            }
        )

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
            "bots": identities,
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
            bot=args.bot,
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
            bot=args.bot,
            github_body=render_github_comment(req, cfg),
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
    p_send.add_argument("--bot", default=None, help="telegram bot key from .kca/notify.yml (default: default_bot)")
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
    p_dec.add_argument("--bot", default=None, help="telegram bot key from .kca/notify.yml (default: default_bot)")
    p_dec.add_argument("--dry-run", action="store_true", dest="dry_run")
    p_dec.add_argument("--force", action="store_true")
    p_dec.set_defaults(func=cmd_decision)
