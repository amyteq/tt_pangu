"""M14-T007 tests — stuck detector + human escalation via the Approval Inbox.

Three posture tiers (mirrors the other M14 test modules):

1. **Pure-Python tier** — the detector heuristic (fires at exactly N=3
   non-improving SCORED submissions with 0 fresh candidates; NOT before; NOT
   when fresh candidates exist; the NULL-score rule neither advances nor
   resets), the redaction filter (a crafted DSN / credential / flag is masked
   in the payload AND the rendered doc), the escalation-doc required sections,
   the resume-seed parser, and the telemetry aggregation. Runs anywhere — no
   network, no DB.

2. **Ephemeral-Postgres tier** — boots a throwaway Postgres, seeds a comp +
   goal + submissions, and drives the full detect -> write doc -> insert
   human_decisions(kaggle.exploration_stuck) -> list in inbox -> approve with
   notes -> escalation_id-on-resume path against real Postgres. A second
   schema variant adds the issue-#60 ``approved_by_user_id`` column to confirm
   the #60-aware write. SKIPs cleanly when no Postgres binary is on PATH.

3. **decision_api smoke tier** — the FastAPI approve endpoint surfaces the
   parsed resume seed for the new decision_type (mocked DB, no Supabase).

Run with:
    python -m pytest tests/test_m14_stuck.py -v
"""

from __future__ import annotations

import datetime as dt
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

import stuck  # noqa: E402

_PG_BINS_PRESENT = all(shutil.which(b) for b in ("initdb", "pg_ctl", "postgres"))

# A crafted secret used across redaction assertions. If this exact string ever
# reaches a committed escalation doc or an audit row, the milestone stop
# criterion (credential leak in an escalation doc) is violated.
SECRET_DSN = "postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres"
SECRET_FLAG = "flag{do_not_leak_me}"
SECRET_KEY = "sk-ant-abc123DEADBEEFtoken"


# ---------------------------------------------------------------------------
# Tier 1 — pure-Python detector heuristic
# ---------------------------------------------------------------------------


def _scored(*vals):
    """Build submissions oldest->newest from public_lb_score values (None = NULL)."""
    return [{"public_lb_score": v} for v in vals]


def test_detector_fires_at_exactly_three_non_improving_with_no_fresh():
    # best=0.80 then three lower/equal scored subs -> 3 non-improving.
    subs = _scored(0.80, 0.79, 0.78, 0.78)
    assert stuck.consecutive_non_improving(subs) == 3
    assert stuck.is_stuck(subs, fresh_candidate_count=0, threshold=3) is True


def test_detector_does_not_fire_before_threshold():
    # Only two non-improving scored subs after the best.
    subs = _scored(0.80, 0.79, 0.78)
    assert stuck.consecutive_non_improving(subs) == 2
    assert stuck.is_stuck(subs, fresh_candidate_count=0, threshold=3) is False


def test_detector_does_not_fire_when_fresh_candidates_exist():
    subs = _scored(0.80, 0.79, 0.78, 0.78)  # 3 non-improving
    assert stuck.consecutive_non_improving(subs) == 3
    # Fresh candidates available -> NOT stuck regardless of the run.
    assert stuck.is_stuck(subs, fresh_candidate_count=2, threshold=3) is False


def test_null_score_neither_advances_nor_resets_counter():
    # 0.80 (best) -> 0.79 (non-improving #1) -> NULL (skipped) -> 0.78 (#2)
    # -> NULL (skipped) -> 0.78 (#3). The two NULLs must not advance the best
    # nor reset the counter.
    subs = _scored(0.80, 0.79, None, 0.78, None, 0.78)
    assert stuck.consecutive_non_improving(subs) == 3
    assert stuck.is_stuck(subs, fresh_candidate_count=0, threshold=3) is True

    # A NULL that is the most-recent submission also does not reset: the
    # counter reflects only the scored run before it.
    subs2 = _scored(0.80, 0.79, 0.78, 0.78, None)
    assert stuck.consecutive_non_improving(subs2) == 3


def test_improvement_resets_counter():
    # 0.80 -> 0.79 -> 0.78 -> 0.85 (new best, reset) -> 0.84 (#1)
    subs = _scored(0.80, 0.79, 0.78, 0.85, 0.84)
    assert stuck.consecutive_non_improving(subs) == 1
    assert stuck.is_stuck(subs, fresh_candidate_count=0, threshold=3) is False


