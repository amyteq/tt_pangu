"""Tests for `kca notify` — the long-run notification / HITL channel (#197).

Pure-Python only: no network, no DB, no Telegram token. The transports are
exercised through `--dry-run` / monkeypatched call sites, so this module runs
anywhere CI does.

Coverage maps 1:1 onto the phase-1a acceptance criteria in issue #197:

1. decision-request format carries decision_id / competition / summary /
   plan_hash / options / expiry;
2. reply parsing is deterministic — an option id, never free-text inference;
3. expiry handling — a lapsed decision never auto-approves;
4. routine traffic is suppressed when nothing changed (dedupe + daily cap +
   quiet hours);
5. nothing secret-shaped is ever rendered into a notification body.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import notify  # noqa: E402

SECRET_TOKEN = "8123456789:AAF_ThisLooksExactlyLikeARealBotToken12345"
SECRET_DSN = "postgresql://postgres:s3cr3t@10.0.0.4:5432/postgres"

MELBOURNE = notify.ZoneInfo("Australia/Melbourne")


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch) -> None:
    """Strip inherited TELEGRAM_* values so no test can reach a live bot.

    `tests/conftest.py::db_url` loads `.vscode/.env` into os.environ for the
    whole session, and `resolve_secret` reads os.environ first — without this,
    a full-suite run could send a real message from a unit test. Tests that
    want a token set it themselves after this fixture has run.
    """
    for key in [k for k in os.environ if k.startswith("TELEGRAM")]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def cfg(tmp_path: Path) -> dict:
    """The shipped config, redirected at a throwaway state dir + secrets file."""
    loaded = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    loaded["state_dir"] = str(tmp_path / "state")
    loaded["secrets_file"] = str(tmp_path / "secrets.env")
    return loaded


def _request(**overrides) -> notify.DecisionRequest:
    kwargs = dict(
        decision_id="d-2026-09-15-001",
        competition="nemo-equation",
        summary="Promote rules24.py (LB 0.951) over the v17 cipher branch as the daily submission.",
        options=[("promote", "Promote rules24"), ("hold", "Hold, keep v17")],
        expires_at="2026-09-16T09:00:00+10:00",
        issue=197,
        account="harrysun2006",
    )
    kwargs.update(overrides)
    return notify.DecisionRequest(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_shipped_config_is_valid() -> None:
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    assert cfg["channels"]["telegram"]["role"] == "primary"
    assert cfg["channels"]["github"]["role"] == "record"
    # A gate must reach the record channel, or an answer would be unattributable.
    assert "github" in cfg["levels"]["gate"]["channels"]
    assert cfg["levels"]["gate"]["quiet_hours"] == "bypass"


def test_config_holds_no_secret_values() -> None:
    """The config names env vars; a value that looks like a token must never
    be committed here."""
    raw = (REPO_ROOT / ".kca" / "notify.yml").read_text(encoding="utf-8")
    assert notify._TELEGRAM_TOKEN_RE.search(raw) is None
    assert "token_env" in raw


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda c: c.__setitem__("version", 2), "version"),
        (lambda c: c["levels"]["gate"].__setitem__("channels", ["carrier-pigeon"]), "unknown channel"),
        (lambda c: c["levels"]["digest"].__setitem__("quiet_hours", "whenever"), "quiet_hours"),
        (lambda c: c["quiet_hours"].pop("timezone"), "timezone"),
    ],
)
def test_validate_config_rejects_broken_config(cfg: dict, mutate, needle: str) -> None:
    mutate(cfg)
    with pytest.raises(ValueError, match=needle):
        notify.validate_config(cfg)


def test_env_file_loader_only_reads_allowlisted_prefixes(tmp_path: Path) -> None:
    """`secrets_file` may hold unrelated credentials; only TELEGRAM_* is loaded."""
    env_file = tmp_path / "secrets.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                f"TELEGRAM_BOT1_TOKEN={SECRET_TOKEN}",
                'TELEGRAM_CHAT_ID_ME="123456"',
                "export TELEGRAM_EXTRA=ok",
                "CTFTIME_PASSWORD=not-yours",
                f"SUPABASE_DB_URL={SECRET_DSN}",
                "malformed-line",
            ]
        ),
        encoding="utf-8",
    )
    loaded = notify.load_env_file(env_file)
    assert set(loaded) == {"TELEGRAM_BOT1_TOKEN", "TELEGRAM_CHAT_ID_ME", "TELEGRAM_EXTRA"}
    assert loaded["TELEGRAM_CHAT_ID_ME"] == "123456"  # quotes stripped
    assert "CTFTIME_PASSWORD" not in loaded
    assert "SUPABASE_DB_URL" not in loaded


# ---------------------------------------------------------------------------
# Redaction (#185 §9: no secret in a notification body)
# ---------------------------------------------------------------------------


def test_redact_masks_bot_token_and_dsn() -> None:
    text = f"pushing with {SECRET_TOKEN} against {SECRET_DSN}"
    out = notify.redact(text)
    assert SECRET_TOKEN not in out
    assert SECRET_DSN not in out
    assert notify.REDACTED in out


def test_rendered_bodies_carry_no_secret() -> None:
    req = _request(summary=f"Retry the push; token {SECRET_TOKEN} was rotated, dsn {SECRET_DSN}.")
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    for body in (notify.render_github_comment(req), notify.render_telegram_text(req, cfg)):
        assert SECRET_TOKEN not in body
        assert SECRET_DSN not in body


@pytest.mark.parametrize(
    "payload, leaked",
    [
        ("export OPENAI_API_KEY=sk-proj-SENTINEL0123 && go", "sk-proj-SENTINEL0123"),
        ("CHAT_ID=123456789 is where it goes", "123456789"),
        ('TELEGRAM_BOT1_TOKEN="8123456789:AAF_NotARealTokenAtAllJustASentinel"', "AAF_NotARealToken"),
        ("clone with ghp_0123456789abcdefghijABCDEFGHIJ0123 first", "ghp_0123456789"),
        ("maps key AIzaSyFAKESENTINEL0123456789abcdefghij", "AIzaSyFAKESENTINEL"),
        ("Authorization: Bearer abcdef0123456789abcdef", "abcdef0123456789abcdef"),
        ("slack hook xoxb-1111111111-2222222222-FAKESENTINEL", "xoxb-1111111111"),
        ("session eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.FAKEsignature0", "eyJhbGciOiJIUzI1NiJ9"),
        ("db_password: hunter2-sentinel-value", "hunter2-sentinel-value"),
    ],
)
def test_redact_masks_credential_shapes(payload: str, leaked: str) -> None:
    """A harness event carries whatever the session said, including a pasted key."""
    out = notify.redact(payload)
    assert leaked not in out
    assert notify.REDACTED in out


def test_redaction_leaves_ordinary_operator_text_alone() -> None:
    """Over-redaction is its own failure: a silenced gate is worse than a noisy one."""
    text = "LB 0.951 after 12345 rows; run 2026-09-17 finished in 42 min on snorlax"
    assert notify.redact(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "tokens: 1500 remaining",
        "max_tokens: 4096 and total_tokens: 12000",
        "branch sk-learn-baseline beat sk-learn-tuned-v2 by 0.004",
        "db_password: hunter2-sentinel-value was wrong, retry tomorrow",
    ],
)
def test_redaction_keeps_the_operator_fields_a_gate_is_read_for(text: str) -> None:
    """#206 F010: a budget number or a branch name is the reason in the message.

    The last case is the boundary — the *value* after a secret-named field is
    masked, but the operator's sentence after it survives.
    """
    out = notify.redact(text)
    for keep in ("1500 remaining", "4096", "12000", "sk-learn-baseline", "was wrong, retry tomorrow"):
        if keep in text:
            assert keep in out


@pytest.mark.parametrize(
    "text, leaked",
    [
        ("TOKENS_SECRET=opaque-short-value", "opaque-short-value"),
        ("API_TOKENS=abcdef-ghijkl-mnopqr", "abcdef-ghijkl-mnopqr"),
        ("max_tokens_secret=abcdef-ghijkl", "abcdef-ghijkl"),
        ("tokens_secret: abcdef-ghijkl", "abcdef-ghijkl"),
        # An exact budget name, but the value is plainly not a budget.
        ("max_tokens=sk-live-abcdefghijkl", "sk-live-abcdefghijkl"),
    ],
)
def test_the_budget_field_exemption_does_not_cover_credential_names(text: str, leaked: str) -> None:
    """#206 F010 (round 3): the exemption was a `tokens` *component* match.

    That let `TOKENS_SECRET=…` through unmasked. It now needs an exact operator
    field name **and** a numeric value, so anything that reads as a credential —
    or a budget name carrying a non-numeric value — masks again.
    """
    out = notify.redact(text)
    assert leaked not in out
    assert notify.REDACTED in out


@pytest.mark.parametrize(
    "payload, leaked",
    [
        ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
        ("curl -H 'Authorization: Basic dXNlcjpwYXNzd29yZA==' https://x", "dXNlcjpwYXNzd29yZA=="),
        ("proxy-authorization = Digest username=admin, response=0123456789abcdef", "0123456789abcdef"),
        ("sk-proj-FAKESENTINELvalue0123456789abcdef", "FAKESENTINELvalue0123456789abcdef"),
    ],
)
def test_a_credential_is_masked_past_its_first_token(payload: str, leaked: str) -> None:
    """#206 F001: masking only the scheme word left the credential in the clear."""
    out = notify.redact(payload)
    assert leaked not in out
    assert notify.REDACTED in out


