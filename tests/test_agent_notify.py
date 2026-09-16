"""Tests for scripts/agent_notify.py — harness events -> Telegram (#197).

Payload shapes are the ones the installed harnesses actually emit:

* Claude Code 2.1.273 pipes a hook JSON object on stdin, keyed by
  `hook_event_name` (`Notification`, `Stop`, `StopFailure`, …);
* codex-cli 0.154.0 execs the `notify` program with one argv holding
  `{"type": "agent-turn-complete", "thread-id": …, "last-assistant-message": …}`.

No network: every dispatch runs with `--dry-run`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import agent_notify  # noqa: E402
import notify  # noqa: E402

CLAUDE_NOTIFICATION = {
    "hook_event_name": "Notification",
    "session_id": "abc123def456789",
    "cwd": "/home/harry/test/tt_pangu",
    "message": "Claude needs your permission to use Bash",
}
CODEX_TURN_COMPLETE = {
    "type": "agent-turn-complete",
    "thread-id": "0199a1b2c3d4",
    "turn-id": "t-1",
    "cwd": "/home/harry/test/tt_pangu",
    "input-messages": ["fix the failing ruff check"],
    "last-assistant-message": "Fixed 3 lint errors in tools/kca/notify.py.",
}


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch) -> None:
    """No test may reach a live bot — see tests/test_notify.py for why."""
    for key in [k for k in os.environ if k.startswith("TELEGRAM")]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    cfg = notify.load_config(REPO_ROOT / ".kca" / "notify.yml")
    cfg["state_dir"] = str(tmp_path / "state")
    cfg["secrets_file"] = str(tmp_path / "secrets.env")
    # agent_notify has no injectable clock, so these tests would otherwise defer
    # every routine push when the suite happens to run at night. start == end
    # means "never quiet"; quiet-hours behaviour itself is covered in
    # tests/test_notify.py.
    cfg["quiet_hours"] = {"timezone": "Australia/Melbourne", "start": "00:00", "end": "00:00"}
    path = tmp_path / "notify.yml"
    path.write_text(notify.yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _run(argv: list[str], stdin: str = "", capsys=None) -> dict:
    code = agent_notify.main(argv)
    assert code == 0, "a notifier must never fail the harness turn it reports on"
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out.startswith("{") else {}


def test_claude_notification_becomes_an_attention_push(config_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(CLAUDE_NOTIFICATION)))
    result = _run(["--source", "claude", "--config", str(config_path), "--dry-run"], capsys=capsys)
    assert result["level"] == "attention"  # bypasses quiet hours: the session is stuck
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "Claude Code" in text and "Notification" in text
    assert "permission to use Bash" in text
    assert "abc123def456" in text  # session id, truncated


def test_codex_turn_complete_becomes_an_info_push(config_path: Path, capsys, monkeypatch) -> None:
    result = _run(
        ["--source", "codex", "--config", str(config_path), "--dry-run", "--content", json.dumps(CODEX_TURN_COMPLETE)],
        capsys=capsys,
    )
    assert result["level"] == "info"  # routine: deduped, capped, deferred at night
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "Codex" in text and "agent-turn-complete" in text
    assert "Fixed 3 lint errors" in text
    assert "fix the failing ruff check" in text


def test_level_and_bot_can_be_overridden(config_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(CLAUDE_NOTIFICATION)))
    result = _run(
        ["--source", "claude", "--config", str(config_path), "--level", "info", "--bot", "bot2", "--dry-run"],
        capsys=capsys,
    )
    assert result["level"] == "info"
    assert next(c for c in result["channels"] if c["channel"] == "telegram")["bot"] == "bot2"


def test_label_names_the_entry(config_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(CLAUDE_NOTIFICATION)))
    result = _run(
        ["--source", "claude", "--config", str(config_path), "--label", "ayla1 · kaggle", "--dry-run"],
        capsys=capsys,
    )
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "ayla1 · kaggle" in text


def test_unknown_event_is_skipped_rather_than_pushed(config_path: Path, capsys, monkeypatch) -> None:
    """An event with no rule should not wake a phone."""
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps({"hook_event_name": "PreToolUse"})))
    assert agent_notify.main(["--source", "claude", "--config", str(config_path), "--dry-run"]) == 0
    captured = capsys.readouterr()
    assert "no level for this event" in captured.err
    assert captured.out.strip() == ""


def test_stop_is_not_wired_to_attention() -> None:
    """#187 §4: every `Stop` is a turn end, not a completed task."""
    assert agent_notify.CLAUDE_EVENT_LEVELS["Stop"] == "info"
    assert agent_notify.CLAUDE_EVENT_LEVELS["StopFailure"] == "attention"


@pytest.mark.parametrize(
    "source, argv, stdin_text",
    [("claude", [], "not json at all"), ("codex", ["{oops"], ""), ("claude", [], "")],
)
def test_malformed_payload_never_fails_the_turn(
    config_path: Path, capsys, monkeypatch, source: str, argv: list[str], stdin_text: str
) -> None:
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_text))
    assert agent_notify.main(["--source", source, "--config", str(config_path), "--dry-run", *argv]) == 0