# ---------------------------------------------------------------------------
# Tier 1 — redaction
# ---------------------------------------------------------------------------


def _payload_with_secrets(ts="20260610T120000Z"):
    return stuck.build_escalation_payload(
        competition="tpu-getting-started",
        goal={
            "target_lb_score": 0.85,
            "target_lb_rank": 30,
            "exit_strategy": "first_reached",
        },
        current={
            "best_public_lb_score": 0.78,
            "best_rank": 120,
            "pushes_used": 6,
            "max_total_pushes": 20,
            # Crafted secret-shaped key — must be redacted by key name.
            "kaggle_key": "AKIAIOSFODNN7EXAMPLE",
            "dsn": SECRET_DSN,
        },
        tried_strategies=[
            {
                "axes": {"backbone": "resnet50", "image_size": 192, "epochs": 3},
                "holdout_accuracy": 0.81,
                "public_lb_score": 0.78,
                "status": "pushed",
            }
        ],
        sources_consulted=[
            {
                "source_url": "https://www.kaggle.com/code/x/notebook",
                "trust_label": "community",
                # Crafted secret in free text — must be masked by value shape.
                "summary": f"connect via {SECRET_DSN} and submit {SECRET_FLAG}",
            }
        ],
        ruled_out_hypotheses=[f"bigger images alone (tried {SECRET_KEY})"],
        questions=["Which augmentation family should we explore next?"],
        ts=ts,
    )


def test_redaction_masks_secrets_in_payload():
    payload = _payload_with_secrets()
    blob = json.dumps(payload)
    # No crafted secret survives anywhere in the structured payload — whether
    # it arrived via a secret-named key (dsn/kaggle_key, which the builder also
    # drops as unknown `current` keys) or as a value-shaped secret embedded in
    # a source summary / ruled-out hypothesis string.
    assert SECRET_DSN not in blob
    assert SECRET_FLAG not in blob
    assert SECRET_KEY not in blob
    # The value-shaped DSN/flag inside the source summary were masked in place.
    assert "[REDACTED]" in payload["sources_consulted"][0]["summary"]
    # Secret-named keys are wholesale-redacted by the recursive filter.
    scrubbed = stuck.redact_escalation_payload({"current": {"dsn": SECRET_DSN, "kaggle_key": "AKIAIOSFODNN7EXAMPLE"}})
    assert scrubbed["current"]["dsn"] == "[REDACTED]"
    assert scrubbed["current"]["kaggle_key"] == "[REDACTED]"


def test_redaction_masks_secrets_in_rendered_doc():
    payload = _payload_with_secrets()
    doc = stuck.render_escalation_md(payload)
    for sentinel in (SECRET_DSN, SECRET_FLAG, SECRET_KEY):
        assert sentinel not in doc, f"secret leaked into escalation doc: {sentinel}"


def test_redaction_is_idempotent_and_recursive():
    nested = {"a": {"b": [{"password": "hunter2", "note": SECRET_DSN}]}}
    out = stuck.redact_escalation_payload(nested)
    assert out["a"]["b"][0]["password"] == "[REDACTED]"
    assert SECRET_DSN not in json.dumps(out)
    # Re-redacting the already-redacted blob changes nothing.
    assert stuck.redact_escalation_payload(out) == out


# ---------------------------------------------------------------------------
# Tier 1 — escalation doc sections + deterministic filename
# ---------------------------------------------------------------------------


def test_escalation_doc_has_required_sections():
    payload = _payload_with_secrets()
    doc = stuck.render_escalation_md(payload)
    assert "## Goal vs current" in doc
    assert "## Tried strategies" in doc
    assert "## Sources consulted" in doc
    assert "## Ruled-out hypotheses" in doc
    assert "## Questions for the human" in doc


def test_escalation_filename_is_injectable_and_deterministic():
    n1 = stuck.escalation_filename("tpu-getting-started", "20260610T120000Z")
    n2 = stuck.escalation_filename("tpu-getting-started", "20260610T120000Z")
    assert n1 == n2 == "tpu-getting-started-20260610T120000Z.md"


