"""M14-T001 smoke tests — goal-loop schema (0011) + DB helpers.

Two posture tiers:

1. **Ephemeral-Postgres tier** — when the `initdb` / `pg_ctl` / `postgres`
   binaries are on PATH, the module spins up a throwaway Postgres cluster in
   a tempdir, applies the M14-T001 prerequisite tables + `0011_m14_goal_loop.sql`,
   and exercises every helper against real Postgres (partial-unique refusal,
   UTC-day submission window, analysis_jsonb merge, count_active_pushes,
   refresh_competition_rules with a stubbed Kaggle view). SKIPs cleanly when
   no local Postgres binary exists.

2. **Pure-Python tier** — input validation + the audit-grep invariant that
   `refresh_competition_rules` reaches no `kaggle competitions submit` /
   `kaggle kernels push`. Runs in any environment.

Run with:
    python -m pytest tests/test_m14_db.py -v
"""

from __future__ import annotations

import datetime as dt
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

# Minimal FK-target schema the 0011 migration layers onto (subset of the
# 0001/0004 shapes that matter for these helpers).
# M14-T009: this prereq is cloud-faithful for the columns the M14 DB helpers
# touch — submissions.project_id is NOT NULL (finding #3), agent_jobs has NO
# competition_id column (finding #3), and the casing of submission status is
# left to the helper. The earlier permissive fixtures masked these.
_PREREQ_SQL = """
CREATE TABLE projects (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text);
CREATE TABLE competitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  platform text DEFAULT 'kaggle',
  slug text UNIQUE,
  title text,
  max_daily_submissions int,
  last_rules_fetch_at timestamptz
);
CREATE TABLE experiments (id uuid PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE experiment_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid,
  metrics jsonb DEFAULT '{}',
  analysis text
);
CREATE TABLE submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL,
  competition_id uuid REFERENCES competitions(id),
  run_id uuid,
  job_id uuid,
  cv_score numeric,
  note text,
  file_path text,
  public_lb_score numeric(10,6),
  status text DEFAULT 'prepared',
  submitted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE agent_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL,
  session_id uuid,
  status text NOT NULL DEFAULT 'queued',
  priority int NOT NULL DEFAULT 0,
  job_type text NOT NULL DEFAULT 'agent',
  payload jsonb NOT NULL DEFAULT '{}',
  attempts int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 1,
  due_at timestamptz NOT NULL DEFAULT now(),
  prompt text,
  model text NOT NULL DEFAULT 'claude-sonnet-4-6',
  turns_used int NOT NULL DEFAULT 0,
  cost_usd numeric NOT NULL DEFAULT 0,
  policy jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
-- Test convenience: a direct INSERT that omits project_id but names a
-- competition_id inherits the competition's project (mirrors how the cloud
-- helper derives it). project_id remains NOT NULL so a truly orphan row fails.
CREATE FUNCTION _fill_submission_project() RETURNS trigger AS $$
BEGIN
  IF NEW.project_id IS NULL AND NEW.competition_id IS NOT NULL THEN
    SELECT project_id INTO NEW.project_id FROM competitions WHERE id = NEW.competition_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER _trg_fill_submission_project BEFORE INSERT ON submissions
  FOR EACH ROW EXECUTE FUNCTION _fill_submission_project();
"""


@pytest.fixture(scope="module")
def pg_url():
    """Boot an ephemeral Postgres; yield its conninfo; tear down at module end."""
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries (initdb/pg_ctl/postgres) on PATH")
    tmp = tempfile.mkdtemp(prefix="m14pg_")
    datadir = os.path.join(tmp, "data")
    sock = os.path.join(tmp, "sock")
    os.makedirs(sock, exist_ok=True)
    logfile = os.path.join(tmp, "pg.log")
    # A sandboxed CI runner may forbid postgres from binding a socket / writing
    # its data dir; SKIP cleanly rather than error so the no-DB job stays green.
    # (Locally, run with the sandbox disabled to exercise this tier.)
    try:
        subprocess.run(
            ["initdb", "-D", datadir, "-U", "postgres", "--auth=trust"],
            check=True,
            capture_output=True,
        )
        # `-l <logfile>` is load-bearing: pg_ctl daemonizes postgres, which
        # would otherwise inherit subprocess's captured stdout/stderr pipes and
        # deadlock `-w` (wait-for-ready) because the daemon never closes them.
        # Redirecting the server log to a file detaches it from the pipe.
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
                # apply twice — idempotency under the same process
                cur.execute(MIGRATION.read_text())
        yield url
    finally:
        subprocess.run(["pg_ctl", "-D", datadir, "-w", "stop"], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def db(pg_url, monkeypatch):
    """Import the kca db module bound to the ephemeral Postgres."""
    monkeypatch.setenv("SUPABASE_DB_URL", pg_url)
    monkeypatch.setenv("KCA_DB_TARGET", "local")
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")
    import db as _db

    return _db


@pytest.fixture
def competition_id(db):
    import psycopg

    slug = f"m14-test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO projects (name) VALUES ('m14-test') RETURNING id::text")
            project_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO competitions (slug, project_id) VALUES (%s, %s::uuid) RETURNING id::text",
                (slug, project_id),
            )
            return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Ephemeral-Postgres tier
