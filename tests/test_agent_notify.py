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
        ["--source", "codex", "--config", str(config_path), "--dry-run", json.dumps(CODEX_TURN_COMPLETE)],
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


def test_secrets_in_an_event_body_are_redacted(config_path: Path, capsys, monkeypatch) -> None:
    leaky = dict(CLAUDE_NOTIFICATION, message="rerun with 8123456789:AAF_ThisLooksExactlyLikeARealBotToken12345")
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(leaky)))
    result = _run(["--source", "claude", "--config", str(config_path), "--dry-run"], capsys=capsys)
    text = next(c for c in result["channels"] if c["channel"] == "telegram")["payload"]["text"]
    assert "8123456789:AAF" not in text
    assert notify.REDACTED in text