def test_write_escalation_doc_uses_injected_dir_and_ts(tmp_path):
    payload = _payload_with_secrets(ts="20260610T130000Z")
    path = stuck.write_escalation_doc(payload, ts="20260610T130000Z", escalations_dir=tmp_path)
    assert path.name == "tpu-getting-started-20260610T130000Z.md"
    text = path.read_text(encoding="utf-8")
    for sentinel in (SECRET_DSN, SECRET_FLAG, SECRET_KEY):
        assert sentinel not in text


# ---------------------------------------------------------------------------
# Tier 1 — resume seed parsing
# ---------------------------------------------------------------------------


def test_resume_seed_structured_options():
    seed = stuck.resume_seed_from_notes("backbone=convnext_tiny image_size=331 epochs=9")
    assert seed["kind"] == "structured"
    assert seed["options"] == {
        "backbone": "convnext_tiny",
        "image_size": 331,
        "epochs": 9,
    }


def test_resume_seed_free_text():
    seed = stuck.resume_seed_from_notes("try heavier augmentation and TTA")
    assert seed["kind"] == "free_text"
    assert seed["options"] == {}
    assert "augmentation" in seed["direction"]


def test_resume_seed_empty():
    assert stuck.resume_seed_from_notes(None)["kind"] == "empty"
    assert stuck.resume_seed_from_notes("   ")["kind"] == "empty"


# ---------------------------------------------------------------------------
# Tier 1 — telemetry
# ---------------------------------------------------------------------------


def test_escalation_telemetry_counts_and_time_to_resolution():
    t0 = dt.datetime(2026, 6, 10, 12, 0, 0)
    rows = [
        # resolved in 3600s
        {
            "decision_type": stuck.DECISION_TYPE,
            "created_at": t0,
            "decided_at": t0 + dt.timedelta(hours=1),
        },
        # resolved in 1800s
        {
            "decision_type": stuck.DECISION_TYPE,
            "created_at": t0,
            "decided_at": t0 + dt.timedelta(minutes=30),
        },
        # still pending
        {
            "decision_type": stuck.DECISION_TYPE,
            "created_at": t0,
            "decided_at": None,
        },
        # unrelated decision_type — not counted
        {"decision_type": "kaggle_submit", "created_at": t0, "decided_at": t0},
    ]
    tel = stuck.escalation_telemetry(rows)
    assert tel["escalation_count"] == 3
    assert tel["resolved_count"] == 2
    assert tel["pending_count"] == 1
    assert tel["time_to_resolution_seconds_total"] == 5400.0
    assert tel["time_to_resolution_seconds_mean"] == 2700.0


def test_telemetry_handles_iso_string_timestamps():
    rows = [
        {
            "decision_type": stuck.DECISION_TYPE,
            "created_at": "2026-06-10T12:00:00",
            "decided_at": "2026-06-10T12:10:00",
        }
    ]
    tel = stuck.escalation_telemetry(rows)
    assert tel["resolved_count"] == 1
    assert tel["time_to_resolution_seconds_total"] == 600.0


# ---------------------------------------------------------------------------
# Tier 1 — audit-grep sentinel (no real Kaggle push/submit lines)
# ---------------------------------------------------------------------------


def test_no_kaggle_push_submit_call_sites_in_stuck_module():
    src = (REPO_ROOT / "tools" / "kca" / "stuck.py").read_text(encoding="utf-8")
    assert "kernels_push(" not in src
    assert "competitions_submit(" not in src
    assert "competition_submit(" not in src
    assert "kaggle kernels push" not in src
    assert "kaggle competitions submit" not in src


# ---------------------------------------------------------------------------
# Tier 2 — Ephemeral-Postgres: row insert + inbox + approve resume + #60
# ---------------------------------------------------------------------------

_PREREQ_SQL = """
CREATE TYPE decision_status AS ENUM ('pending','approved','rejected','expired');
CREATE TABLE projects (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text);
CREATE TABLE competitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  platform text DEFAULT 'kaggle',
  slug text UNIQUE,
  title text
);
CREATE TABLE goals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id uuid REFERENCES competitions(id),
  target_lb_score numeric(10,6),
  target_lb_rank int,
  exit_strategy text DEFAULT 'first_reached',
  max_total_pushes int DEFAULT 20,
  stuck_threshold int DEFAULT 3,
  status text DEFAULT 'active'
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
CREATE TABLE human_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL,
  session_id uuid,
  decision_type text NOT NULL,
  prompt text NOT NULL,
  options jsonb NOT NULL DEFAULT '[]',
  status decision_status NOT NULL DEFAULT 'pending',
  selected jsonb,
  rationale text,
  requested_by text,
  job_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz
);
"""

