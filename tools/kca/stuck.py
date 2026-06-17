"""kca stuck detector + human escalation (M14-T007 / ADR-0020 §8).

The stuck detector fires when N (= ``goal.stuck_threshold``, default 3)
consecutive **scored** submissions show no monotone LB improvement AND
idea-sourcing (``kca explore propose-next``) returned 0 fresh candidates.

On stuck:
  1. build a redacted escalation payload (goal vs current; tried-strategies
     table; sources consulted; ruled-out hypotheses; concrete questions),
  2. write ``docs/escalations/<comp>-<ts>.md`` (the human-readable mirror;
     ``ts`` is injectable so tests are deterministic),
  3. insert a ``human_decisions`` row with
     ``decision_type=kaggle.exploration_stuck`` carrying the same payload in
     ``options`` (the row is authoritative; the doc mirrors it),
  4. surface in the existing Approval Inbox (no new surface).

A human response (UI form or ``kca decisions approve --notes "<direction>"``)
becomes the new exploration seed; ``resume_seed_from_notes`` parses the notes
as a structured option or free-text direction. The resolving
``human_decisions.id`` is recorded on the resumed run's
``analysis_jsonb.escalation_id`` by the caller (T008 loop).

Redaction (ADR-0020 §8): the payload + doc pass through
``redact_escalation_payload`` — a ``_redact_tool_input``-style filter — so no
DSN / credential / flag is rendered into the committed doc or the audit row.
This module never calls a real Kaggle push / submit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DECISION_TYPE = "kaggle.exploration_stuck"
DEFAULT_STUCK_THRESHOLD = 3

# ---------------------------------------------------------------------------
# Redaction (reuse the reviewer's _redact_tool_input posture, generalized).
#
# The escalation payload aggregates run / source / goal data that MUST NOT
# leak a DSN, an API credential, or a CTF flag into the committed doc or the
# audit row. We scrub by (a) key name and (b) value shape. This is the same
# deny-default spirit as src/worker/reviewer.py:_redact_tool_input — there it
# is scoped to flag_submit; here the payload is heterogeneous so we walk it.
# ---------------------------------------------------------------------------

_REDACTED = "[REDACTED]"

# Substring match on the *key* (case-insensitive) → redact the value.
_SECRET_KEY_SUBSTRINGS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "kaggle_key",
    "kaggle_username",
    "aws_",
    "dsn",
    "conninfo",
    "credential",
    "private_key",
    "flag",
    "anthropic_api_key",
)

# Value-shape patterns that look like a secret regardless of the key name.
_SECRET_VALUE_PATTERNS = (
    # libpq / SQLAlchemy DSNs: postgres://user:pass@host/db, postgresql+psycopg://...
    re.compile(r"\b(?:postgres(?:ql)?|mysql|redis|mongodb)(?:\+\w+)?://[^\s\"']+"),
    # bare user:pass@host
    re.compile(r"\b[\w.-]+:[^\s:@/\"']{3,}@[\w.-]+"),
    # CTF-style flags: flag{...} / CTF{...} / picoCTF{...}
    re.compile(r"\b[A-Za-z0-9_]{0,12}\{[^}\n]{2,}\}"),
    # AWS access key id
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Anthropic key prefix
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{8,}"),
)


def _key_is_secret(key: str) -> bool:
    k = str(key).lower()
    return any(sub in k for sub in _SECRET_KEY_SUBSTRINGS)


def _scrub_str(value: str) -> str:
    out = value
    for pat in _SECRET_VALUE_PATTERNS:
        out = pat.sub(_REDACTED, out)
    return out


def redact_escalation_payload(value: Any) -> Any:
    """Recursively strip secret-shaped keys/values from an escalation payload.

    - A dict key whose name matches a known-secret substring has its value
      replaced wholesale with ``[REDACTED]``.
    - Any string value (at any depth) has DSN / credential / flag substrings
      masked.
    - Lists / tuples / dicts are walked; scalars pass through unchanged.

    Pure + side-effect-free so tests can assert a no-secret sentinel against
    both the doc and the row payload.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _key_is_secret(k):
                out[k] = _REDACTED
            else:
                out[k] = redact_escalation_payload(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_escalation_payload(v) for v in value]
    if isinstance(value, str):
        return _scrub_str(value)
    return value


# ---------------------------------------------------------------------------
# Stuck heuristic (ADR-0020 §8).
# ---------------------------------------------------------------------------


