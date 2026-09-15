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
                f"TELEGRAM_BOT_TOKEN={SECRET_TOKEN}",
                'TELEGRAM_CHAT_ID_HARRY="123456"',
                "export TELEGRAM_EXTRA=ok",
                "CTFTIME_PASSWORD=not-yours",
                f"SUPABASE_DB_URL={SECRET_DSN}",
                "malformed-line",
            ]
        ),
        encoding="utf-8",
    )
    loaded = notify.load_env_file(env_file)
    assert set(loaded) == {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID_HARRY", "TELEGRAM_EXTRA"}
    assert loaded["TELEGRAM_CHAT_ID_HARRY"] == "123456"  # quotes stripped
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


def test_decision_request_rejects_unusable_input() -> None:
    with pytest.raises(ValueError, match="at least 2 options"):
        _request(options=[("only", "one")])
    with pytest.raises(ValueError, match="duplicate option ids"):
        _request(options=[("a", "A"), ("a", "A again")])
    with pytest.raises(ValueError, match="ISO-8601"):
        _request(expires_at="tomorrow-ish")
    with pytest.raises(ValueError, match="callback_data too long"):
        _request(decision_id="d" * 60, options=[("promote", "P"), ("hold", "H")])


def test_telegram_card_has_one_button_per_option_plus_the_record_link() -> None:
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    req = _request()
    keyboard = notify.build_keyboard(req, cfg)
    rows = keyboard["inline_keyboard"]
    assert [row[0]["callback_data"] for row in rows[:2]] == [
        f"kca:{req.decision_id}:promote",
        f"kca:{req.decision_id}:hold",
    ]
    assert rows[-1][0]["url"].endswith("/issues/197")
    assert all(len(row[0].get("callback_data", "").encode()) <= notify.CALLBACK_DATA_MAX_BYTES for row in rows[:2])


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
    first = notify.dispatch(cfg, level="info", title="status", body="no change", now=noon)
    assert first["status"] == "sent" or first["channels"]  # transport may fail; the ledger entry is the point
    notify.append_ledger(
        cfg,
        {
            "ts": noon.isoformat(),
            "level": "info",
            "key": notify.dedupe_key("info", "status", "no change"),
            "status": "sent",
        },
    )
    again = notify.dispatch(cfg, level="info", title="status", body="no change", now=noon)
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


def test_force_overrides_suppression(cfg: dict) -> None:
    night = dt.datetime(2026, 9, 15, 23, 30, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="digest", title="nightly", body="body", now=night, dry_run=True, force=True)
    assert out["status"] == "sent"


def test_dry_run_writes_nothing_and_masks_the_chat_id(cfg: dict) -> None:
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="info", title="t", body="b", now=noon, dry_run=True)
    telegram = next(c for c in out["channels"] if c["channel"] == "telegram")
    assert telegram["dry_run"] is True
    assert telegram["payload"]["chat_id"] == "<TELEGRAM_CHAT_ID_HARRY>"
    assert not notify.ledger_path(cfg).exists()


def test_gate_without_an_issue_reports_a_failed_record_leg(cfg: dict) -> None:
    """The record is not optional: a gate with no issue must say so loudly."""
    noon = dt.datetime(2026, 9, 15, 12, 0, tzinfo=MELBOURNE)
    out = notify.dispatch(cfg, level="gate", title="t", body="b", now=noon, dry_run=True)
    github = next(c for c in out["channels"] if c["channel"] == "github")
    assert github["ok"] is False
    assert "record not written" in github["error"]


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
    monkeypatch.setenv("TELEGRAM_CHAT_ID_HARRY", "42")

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
    ],
)
def test_exit_code_separates_suppression_from_failure(status: str, expected: int) -> None:
    """Exit 2 means policy held the message back; exit 1 means it did not get out."""
    assert notify.exit_code_for({"status": status}) == expected
