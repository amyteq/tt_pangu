"""M12-T003 — tools/kca/devpost.py adapter (READ_ONLY register / fetch / info).

These tests run without network access and without a live DB. The DB
write path in `register_competition` is exercised via a small in-memory
stub that satisfies the same `db.get_conn()` + `db.get_competition_by_slug()`
+ `db.ensure_competition()` surface the adapter uses. The DB-gated smoke
test in tests/test_m12_smoke.py (M12-T008 scope) will exercise the live
Postgres path against the real `competitions` row.

Tests covered:

1. `fetch_metadata` parses the fixture HTML and returns the four
   canonical fields (`title`, `deadline_utc`, `prize_summary`,
   `submission_format`).
2. `register_competition` is idempotent: calling it twice on the same
   slug yields the same competition_id, the same competition_type, and
   the same `submission_format` ordering.
3. `cmd_info` exits non-zero (EXIT_RUNTIME) with a clean error message
   when the slug is unknown.
4. Sanity: `import tools.kca.devpost` does NOT eagerly import Playwright.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import textwrap
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools" / "kca"
FIXTURE_HTML = REPO_ROOT / "tests" / "fixtures" / "devpost_h01.html"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import devpost as devpost_mod  # noqa: E402  (import after sys.path tweak)


# ---------------------------------------------------------------------------
# In-memory DB stub
# ---------------------------------------------------------------------------


class _StubCursor:
    """Minimal cursor that records UPDATE statements but executes nothing."""

    def __init__(self, store: "_StubDB") -> None:
        self._store = store

    def __enter__(self) -> "_StubCursor":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple) -> None:
        # devpost.register_competition issues a single UPDATE statement;
        # mirror the column writes onto the stub row.
        if sql.strip().startswith("UPDATE competitions"):
            comp_type, deadline, sub_fmt_json, title, comp_id = params
            row = self._store.rows_by_id.get(comp_id)
            if row is None:
                raise AssertionError(f"unknown competition id in stub: {comp_id}")
            row["competition_type"] = comp_type
            row["deadline"] = deadline
            row["submission_format"] = json.loads(sub_fmt_json)
            if title is not None:
                row["title"] = title


class _StubConn:
    def __init__(self, store: "_StubDB") -> None:
        self._store = store

    def __enter__(self) -> "_StubConn":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def cursor(self) -> _StubCursor:
        return _StubCursor(self._store)

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


class _StubDB:
    """Stand-in for `tools.kca.db` (the module devpost imports as `db`)."""

    def __init__(self) -> None:
        self.rows_by_id: dict[str, dict[str, Any]] = {}
        self.rows_by_slug: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def get_conn(self) -> _StubConn:
        return _StubConn(self)

    def ensure_competition(
        self,
        *,
        slug: str,
        platform: str = "kaggle",
        title: str | None = None,
    ) -> str:
        existing = self.rows_by_slug.get(slug)
        if existing:
            if title:
                existing["title"] = existing.get("title") or title
            return existing["id"]
        self._counter += 1
        new_id = f"00000000-0000-0000-0000-{self._counter:012d}"
        row: dict[str, Any] = {
            "id": new_id,
            "slug": slug,
            "platform": platform,
            "title": title,
            "competition_type": "kaggle",
            "deadline": None,
            "submission_format": None,
        }
        self.rows_by_id[new_id] = row
        self.rows_by_slug[slug] = row
        return new_id

    def get_competition_by_slug(self, slug: str) -> dict[str, Any]:
        if slug not in self.rows_by_slug:
            raise KeyError(f"competition slug not found: {slug}")
        return self.rows_by_slug[slug]


@pytest.fixture()
def stub_db(monkeypatch: pytest.MonkeyPatch) -> _StubDB:
    """Patch `devpost.db` (which devpost loads via `import db`) with our stub."""
    stub = _StubDB()
    # The adapter does `import db as _db` inside register_competition and
    # get_competition_row. Patch sys.modules so that import returns our stub.
    monkeypatch.setitem(sys.modules, "db", stub)  # type: ignore[arg-type]
    return stub


@pytest.fixture()
def offline_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace devpost._fetch_html with a fixture-HTML reader.

    Keeps the test fully offline — no requests / no DNS / no playwright.
    """
    html = FIXTURE_HTML.read_text(encoding="utf-8")

    def _fake_fetch(url: str, *, playwright: bool = False, timeout_s: int = 20) -> str:
        if playwright:
            raise AssertionError("offline test must not exercise the playwright branch")
        return html

    monkeypatch.setattr(devpost_mod, "_fetch_html", _fake_fetch)