def consecutive_non_improving(
    submissions: list[dict],
    *,
    score_key: str = "public_lb_score",
) -> int:
    """Count the trailing run of SCORED submissions with no monotone improvement.

    ``submissions`` are ordered oldest → newest. A higher-is-better metric is
    assumed (ADR-0020 §1; M14's getting-started surface is accuracy/F1).

    NULL-score rule (ADR-0020 §8 / skeptic edge_cases.4): a submission whose
    ``public_lb_score`` is NULL is "no result" — it neither advances the best
    nor resets the non-improving counter; it is skipped entirely.

    Returns the number of consecutive scored submissions (counting from the
    most-recent scored one backward) that failed to set a new best vs the best
    seen *before* them. A new best resets the counter to 0.
    """
    best: float | None = None
    counter = 0
    for sub in submissions:
        raw = sub.get(score_key)
        if raw is None:
            # NULL score: no result — do not advance, do not reset.
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            continue
        if best is None or score > best:
            best = score
            counter = 0  # improvement → reset
        else:
            counter += 1  # no monotone improvement
    return counter


def is_stuck(
    submissions: list[dict],
    fresh_candidate_count: int,
    *,
    threshold: int = DEFAULT_STUCK_THRESHOLD,
    score_key: str = "public_lb_score",
) -> bool:
    """True when stuck: ≥ threshold non-improving SCORED subs AND 0 fresh cands.

    BOTH conditions are required (ADR-0020 §8). Fires at *exactly* the
    threshold (>= threshold), never before; and never while fresh candidates
    exist regardless of the non-improving run.
    """
    if fresh_candidate_count > 0:
        return False
    return consecutive_non_improving(submissions, score_key=score_key) >= int(threshold)


# ---------------------------------------------------------------------------
# Escalation artefact.
# ---------------------------------------------------------------------------


def escalation_filename(slug: str, ts: str) -> str:
    """Deterministic ``<comp>-<ts>.md`` name; ``ts`` is injected (no wall clock)."""
    safe_slug = re.sub(r"[^A-Za-z0-9_.-]", "-", str(slug))
    safe_ts = re.sub(r"[^A-Za-z0-9_.-]", "-", str(ts))
    return f"{safe_slug}-{safe_ts}.md"


def build_escalation_payload(
    *,
    competition: str,
    goal: dict,
    current: dict,
    tried_strategies: list[dict],
    sources_consulted: list[dict],
    ruled_out_hypotheses: list[str],
    questions: list[str],
    ts: str,
) -> dict:
    """Build the structured escalation payload (ADR-0020 §8 schema), redacted.

    The returned dict is already passed through ``redact_escalation_payload``
    so callers can persist it to both the doc and the ``human_decisions`` row
    without a second scrub.
    """
    payload = {
        "decision_type": DECISION_TYPE,
        "competition": competition,
        "ts": ts,
        "goal": {
            "target_lb_score": goal.get("target_lb_score"),
            "target_lb_rank": goal.get("target_lb_rank"),
            "exit_strategy": goal.get("exit_strategy"),
        },
        "current": {
            "best_public_lb_score": current.get("best_public_lb_score"),
            "best_rank": current.get("best_rank"),
            "pushes_used": current.get("pushes_used"),
            "max_total_pushes": current.get("max_total_pushes"),
        },
        "tried_strategies": [
            {
                "axes": s.get("axes") or s.get("cell") or {},
                "holdout_accuracy": s.get("holdout_accuracy"),
                "public_lb_score": s.get("public_lb_score"),
                "status": s.get("status"),
            }
            for s in tried_strategies
        ],
        "sources_consulted": [
            {
                "source_url": s.get("source_url"),
                "trust_label": s.get("trust_label"),
                "summary": s.get("summary") or s.get("rationale") or "",
            }
            for s in sources_consulted
        ],
        "ruled_out_hypotheses": list(ruled_out_hypotheses),
        "questions": list(questions),
    }
    return redact_escalation_payload(payload)


