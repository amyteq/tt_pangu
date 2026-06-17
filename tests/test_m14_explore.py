"""M14-T003 tests — kca explore {init, run, rank, prune} + search-space expansion.

Two posture tiers (mirrors tests/test_m14_db.py):

1. **Pure-Python tier** — search-space cross-product / deterministic random
   sub-sample, baseline.py templating, the synthetic dry-run screener, and the
   audit-grep invariant that explore.py reaches no `kaggle kernels push` /
   `kaggle competitions submit`. Runs anywhere.

2. **Ephemeral-Postgres tier** — boots a throwaway Postgres cluster, applies a
   minimal FK-target schema + `0011_m14_goal_loop.sql`, and exercises the full
   init -> run(--dry-run) -> rank -> prune lifecycle against real Postgres via
   the kca CLI subprocess. SKIPs cleanly when no Postgres binary is on PATH.

Run with:
    python -m pytest tests/test_m14_explore.py -v
"""

from __future__ import annotations

import json
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

import explore  # noqa: E402

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "0011_m14_goal_loop.sql"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tpu-getting-started" / "search-space.yaml"
FIXTURE_SAMPLE = REPO_ROOT / "tests" / "fixtures" / "tpu-getting-started" / "search-space-sample.yaml"
KCA = REPO_ROOT / "tools" / "kca" / "kca.py"

_PG_BINS_PRESENT = all(shutil.which(b) for b in ("initdb", "pg_ctl", "postgres"))

# Minimal FK-target schema the 0011 migration layers onto + the M2/M4 columns
# explore.py reads/writes (experiments.competition_id, experiment_runs.status).
# NOTE (M14-T009): experiment_runs.status is a real run_status ENUM here —
# {queued,running,succeeded,failed,cancelled} — to FAITHFULLY mirror the cloud
# schema. The earlier `status text` fixture masked the bug where explore wrote
# the non-enum values 'planned'/'screened' (M14-T009 finding #2). submissions
# also carries a NOT NULL project_id, matching cloud (finding #3).
_PREREQ_SQL = """
CREATE TYPE run_status AS ENUM ('queued','running','succeeded','failed','cancelled');
CREATE TABLE projects (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text);
CREATE TABLE competitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  platform text DEFAULT 'kaggle',
  slug text UNIQUE,
  title text,
  max_daily_submissions int,
  last_rules_fetch_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE experiments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  name text,
  competition_id uuid,
  job_id uuid,
  hypothesis text,
  branch text,
  tags text[] DEFAULT '{}',
  config jsonb DEFAULT '{}',
  status text DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE experiment_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  external_run_id text,
  run_number int,
  run_dir text,
  command text,
  status run_status NOT NULL DEFAULT 'running',
  metrics jsonb NOT NULL DEFAULT '{}',
  analysis text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL,
  competition_id uuid REFERENCES competitions(id),
  file_path text,
  public_lb_score numeric(10,6),
  status text DEFAULT 'prepared',
  submitted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
"""


# ---------------------------------------------------------------------------
# Pure-Python tier
# ---------------------------------------------------------------------------


def test_expand_full_cross_product():
    spec = explore._load_search_space(FIXTURE)
    cells = explore.expand_cells(spec)
    assert len(cells) == 12  # 3 backbones x 2 sizes x 2 epochs
    # No duplicates.
    keys = {json.dumps(c, sort_keys=True) for c in cells}
    assert len(keys) == 12


def test_expand_random_sample_deterministic():
    spec = explore._load_search_space(FIXTURE_SAMPLE)
    first = explore.expand_cells(spec)
    second = explore.expand_cells(spec)
    assert len(first) == 4
    assert first == second  # same seed -> same cells, same order


def test_expand_random_sample_inline_directive():
    spec = {
        "axes": {"a": [1, 2, 3], "b": ["x", "y"]},
        "sample": {"random": 3, "seed": 7},
    }
    cells = explore.expand_cells(spec)
    assert len(cells) == 3
    assert cells == explore.expand_cells(spec)


def test_expand_empty_axes_raises():
    with pytest.raises(ValueError):
        explore.expand_cells({"axes": {}})


def test_fake_screen_is_pure_and_in_range():
    cell = {"backbone": "resnet50", "image_size": 224, "epochs": 6}
    a = explore.fake_screen(cell, "run-x", seed=0)
    b = explore.fake_screen(cell, "run-x", seed=0)
    assert a == b  # deterministic
    assert 0.0 <= a["holdout_accuracy"] <= 1.0
    assert 0.0 <= a["macro_f1"] <= 1.0
    assert a["train_seconds"] > 0
    # Different run_id -> different metrics (so a cohort ranks non-trivially).
    c = explore.fake_screen(cell, "run-y", seed=0)
    assert c != a


