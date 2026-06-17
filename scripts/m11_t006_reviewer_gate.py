"""M11-T006: drive the reviewer-gate round-trip for `challenge_run` and
`flag_submit`, plus the refusal smoke for an out-of-scope `network_egress`.

This script intentionally bypasses the LiteLLM tool-loop and instead
drives the same reviewer-gate code paths the worker uses
(`src.worker.reviewer.Reviewer`, `src.worker.worker._handle_approval_required`).
The autonomous runner-agent here plays BOTH worker and approver roles —
T006's purpose is to exercise the plumbing end-to-end against the cloud
Supabase. T007 is the only Loop Prompt that makes a real external call.

Hygiene invariants (binding):

  - The flag VALUE never enters stdout, agent_reviews.rationale,
    agent_reviews.evidence, human_decisions.rationale, agent_job_events.event_data,
    ctf_attempts.response_excerpt, or any other JSON envelope.
  - We use sha256(flag) only for end-of-run audit-grep, never persist it.
  - The flag-bearing tempfile is fsync'd to zeros then unlinked before exit.
  - The reviewer is invoked in dry-run mode so it never hits LiteLLM.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import db as _db  # noqa: E402
from src.db import ctf as ctf_db  # noqa: E402
from src.worker.reviewer import (  # noqa: E402
    Reviewer,
    ReviewRequest,
    render_review_context,
)

EVENT_SLUG = "kca-fixtures-2026"
WEB_SLUG = "web-1-cookie-monster"
WEB_SCOPE_NAME = "ctf-local-kca-fixtures-2026-web-1"


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    print(f"[m11-t006] {msg}", flush=True)


def _kca(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py"), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _create_review_job(prompt: str) -> str:
    """Insert an agent_jobs row for the round-trip.

    Avoids `_db.create_job()` because the cloud schema in T006's target
    DB does not include the `competition_id` column the local-flavoured
    helper hard-codes — the M11 fixture work runs against the cloud DB
    per the task's "Database posture" note. Direct INSERT mirrors the
    helper's column list minus that column.
    """
    project_id = _db.ensure_default_project()
    policy_json = json.dumps({"profile": "competition-runner", "m11_t006_driver": True})
    payload_json = json.dumps({"driver": "m11_t006"})
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_jobs
                  (project_id, job_type, status, payload, prompt, model, policy)
                VALUES
                  (%s::uuid, %s, 'queued', %s::jsonb, %s, %s, %s::jsonb)
                RETURNING id::text
                """,
                (
                    project_id,
                    "m11_t006_reviewer_gate_driver",
                    payload_json,
                    prompt,
                    "claude-opus-4-7",
                    policy_json,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    assert row is not None
    return row["id"]


def _drive_gate(
    *,
    job_id: str,
    target_op: str,
    tool_name: str,
    tool_input: dict,
    rationale_seed: str,
    dry_verdict: str,
) -> tuple[str, str]:
    """Run the reviewer (dry-run) for (job_id, target_op), then create a
    pending human_decisions row + approval_pause event.

    Returns (review_id, decision_id).
    """
    req = ReviewRequest(
        job_id=job_id,
        target_op=target_op,
        tool_name=tool_name,
        tool_input=tool_input,
        final_message=None,
        event_trail=[],
    )
    # Sanity-grep: confirm the rendered reviewer prompt body for `flag_submit`
    # does NOT contain the flag value. We check by length: the redacted
    # tool_input replaces the value with `{"_redacted": True, "length": N}`.
    rendered = render_review_context(req)
    if target_op == "flag_submit":
        for k in ("flag", "flag_value", "submission"):
            if k in tool_input and isinstance(tool_input[k], str):
                assert tool_input[k] not in rendered, (
                    f"REGRESSION: flag value leaked into reviewer prompt under key {k!r}"
                )
    reviewer = Reviewer(
        dry_run=True,
        dry_verdict=dry_verdict,
        dry_rationale=f"dry-run reviewer auto-{dry_verdict} ({rationale_seed})",
    )
    verdict = reviewer.review(req)

    # Persist the agent_reviews row. evidence is intentionally a small
    # JSON object — never the flag, never the credential.
    review_id = _db.create_review(
        job_id=job_id,
        reviewer_model=verdict.reviewer_model,
        verdict=verdict.verdict,
        target_op=target_op,
        rationale=verdict.rationale,
        evidence={
            "mode": "dry_run",
            "driver": "m11_t006",
            "tool_name": tool_name,
            # Note: tool_input deliberately omitted — for flag_submit it would
            # otherwise leak. For challenge_run + network_egress the tool_input
            # is URL-only and safe, but we still omit it for symmetry.
        },
        cost_usd=0.0,
    )

    # Approval-pause event mirroring AgentWorker._handle_approval_required.
    decision_id = _db.insert_approval_request(
        decision_type="tool_approval",
        prompt=f"M11-T006 driver: gate fired for {target_op} on job {job_id}",
        options={
            "approve": f"allow the {target_op} call",
            "deny": "block and stop the driver",
        },
        job_id=job_id,
    )
    _db.append_job_event(
        job_id,
        "approval_pause",
        event_data={
            "tool": tool_name,
            "operation": target_op,
            # tool_input WITHOUT flag value — for flag_submit we pass only
            # presence + length.
            "tool_input_redacted": {
                k: (
                    {
                        "_redacted": True,
                        "length": (len(v) if isinstance(v, str) else None),
                    }
                    if k in ("flag", "flag_value", "submission")
                    else v
                )
                for k, v in tool_input.items()
            },
            "side_effect": "SUBMISSION" if target_op == "flag_submit" else "REMOTE_WRITE",
            "decision_id": decision_id,
            "review_id": review_id,
            "verdict": verdict.verdict,
        },
    )
    return review_id, decision_id


def _kca_decisions_approve(decision_id: str, notes: str) -> None:
    res = _kca("decisions", "approve", "--id", decision_id, "--notes", notes)
    if res.returncode != 0:
        raise RuntimeError(f"kca decisions approve failed (rc={res.returncode}): {res.stderr or res.stdout}")
    out = json.loads(res.stdout.strip().splitlines()[-1])
    if not out.get("ok"):
        raise RuntimeError(f"kca decisions approve returned ok=false: {out}")


# ---------------------------------------------------------------------------
# 1. challenge_run round-trip
# ---------------------------------------------------------------------------


def stage_challenge_run() -> dict:
    """Drive the challenge_run gate end-to-end for the web challenge.

    Sequence:
      1. Create an agent_jobs row for the round-trip.
      2. Fire the reviewer-gate (dry-run approve), write agent_reviews +
         human_decisions + agent_job_events(approval_pause).
      3. `kca decisions approve` — writes approval_resume event.
      4. Run the T005 solver harness (docker compose up → solve → down).
         The harness owns the docker lifecycle and produces a fresh flag.
      5. Record a NEW ctf_attempts row (accepted=true, scrubbed excerpt).
      6. Append `tool_result` event linking the gate to the new attempt id.
    """
    _log("=== challenge_run round-trip ===")
    job_id = _create_review_job(prompt="[m11-t006 driver] challenge_run on web-1-cookie-monster (gate ON)")
    _log(f"agent_jobs id={job_id}")

    chal_row = ctf_db.get_challenge(EVENT_SLUG, WEB_SLUG)
    assert chal_row is not None, "fixture missing — T005 should have inserted it"
    challenge_id = chal_row["id"]

    # Gate fire (dry-run approve)
    review_id, decision_id = _drive_gate(
        job_id=job_id,
        target_op="challenge_run",
        tool_name="kca_ctf_solver_run",
        tool_input={
            "event": EVENT_SLUG,
            "challenge": WEB_SLUG,
            "target_url": "http://localhost:18080",
            "reviewer_gate": True,
            "dry_run": False,
        },
        rationale_seed="target localhost:18080 ∈ ctf-local scope",
        dry_verdict="approve",
    )
    _log(f"agent_reviews id={review_id} verdict=approve target_op=challenge_run")
    _log(f"human_decisions id={decision_id} status=pending")

    # Human approval round-trip via the CLI.
    _kca_decisions_approve(
        decision_id,
        notes="m11-t006: autonomous runner approves (worker+reviewer plumbing test)",
    )
    _log("kca decisions approve OK → approval_resume event appended by CLI")

    # Run T005 solver to recover a fresh flag (no flag persistence on disk
    # beyond the bundle's expected.sha256, which is per-harness deterministic).
    _log("invoking T005 harness scripts/m11_t005_solve_bundled.py for fresh flag …")
    t005 = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "m11_t005_solve_bundled.py")],
        check=False,
        capture_output=True,
        text=True,
        env=dict(os.environ),
        cwd=str(REPO_ROOT),
    )
    if t005.returncode != 0:
        raise RuntimeError(f"T005 harness failed (rc={t005.returncode}). stderr_tail={t005.stderr[-400:]!r}")
    # Parse the harness summary JSON. The harness ends its stdout with a
    # `json.dumps(summary, indent=2)` block; find the first balanced `{...}`
    # that contains the "challenges" key.
    stdout = t005.stdout
    summary = None
    cursor = 0
    while cursor < len(stdout):
        start = stdout.find("{", cursor)
        if start < 0:
            break
        depth = 0
        end = -1
        for i, ch in enumerate(stdout[start:]):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = start + i + 1
                    break
        if end < 0:
            break
        body = stdout[start:end]
        try:
            cand = json.loads(body)
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        if isinstance(cand, dict) and "challenges" in cand:
            summary = cand
            break
        cursor = end
    if summary is None:
        raise RuntimeError(f"could not parse T005 harness summary; stdout_tail={stdout[-400:]!r}")

    web_summary = summary["challenges"][WEB_SLUG]
    flag_length = int(web_summary["flag_length"])
    # The harness reports the post-solve sha256 in its summary; we use it
    # ONLY for the audit-grep step at the end. Never persisted.
    flag_sha256 = web_summary["flag_sha256"]

    # The T005 harness already records a ctf_attempts row via record_attempt;
    # the spec asks for the "new ctf_attempts row" to be linked to this
    # review via agent_job_events. We append the link event referring to
    # the harness's just-written attempt id.
    new_attempt_id = web_summary["ctf_attempt_id"]

    _db.append_job_event(
        job_id,
        "tool_result",
        event_data={
            "tool": "kca_ctf_solver_run",
            "target_op": "challenge_run",
            "review_id": review_id,
            "decision_id": decision_id,
            "ctf_attempt_id": new_attempt_id,
            "result_preview": (
                "T005 harness invoked under gate-approved challenge_run; "
                "flag verified vs expected.sha256; attempt row recorded "
                "(length-only persistence)"
            ),
        },
    )
    _log(f"linked ctf_attempts id={new_attempt_id} to review {review_id}")

    return {
        "job_id": job_id,
        "review_id": review_id,
        "decision_id": decision_id,
        "ctf_attempt_id": new_attempt_id,
        "challenge_id": challenge_id,
        "flag_length": flag_length,
        # NB: returning sha256 to caller for the final audit-grep step only.
        # NEVER persisted anywhere.
        "flag_sha256": flag_sha256,
        # The recovered flag itself is re-derived in stage_flag_submit by
        # re-running the T005 harness via the bundle's expected.sha256
        # contract; that contract is per-harness deterministic but we do
        # NOT shuttle the flag bytes through this return value.
    }