def render_escalation_md(payload: dict) -> str:
    """Render the human-readable escalation doc from a (redacted) payload.

    Required sections (ADR-0020 §8): goal vs current; tried-strategies table;
    sources consulted; ruled-out hypotheses; concrete questions.
    """
    goal = payload.get("goal") or {}
    current = payload.get("current") or {}
    lines: list[str] = []
    lines.append(f"# Exploration stuck — {payload.get('competition')}")
    lines.append("")
    lines.append(
        "_Auto-generated by the M14 stuck detector (ADR-0020 §8). The "
        "`human_decisions` row is authoritative; this file mirrors its "
        "redacted payload for humans + git history. No DSN / credential / "
        "flag is rendered here._"
    )
    lines.append("")
    lines.append(f"- **decision_type:** `{payload.get('decision_type')}`")
    lines.append(f"- **timestamp:** {payload.get('ts')}")
    lines.append("")

    lines.append("## Goal vs current")
    lines.append("")
    lines.append("| | Goal | Current |")
    lines.append("|---|---|---|")
    lines.append(f"| LB score | {goal.get('target_lb_score')} | {current.get('best_public_lb_score')} |")
    lines.append(f"| LB rank | {goal.get('target_lb_rank')} | {current.get('best_rank')} |")
    lines.append(f"| Pushes | {current.get('max_total_pushes')} (budget) | {current.get('pushes_used')} (used) |")
    lines.append(f"| Exit strategy | {goal.get('exit_strategy')} | — |")
    lines.append("")

    lines.append("## Tried strategies")
    lines.append("")
    lines.append("| Axes | Holdout accuracy | Public LB |")
    lines.append("|---|---|---|")
    for s in payload.get("tried_strategies") or []:
        axes = json.dumps(s.get("axes") or {}, sort_keys=True)
        lines.append(f"| `{axes}` | {s.get('holdout_accuracy')} | {s.get('public_lb_score')} |")
    if not (payload.get("tried_strategies") or []):
        lines.append("| _none recorded_ | — | — |")
    lines.append("")

    lines.append("## Sources consulted")
    lines.append("")
    srcs = payload.get("sources_consulted") or []
    if srcs:
        for s in srcs:
            lines.append(f"- [{s.get('trust_label')}] {s.get('source_url')} — {s.get('summary')}")
    else:
        lines.append("- _none recorded_")
    lines.append("")

    lines.append("## Ruled-out hypotheses")
    lines.append("")
    hyps = payload.get("ruled_out_hypotheses") or []
    if hyps:
        for h in hyps:
            lines.append(f"- {h}")
    else:
        lines.append("- _none recorded_")
    lines.append("")

    lines.append("## Questions for the human")
    lines.append("")
    qs = payload.get("questions") or []
    if qs:
        for q in qs:
            lines.append(f"- {q}")
    else:
        lines.append("- _none recorded_")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        'Respond with `kca decisions approve --id <id> --notes "<direction>"` '
        "(or the Approval Inbox form). The notes become the next exploration "
        "seed; the resolving decision id is recorded on the resumed run's "
        "`analysis_jsonb.escalation_id`."
    )
    lines.append("")
    return "\n".join(lines)


def _escalations_dir() -> Path:
    # tools/kca/stuck.py -> repo root is two parents up from tools/kca/.
    return Path(__file__).resolve().parent.parent.parent / "docs" / "escalations"