def test_baseline_template_overrides_axes():
    seed = (REPO_ROOT / "experiments" / "tpu-getting-started" / "baseline-tl" / "baseline.py").read_text(
        encoding="utf-8"
    )
    cell = {"backbone": "resnet50", "image_size": 224, "epochs": 6}
    out = explore._render_cell_baseline(seed, cell, "run-z")
    assert "_KCA_IMAGE_SIZE = (224, 224)" in out
    assert "_KCA_EPOCHS = 6" in out
    assert "_KCA_BACKBONE = 'ResNet50'" in out
    # The backbone constructor line was rewritten to the cell's backbone.
    assert "tf.keras.applications.ResNet50(" in out
    assert "IMAGE_SIZE = _KCA_IMAGE_SIZE" in out


def test_resolve_max_concurrent_explicit_and_serial(monkeypatch):
    # Explicit request is honoured (clamped to n_cells).
    val, _ = explore.resolve_max_concurrent(8, 4)
    assert val == 4
    val, _ = explore.resolve_max_concurrent(2, 4)
    assert val == 2
    # No GPU -> serial.
    monkeypatch.setattr(explore, "_free_vram_mib", lambda: None)
    val, reason = explore.resolve_max_concurrent(None, 4)
    assert val == 1
    assert "serial" in reason.lower()
    # With VRAM -> capped by free // est.
    monkeypatch.setattr(explore, "_free_vram_mib", lambda: 10000)
    val, _ = explore.resolve_max_concurrent(None, 10)
    assert val == 10000 // explore._EST_CELL_VRAM_MIB


def test_no_kaggle_push_lines_in_module():
    """Audit-grep invariant: explore.py reaches no real Kaggle push/submit."""
    src = (REPO_ROOT / "tools" / "kca" / "explore.py").read_text(encoding="utf-8")
    assert "kaggle kernels push" not in src
    assert "kaggle competitions submit" not in src
    assert "kernels_push" not in src
    assert "competition_submit" not in src


# ---------------------------------------------------------------------------
# Ephemeral-Postgres tier
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_url():
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries (initdb/pg_ctl/postgres) on PATH")
    tmp = tempfile.mkdtemp(prefix="m14exp_")
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
def comp_env(pg_url):
    """A registered competition + active goal; yields (slug, env, cleanup-of-dirs)."""
    import psycopg

    slug = f"tpu-explore-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO competitions (slug, title) VALUES (%s, %s) RETURNING id::text",
                (slug, "explore test"),
            )
            comp_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO goals (competition_id, target_lb_score, exit_strategy) VALUES (%s::uuid, %s, %s)",
                (comp_id, 0.85, "score_only"),
            )
    env = dict(os.environ)
    env["SUPABASE_DB_URL"] = pg_url
    env["KCA_DB_TARGET"] = "local"
    env["KCA_SKIP_DOTENV"] = "1"
    created_dirs: list[Path] = []
    yield slug, env, created_dirs
    # Clean up any generated experiments/<slug>/ dirs.
    comp_dir = REPO_ROOT / "experiments" / slug
    if comp_dir.exists():
        shutil.rmtree(comp_dir, ignore_errors=True)


def _run_kca(env, *argv) -> dict:
    proc = subprocess.run(
        [sys.executable, str(KCA), *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    # The JSON envelope is the last stdout line.
    last = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    assert last, f"no JSON envelope in stdout:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(last[-1])


def test_init_full_product_creates_12_runs(comp_env):
    slug, env, _ = comp_env
    out = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE),
        "--json",
    )
    assert out["ok"] is True, out
    assert out["n_cells"] == 12
    batch_id = out["exploration_batch_id"]
    assert len(out["cells"]) == 12
    # Every cell has analysis_jsonb.exploration_batch_id set.
    import psycopg

    with psycopg.connect(env["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM experiment_runs "
                "WHERE analysis_jsonb ->> 'exploration_batch_id' = %s "
                "AND analysis_jsonb ->> 'explore_stage' = 'planned' "
                "AND status = 'queued'",
                (batch_id,),
            )
            assert cur.fetchone()[0] == 12


def test_init_random_sample_creates_4(comp_env):
    slug, env, _ = comp_env
    out = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE_SAMPLE),
        "--json",
    )
    assert out["ok"] is True, out
    assert out["n_cells"] == 4