def test_a_configured_chat_id_is_masked_even_though_it_is_only_digits(cfg: dict, monkeypatch) -> None:
    """Shape rules cannot know a chat id — but this config resolves ours."""
    monkeypatch.setenv("TELEGRAM_CHAT_ID_ME", "987654321")
    assert "987654321" not in notify.redact("reply to 987654321 to approve", cfg)
    # A same-shaped number that is not ours stays readable.
    assert notify.redact("run 123123123 finished", cfg) == "run 123123123 finished"


def test_a_leaky_body_is_scrubbed_before_it_reaches_a_payload(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(
        cfg,
        level="info",
        title="turn done",
        body="rerun with OPENAI_API_KEY=sk-proj-SENTINEL0123 CHAT_ID=123456789",
        now=noon,
        dry_run=True,
    )
    text = next(c for c in out["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "sk-proj-SENTINEL0123" not in text
    assert "123456789" not in text
    assert notify.REDACTED in text


def test_a_runaway_body_is_bounded_before_transmission(cfg: dict) -> None:
    """Telegram caps a message at 4096 chars, and an unbounded body is a leak
    surface of its own."""
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="info", title="t" * 500, body="x" * 9000, now=noon, dry_run=True)
    text = next(c for c in out["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert len(text) <= notify.MAX_TITLE_CHARS + notify.MAX_BODY_CHARS + 32
    assert text.endswith("…")


def test_every_decision_field_is_scrubbed_including_the_machine_block() -> None:
    """The YAML block is transmitted exactly like the prose above it."""
    req = _request(
        competition=f"nemo {SECRET_DSN}",
        options=[("promote", f"Promote with {SECRET_TOKEN}"), ("hold", "Hold")],
        links=[f"https://example.invalid/?dsn={SECRET_DSN}"],
    )
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    record = notify.render_github_comment(req)
    machine = notify.yaml.safe_load(record.split("```yaml")[1].split("```")[0])
    assert SECRET_DSN not in record
    assert SECRET_TOKEN not in record
    assert SECRET_DSN not in machine["competition"]
    assert SECRET_TOKEN not in notify.render_telegram_text(req, cfg)


# ---------------------------------------------------------------------------
# Decision-request format (#197 acceptance criterion 1)
# ---------------------------------------------------------------------------


def test_github_record_carries_every_required_field() -> None:
    req = _request()
    body = notify.render_github_comment(req)
    for needle in (req.decision_id, req.competition, req.plan_hash, req.expires_at, "promote", "hold"):
        assert needle in body
    assert notify.RECORD_MARKER in body
    assert f"/decide {req.decision_id} <option_id>" in body
    # The machine-readable block must round-trip.
    block = body.split("```yaml")[1].split("```")[0]
    parsed = notify.yaml.safe_load(block)
    assert parsed["decision_id"] == req.decision_id
    assert parsed["options"] == ["promote", "hold"]


def test_plan_hash_is_derived_and_stable_when_not_supplied() -> None:
    first, second = _request(), _request()
    assert first.plan_hash == second.plan_hash
    assert _request(summary="a different plan").plan_hash != first.plan_hash


@pytest.mark.parametrize(
    "overrides",
    [
        {"decision_id": "approval/v2"},  # `/` is not in the reply grammar
        {"decision_id": "d 2026"},  # a space ends the id the parser reads
        {"decision_id": "d" * 65},  # longer than the parser accepts
        {"options": [("ship.now", "Ship now"), ("hold", "Hold")]},  # `.` is not an option char
        {"options": [("ship now", "Ship now"), ("hold", "Hold")]},
        {"options": [("s" * 33, "Ship"), ("hold", "Hold")]},
        # #206 F005: Python's `$` matches before a final newline, so `^…$`
        # accepted these while the line-oriented parser split the newline away
        # — `approval-v2\n` parsed as no reply at all, `ship\n` as INVALID_OPTION.
        {"decision_id": "approval-v2\n"},
        {"options": [("ship\n", "Ship"), ("hold", "Hold")]},
        {"decision_id": "d-2026\r"},
    ],
)
def test_a_decision_its_own_parser_could_not_answer_is_refused(overrides: dict) -> None:
    """Publishing `approval/v2` would strand the gate: `/decide approval/v2 …`
    does not parse, and the GitHub comment is the only answer path there is."""
    with pytest.raises(ValueError, match="not answerable"):
        _request(**overrides)


def test_a_secret_shaped_id_is_never_published() -> None:
    """Ids are rendered verbatim so they round-trip through `/decide`, which
    makes them the one field redaction cannot clean up after the fact."""
    with pytest.raises(ValueError, match="secret-shaped"):
        _request(decision_id=SECRET_TOKEN)


def test_every_publishable_decision_round_trips_through_the_reply_parser() -> None:
    req = _request(decision_id="kca:nemo:2026-09-17.1", options=[("promote-v18", "Promote"), ("hold", "Hold")])
    before = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.timezone.utc)
    for opt_id, _label in req.options:
        assert notify.parse_decision_reply(f"/decide {req.decision_id} {opt_id}") == {
            "decision_id": req.decision_id,
            "option_id": opt_id,
            "note": "",
        }
    answered = notify.resolve_reply(req, f"/decide {req.decision_id} promote-v18", now=before)
    assert (answered["status"], answered["option_id"]) == ("ANSWERED", "promote-v18")


def test_decision_request_rejects_unusable_input() -> None:
    with pytest.raises(ValueError, match="at least 2 options"):
        _request(options=[("only", "one")])
    with pytest.raises(ValueError, match="duplicate option ids"):
        _request(options=[("a", "A"), ("a", "A again")])
    with pytest.raises(ValueError, match="ISO-8601"):
        _request(expires_at="tomorrow-ish")
    with pytest.raises(ValueError, match="callback_data too long"):
        _request(decision_id="d" * 60, options=[("promote", "P"), ("hold", "H")])


def test_telegram_card_offers_no_button_that_nothing_would_answer() -> None:
    """Phase 1a consumes no callbacks, so a tapped option must not exist.

    A tappable button that resolves nothing is worse than no button: the human
    taps it, believes the gate is answered, and the decision blocks until expiry.
    """
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    req = _request()
    keyboard = notify.build_keyboard(req, cfg)
    rows = keyboard["inline_keyboard"]
    assert len(rows) == 1
    assert rows[0][0]["url"].endswith("/issues/197")
    assert "callback_data" not in json.dumps(keyboard)

    # The card carries the answer path it *does* support, one line per option.
    text = notify.render_telegram_text(req, cfg)
    for opt_id, _label in req.options:
        assert f"/decide {req.decision_id} {opt_id}" in text

    record = notify.render_github_comment(req)
    assert "Tapping a button" not in record
    assert "only way to answer" in record


def test_a_decision_card_never_exceeds_the_telegram_message_limit() -> None:
    """#206 F011: a valid decision with long labels must still be sendable.

    Telegram rejects a body over 4096 characters, so an unbounded label used to
    fail the primary push and leave the gate `partial`.
    """
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    req = _request(
        summary="s" * 4000,
        competition="c" * 2000,
        options=[("ship", "L" * 5000), ("hold", "hold the run")]
        + [(f"opt{i}", f"option {i} " * 40) for i in range(30)],
    )
    text = notify.render_telegram_text(req, cfg)
    assert len(text) <= notify.TELEGRAM_MAX_CHARS
    # The first options stay answerable and the elision is visible, not silent.
    assert f"/decide {req.decision_id} ship" in text
    assert "more option(s)" in text
    assert "…" in text


def test_a_card_that_hits_the_backstop_is_still_balanced_html() -> None:
    """#206 F011 (round 3): the backstop used to cut between `<code>` tags.

    Escaping expands — `&` becomes `&amp;` — so escaped text can reach 4096 even
    with every field bounded in source characters. Slicing the assembled string
    there leaves `<code>` unclosed and Telegram rejects the *whole* card, losing
    the gate. Only balanced markup is sendable.
    """
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    req = _request(
        summary="&" * 28,
        options=[(f"o{i}", "&" * 120) for i in range(12)],
    )
    text = notify.render_telegram_text(req, cfg)
    assert len(text) <= notify.TELEGRAM_MAX_CHARS
    for tag in ("code", "b", "a"):
        assert text.count(f"<{tag}>") + text.count(f"<{tag} ") == text.count(f"</{tag}>")
    assert text.count("<") == text.count(">")
    assert "&amp" not in text.replace("&amp;", "")  # no half-written entity survived


def test_callback_data_stays_within_the_phase_1b_contract() -> None:
    """The ids must still fit a future callback button, even with none rendered."""
    req = _request()
    for opt_id, _label in req.options:
        assert len(notify.callback_data(req.decision_id, opt_id).encode()) <= notify.CALLBACK_DATA_MAX_BYTES


def test_telegram_card_escapes_html() -> None:
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    text = notify.render_telegram_text(_request(competition="<b>not-markup</b>"), cfg)
    assert "&lt;b&gt;not-markup&lt;/b&gt;" in text


# ---------------------------------------------------------------------------
# Reply contract (#197 acceptance criteria 2 + 3)
# ---------------------------------------------------------------------------


def test_reply_parsing_is_deterministic() -> None:
    assert notify.parse_decision_reply("/decide d-1 promote") == {
        "decision_id": "d-1",
        "option_id": "promote",
        "note": "",
    }
    # Free text is recorded as context, never as the answer.
    parsed = notify.parse_decision_reply("thoughts below\n/decide d-1 hold keep the v17 branch warm")
    assert parsed == {"decision_id": "d-1", "option_id": "hold", "note": "keep the v17 branch warm"}


@pytest.mark.parametrize(
    "prose",
    ["yes", "A", "go ahead", "approved 👍", "promote", "sounds good, promote it", "/decide d-1"],
)
def test_prose_never_parses_as_an_answer(prose: str) -> None:
    assert notify.parse_decision_reply(prose) is None


def test_resolve_reply_statuses() -> None:
    req = _request()
    before = dt.datetime(2026, 9, 15, 12, 0, tzinfo=dt.timezone.utc)

    answered = notify.resolve_reply(req, f"/decide {req.decision_id} promote", now=before)
    assert (answered["status"], answered["approved"], answered["option_id"]) == ("ANSWERED", True, "promote")

    silent = notify.resolve_reply(req, "still thinking about it", now=before)
    assert (silent["status"], silent["approved"]) == ("WAIT_HUMAN", False)

    bad_option = notify.resolve_reply(req, f"/decide {req.decision_id} yolo", now=before)
    assert (bad_option["status"], bad_option["approved"]) == ("INVALID_OPTION", False)

    other = notify.resolve_reply(req, "/decide d-somewhere-else promote", now=before)
    assert (other["status"], other["approved"]) == ("MISMATCHED_DECISION", False)


def test_expiry_never_auto_approves() -> None:
    """#197: 'No reply ≠ consent' and a late answer does not resolve a lapse."""
    req = _request()
    after = dt.datetime(2026, 9, 20, 0, 0, tzinfo=dt.timezone.utc)

    lapsed = notify.resolve_reply(req, "", now=after)
    assert (lapsed["status"], lapsed["approved"]) == ("EXPIRED", False)

    late = notify.resolve_reply(req, f"/decide {req.decision_id} promote", now=after)
    assert (late["status"], late["approved"], late["option_id"]) == ("EXPIRED", False, None)


def test_resolve_reply_accepts_a_plain_dict_record() -> None:
    record = {"decision_id": "d-1", "expires_at": "2099-01-01T00:00:00+00:00", "options": ["a", "b"]}
    out = notify.resolve_reply(record, "/decide d-1 b")
    assert (out["status"], out["option_id"]) == ("ANSWERED", "b")


# ---------------------------------------------------------------------------
# Quiet hours + suppression (#197 acceptance criterion 4, #185 §18)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hour, expected",
    [(23, True), (2, True), (7, True), (8, False), (12, False), (21, False), (22, True)],
)
def test_quiet_hours_window_wraps_midnight(cfg: dict, hour: int, expected: bool) -> None:
    moment = dt.datetime(2026, 9, 15, hour, 0, tzinfo=MELBOURNE)
    assert notify.in_quiet_hours(cfg, moment) is expected


def test_next_send_window_is_the_end_of_quiet_hours(cfg: dict) -> None:
    moment = dt.datetime(2026, 9, 15, 23, 30, tzinfo=MELBOURNE)
    window = notify.next_send_window(cfg, moment)
    assert (window.date(), window.hour) == (dt.date(2026, 9, 16), 8)
    # Outside quiet hours the window is "now".
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    assert notify.next_send_window(cfg, noon) == noon


def test_digest_is_deferred_during_quiet_hours(cfg: dict) -> None:
    night = dt.datetime(2026, 9, 15, 23, 30, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="digest", title="nightly", body="two runs finished", now=night, dry_run=True)
    assert out["status"] == "deferred"
    assert out["channels"] == []
    assert out["retry_after"].startswith("2026-09-16T08:00")


def test_gate_bypasses_quiet_hours(cfg: dict) -> None:
    night = dt.datetime(2026, 9, 15, 23, 30, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="gate", title="blocked", body="need a call", issue=197, now=night, dry_run=True)
    assert out["status"] == "sent"
    assert {c["channel"] for c in out["channels"]} == {"github", "telegram"}


def test_identical_routine_message_is_deduped(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    first = notify.dispatch(cfg, level="info", title="status", body="no change", now=noon, dry_run=True)
    assert first["status"] == "sent"
    notify.append_ledger(
        cfg,
        {
            "ts": noon.isoformat(),
            "level": "info",
            "key": notify.dedupe_key("info", "status", "no change"),
            "status": "sent",
        },
    )
    again = notify.dispatch(cfg, level="info", title="status", body="no change", now=noon, dry_run=True)
    assert again["status"] == "deduped"
    # A changed body is a real update and goes out.
    changed = notify.dispatch(cfg, level="info", title="status", body="LB moved to 0.96", now=noon, dry_run=True)
    assert changed["status"] != "deduped"


def test_routine_daily_cap_blocks_the_third_push(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    for idx in range(2):
        notify.append_ledger(
            cfg,
            {"ts": noon.isoformat(), "level": "digest", "key": f"k{idx}", "status": "sent"},
        )
    out = notify.dispatch(cfg, level="digest", title="third", body="body", now=noon, dry_run=True)
    assert out["status"] == "rate_limited"
    assert "2/2" in out["reason"]
    # A gate is never rate-limited — it is what the budget exists to protect.
    gate = notify.dispatch(cfg, level="gate", title="gate", body="body", issue=197, now=noon, dry_run=True)
    assert gate["status"] == "sent"


def test_an_unchanged_daily_digest_is_suppressed_the_next_day(cfg: dict, monkeypatch) -> None:
    """#197 AC: "daily digest suppressed when nothing changed".

    A rolling dedupe window cannot express that — a once-daily digest always
    repeats outside it — so `suppress_unchanged` compares against the last
    digest actually sent, whenever that was.
    """
    sent: list[str] = []
    monkeypatch.setattr(
        notify,
        "send_telegram",
        lambda cfg, **kw: sent.append(kw["text"]) or {"ok": True, "channel": "telegram", "message_id": len(sent)},
    )
    day1 = dt.datetime(2026, 9, 15, 9, 0, tzinfo=MELBOURNE)
    day2 = day1 + dt.timedelta(days=1)
    unchanged = dict(level="digest", title="daily digest", body="LB 0.951 · 2 runs · nothing changed")

    assert notify.dispatch(cfg, **unchanged, now=day1)["status"] == "sent"
    repeat = notify.dispatch(cfg, **unchanged, now=day2)
    assert repeat["status"] == "deduped"
    assert "unchanged" in repeat["reason"]
    # A digest that says something new is a real update and still goes out.
    changed = notify.dispatch(cfg, level="digest", title="daily digest", body="LB 0.962 after v18", now=day2)
    assert changed["status"] == "sent"
    assert len(sent) == 2


def test_force_overrides_suppression(cfg: dict) -> None:
    night = dt.datetime(2026, 9, 15, 23, 30, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="digest", title="nightly", body="body", now=night, dry_run=True, force=True)
    assert out["status"] == "sent"


def test_dry_run_writes_nothing_and_masks_the_chat_id(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="info", title="t", body="b", now=noon, dry_run=True)
    telegram = next(c for c in out["channels"] if c["channel"] == "telegram")
    assert telegram["dry_run"] is True
    assert telegram["payload"]["chat_id"] == "<TELEGRAM_CHAT_ID_ME>"
    assert not notify.ledger_path(cfg).exists()
    # #206 F012: a rehearsal creates nothing at all — not the ledger, not the
    # lock file, not the state directory it would live in.
    assert not (notify.state_dir(cfg) / "ledger.lock").exists()
    assert not notify.state_dir(cfg).exists()


def test_gate_without_an_issue_reports_a_failed_record_leg(cfg: dict) -> None:
    """The record is not optional: a gate with no issue must say so loudly."""
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="gate", title="t", body="b", now=noon, dry_run=True)
    github = next(c for c in out["channels"] if c["channel"] == "github")
    assert github["ok"] is False
    assert "record not written" in github["error"]
    # …and the overall result must not claim the gate was sent.
    assert out["status"] == "partial"
    assert out["ok"] is False
    assert notify.exit_code_for(out) == notify.EXIT_RUNTIME


def test_one_failed_channel_is_partial_not_sent(cfg: dict, monkeypatch) -> None:
    """A `sent` gate whose GitHub record failed would be a decision nobody filed."""
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    monkeypatch.setattr(
        notify, "post_github_comment", lambda cfg, **kw: {"ok": False, "channel": "github", "error": "gh: 503"}
    )
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram", "message_id": 7})
    out = notify.dispatch(cfg, level="gate", title="record down", body="b", issue=197, now=noon)
    assert (out["status"], out["ok"]) == ("partial", False)
    assert "github" in out["reason"]
    assert notify.exit_code_for(out) == notify.EXIT_RUNTIME
    assert [e["status"] for e in notify.read_ledger(cfg)] == ["partial"]

    # The mirror image: the record is written but the primary push never lands.
    monkeypatch.setattr(notify, "post_github_comment", lambda cfg, **kw: {"ok": True, "channel": "github"})
    monkeypatch.setattr(
        notify, "send_telegram", lambda cfg, **kw: {"ok": False, "channel": "telegram", "error": "timeout"}
    )
    out = notify.dispatch(cfg, level="gate", title="push down", body="b", issue=197, now=noon)
    assert (out["status"], out["ok"]) == ("partial", False)
    assert "telegram" in out["reason"]

    # Both legs healthy is the only way to earn `sent`.
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    out = notify.dispatch(cfg, level="gate", title="both up", body="b", issue=197, now=noon)
    assert (out["status"], out["ok"]) == ("sent", True)


# ---------------------------------------------------------------------------
# The send ledger: shared, serialised, corruption-tolerant, bounded
# ---------------------------------------------------------------------------


def test_every_worktree_shares_the_primary_checkout_ledger(tmp_path: Path, monkeypatch) -> None:
    """The daily cap protects a phone, not a directory — a worktree must not
    hand itself a fresh budget."""
    primary = tmp_path / "primary"
    linked_gitdir = primary / ".git" / "worktrees" / "wt"
    linked_gitdir.mkdir(parents=True)
    (linked_gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {linked_gitdir}\n", encoding="utf-8")

    assert notify.primary_checkout_root(worktree) == primary.resolve()
    assert notify.primary_checkout_root(primary) == primary
    monkeypatch.setattr(notify, "REPO_ROOT", worktree)
    assert notify.state_dir({"state_dir": ".agent/notify"}) == primary.resolve() / ".agent" / "notify"
    # An absolute state_dir is still honoured verbatim.
    assert notify.state_dir({"state_dir": str(tmp_path / "abs")}) == tmp_path / "abs"


def test_the_ledger_lock_is_exclusive_but_never_swallows_a_gate(cfg: dict, monkeypatch) -> None:
    """Two agents must not both spend the last of the budget — and a wedged
    lock holder must not stop a blocking notification either."""
    import fcntl

    cfg["limits"]["lock_wait_s"] = 0.05
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    lock_file = notify.state_dir(cfg) / "ledger.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with lock_file.open("a+", encoding="utf-8") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
        with notify.ledger_lock(cfg, timeout_s=0.05) as locked:
            assert locked is False
        blocked = notify.dispatch(cfg, level="gate", title="t", body="b", issue=197, now=noon, dry_run=True)
        assert blocked["status"] == "sent"  # the gate still gets out
        assert blocked["serialized"] is False  # …and says it was not serialised
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)

    with notify.ledger_lock(cfg) as locked:
        assert locked is True
    # A dry run reports `serialized: false` whether or not the lock is free: it
    # appends nothing, so it takes no lock and creates no state (#206 F012).
    free = notify.dispatch(cfg, level="gate", title="t2", body="b", issue=197, now=noon, dry_run=True)
    assert free["serialized"] is False


def test_the_lock_wait_outlasts_the_transports_it_serialises(cfg: dict) -> None:
    """#206 F003: a ceiling below the worst-case hold makes the unlocked
    fallback the normal path, so the daily cap stops being enforced."""
    telegram_timeout = float(cfg["channels"]["telegram"]["timeout_s"])
    assert notify.lock_wait_s(cfg) > telegram_timeout + notify.GITHUB_TIMEOUT_S
    cfg["limits"]["lock_wait_s"] = 0.25  # an operator may still override it
    assert notify.lock_wait_s(cfg) == 0.25


def test_a_routine_push_fails_closed_when_it_cannot_be_serialised(cfg: dict, monkeypatch) -> None:
    """#206 F003: sending unserialised spends the budget against a stale count,
    which is how two processes both take the last slot. A gate still goes out."""
    import fcntl

    cfg["limits"]["lock_wait_s"] = 0.05
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    sent: list[str] = []
    monkeypatch.setattr(
        notify, "send_telegram", lambda cfg, **kw: sent.append(kw["text"]) or {"ok": True, "channel": "telegram"}
    )
    monkeypatch.setattr(notify, "post_github_comment", lambda cfg, **kw: {"ok": True, "channel": "github"})
    lock_file = notify.state_dir(cfg) / "ledger.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with lock_file.open("a+", encoding="utf-8") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
        routine = notify.dispatch(cfg, level="digest", title="d", body="b", now=noon)
        assert routine["status"] == "deferred"
        assert routine["serialized"] is False
        assert "stale budget" in routine["reason"]
        assert notify.exit_code_for(routine) == notify.EXIT_BLOCKED
        assert sent == []  # nothing was transmitted against an unread budget
        gate = notify.dispatch(cfg, level="gate", title="g", body="b", issue=197, now=noon)
        assert (gate["status"], gate["serialized"]) == ("sent", False)
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)

    # With the lock free the same digest goes out normally.
    assert notify.dispatch(cfg, level="digest", title="d", body="b", now=noon)["status"] == "sent"


def test_compaction_keeps_the_state_unchanged_suppression_depends_on(cfg: dict, monkeypatch) -> None:
    """#206 F004: `suppress_unchanged` compares against the last digest sent
    however old it is, so compaction must pin it rather than drop it."""
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    monkeypatch.setattr(notify, "LEDGER_MAX_BYTES", 400)
    monkeypatch.setattr(notify, "LEDGER_KEEP_ENTRIES", 5)
    day1 = dt.datetime(2026, 9, 15, 9, 0, tzinfo=MELBOURNE)
    unchanged = dict(level="digest", title="daily digest", body="LB 0.951 · nothing changed")
    assert notify.dispatch(cfg, **unchanged, now=day1)["status"] == "sent"

    # …then enough later traffic to push that entry out of the newest-N window.
    for idx in range(40):
        notify.append_ledger(cfg, {"ts": day1.isoformat(), "level": "gate", "key": f"k{idx}", "status": "partial"})
    entries = notify.read_ledger(cfg)
    assert len(entries) < 41  # the ledger really was compacted
    assert notify.last_sent(entries, "digest") is not None

    repeat = notify.dispatch(cfg, **unchanged, now=day1 + dt.timedelta(days=1))
    assert repeat["status"] == "deduped"
    assert "unchanged" in repeat["reason"]


def test_a_disabled_record_channel_is_a_failed_gate_not_a_skip(cfg: dict, monkeypatch) -> None:
    """#206 F002: a gate is its GitHub record. "Off by configuration" must not
    read as "this leg succeeded", or a gate reports `sent` with no record."""
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    cfg["channels"]["github"]["enabled"] = False

    out = notify.dispatch(cfg, level="gate", title="t", body="b", issue=197, now=noon)
    github = next(c for c in out["channels"] if c["channel"] == "github")
    assert github["ok"] is False
    assert "disabled" in github["error"]
    assert (out["status"], out["ok"]) == ("partial", False)
    assert notify.exit_code_for(out) == notify.EXIT_RUNTIME
    # …while a push-only level is unaffected by a disabled record channel.
    assert notify.dispatch(cfg, level="attention", title="t", body="b", now=noon)["status"] == "sent"
    # The same shape is rejected at load time rather than at 3am.
    with pytest.raises(ValueError, match="record channel"):
        notify.validate_config(cfg)


def test_a_gate_routed_to_no_record_channel_is_not_sent(cfg: dict, monkeypatch) -> None:
    """#206 F002: omitting the record channel from `levels.gate.channels` is the
    same missing system of record as disabling it, and must fail the same way."""
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    cfg["levels"]["gate"]["channels"] = ["telegram"]

    with pytest.raises(ValueError, match="no system-of-record channel"):
        notify.validate_config(cfg)

    out = notify.dispatch(cfg, level="gate", title="t", body="b", issue=197, now=noon)
    record = next(c for c in out["channels"] if c["channel"] == "record")
    assert record["ok"] is False
    assert (out["status"], out["ok"]) == ("partial", False)
    assert notify.exit_code_for(out) == notify.EXIT_RUNTIME
    # A push-only level routed to Telegram alone is still perfectly fine.
    assert notify.dispatch(cfg, level="info", title="t", body="b", now=noon)["status"] == "sent"


def test_the_budget_is_serialised_even_without_fcntl(cfg: dict, monkeypatch) -> None:
    """#206 F003: on a platform with no `fcntl` the lock used to degrade to no
    serialisation *and* skip the routine fail-closed rule — the one case that
    needs it most. The `O_CREAT|O_EXCL` fallback holds the same contract."""
    monkeypatch.setattr(notify, "fcntl", None)
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    monkeypatch.setattr(notify, "post_github_comment", lambda cfg, **kw: {"ok": True, "channel": "github"})
    cfg["limits"]["lock_wait_s"] = 0.05
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)

    with notify.ledger_lock(cfg) as held:
        assert held is True  # the fallback really acquires
        with notify.ledger_lock(cfg) as second:
            assert second is False  # …and really excludes a second holder
        routine = notify.dispatch(cfg, level="digest", title="d", body="b", now=noon)
        assert (routine["status"], routine["serialized"]) == ("deferred", False)
        gate = notify.dispatch(cfg, level="gate", title="g", body="b", issue=197, now=noon)
        assert (gate["status"], gate["serialized"]) == ("sent", False)

    assert notify.dispatch(cfg, level="digest", title="d", body="b", now=noon)["status"] == "sent"
    # …and `doctor` names the mechanism rather than implying flock everywhere.
    assert not (notify.state_dir(cfg) / "ledger.lock").exists()


def test_compaction_keeps_every_routine_send_of_the_live_day(cfg: dict, monkeypatch) -> None:
    """#206 F014: the daily cap counts every same-day routine `sent` entry, so
    pinning only the last one per level lets two collapse into one and a third
    push through the 2/day budget."""
    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    monkeypatch.setattr(notify, "LEDGER_MAX_BYTES", 400)
    monkeypatch.setattr(notify, "LEDGER_KEEP_ENTRIES", 5)
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)

    # Both of today's allowed routine sends are the same level…
    assert notify.dispatch(cfg, level="info", title="one", body="b", now=noon)["status"] == "sent"
    assert notify.dispatch(cfg, level="info", title="two", body="b", now=noon)["status"] == "sent"
    # …then newer traffic pushes them out of the newest-N window.
    for idx in range(40):
        notify.append_ledger(cfg, {"ts": noon.isoformat(), "level": "gate", "key": f"k{idx}", "status": "partial"})

    entries = notify.read_ledger(cfg)
    assert len(entries) < 42  # the ledger really was compacted
    assert notify.routine_sends_today(cfg, entries, noon) == 2
    third = notify.dispatch(cfg, level="info", title="three", body="b", now=noon)
    assert third["status"] == "rate_limited"
    assert "2/2" in third["reason"]