# The #60 variant adds the FK-ready column the audit task will harden.
_PREREQ_SQL_WITH_60 = _PREREQ_SQL + ("ALTER TABLE human_decisions ADD COLUMN approved_by_user_id uuid;\n")


def _boot_pg(prereq_sql):
    tmp = tempfile.mkdtemp(prefix="m14stuck_")
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
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(prereq_sql)
    return url, tmp, datadir


def _stop_pg(tmp, datadir):
    subprocess.run(["pg_ctl", "-D", datadir, "-w", "stop"], capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def db_env(monkeypatch):
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries (initdb/pg_ctl/postgres) on PATH")
    url, tmp, datadir = _boot_pg(_PREREQ_SQL)
    monkeypatch.setenv("SUPABASE_DB_URL", url)
    monkeypatch.setenv("KCA_DB_TARGET", "local")
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")
    sys.modules.pop("db", None)
    import db  # noqa: F811

    # default project for the not-null project_id on human_decisions.
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (id, name) VALUES (%s::uuid, 'default')",
                (db.DEFAULT_PROJECT_ID,),
            )
    try:
        yield url, db
    finally:
        _stop_pg(tmp, datadir)


def _seed_comp_goal(url, db):
    import psycopg

    slug = f"tpu-stuck-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO competitions (project_id, slug, title) VALUES (%s::uuid, %s, %s) RETURNING id::text",
                (db.DEFAULT_PROJECT_ID, slug, "stuck test"),
            )
            comp_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO goals (competition_id, target_lb_score, stuck_threshold) VALUES (%s::uuid, 0.85, 3)",
                (comp_id,),
            )
    return slug, comp_id


def test_insert_stuck_decision_visible_in_inbox(db_env):
    url, db = db_env
    slug, comp_id = _seed_comp_goal(url, db)
    payload = _payload_with_secrets()
    decision_id = stuck.insert_stuck_decision(db, payload=payload)

    # Visible in the Approval Inbox surface (list_pending_decisions == GET).
    pending = db.list_pending_decisions()
    match = [d for d in pending if str(d["id"]) == decision_id]
    assert match, "stuck decision not visible in the inbox"
    row = match[0]
    assert row["decision_type"] == stuck.DECISION_TYPE
    # The stored options carry the redacted payload — no secret reaches the row.
    blob = json.dumps(row["options"], default=str)
    assert SECRET_DSN not in blob
    assert SECRET_FLAG not in blob


def test_approve_with_notes_resolves_and_yields_resume_seed(db_env, capsys):
    url, db = db_env
    slug, comp_id = _seed_comp_goal(url, db)
    decision_id = stuck.insert_stuck_decision(db, payload=_payload_with_secrets())

    import decisions as decisions_mod

    ns = type("NS", (), {})()
    ns.id = decision_id
    ns.notes = "backbone=convnext_tiny image_size=331"
    ns.json = True
    rc = decisions_mod.cmd_approve(ns)
    out = capsys.readouterr().out
    line = [ln for ln in out.splitlines() if ln.strip().startswith("{")][-1]
    resp = json.loads(line)
    assert rc == 0, resp
    assert resp["ok"] is True
    assert resp["resolution"] == "approved"
    # The resolving id becomes the escalation_id the resumed run records.
    assert resp["escalation_id"] == decision_id
    assert resp["resume_seed"]["kind"] == "structured"
    assert resp["resume_seed"]["options"]["backbone"] == "convnext_tiny"

    # Row is no longer pending.
    assert decision_id not in {str(d["id"]) for d in db.list_pending_decisions()}
    resolved = db.get_decision(decision_id)
    assert resolved["status"] == "approved"
    assert resolved["rationale"] == "backbone=convnext_tiny image_size=331"