def test_second_init_refused_active_batch(comp_env):
    slug, env, _ = comp_env
    first = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE),
        "--json",
    )
    assert first["ok"] is True
    second = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE),
        "--json",
    )
    assert second["ok"] is False
    assert second["error"] == "ACTIVE_BATCH_EXISTS"


def test_run_dry_run_screens_all_cells(comp_env):
    slug, env, _ = comp_env
    init = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE_SAMPLE),
        "--json",
    )
    batch_id = init["exploration_batch_id"]
    run = _run_kca(
        env,
        "explore",
        "run",
        "--batch",
        batch_id,
        "--dry-run",
        "--json",
    )
    assert run["ok"] is True, run
    assert run["screened"] == 4
    assert run["dry_run"] is True
    # Metrics + status flip persisted.
    import psycopg

    with psycopg.connect(env["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metrics, status, analysis_jsonb ->> 'explore_stage' "
                "FROM experiment_runs "
                "WHERE analysis_jsonb ->> 'exploration_batch_id' = %s",
                (batch_id,),
            )
            rows = cur.fetchall()
            assert len(rows) == 4
            for metrics, status, stage in rows:
                # enum column is a valid run_status; explore_stage carries the
                # planned/screened lifecycle marker (M14-T009 finding #2).
                assert stage == "screened"
                assert status == "succeeded"
                assert "holdout_accuracy" in metrics
                assert "macro_f1" in metrics
                assert "train_seconds" in metrics


def test_run_requires_dry_run_in_t003(comp_env):
    slug, env, _ = comp_env
    init = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE_SAMPLE),
        "--json",
    )
    batch_id = init["exploration_batch_id"]
    out = _run_kca(env, "explore", "run", "--batch", batch_id, "--json")
    assert out["ok"] is False
    assert out["error"] == "REAL_TRAINING_NOT_ENABLED_IN_T003"


def test_rank_sorts_and_flags_qualify(comp_env):
    slug, env, _ = comp_env
    init = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE),
        "--json",
    )
    batch_id = init["exploration_batch_id"]
    _run_kca(env, "explore", "run", "--batch", batch_id, "--dry-run", "--json")
    rank = _run_kca(env, "explore", "rank", "--batch", batch_id, "--json")
    assert rank["ok"] is True, rank
    assert rank["n_screened"] == 12
    ranked = rank["ranked"]
    # Sorted descending by holdout_accuracy.
    holds = [c["holdout_accuracy"] for c in ranked]
    assert holds == sorted(holds, reverse=True)
    # Threshold = 0.90 x 0.85 = 0.765; each cell flagged accordingly.
    thr = rank["screen_threshold"]
    assert thr == pytest.approx(0.765, abs=1e-6)
    for c in ranked:
        assert c["qualifies"] == (c["holdout_accuracy"] >= thr)


def test_prune_removes_only_planned(comp_env):
    slug, env, _ = comp_env
    init = _run_kca(
        env,
        "explore",
        "init",
        "--competition",
        slug,
        "--search-space",
        str(FIXTURE_SAMPLE),
        "--json",
    )
    batch_id = init["exploration_batch_id"]
    import psycopg

    # Screen 2 of the 4 by flipping their stage directly, leave 2 planned.
    with psycopg.connect(env["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM experiment_runs "
                "WHERE analysis_jsonb ->> 'exploration_batch_id' = %s "
                "ORDER BY created_at LIMIT 2",
                (batch_id,),
            )
            ids = [r[0] for r in cur.fetchall()]
            cur.execute(
                "UPDATE experiment_runs "
                "SET status = 'succeeded', "
                '    analysis_jsonb = analysis_jsonb || \'{"explore_stage":"screened"}\'::jsonb '
                "WHERE id = ANY(%s)",
                (ids,),
            )
    pruned = _run_kca(env, "explore", "prune", "--batch", batch_id, "--json")
    assert pruned["ok"] is True, pruned
    assert pruned["pruned_runs"] == 2
    with psycopg.connect(env["SUPABASE_DB_URL"], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analysis_jsonb ->> 'explore_stage' FROM experiment_runs "
                "WHERE analysis_jsonb ->> 'exploration_batch_id' = %s",
                (batch_id,),
            )
            stages = sorted(r[0] for r in cur.fetchall())
            assert stages == ["screened", "screened"]