def test_an_unserialised_writer_does_not_rewrite_the_ledger(cfg: dict, monkeypatch) -> None:
    """#206 F015: compaction is a read/rewrite/`os.replace`, so a gate that had
    to write without the lock must not do it — its snapshot can be stale by the
    time it replaces the file, silently discarding the lock holder's line."""
    import fcntl

    monkeypatch.setattr(notify, "send_telegram", lambda cfg, **kw: {"ok": True, "channel": "telegram"})
    monkeypatch.setattr(notify, "post_github_comment", lambda cfg, **kw: {"ok": True, "channel": "github"})
    monkeypatch.setattr(notify, "LEDGER_MAX_BYTES", 400)
    monkeypatch.setattr(notify, "LEDGER_KEEP_ENTRIES", 5)
    cfg["limits"]["lock_wait_s"] = 0.05
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    for idx in range(40):
        notify.append_ledger(cfg, {"ts": noon.isoformat(), "level": "gate", "key": f"k{idx}", "status": "partial"})

    path = notify.ledger_path(cfg)
    lock_file = notify.state_dir(cfg) / "ledger.lock"
    with lock_file.open("a+", encoding="utf-8") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
        # Pad past the size bound so compaction *would* fire if it were allowed.
        padding = json.dumps({"ts": noon.isoformat(), "level": "gate", "status": "partial"})
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(padding for _ in range(40)) + "\n")
        padded = len(notify.read_ledger(cfg))
        gate = notify.dispatch(cfg, level="gate", title="g", body="b", issue=197, now=noon)
        assert (gate["status"], gate["serialized"]) == ("sent", False)
        assert len(notify.read_ledger(cfg)) == padded + 1  # nothing was rewritten away
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)

    # The next serialised send does compact, so the bound is still enforced.
    assert notify.dispatch(cfg, level="gate", title="g2", body="b", issue=197, now=noon)["status"] == "sent"
    assert len(notify.read_ledger(cfg)) < padded


