"""M14-T005 — smart-polling state machine (ADR-0020 §6).

Everything here runs against a MOCKED clock + MOCKED Kaggle responses. No real
Kaggle CLI call and no real ``time.sleep`` ever fires: the watcher's time and
I/O seams (``sleep_fn`` / ``now_fn`` / ``status_fetch`` / ``output_fetch`` /
``list_fetch``) are injected so the cadence is driven deterministically.

Two posture tiers:

- **Pure-Python tier** (most tests) — drives ``_watch_kernel_until_terminal`` /
  ``_watch_many`` directly with fake seams; needs no DB and no Postgres.
- **Ephemeral-Postgres tier** — exercises the telemetry write
  (``queue_time_seconds`` / ``running_time_seconds`` recorded separately on
  ``analysis_jsonb``) and the STALLED slot release (``count_active_pushes``)
  against a fixture competition; SKIPs cleanly when no local Postgres binary
  exists.

A global ``subprocess.run`` sentinel asserts ZERO real Kaggle ``kernels
push`` / ``competitions submit`` lines are reached on any path.

Run with:
    python -m pytest tests/test_m14_polling.py -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "0011_m14_goal_loop.sql"
_PG_BINS_PRESENT = all(shutil.which(b) for b in ("initdb", "pg_ctl", "postgres"))

_REAL_KAGGLE_PREFIXES = (
    ["kaggle", "kernels", "push"],
    ["kaggle", "competitions", "submit"],
)


@pytest.fixture(autouse=True)
def _no_real_kaggle(monkeypatch):
    """Hard sentinel: fail loudly if any test reaches a real Kaggle push/submit."""
    import kg

    real_run = subprocess.run

    def _guard(argv, *a, **kw):
        if isinstance(argv, (list, tuple)):
            head = list(argv)[:3]
            for prefix in _REAL_KAGGLE_PREFIXES:
                if head[: len(prefix)] == prefix:
                    raise AssertionError(f"a real Kaggle command leaked: {head}")
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(kg.subprocess, "run", _guard)
    return _guard


# ---------------------------------------------------------------------------
# Mocked-clock + mocked-CLI harness.
# ---------------------------------------------------------------------------


class FakeClock:
    """Monotonic clock advanced only by the watcher's own ``sleep_fn`` calls."""

    def __init__(self):
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def _output_fetch_factory(tmp_dir, *, terminal_after: int, blob: bytes = b"x" * 200):
    """Return an output_fetch that writes a >100B log only on poll N (1-indexed).

    Polls before ``terminal_after`` leave the log absent (run not terminal);
    on/after it, the log is written with ``blob`` so the size>100 oracle fires.
    ``terminal_after = 0`` means never terminal (status-only / stall scenarios).
    """
    state = {"calls": 0}

    def _fetch(kernel_ref, _tmp):
        state["calls"] += 1
        log_path = Path(tmp_dir) / f"{kernel_ref.split('/')[-1]}.log"
        try:
            if log_path.exists():
                log_path.unlink()
        except OSError:
            pass
        if terminal_after and state["calls"] >= terminal_after:
            log_path.write_bytes(blob)
        return log_path

    return _fetch


# ---------------------------------------------------------------------------
# Fibonacci ramp + cap (pure unit).
# ---------------------------------------------------------------------------


def test_fibonacci_ramp_sequence_and_cap():
    import kg

    # est_queue = 1800s (default 15min) -> cap = 600s. Ramp 60,90,150,240,390,
    # 630->capped to 600, then holds 600.
    gen = kg._fibonacci_queued_cadence(cap_seconds=600)
    seq = [next(gen) for _ in range(8)]
    assert seq == [60, 90, 150, 240, 390, 600, 600, 600]


def test_fibonacci_cap_floor_for_tiny_estimate():
    import kg

    # A tiny cap floors at 60 so the first wait is always sane.
    gen = kg._fibonacci_queued_cadence(cap_seconds=5)
    seq = [next(gen) for _ in range(3)]
    assert seq == [60, 60, 60]


# ---------------------------------------------------------------------------
# QUEUED -> RUNNING -> TERMINAL cadence with the mocked clock.
# ---------------------------------------------------------------------------