# ---------------------------------------------------------------------------


def test_create_goal_and_get_active(db, competition_id):
    gid = db.create_goal(
        competition_id,
        target_lb_score=0.85,
        target_lb_rank=30,
        target_rank_kind="percentile",
        exit_strategy="first_reached",
    )
    assert gid
    active = db.get_active_goal(competition_id)
    assert active is not None
    assert str(active["id"]) == gid
    assert float(active["target_lb_score"]) == pytest.approx(0.85)
    assert active["exit_strategy"] == "first_reached"
    assert active["max_total_pushes"] == 20
    assert active["stuck_threshold"] == 3


def test_second_active_goal_refused(db, competition_id):
    db.create_goal(competition_id, target_lb_score=0.5, exit_strategy="score_only")
    with pytest.raises(db.ActiveGoalExists):
        db.create_goal(competition_id, target_lb_score=0.6, exit_strategy="score_only")


def test_close_goal_frees_the_slot(db, competition_id):
    g1 = db.create_goal(competition_id, target_lb_score=0.5, exit_strategy="score_only")
    db.close_goal(g1, status="reached", reason="hit target")
    assert db.get_active_goal(competition_id) is None
    # a new active goal is now allowed
    g2 = db.create_goal(competition_id, target_lb_score=0.9, exit_strategy="score_only")
    assert g2 != g1


def test_update_goal_partial(db, competition_id):
    gid = db.create_goal(competition_id, target_lb_score=0.5, exit_strategy="score_only")
    db.update_goal(gid, target_lb_score=0.7, stuck_threshold=5)
    active = db.get_active_goal(competition_id)
    assert float(active["target_lb_score"]) == pytest.approx(0.7)
    assert active["stuck_threshold"] == 5


def test_count_today_submissions_utc_window(db, competition_id):
    """A submission just-before vs just-after UTC midnight is counted correctly."""
    now = dt.datetime.now(dt.timezone.utc)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    just_after_midnight = today_midnight + dt.timedelta(minutes=1)
    just_before_midnight = today_midnight - dt.timedelta(minutes=1)  # yesterday
    tomorrow = today_midnight + dt.timedelta(days=1, minutes=1)  # next UTC day

    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            for ts in (just_after_midnight, just_before_midnight, tomorrow, now):
                cur.execute(
                    "INSERT INTO submissions (competition_id, file_path, status, "
                    "submitted_at) VALUES (%s::uuid, %s, 'complete', %s)",
                    (competition_id, f"sub-{ts.isoformat()}.csv", ts),
                )
            # a prepared row with no submitted_at must NOT count
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status) "
                "VALUES (%s::uuid, 'prepared.csv', 'prepared')",
                (competition_id,),
            )

    n = db.count_today_submissions(competition_id)
    # just_after_midnight + now == 2 today; yesterday + tomorrow + prepared excluded
    assert n == 2, f"expected 2 in the UTC day window, got {n}"


def test_count_active_pushes(db, competition_id):
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            # slug A: latest is running -> active
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, created_at)"
                " VALUES (%s::uuid,'kca/a','queued', now() - interval '2 min')",
                (competition_id,),
            )
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, created_at)"
                " VALUES (%s::uuid,'kca/a','running', now())",
                (competition_id,),
            )
            # slug B: latest is complete -> not active
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, created_at)"
                " VALUES (%s::uuid,'kca/b','complete', now())",
                (competition_id,),
            )
            # slug C: latest is stalled -> not active
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, created_at)"
                " VALUES (%s::uuid,'kca/c','stalled', now())",
                (competition_id,),
            )
    assert db.count_active_pushes(competition_id) == 1