def write_escalation_doc(payload: dict, *, ts: str, escalations_dir: Path | None = None) -> Path:
    """Write ``docs/escalations/<comp>-<ts>.md`` from a redacted payload.

    Returns the written path. ``ts`` is injected so the filename is
    deterministic (no ``datetime.now`` / wall clock). ``escalations_dir`` is
    overridable for tests so we never pollute the real docs tree.
    """
    out_dir = escalations_dir or _escalations_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / escalation_filename(payload.get("competition", "comp"), ts)
    path.write_text(render_escalation_md(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# human_decisions row (#60-aware) + resume.
# ---------------------------------------------------------------------------


def _human_decisions_has_column(_db, column: str) -> bool:
    """True if ``human_decisions`` has ``column`` in the live schema (#60-aware).

    The ``approved_by_user_id`` FK is issue #60 and lands separately; this
    helper lets T007 write it when present and silently skip it when absent
    (FK-ready, not FK-required). Never raises.
    """
    try:
        conn = _db.get_conn()
    except Exception:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_name = 'human_decisions'
                   AND column_name = %s
                 LIMIT 1
                """,
                (column,),
            )
            return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def insert_stuck_decision(
    _db,
    *,
    payload: dict,
    prompt: str | None = None,
    job_id: str | None = None,
    approved_by_user_id: str | None = None,
) -> str:
    """Insert a pending ``kaggle.exploration_stuck`` human_decisions row.

    The redacted ``payload`` is stored in ``options`` (the existing structured
    column; ADR-0020 §8 treats the row as authoritative). Writes
    ``approved_by_user_id`` only if that column exists in the live schema
    (issue #60); otherwise the parameter is ignored — the row is FK-ready.
    Returns the decision id.
    """
    safe_payload = redact_escalation_payload(payload)
    prompt = prompt or (
        f"Exploration stuck for {safe_payload.get('competition')}: "
        f"{len(safe_payload.get('tried_strategies') or [])} strategies tried, "
        "0 fresh candidates. Provide a new direction."
    )
    decision_id = _db.insert_approval_request(
        DECISION_TYPE,
        prompt,
        options=safe_payload,
        job_id=job_id,
    )
    if approved_by_user_id is not None and _human_decisions_has_column(_db, "approved_by_user_id"):
        try:
            conn = _db.get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE human_decisions SET approved_by_user_id = %s::uuid WHERE id = %s::uuid",
                        (approved_by_user_id, decision_id),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            # FK hardening is #60; a write failure here must never block the
            # escalation (the column is best-effort in T007).
            pass
    return decision_id


# Structured-option vocabulary the loop understands when notes start with one
# of these tokens (case-insensitive, "key=value" or "key: value"). Anything
# else is treated as a free-text direction.
_STRUCTURED_KEYS = ("backbone", "image_size", "epochs", "axis", "strategy")


def resume_seed_from_notes(notes: str | None) -> dict:
    """Parse human approval notes into a new exploration seed.

    Returns ``{"kind": "structured"|"free_text"|"empty", "options": {...},
    "direction": "<text>"}``. A structured note looks like
    ``backbone=convnext_tiny image_size=331`` (whitespace- or comma-separated
    ``key=value`` / ``key: value`` pairs over the known axis vocabulary);
    anything else is free text the loop seeds a research pass from.
    """
    if not notes or not str(notes).strip():
        return {"kind": "empty", "options": {}, "direction": ""}
    text = str(notes).strip()
    pairs: dict[str, Any] = {}
    # Tokenize on commas / whitespace; accept key=value and key:value.
    for token in re.split(r"[,\s]+", text):
        if not token:
            continue
        m = re.match(r"^([A-Za-z_]+)\s*[:=]\s*(.+)$", token)
        if not m:
            continue
        key, raw = m.group(1).lower(), m.group(2)
        if key not in _STRUCTURED_KEYS:
            continue
        pairs[key] = _coerce(raw)
    if pairs:
        return {"kind": "structured", "options": pairs, "direction": text}
    return {"kind": "free_text", "options": {}, "direction": text}


def _coerce(raw: str) -> Any:
    raw = raw.strip().strip("\"'")
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# Telemetry — escalation count + time-to-resolution per competition.
# ---------------------------------------------------------------------------


def escalation_telemetry(decisions: list[dict]) -> dict:
    """Aggregate escalation telemetry from a list of human_decisions rows.

    Each row is expected to carry ``decision_type``, ``created_at``,
    ``decided_at`` (None while pending). Counts only
    ``kaggle.exploration_stuck`` rows; computes time-to-resolution (seconds)
    for resolved rows and reports count, resolved count, and the mean/total
    resolution time. Pure: callers pass already-fetched rows so the function
    is DB-agnostic and unit-testable.
    """
    esc = [d for d in decisions if d.get("decision_type") == DECISION_TYPE]
    resolutions: list[float] = []
    for d in esc:
        created = d.get("created_at")
        decided = d.get("decided_at")
        if created is None or decided is None:
            continue
        secs = _seconds_between(created, decided)
        if secs is not None and secs >= 0:
            resolutions.append(secs)
    n = len(esc)
    n_resolved = len(resolutions)
    total = round(sum(resolutions), 3) if resolutions else 0.0
    mean = round(total / n_resolved, 3) if n_resolved else None
    return {
        "escalation_count": n,
        "resolved_count": n_resolved,
        "pending_count": n - n_resolved,
        "time_to_resolution_seconds_total": total,
        "time_to_resolution_seconds_mean": mean,
    }


def _seconds_between(a: Any, b: Any) -> float | None:
    """Seconds between two timestamps (datetime or ISO string). None on parse fail."""
    import datetime as _dt

    def _parse(x: Any):
        if hasattr(x, "timestamp"):
            return x
        try:
            return _dt.datetime.fromisoformat(str(x))
        except (ValueError, TypeError):
            return None

    pa, pb = _parse(a), _parse(b)
    if pa is None or pb is None:
        return None
    try:
        return (pb - pa).total_seconds()
    except (TypeError, ValueError):
        return None