@pytest.mark.parametrize("stdin_text", ["[]", "null", '"just a string"', "42", '[{"hook_event_name": "Stop"}]'])
def test_valid_json_of_the_wrong_shape_never_fails_the_turn(
    config_path: Path, capsys, monkeypatch, stdin_text: str
) -> None:
    """`[]` is a perfectly valid JSON document; a notifier that dies on one
    takes down the turn it exists to report on."""
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(stdin_text))
    assert agent_notify.main(["--source", "claude", "--config", str(config_path), "--dry-run"]) == 0
    assert "no level for this event" in capsys.readouterr().err


def test_secrets_in_an_event_body_are_redacted(config_path: Path, capsys, monkeypatch) -> None:
    leaky = dict(CLAUDE_NOTIFICATION, message="rerun with 8123456789:AAF_ThisLooksExactlyLikeARealBotToken12345")
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(leaky)))
    result = _run(["--source", "claude", "--config", str(config_path), "--dry-run"], capsys=capsys)
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "8123456789:AAF" not in text
    assert notify.REDACTED in text


def test_a_codex_turn_quoting_an_api_key_does_not_forward_it(config_path: Path, capsys) -> None:
    """With `--content` the prompt and reply are forwarded, so whatever the
    session pasted is exactly what this channel would otherwise transmit."""
    leaky = dict(
        CODEX_TURN_COMPLETE,
        **{
            "input-messages": ["use OPENAI_API_KEY=sk-proj-SENTINEL0123 for the run"],
            "last-assistant-message": "done; CHAT_ID=123456789 was already set",
        },
    )
    result = _run(
        ["--source", "codex", "--config", str(config_path), "--dry-run", "--content", json.dumps(leaky)],
        capsys=capsys,
    )
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "sk-proj-SENTINEL0123" not in text
    assert "123456789" not in text
    assert notify.REDACTED in text


@pytest.mark.parametrize("switch", [[], ["--no-content"]])
def test_session_text_is_not_forwarded_unless_asked_for(
    config_path: Path, capsys, monkeypatch, switch: list[str]
) -> None:
    """#206 F001: redaction masks credential *shapes*, never private data.

    So the default push is metadata only — event and thread id, no prompt, no
    reply — and an operator under a competition's data rules has nothing to
    remember. The deprecated `--no-content` is accepted as the same no-op, so a
    hook line written against the old flag still runs.
    """
    private = dict(
        CODEX_TURN_COMPLETE,
        **{
            "input-messages": ["score PRIVATE_COMPETITION_PAYLOAD row_17 target=1"],
            "last-assistant-message": "row_17 target=1 leaks the private split",
        },
    )
    result = _run(
        ["--source", "codex", "--config", str(config_path), "--dry-run", *switch, json.dumps(private)],
        capsys=capsys,
    )
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "PRIVATE_COMPETITION_PAYLOAD" not in text
    assert "row_17" not in text
    assert "agent-turn-complete" in text
    assert "thread 0199a1b2c3d4" in text


@pytest.mark.parametrize("switch", [["--content"], []])
def test_content_is_forwarded_when_the_owner_opts_in(config_path: Path, capsys, monkeypatch, switch: list[str]) -> None:
    """One documented flag (or env var) still gets you what the session said."""
    if not switch:
        monkeypatch.setenv("KCA_NOTIFY_CONTENT", "1")
    result = _run(
        ["--source", "codex", "--config", str(config_path), "--dry-run", *switch, json.dumps(CODEX_TURN_COMPLETE)],
        capsys=capsys,
    )
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "Fixed 3 lint errors" in text
    assert "fix the failing ruff check" in text


def test_a_claude_notification_still_carries_the_harness_status_line(config_path: Path, capsys, monkeypatch) -> None:
    """#206 F001: metadata-only must still be a useful notification.

    The Claude hook payload has no prompt or reply in it; `message` is the
    harness's own status string, so it is metadata and survives the default.
    """
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(CLAUDE_NOTIFICATION)))
    result = _run(["--source", "claude", "--config", str(config_path), "--dry-run"], capsys=capsys)
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "permission to use Bash" in text
    assert "abc123def456" in text


def test_a_bad_command_line_never_fails_the_turn(config_path: Path, capsys) -> None:
    """#206 F013: argparse exits 2 on a rejected flag; this program never does.

    A stale hook command line — an old flag name after a rename — must degrade to
    "no notification", not to a failed turn.
    """
    assert agent_notify.main(["--source", "invalid"]) == 0
    assert agent_notify.main(["--flag-we-renamed-away", "--source", "claude"]) == 0
    assert agent_notify.main([]) == 0
    assert "bad arguments; nothing sent" in capsys.readouterr().err


def test_a_long_assistant_message_is_clipped_after_redaction(config_path: Path, capsys) -> None:
    """Clip first and a token split in half leaks its prefix; redact first and
    it cannot."""
    tail = "x" * agent_notify.MAX_BODY_CHARS
    leaky = dict(CODEX_TURN_COMPLETE, **{"last-assistant-message": f"ghp_0123456789abcdefghijABCDEFGHIJ0123 {tail}"})
    result = _run(
        ["--source", "codex", "--config", str(config_path), "--dry-run", "--content", json.dumps(leaky)],
        capsys=capsys,
    )
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "ghp_0123456789" not in text
    assert notify.REDACTED in text