def test_escalation_id_lands_on_resumed_run_analysis_jsonb(db_env):
    """The resolving decision id is recordable as a run's escalation_id.

    T008 owns the live loop; here we assert the recording contract: the
    resume seed's escalation_id round-trips onto a run's analysis_jsonb via
    the T001 helper (analysis_jsonb merge), so the resumed batch is attributed
    to the escalation that unblocked it.
    """
    url, db = db_env
    slug, comp_id = _seed_comp_goal(url, db)
    decision_id = stuck.insert_stuck_decision(db, payload=_payload_with_secrets())

    import psycopg

    # analysis_jsonb lives on experiment_runs; build the minimal table here so
    # we exercise the real set/get helpers (the full schema is in 0011).
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS experiments (id uuid PRIMARY KEY DEFAULT gen_random_uuid())")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS experiment_runs ("
                "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
                "experiment_id uuid, metrics jsonb DEFAULT '{}', "
                "analysis_jsonb jsonb)"
            )
            cur.execute("INSERT INTO experiments DEFAULT VALUES RETURNING id::text")
            exp_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO experiment_runs (experiment_id) VALUES (%s::uuid) RETURNING id::text",
                (exp_id,),
            )
            run_id = cur.fetchone()[0]

    db.set_run_analysis_jsonb(run_id, escalation_id=decision_id)
    blob = db.get_run_analysis_jsonb(run_id)
    assert blob is not None
    assert blob.get("escalation_id") == decision_id


def test_insert_stuck_decision_writes_approved_by_user_id_when_present(monkeypatch):
    """Issue #60: write approved_by_user_id only if the column exists."""
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries on PATH")
    url, tmp, datadir = _boot_pg(_PREREQ_SQL_WITH_60)
    monkeypatch.setenv("SUPABASE_DB_URL", url)
    monkeypatch.setenv("KCA_DB_TARGET", "local")
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")
    sys.modules.pop("db", None)
    import db  # noqa: F811

    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (id, name) VALUES (%s::uuid, 'default')",
                (db.DEFAULT_PROJECT_ID,),
            )
    try:
        slug, comp_id = _seed_comp_goal(url, db)
        user_id = str(uuid.uuid4())
        assert stuck._human_decisions_has_column(db, "approved_by_user_id") is True
        decision_id = stuck.insert_stuck_decision(db, payload=_payload_with_secrets(), approved_by_user_id=user_id)
        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT approved_by_user_id::text FROM human_decisions WHERE id = %s::uuid",
                    (decision_id,),
                )
                got = cur.fetchone()[0]
        assert got == user_id
    finally:
        _stop_pg(tmp, datadir)


def test_insert_stuck_decision_ignores_approved_by_user_id_when_absent(db_env):
    """When the column is absent (base schema), the write is a clean no-op."""
    url, db = db_env
    slug, comp_id = _seed_comp_goal(url, db)
    assert stuck._human_decisions_has_column(db, "approved_by_user_id") is False
    # Passing approved_by_user_id must not raise even though the column is gone.
    decision_id = stuck.insert_stuck_decision(
        db, payload=_payload_with_secrets(), approved_by_user_id=str(uuid.uuid4())
    )
    assert decision_id in {str(d["id"]) for d in db.list_pending_decisions()}


# ---------------------------------------------------------------------------
# Tier 3 — decision_api smoke for the new decision_type
# ---------------------------------------------------------------------------


def test_decision_api_approve_surfaces_resume_seed():
    from fastapi.testclient import TestClient

    from services.decision_api.app import make_app

    class FakeDB:
        def __init__(self):
            self.decisions = {
                "esc1": {
                    "id": "esc1",
                    "status": "pending",
                    "job_id": None,
                    "decision_type": "kaggle.exploration_stuck",
                }
            }

        def get_decision(self, decision_id):
            return self.decisions.get(decision_id)

        def resolve_decision(self, decision_id, resolution, notes=None):
            self.decisions[decision_id]["status"] = resolution
            self.decisions[decision_id]["notes"] = notes

        def append_job_event(self, *a, **k):
            return 1

    app = make_app(decisions_module=FakeDB(), audit_logger=lambda **_: None)
    client = TestClient(app)
    r = client.post(
        "/decision/esc1/approve",
        json={"reason": "backbone=efficientnetv2_s image_size=256"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["escalation_id"] == "esc1"
    assert body["resume_seed"]["kind"] == "structured"
    assert body["resume_seed"]["options"]["backbone"] == "efficientnetv2_s"
    assert body["resume_seed"]["options"]["image_size"] == 256