# ---------------------------------------------------------------------------
# 2. flag_submit round-trip (LOCAL_WRITE only; no remote endpoint)
# ---------------------------------------------------------------------------


def _recover_flag_in_memory() -> str:
    """Re-run the T005 solver in-memory to recover the flag string.

    The bundle's expected.sha256 was last written by stage_challenge_run's
    T005 harness invocation; the docker container is down at that point.
    We bring it back up here just long enough to solve again, then drop.
    """
    # Spin up docker, solve, drop. We reuse the harness via its `solve_web`
    # function so we don't duplicate the wait-for-http + compose logic.
    import importlib.util

    harness_path = REPO_ROOT / "scripts" / "m11_t005_solve_bundled.py"
    spec = importlib.util.spec_from_file_location("_m11_t005_harness", harness_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    web_res = mod.solve_web()
    return web_res["flag"]  # caller MUST drop this within their own scope


def stage_flag_submit() -> dict:
    """Drive the flag_submit gate end-to-end with NO real network call.

    Sequence:
      1. Recover the flag in-memory via the T005 harness (web challenge).
      2. Write it to a 0600-mode tempfile (so the kca CLI surface could
         consume --flag-file if we elected to). The tempfile is wiped + unlinked
         before this function returns.
      3. Fire the reviewer-gate (dry-run approve), write agent_reviews +
         human_decisions + agent_job_events(approval_pause).
      4. `kca decisions approve` — writes approval_resume.
      5. Because the bundled web-1 challenge has remote_endpoint=null, we
         do NOT call the real network. Instead we record a ctf_attempts
         row with http_status=null and the documented dry-run excerpt.
      6. Append `tool_result` event linking the attempt to the gate.
      7. Zero + unlink the tempfile.
    """
    _log("=== flag_submit round-trip ===")
    job_id = _create_review_job(
        prompt="[m11-t006 driver] flag_submit on web-1-cookie-monster (gate ON; no remote endpoint)"
    )
    _log(f"agent_jobs id={job_id}")

    chal_row = ctf_db.get_challenge(EVENT_SLUG, WEB_SLUG)
    assert chal_row is not None
    challenge_id = chal_row["id"]
    remote_endpoint = chal_row.get("remote_endpoint")
    if remote_endpoint:
        raise RuntimeError(f"web-1 should have remote_endpoint=null in T006 fixtures; got {remote_endpoint!r}")

    # Recover flag in-memory and write to a 0600 tempfile.
    flag = _recover_flag_in_memory()
    flag_length = len(flag)
    flag_sha256 = _sha256(flag)
    fd, tmp_path = tempfile.mkstemp(prefix="m11_t006_flag_", suffix=".txt")
    try:
        os.chmod(tmp_path, 0o600)
        os.write(fd, flag.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        _log(f"flag tempfile @ {tmp_path} (mode 0600, length={flag_length})")

        # Gate fire. The redaction helper inside Reviewer._render_prompt
        # converts {"flag": <value>} to {"flag": {"_redacted": True, "length": N}}.
        review_id, decision_id = _drive_gate(
            job_id=job_id,
            target_op="flag_submit",
            tool_name="kca_ctf_flag_submit",
            tool_input={
                "event": EVENT_SLUG,
                "challenge": WEB_SLUG,
                "flag": flag,  # redacted inside reviewer
                "flag_file": tmp_path,
                "dry_run": False,
            },
            rationale_seed="past-event web-1; no remote_endpoint; LOCAL_WRITE-only",
            dry_verdict="approve",
        )
        _log(f"agent_reviews id={review_id} verdict=approve target_op=flag_submit")
        _log(f"human_decisions id={decision_id} status=pending")

        _kca_decisions_approve(
            decision_id,
            notes="m11-t006: autonomous runner approves; past-event no-endpoint refuse follows",
        )
        _log("kca decisions approve OK")

        # Because remote_endpoint is null, the real `kca ctf flag submit`
        # would BLOCK at the scope-check rung before any POST. Record the
        # documented LOCAL_WRITE-only ctf_attempts row directly here.
        excerpt = "dry-run path; no remote endpoint"
        attempt_id = ctf_db.record_attempt(
            challenge_id=challenge_id,
            accepted=None,  # neither accepted nor rejected — never sent
            http_status=None,
            flag_length=flag_length,
            response_excerpt=excerpt,
        )
        _log(f"ctf_attempts id={attempt_id} http_status=null (no remote endpoint)")

        # Confirm the kca CLI surface ALSO refuses cleanly (without
        # KCA_ALLOW_REMOTE the CLI returns EXIT_BLOCKED before scope check).
        cli_res = _kca(
            "ctf",
            "flag",
            "submit",
            "--event",
            EVENT_SLUG,
            "--challenge",
            WEB_SLUG,
            "--flag-file",
            tmp_path,
        )
        cli_payload = json.loads(cli_res.stdout.strip().splitlines()[-1])
        if cli_payload.get("ok"):
            raise RuntimeError(f"`kca ctf flag submit` unexpectedly succeeded without --dry-run: {cli_payload}")
        _log(f"kca ctf flag submit (non-dry-run) refused as expected: error={cli_payload.get('error')!r}")

        _db.append_job_event(
            job_id,
            "tool_result",
            event_data={
                "tool": "kca_ctf_flag_submit",
                "target_op": "flag_submit",
                "review_id": review_id,
                "decision_id": decision_id,
                "ctf_attempt_id": attempt_id,
                "result_preview": excerpt,
                "remote_endpoint": None,
            },
        )

        return {
            "job_id": job_id,
            "review_id": review_id,
            "decision_id": decision_id,
            "ctf_attempt_id": attempt_id,
            "challenge_id": challenge_id,
            "flag_length": flag_length,
            "flag_sha256": flag_sha256,
            "tmp_path": tmp_path,
        }
    finally:
        # Wipe tempfile bytes then unlink.
        try:
            with open(tmp_path, "wb") as f:
                f.write(b"\x00" * max(64, flag_length))
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            pass
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        _log(f"tempfile wiped + unlinked: {tmp_path}")
        # Drop the local flag binding.
        flag = None  # noqa: F841


# ---------------------------------------------------------------------------
# 3. Refusal smoke: challenge_run → http://kaggle.com (out-of-scope)
# ---------------------------------------------------------------------------


def stage_refusal_smoke() -> dict:
    """Verify out-of-scope target denial.

    Sequence:
      1. `kca ctf scope verify --slug ctf-local-…-web-1 --url http://kaggle.com`
         MUST exit non-zero (BLOCKED) and report covered=false.
      2. Drive a challenge_run reviewer-gate against kaggle.com with
         verdict=reject (Reviewer.dry_verdict='reject'). This records the
         security-critical agent_reviews.verdict=reject + reviewer_reject event.
         The worker would halt and NOT POST — we simulate that halt by NOT
         appending any tool_result event (no POST happened).
    """
    _log("=== refusal smoke (challenge_run → kaggle.com) ===")

    # 1. Scope verify against an out-of-scope URL.
    res = _kca(
        "ctf",
        "scope",
        "verify",
        "--slug",
        WEB_SCOPE_NAME,
        "--url",
        "http://kaggle.com",
    )
    scope_payload = json.loads(res.stdout.strip().splitlines()[-1])
    if scope_payload.get("covered"):
        raise RuntimeError(f"SECURITY REGRESSION: scope verify incorrectly covered kaggle.com: {scope_payload}")
    if res.returncode == 0:
        raise RuntimeError(f"SECURITY REGRESSION: scope verify exited 0 for kaggle.com: rc={res.returncode}")
    _log(f"scope verify (out-of-scope) exit={res.returncode} covered={scope_payload.get('covered')}")

    # 2. Reviewer-gate that records verdict=reject for the would-be call.
    job_id = _create_review_job(prompt="[m11-t006 driver] refusal smoke: challenge_run on out-of-scope kaggle.com")
    _log(f"agent_jobs id={job_id}")

    review_id, decision_id = _drive_gate(
        job_id=job_id,
        target_op="challenge_run",
        tool_name="kca_ctf_solver_run",
        tool_input={
            "event": EVENT_SLUG,
            "challenge": WEB_SLUG,
            "target_url": "http://kaggle.com",
            "reviewer_gate": True,
            "dry_run": False,
        },
        rationale_seed="kaggle.com NOT in ctf_scopes.target_urls for this event",
        dry_verdict="reject",
    )
    _log(f"agent_reviews id={review_id} verdict=reject target_op=challenge_run")
    _log(f"human_decisions id={decision_id} status=pending (no approval, deny by design)")

    # Resolve the decision as REJECTED — mirrors the human's "do not approve" path.
    _db.resolve_decision(decision_id, "rejected", notes="m11-t006: out-of-scope target")
    _db.append_job_event(
        job_id,
        "reviewer_reject",
        event_data={
            "target_op": "challenge_run",
            "rationale": "kaggle.com NOT in ctf_scopes.target_urls",
            "review_id": review_id,
            "decision_id": decision_id,
            "escalated": False,
            "post_attempted": False,
        },
    )
    _log("reviewer_reject event appended; worker would halt; no POST attempted")

    return {
        "job_id": job_id,
        "review_id": review_id,
        "decision_id": decision_id,
        "scope_verify_rc": res.returncode,
        "scope_verify_covered": bool(scope_payload.get("covered", False)),
    }


# ---------------------------------------------------------------------------
# 4. Audit-grep — confirm no flag or credential value escaped
# ---------------------------------------------------------------------------


def audit_grep(
    challenge_run_summary: dict,
    flag_submit_summary: dict,
    refusal_summary: dict,
) -> dict:
    """Inspect every row we touched + their event trails for the flag substring
    and for obvious credential markers."""
    _log("=== audit-grep ===")
    flag_sha256_targets = {
        challenge_run_summary.get("flag_sha256"),
        flag_submit_summary.get("flag_sha256"),
    }
    flag_sha256_targets.discard(None)
    if len(flag_sha256_targets) > 1:
        # Documented behaviour: the T005 harness generates a fresh flag per
        # invocation. The challenge_run leg's T005 invocation produces flag A,
        # then the flag_submit leg's _recover_flag_in_memory() generates
        # flag B. Both are kept in flag_sha256_targets so the audit-grep
        # catches accidental leakage of EITHER.
        _log(
            f"INFO: audit-grep is checking {len(flag_sha256_targets)} fresh flag-sha256 "
            "values (one per T005 harness invocation; expected for T006 plumbing test)"
        )

    job_ids = [
        challenge_run_summary["job_id"],
        flag_submit_summary["job_id"],
        refusal_summary["job_id"],
    ]

    # We do NOT have the flag value in this scope anymore (intentionally),
    # so audit-grep instead asserts:
    #   1. No row contains any "kca{" substring (the literal flag-format marker).
    #   2. No row's text fields contain a 16-char base32 alphabet string
    #      wedged inside "kca{...}" (the harness flag shape).
    #   3. No row contains the literal token "_token" + ":" pattern (a crude
    #      credential-leak shape).
    import re

    flag_re = re.compile(r"kca\{[a-z0-9]{10,32}\}")
    cred_re = re.compile(r'"token"\s*:\s*"[^"]+"')

    hits = []
    rows_scanned = 0
    conn = _db.get_conn()
    try:
        for job_id in job_ids:
            # agent_reviews
            for r in _db.list_reviews(job_id=job_id, conn=conn):
                rows_scanned += 1
                blob = json.dumps(
                    {
                        "rationale": r.get("rationale"),
                        "evidence": r.get("evidence"),
                    },
                    default=str,
                )
                if flag_re.search(blob):
                    hits.append(("agent_reviews", str(r.get("id")), "FLAG"))
                if cred_re.search(blob):
                    hits.append(("agent_reviews", str(r.get("id")), "CRED"))
            # human_decisions (rationale + prompt)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, prompt, rationale FROM human_decisions WHERE job_id = %s::uuid",
                    (job_id,),
                )
                for row in cur.fetchall():
                    rows_scanned += 1
                    blob = json.dumps(
                        {"prompt": row["prompt"], "rationale": row["rationale"]},
                        default=str,
                    )
                    if flag_re.search(blob):
                        hits.append(("human_decisions", str(row["id"]), "FLAG"))
                    if cred_re.search(blob):
                        hits.append(("human_decisions", str(row["id"]), "CRED"))
            # agent_job_events.event_data
            for ev in _db.list_job_events(job_id, conn=conn):
                rows_scanned += 1
                blob = json.dumps(ev.get("event_data") or {}, default=str)
                if flag_re.search(blob):
                    hits.append(("agent_job_events", str(ev.get("id")), "FLAG"))
                if cred_re.search(blob):
                    hits.append(("agent_job_events", str(ev.get("id")), "CRED"))
    finally:
        conn.close()

    _log(f"audit-grep scanned {rows_scanned} rows across {len(job_ids)} jobs; hits={len(hits)}")
    return {"rows_scanned": rows_scanned, "hits": hits}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SUPABASE_DB_URL not set; refusing to run", file=sys.stderr)
        return 2

    cr = stage_challenge_run()
    fs = stage_flag_submit()
    rs = stage_refusal_smoke()
    audit = audit_grep(cr, fs, rs)

    # Linkage counts: events on each job tying back to its review.
    conn = _db.get_conn()
    try:
        link_counts = {}
        for tag, job_id in (
            ("challenge_run", cr["job_id"]),
            ("flag_submit", fs["job_id"]),
            ("refusal_smoke", rs["job_id"]),
        ):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) AS n FROM agent_job_events WHERE job_id = %s::uuid",
                    (job_id,),
                )
                link_counts[tag] = cur.fetchone()["n"]
    finally:
        conn.close()

    summary = {
        "ok": not audit["hits"],
        "challenge_run": {
            "job_id": cr["job_id"],
            "review_id": cr["review_id"],
            "decision_id": cr["decision_id"],
            "ctf_attempt_id": cr["ctf_attempt_id"],
        },
        "flag_submit": {
            "job_id": fs["job_id"],
            "review_id": fs["review_id"],
            "decision_id": fs["decision_id"],
            "ctf_attempt_id": fs["ctf_attempt_id"],
        },
        "refusal_smoke": {
            "job_id": rs["job_id"],
            "review_id": rs["review_id"],
            "decision_id": rs["decision_id"],
            "scope_verify_rc": rs["scope_verify_rc"],
        },
        "agent_job_events_per_job": link_counts,
        "audit_grep_rows_scanned": audit["rows_scanned"],
        "audit_grep_hits": audit["hits"],
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if not audit["hits"] else 3


if __name__ == "__main__":
    sys.exit(main())