# ---------------------------------------------------------------------------
# 1. fetch_metadata extracts the four canonical fields
# ---------------------------------------------------------------------------


def test_fetch_metadata_extracts_four_fields(offline_fetch: None) -> None:
    result = devpost_mod.fetch_metadata("sample-hack")
    # Shape: four canonical keys (plus slug + url for traceability).
    for key in ("title", "deadline_utc", "prize_summary", "submission_format"):
        assert key in result, f"missing key {key!r} in fetch_metadata output"

    assert result["slug"] == "sample-hack"
    assert result["url"] == "https://sample-hack.devpost.com/"
    # Title comes from og:title; the fixture's og:title is canonical.
    assert result["title"] == "Sample Devpost Hackathon"
    # Deadline is normalised to UTC (the fixture's -04:00 -> +00:00).
    assert result["deadline_utc"] == "2026-06-30T00:00:00Z"
    # Prize summary should be a non-empty string.
    assert isinstance(result["prize_summary"], str)
    assert "$" in result["prize_summary"]
    # Submission format is an ordered, JSON-safe list of key slugs.
    assert isinstance(result["submission_format"], list)
    assert len(result["submission_format"]) >= 4
    # Keys are lowercase + underscore, no spaces / punctuation.
    for k in result["submission_format"]:
        assert k == k.lower()
        assert " " not in k
        assert k.replace("_", "").isalnum()


# ---------------------------------------------------------------------------
# 2. register_competition is idempotent
# ---------------------------------------------------------------------------


def test_register_competition_idempotent(offline_fetch: None, stub_db: _StubDB) -> None:
    first = devpost_mod.register_competition("sample-hack")
    second = devpost_mod.register_competition("sample-hack")
    assert first["id"] == second["id"]
    assert first["competition_type"] == second["competition_type"] == "devpost"
    assert first["submission_format"] == second["submission_format"]
    # The DB row carries the post-UPDATE values.
    row = stub_db.rows_by_slug["sample-hack"]
    assert row["competition_type"] == "devpost"
    assert row["deadline"] == "2026-06-30T00:00:00Z"
    assert isinstance(row["submission_format"], list)


def test_register_rejects_invalid_competition_type(offline_fetch: None, stub_db: _StubDB) -> None:
    with pytest.raises(ValueError, match="competition_type"):
        devpost_mod.register_competition("sample-hack", competition_type="kaggle")


# ---------------------------------------------------------------------------
# 3. cmd_info exits non-zero with a clean error for an unknown slug
# ---------------------------------------------------------------------------


def test_cmd_info_unknown_slug_exits_nonzero(stub_db: _StubDB) -> None:
    args = argparse.Namespace(slug="nonexistent-slug")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = devpost_mod.cmd_info(args)
    assert rc != 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is False
    assert "nonexistent-slug" in payload["error"]
    # No secret-shaped output.
    assert "password" not in buf.getvalue().lower()
    assert "kaggle_key" not in buf.getvalue().lower()


# ---------------------------------------------------------------------------
# 4. Sanity: importing tools.kca.devpost does NOT pull playwright
# ---------------------------------------------------------------------------


def test_import_devpost_does_not_eagerly_import_playwright() -> None:
    """Spawn a fresh interpreter so the assertion is independent of test ordering.

    The test asserts that after `import devpost`, `playwright` is not yet
    in `sys.modules`. We have to run this in a fresh process because the
    surrounding test process likely has playwright imported already (or
    the import lattice changes between test runs).
    """
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(TOOLS_DIR)!r})
        import devpost  # noqa: F401
        for mod in list(sys.modules):
            if mod == "playwright" or mod.startswith("playwright."):
                raise SystemExit(
                    f"playwright was imported eagerly via 'import devpost' "
                    f"(found module {{mod!r}})"
                )
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"playwright leaked into the import graph: {proc.stdout}{proc.stderr}"


# ---------------------------------------------------------------------------
# Bonus regression: cmd_fetch wires through fetch_metadata cleanly
# ---------------------------------------------------------------------------


def test_cmd_fetch_emits_json_with_four_fields(offline_fetch: None) -> None:
    args = argparse.Namespace(slug="sample-hack", playwright=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = devpost_mod.cmd_fetch(args)
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True
    assert payload["side_effect"] == "READ_ONLY"
    for key in ("title", "deadline_utc", "prize_summary", "submission_format"):
        assert key in payload
