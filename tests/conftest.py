"""Shared pytest fixtures for kca tests."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = REPO_ROOT / "runs"


@pytest.fixture
def unique_competition() -> str:
    """Return a unique competition slug for filesystem + DB isolation."""
    return f"smoke_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_run_dir(unique_competition: str) -> Iterator[str]:
    """Clean up runs/<competition>/ after the test."""
    yield unique_competition
    target = RUNS_ROOT / unique_competition
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


@pytest.fixture(scope="session")
def db_url() -> str:
    """Return the SUPABASE_DB_URL from env. Test files using this fixture should
    also be guarded by `@requires_db` so they skip cleanly when unset.
    """
    return os.environ.get("SUPABASE_DB_URL") or ""
