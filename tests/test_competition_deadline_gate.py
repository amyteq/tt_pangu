"""Guardrail: a competition claiming `status: open` must not have a past deadline.

Prevents the drift #195 called out — the same drift PR #201 corrected by hand for
`nvidia-nemotron`, `orbit-wars` and `sec-attack`, where competition.yaml still said
`status: active` months after the submission window closed. Runs alongside the other
`test_competition_contract.py` invariants; no DB, no credentials, no network.

Partial fix for #195 AC #4 — the CI-check half. The data half (three stale
`status:` fields) already landed in #201.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
LIVE = sorted(p for p in (ROOT / "competitions").glob("*/competition.yaml") if not p.parent.name.startswith("_"))


@pytest.mark.parametrize("path", LIVE, ids=lambda p: p.parent.name)
def test_open_status_implies_deadline_not_past(path: Path) -> None:
    record = yaml.safe_load(path.read_text())
    if record.get("status") != "open":
        return
    deadline = record.get("deadline")
    if deadline is None:
        return
    assert isinstance(deadline, _dt.date), f"{path}: deadline must parse as YYYY-MM-DD, got {deadline!r}"
    today = _dt.date.today()
    assert deadline >= today, (
        f"{path.parent.name}: status: open but deadline {deadline} < today {today} — "
        "flip status to `closed` (or `unknown` if the window is uncertain)"
    )