def test_count_active_pushes_normalizes_status_casing(db, competition_id):
    """Regression for M14-T009 finding #4: enum-repr / upper-case terminal
    statuses must normalize to terminal and not be miscounted as active."""
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            for slug_path, status in (
                ("kca/a", "SubmissionStatus.COMPLETE"),
                ("kca/b", "COMPLETE"),
                ("kca/c", "Complete"),
            ):
                cur.execute(
                    "INSERT INTO submissions (competition_id, file_path, status, "
                    "created_at) VALUES (%s::uuid,%s,%s, now())",
                    (competition_id, slug_path, status),
                )
    assert db.count_active_pushes(competition_id) == 0


def test_create_submission_populates_project_id(db, competition_id):
    """Regression for M14-T009 finding #3: submissions.project_id is NOT NULL
    on cloud; create_submission must derive it from the competition's project."""
    import psycopg

    sub_id = db.create_submission(competition_id, "kca/derived.csv", cv_score=0.5, note="t009")
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.project_id::text, c.project_id::text "
                "FROM submissions s JOIN competitions c ON c.id = s.competition_id "
                "WHERE s.id = %s::uuid",
                (sub_id,),
            )
            sub_proj, comp_proj = cur.fetchone()
    assert sub_proj is not None
    assert sub_proj == comp_proj


def test_create_submission_rejects_competition_without_project(db):
    """If a competition has no project_id, create_submission must raise rather
    than violate the NOT NULL constraint."""
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO competitions (slug) VALUES (%s) RETURNING id::text",
                (f"no-proj-{uuid.uuid4().hex[:8]}",),
            )
            orphan_comp = cur.fetchone()[0]
    with pytest.raises(ValueError, match="project_id"):
        db.create_submission(orphan_comp, "kca/orphan.csv")


def test_create_job_no_competition_id_column(db, competition_id):
    """Regression for M14-T009 finding #3: agent_jobs has NO competition_id
    column on cloud; create_job must store the linkage inside payload."""
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM competitions WHERE id = %s::uuid", (competition_id,))
            slug = cur.fetchone()[0]
            cur.execute("INSERT INTO projects (name) VALUES ('jobproj') RETURNING id::text")
            project_id = cur.fetchone()[0]

    job_id = db.create_job(
        project_id,
        prompt="explore",
        policy={"k": 1},
        competition_slug=slug,
    )
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload ->> 'competition_slug', payload ->> 'competition_id' "
                "FROM agent_jobs WHERE id = %s::uuid",
                (job_id,),
            )
            payload_slug, payload_comp = cur.fetchone()
    assert payload_slug == slug
    assert payload_comp == competition_id


def test_analysis_jsonb_roundtrip(db, competition_id):
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO experiment_runs (analysis) VALUES ('M10 free-text survives') RETURNING id::text")
            run_id = cur.fetchone()[0]
    batch = str(uuid.uuid4())
    db.set_run_analysis_jsonb(run_id, exploration_batch_id=batch, queue_time_seconds=42)
    db.set_run_analysis_jsonb(run_id, running_time_seconds=300)  # merge, not clobber
    blob = db.get_run_analysis_jsonb(run_id)
    assert blob["exploration_batch_id"] == batch
    assert blob["queue_time_seconds"] == 42
    assert blob["running_time_seconds"] == 300

    # analysis text column left untouched (ADR-0020 §3)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT analysis FROM experiment_runs WHERE id = %s::uuid", (run_id,))
            assert cur.fetchone()[0] == "M10 free-text survives"


def test_refresh_competition_rules_writes_columns(db, competition_id, monkeypatch):
    """refresh_competition_rules maps a stubbed Kaggle view into 0011 columns."""

    class _FakeView:
        deadline = "2026-07-01T23:59:00Z"
        maxDailySubmissions = 5
        rulesUrl = "https://www.kaggle.com/competitions/tpu/rules"
        evaluationMetric = "macro_f1"

    # find the competition's slug
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM competitions WHERE id = %s::uuid", (competition_id,))
            comp_slug = cur.fetchone()[0]

    # stub the Kaggle call (READ_ONLY); never touches the real API
    monkeypatch.setattr(
        db,
        "_fetch_competition_view",
        lambda s: db._map_competition_view(_FakeView(), s),
    )
    written = db.refresh_competition_rules(comp_slug)
    assert written["rows_updated"] == 1
    assert written["max_daily_submissions"] == 5
    assert written["rules_summary_url"].endswith("/rules")
    assert written["submission_format"]["kind"] == "csv"

    comp = db.get_competition_by_slug(comp_slug)
    assert comp["max_daily_submissions"] == 5
    assert comp["last_rules_fetch_at"] is not None
    assert comp["submission_format"]["evaluation_metric"] == "macro_f1"