def test_queued_ramp_then_running_then_terminal():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    # status_fetch script: 2 QUEUED ticks, then RUNNING for the rest.
    status_script = iter(
        [
            (200, "status: queued"),
            (200, "status: queued"),
            (200, "status: running"),
            (200, "status: running"),
            (200, "status: running"),
            (200, "status: running"),
        ]
    )

    def status_fetch(_ref):
        try:
            return next(status_script)
        except StopIteration:
            return (200, "status: running")

    # Terminal log appears on the 5th output poll.
    output_fetch = _output_fetch_factory(tmp, terminal_after=5)

    result = kg._watch_kernel_until_terminal(
        "u/synthetic",
        max_minutes=600,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,  # cap = 600
    )

    assert result["terminal"] is True
    assert result["stalled"] is False
    assert result["state"] == "terminal"
    # cadence: two QUEUED Fibonacci waits (60, 90) while queued, then RUNNING
    # 300s waits until terminal on poll 5.
    assert result["cadence"] == [60, 90, 300, 300]
    # queue_time + running_time recorded separately and add up sensibly.
    assert result["queue_time_seconds"] is not None
    assert result["running_time_seconds"] is not None
    shutil.rmtree(tmp, ignore_errors=True)


def test_running_cadence_is_stable_300():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    def status_fetch(_ref):
        return (200, "running")

    output_fetch = _output_fetch_factory(tmp, terminal_after=4)
    result = kg._watch_kernel_until_terminal(
        "u/run",
        max_minutes=600,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    # Immediately RUNNING -> every cadence step is the stable 300s.
    assert result["cadence"] == [300, 300, 300]
    assert result["terminal"] is True
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 500/503 ignored as non-terminal, no state change.
# ---------------------------------------------------------------------------


def test_500_does_not_change_state_or_exit():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    calls = {"status": 0}

    def status_fetch(_ref):
        calls["status"] += 1
        # Always 500 — must never be read as terminal nor flip state to RUNNING.
        return (500, "500 - Internal Server Error")

    # Terminal only appears via the output oracle on poll 4 — proving the 500s
    # never short-circuited the loop into an early exit/error.
    output_fetch = _output_fetch_factory(tmp, terminal_after=4)
    result = kg._watch_kernel_until_terminal(
        "u/fivehundred",
        max_minutes=600,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    assert result["terminal"] is True
    assert result["stalled"] is False
    # State stayed QUEUED throughout (500 never advanced it to RUNNING), so the
    # cadence is the pure Fibonacci ramp, not the 300s RUNNING cadence.
    assert result["cadence"] == [60, 90, 150]
    assert all(c in (60, 90, 150, 240, 390, 600) for c in result["cadence"])
    shutil.rmtree(tmp, ignore_errors=True)


def test_503_also_non_terminal():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    def status_fetch(_ref):
        return (503, "503 Service Unavailable")

    output_fetch = _output_fetch_factory(tmp, terminal_after=2)
    result = kg._watch_kernel_until_terminal(
        "u/fiveohthree",
        max_minutes=600,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    assert result["terminal"] is True
    assert result["cadence"] == [60]  # one QUEUED wait, then terminal on poll 2
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# output-size>0 (>100B) terminal fallback when status NEVER returns 200 (M10).
# ---------------------------------------------------------------------------


def test_output_size_terminal_when_status_never_200():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    def status_fetch(_ref):
        # The M10 case: status API 500s forever; only the output oracle works.
        return (500, "500 - Internal Server Error")

    output_fetch = _output_fetch_factory(tmp, terminal_after=3)
    result = kg._watch_kernel_until_terminal(
        "u/m10case",
        max_minutes=600,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    assert result["terminal"] is True
    assert result["log_path"] is not None
    # A log <=100B must NOT be read as terminal.
    shutil.rmtree(tmp, ignore_errors=True)


def test_small_log_is_not_terminal():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    # Output writes only a tiny (<=100B) log every poll: never terminal, so the
    # watcher must stall out at max_minutes rather than declaring terminal.
    def output_fetch(kernel_ref, _tmp):
        log_path = Path(tmp) / f"{kernel_ref.split('/')[-1]}.log"
        log_path.write_bytes(b"tiny")
        return log_path

    def status_fetch(_ref):
        return (200, "queued")

    result = kg._watch_kernel_until_terminal(
        "u/tiny",
        max_minutes=2,  # short so the stall is quick under the mocked clock
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=60,  # cap=20 -> floored to 60 cadence
    )
    assert result["terminal"] is False
    assert result["stalled"] is True
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# STALLED: QUEUED past max_poll_minutes -> exit non-terminal.
# ---------------------------------------------------------------------------


def test_stall_when_queued_past_max_minutes():
    import kg

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    def status_fetch(_ref):
        return (200, "queued")  # forever QUEUED

    output_fetch = _output_fetch_factory(tmp, terminal_after=0)  # never terminal
    result = kg._watch_kernel_until_terminal(
        "u/staller",
        max_minutes=5,  # 300s budget
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    assert result["terminal"] is False
    assert result["stalled"] is True
    assert result["state"] == "stalled"
    # queue_time recorded even on stall so the estimator still gets a sample.
    assert result["queue_time_seconds"] is not None
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# _watch_many: ONE kernels list per tick for >= 2 slugs.
# ---------------------------------------------------------------------------


def test_watch_many_one_list_per_tick():
    import kg

    clock = FakeClock()
    # Scripted list responses: tick 1 both queued; tick 2 a running, b complete;
    # tick 3 a complete.
    script = iter(
        [
            {"a": "queued", "b": "queued"},
            {"a": "running", "b": "complete"},
            {"a": "complete", "b": "complete"},
        ]
    )

    def list_fetch():
        try:
            return next(script)
        except StopIteration:
            return {"a": "complete", "b": "complete"}

    result = kg._watch_many(
        ["u/a", "u/b"],
        max_minutes=600,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        list_fetch=list_fetch,
        est_queue_seconds=1800,
    )
    # Exactly ONE list call per tick.
    assert result["list_calls"] == result["polls"]
    assert result["slugs"]["a"]["terminal"] is True
    assert result["slugs"]["b"]["terminal"] is True
    # 3 ticks were enough; only 2 sleeps happened (no sleep after the final tick).
    assert result["polls"] == 3
    assert len(clock.slept) == 2


def test_watch_many_requires_two_slugs():
    import kg

    with pytest.raises(ValueError):
        kg._watch_many(["u/only-one"])


def test_single_slug_uses_one_slug_watcher_not_watch_many(monkeypatch):
    """The single-slug auto-watch path calls _watch_kernel_until_terminal, never
    _watch_many (ADR-0020 §6: _watch_many activates only at >= 2 slugs)."""
    import argparse

    import kg

    called = {"watch_one": 0, "watch_many": 0}

    def fake_watch_one(kernel_ref, **kw):
        called["watch_one"] += 1
        return {"terminal": True, "stalled": False, "state": "terminal"}

    def fake_watch_many(*a, **kw):
        called["watch_many"] += 1
        return {}

    monkeypatch.setattr(kg, "_watch_kernel_until_terminal", fake_watch_one)
    monkeypatch.setattr(kg, "_watch_many", fake_watch_many)

    # Drive cmd_push's auto-watch wiring through a stubbed successful push.
    def fake_run(argv, *a, **kw):
        class P:
            returncode = 0
            stdout = "Kernel version 1 successfully pushed"
            stderr = ""

        return P()

    monkeypatch.setattr(kg.subprocess, "run", fake_run)
    monkeypatch.setenv("KCA_ALLOW_REMOTE", "1")  # bypass approval for the test
    monkeypatch.setenv("KAGGLE_USERNAME", "u")
    monkeypatch.setenv("KAGGLE_KEY", "k")

    tmp = tempfile.mkdtemp(prefix="m14push_")
    (Path(tmp) / "kernel-metadata.json").write_text('{"id": "u/single"}')
    args = argparse.Namespace(
        kernel_dir=tmp,
        competition=None,
        dry_run=False,
        watch=True,
        poll_seconds=60,
        max_poll_minutes=60,
        run_id=None,
    )
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        kg.cmd_push(args)
    assert called["watch_one"] == 1
    assert called["watch_many"] == 0
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Ephemeral-Postgres tier: telemetry + STALLED slot release.
# ---------------------------------------------------------------------------

_PREREQ_SQL = """
CREATE TABLE competitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  platform text DEFAULT 'kaggle',
  slug text UNIQUE,
  title text,
  max_daily_submissions int,
  max_concurrent_pushes int,
  last_rules_fetch_at timestamptz
);
CREATE TABLE experiments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id uuid REFERENCES competitions(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE experiment_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid REFERENCES experiments(id),
  metrics jsonb DEFAULT '{}',
  analysis text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id uuid REFERENCES competitions(id),
  file_path text,
  public_lb_score numeric(10,6),
  status text DEFAULT 'prepared',
  submitted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
"""


@pytest.fixture(scope="module")
def pg_url():
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries (initdb/pg_ctl/postgres) on PATH")
    tmp = tempfile.mkdtemp(prefix="m14poll_pg_")
    datadir = os.path.join(tmp, "data")
    sock = os.path.join(tmp, "sock")
    os.makedirs(sock, exist_ok=True)
    logfile = os.path.join(tmp, "pg.log")
    try:
        subprocess.run(
            ["initdb", "-D", datadir, "-U", "postgres", "--auth=trust"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                datadir,
                "-l",
                logfile,
                "-w",
                "-t",
                "30",
                "start",
                "-o",
                f"-c listen_addresses='' -c unix_socket_directories='{sock}'",
            ],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"could not boot ephemeral Postgres (likely sandboxed): {exc}")
    url = f"postgresql://postgres@/postgres?host={sock}"
    try:
        import psycopg

        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(_PREREQ_SQL)
                cur.execute(MIGRATION.read_text())
        yield url
    finally:
        subprocess.run(["pg_ctl", "-D", datadir, "-w", "stop"], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def kg_db(pg_url, monkeypatch):
    monkeypatch.setenv("SUPABASE_DB_URL", pg_url)
    monkeypatch.setenv("KCA_DB_TARGET", "local")
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")
    import db
    import kg

    return kg, db


def _new_comp_with_run(pg_url, *, slug):
    """Insert a competition + experiment + run; return (comp_id, run_id)."""
    import psycopg

    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO competitions (slug) VALUES (%s) RETURNING id::text",
                (slug,),
            )
            comp_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO experiments (competition_id) VALUES (%s::uuid) RETURNING id::text",
                (comp_id,),
            )
            exp_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO experiment_runs (experiment_id) VALUES (%s::uuid) RETURNING id::text",
                (exp_id,),
            )
            run_id = cur.fetchone()[0]
    return comp_id, run_id


def test_queue_and_running_time_recorded_separately(kg_db, pg_url):
    """A synthetic kernel records queue_time_seconds AND running_time_seconds as
    two distinct keys on experiment_runs.analysis_jsonb."""
    kg, db = kg_db
    slug = f"tele-{uuid.uuid4().hex[:8]}"
    _comp_id, run_id = _new_comp_with_run(pg_url, slug=slug)

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()
    status_script = iter(
        [
            (200, "queued"),
            (200, "running"),
            (200, "running"),
        ]
    )

    def status_fetch(_ref):
        try:
            return next(status_script)
        except StopIteration:
            return (200, "running")

    output_fetch = _output_fetch_factory(tmp, terminal_after=3)
    result = kg._watch_kernel_until_terminal(
        f"kca/{slug}",
        max_minutes=600,
        run_id=run_id,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    assert result["terminal"] is True

    stored = db.get_run_analysis_jsonb(run_id)
    assert stored is not None
    assert "queue_time_seconds" in stored
    assert "running_time_seconds" in stored
    # Two distinct, non-null, positive values — recorded SEPARATELY.
    assert stored["queue_time_seconds"] is not None
    assert stored["running_time_seconds"] is not None
    assert stored["queue_time_seconds"] != stored["running_time_seconds"]
    shutil.rmtree(tmp, ignore_errors=True)


def test_stall_releases_slot_via_count_active_pushes(kg_db, pg_url):
    """A kernel still QUEUED past max_poll_minutes is marked `stalled`, and the
    slot is released (count_active_pushes drops it)."""
    import psycopg

    kg, db = kg_db
    slug = f"stallcomp-{uuid.uuid4().hex[:8]}"
    comp_id, _run_id = _new_comp_with_run(pg_url, slug=slug)
    # One active submission for the kernel slug, holding a concurrency slot.
    kernel_slug = "stallkernel"
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "created_at) VALUES (%s::uuid, %s, 'queued', now())",
                (comp_id, f"kca/{kernel_slug}.ipynb"),
            )

    assert db.count_active_pushes(comp_id) == 1  # slot occupied

    tmp = tempfile.mkdtemp(prefix="m14poll_")
    clock = FakeClock()

    def status_fetch(_ref):
        return (200, "queued")  # forever queued

    output_fetch = _output_fetch_factory(tmp, terminal_after=0)
    result = kg._watch_kernel_until_terminal(
        f"kca/{kernel_slug}",
        max_minutes=5,
        competition=slug,
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        status_fetch=status_fetch,
        output_fetch=output_fetch,
        est_queue_seconds=1800,
    )
    assert result["stalled"] is True
    # Slot released: the stalled submission no longer counts as active.
    assert db.count_active_pushes(comp_id) == 0
    shutil.rmtree(tmp, ignore_errors=True)