def test_a_corrupt_ledger_line_never_blocks_a_send(cfg: dict) -> None:
    """Valid JSON of the wrong type is as likely as invalid JSON, and either one
    must not take down the channel — including the doctor you would diagnose with."""
    path = notify.ledger_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    path.write_text(
        "\n".join(
            [
                "null",
                "[]",
                '"a bare string"',
                "42",
                "{not json at all",
                json.dumps({"ts": noon.isoformat(), "level": "info", "key": "k-ok", "status": "sent"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    entries = notify.read_ledger(cfg)
    assert [e["key"] for e in entries] == ["k-ok"]
    assert notify.routine_sends_today(cfg, entries, noon) == 1
    assert notify.dispatch(cfg, level="info", title="t", body="b", now=noon, dry_run=True)["status"] == "sent"


def test_a_spent_budget_does_not_add_a_ledger_line_per_event(cfg: dict) -> None:
    """Once the cap is spent every later hook invocation hits the same branch;
    recording each one would grow the file for as long as the agent runs."""
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    for idx in range(2):
        notify.append_ledger(cfg, {"ts": noon.isoformat(), "level": "info", "key": f"k{idx}", "status": "sent"})
    for _ in range(3):
        assert notify.dispatch(cfg, level="info", title="stuck", body="same", now=noon)["status"] == "rate_limited"
    assert [e["status"] for e in notify.read_ledger(cfg)].count("rate_limited") == 1


def test_the_ledger_is_compacted_once_it_crosses_its_size_bound(cfg: dict, monkeypatch) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    monkeypatch.setattr(notify, "LEDGER_MAX_BYTES", 400)
    monkeypatch.setattr(notify, "LEDGER_KEEP_ENTRIES", 5)
    for idx in range(40):
        notify.append_ledger(cfg, {"ts": noon.isoformat(), "level": "info", "key": f"k{idx}", "status": "sent"})
    entries = notify.read_ledger(cfg)
    assert len(entries) == 5
    assert entries[-1]["key"] == "k39"  # the newest entries are the ones kept


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_notify_is_registered_in_the_kca_cli() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    from agent.command_registry import REGISTRY

    spec = REGISTRY.get("notify")
    assert spec is not None
    assert spec.side_effect == "REMOTE_WRITE"
    assert spec.requires_db is False


def test_decision_cli_dry_run_emits_json(cfg: dict, tmp_path: Path, capsys, monkeypatch) -> None:
    config_path = tmp_path / "notify.yml"
    config_path.write_text(notify.yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_CHAT_ID_ME", "42")

    from kca import main

    code = main(
        [
            "notify",
            "decision",
            "--config",
            str(config_path),
            "--decision-id",
            "d-cli-1",
            "--competition",
            "nemo",
            "--summary",
            "Promote rules24",
            "--option",
            "promote=Promote rules24",
            "--option",
            "hold=Hold",
            "--expires-at",
            "2099-01-01T00:00:00+00:00",
            "--issue",
            "197",
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == notify.EXIT_OK
    assert payload["decision_id"] == "d-cli-1"
    assert payload["status"] == "sent"
    github = next(c for c in payload["channels"] if c["channel"] == "github")
    assert "/decide d-cli-1 <option_id>" in github["body"]


@pytest.mark.parametrize(
    "status, expected",
    [
        ("sent", notify.EXIT_OK),
        ("deduped", notify.EXIT_BLOCKED),
        ("deferred", notify.EXIT_BLOCKED),
        ("rate_limited", notify.EXIT_BLOCKED),
        ("failed", notify.EXIT_RUNTIME),
        ("partial", notify.EXIT_RUNTIME),
    ],
)
def test_exit_code_separates_suppression_from_failure(status: str, expected: int) -> None:
    """Exit 2 means policy held the message back; exit 1 means it did not get out."""
    assert notify.exit_code_for({"status": status}) == expected


def test_doctor_reports_read_only_and_no_secret_value(tmp_path: Path, cfg: dict, capsys, monkeypatch) -> None:
    config_path = tmp_path / "notify.yml"
    config_path.write_text(notify.yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_BOT1_TOKEN", SECRET_TOKEN)
    monkeypatch.setenv("TELEGRAM_BOT2_TOKEN", SECRET_TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID_ME", "123456789")

    from kca import main

    main(["notify", "doctor", "--config", str(config_path), "--offline"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["side_effect"] == "READ_ONLY"
    # Presence is reported; the value never is.
    assert {c["detail"] for c in payload["checks"] if "TELEGRAM" in c["name"]} == {"set"}
    assert SECRET_TOKEN not in out
    assert "123456789" not in out
    # Both bots are preflighted, not just the default one.
    assert {c["name"] for c in payload["checks"] if c["name"].startswith("bot ")} == {
        "bot bot1: TELEGRAM_BOT1_TOKEN",
        "bot bot2: TELEGRAM_BOT2_TOKEN",
    }


# ---------------------------------------------------------------------------
# One bot per agent entry (#187 §3)
# ---------------------------------------------------------------------------


def test_shipped_config_declares_one_bot_per_agent_entry() -> None:
    telegram = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")["channels"]["telegram"]
    assert set(telegram["bots"]) == {"bot1", "bot2"}
    assert telegram["default_bot"] == "bot1"
    assert [b["token_env"] for b in telegram["bots"].values()] == ["TELEGRAM_BOT1_TOKEN", "TELEGRAM_BOT2_TOKEN"]


def test_resolve_bot_precedence(cfg: dict) -> None:
    """Explicit --bot wins, then the recipient's bot, then default_bot."""
    assert notify.resolve_bot(cfg)[0] == "bot1"
    assert notify.resolve_bot(cfg, "bot2")[0] == "bot2"
    assert notify.resolve_bot(cfg, None, {"bot": "bot2"})[0] == "bot2"
    assert notify.resolve_bot(cfg, "bot1", {"bot": "bot2"})[0] == "bot1"
    with pytest.raises(KeyError, match="unknown telegram bot"):
        notify.resolve_bot(cfg, "bot9")


def test_send_reports_which_bot_it_used(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="info", title="t", body="b", bot="bot2", now=noon, dry_run=True)
    telegram = next(c for c in out["channels"] if c["channel"] == "telegram")
    assert telegram["bot"] == "bot2"


def test_legacy_single_token_config_is_rejected_with_a_migration_hint(cfg: dict) -> None:
    cfg["channels"]["telegram"]["token_env"] = "TELEGRAM_BOT_TOKEN"
    with pytest.raises(ValueError, match="no longer supported"):
        notify.validate_config(cfg)


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda c: c["channels"]["telegram"].__setitem__("default_bot", "nope"), "default_bot"),
        (lambda c: c["channels"]["telegram"]["bots"]["bot1"].pop("token_env"), "token_env is required"),
        (lambda c: c["channels"]["telegram"]["recipients"]["harry"].__setitem__("bot", "ghost"), "unknown bot"),
    ],
)
def test_validate_config_rejects_broken_bot_wiring(cfg: dict, mutate, needle: str) -> None:
    mutate(cfg)
    with pytest.raises(ValueError, match=needle):
        notify.validate_config(cfg)


# ---------------------------------------------------------------------------
# `attention` — an agent session is blocked on the human
# ---------------------------------------------------------------------------


def test_attention_bypasses_quiet_hours_and_the_daily_cap(cfg: dict) -> None:
    night = dt.datetime(2026, 9, 15, 23, 30, tzinfo=MELBOURNE)
    for idx in range(5):  # budget already blown by routine traffic
        notify.append_ledger(cfg, {"ts": night.isoformat(), "level": "info", "key": f"k{idx}", "status": "sent"})
    out = notify.dispatch(cfg, level="attention", title="permission needed", body="Bash(rm)", now=night, dry_run=True)
    assert out["status"] == "sent"
    assert [c["channel"] for c in out["channels"]] == ["telegram"]


def test_attention_is_not_counted_as_routine(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    notify.append_ledger(cfg, {"ts": noon.isoformat(), "level": "attention", "key": "a", "status": "sent"})
    assert notify.routine_sends_today(cfg, notify.read_ledger(cfg), noon) == 0