# ---------------------------------------------------------------------------
# Pure-Python tier (no DB)
# ---------------------------------------------------------------------------


def test_create_goal_rejects_bad_exit_strategy():
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    import db as _db

    with pytest.raises(ValueError):
        _db.create_goal("00000000-0000-0000-0000-000000000001", exit_strategy="nope")


def test_close_goal_rejects_active_status():
    import db as _db

    with pytest.raises(ValueError):
        _db.close_goal("00000000-0000-0000-0000-000000000001", status="active")


def test_map_competition_view_tolerates_missing_fields():
    import db as _db

    class _Bare:
        pass

    out = _db._map_competition_view(_Bare(), "some-slug")
    # rules_summary_url is synthesized from the slug even when nothing is set
    assert out["rules_summary_url"].endswith("some-slug/rules")
    assert out["max_daily_submissions"] is None
    assert out["submission_format"] is None


def test_refresh_rules_reaches_no_kaggle_write(monkeypatch):
    """Audit-grep invariant (M10-T007): the rules path never shells out to
    `kaggle competitions submit` / `kaggle kernels push`. We assert the
    helper's only Kaggle touchpoint is `competition_view`."""
    import db as _db

    calls: list[tuple] = []

    class _FakeApi:
        def authenticate(self):
            calls.append(("authenticate",))

        def competition_view(self, slug):
            calls.append(("competition_view", slug))

            class _V:
                ref = slug

            return _V()

        def competition_submit(self, *a, **k):  # pragma: no cover - must not run
            calls.append(("competition_submit", a, k))
            raise AssertionError("competition_submit must not be called")

        def kernels_push(self, *a, **k):  # pragma: no cover - must not run
            calls.append(("kernels_push", a, k))
            raise AssertionError("kernels_push must not be called")

    fake_module = type(sys)("kaggle")
    fake_module.api = _FakeApi()
    monkeypatch.setitem(sys.modules, "kaggle", fake_module)

    parsed = _db._fetch_competition_view("tpu-getting-started")
    assert parsed["rules_summary_url"].endswith("tpu-getting-started/rules")
    ops = [c[0] for c in calls]
    assert "competition_view" in ops
    assert "competition_submit" not in ops
    assert "kernels_push" not in ops


def test_fetch_competition_view_unsupported_api_degrades(monkeypatch):
    """M14-T009 finding #6: when the installed Kaggle CLI (2.0.x) lacks
    competition_view, _fetch_competition_view raises a typed KaggleApiUnsupported
    instead of an AttributeError traceback."""
    import db as _db

    class _ApiNoView:
        def authenticate(self):  # pragma: no cover - must not be reached
            raise AssertionError("authenticate must not run when API is unsupported")

    fake_module = type(sys)("kaggle")
    fake_module.__version__ = "2.0.1"
    fake_module.api = _ApiNoView()
    monkeypatch.setitem(sys.modules, "kaggle", fake_module)

    with pytest.raises(_db.KaggleApiUnsupported, match="competition_view"):
        _db._fetch_competition_view("tpu-getting-started")


def test_cmd_refresh_rules_degrades_cleanly_on_unsupported_api(monkeypatch, capsys):
    """The `kca competition refresh-rules` CLI emits a clean degraded envelope
    (no crash) when the Kaggle API surface is unsupported (finding #6)."""
    import json as _json

    import competition as _comp
    import db as _db

    class _FakeDb:
        KaggleApiUnsupported = _db.KaggleApiUnsupported

        def get_competition_by_slug(self, slug):
            return {"slug": slug}

        def refresh_competition_rules(self, slug):
            raise _db.KaggleApiUnsupported("kaggle.api has no 'competition_view' (installed version: 2.0.1)")

    monkeypatch.setattr(_comp, "_load_db", lambda: _FakeDb())

    args = type("A", (), {"slug": "tpu-getting-started"})()
    rc = _comp.cmd_refresh_rules(args)
    assert rc != 0  # EXIT_RUNTIME — a refusal, not a success
    out = capsys.readouterr().out
    payload = _json.loads([ln for ln in out.splitlines() if ln.strip().startswith("{")][-1])
    assert payload["ok"] is False
    assert payload["error_code"] == "KAGGLE_API_UNSUPPORTED"
    assert payload["degraded"] is True
    assert "competition_view" in payload["error"]
