"""Audit logger: records policy decisions for tool executions to JSONL/DB.

M7 shipped the JSONL backend; since ADR-0021 the KCA product log lives at
``.agent/kca/audit.jsonl`` (namespaced away from the Claude Code harness hook
log ``.agent/audit/tool-events.jsonl`` — see ADR-0021 "Two agents"). M8 adds an
optional dual-write into the ``agent_tool_audit`` table (migration 0007) when
``SUPABASE_DB_URL`` is set. The writer never raises on DB failure — the JSONL
line is always the source of truth for offline ops. Override with
``KCA_AUDIT_PATH``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_audit_path() -> Path:
    override = os.environ.get("KCA_AUDIT_PATH")
    if override:
        return Path(override)
    return _repo_root() / ".agent" / "kca" / "audit.jsonl"


@dataclass
class AuditRecord:
    timestamp: str
    session_id: str
    skill_name: str | None
    tool_name: str
    operation: str
    decision: str
    mode: str
    policy_profile: str
    audit_required: bool
    args_hash: str
    job_id: str | None = None
    extra: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _hash_args(args: dict | None) -> str:
    if not args:
        return ""
    try:
        serialized = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        serialized = str(sorted(args.items()))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


_SESSION_ID = os.environ.get("KCA_SESSION_ID") or str(uuid.uuid4())


def _db_configured() -> bool:
    return bool(os.environ.get("SUPABASE_DB_URL") or os.environ.get("SUPABASE_DB_HOST"))


@dataclass
class AuditLogger:
    backend: str = "file"  # "file" | "db" | "both"
    file_path: Path = field(default_factory=lambda: _default_audit_path())
    db_available: bool | None = None
    session_id: str = field(default_factory=lambda: _SESSION_ID)

    def _ensure_dir(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            sys.stderr.write(f"[audit warn] mkdir failed: {exc}\n")

    def _db_enabled(self) -> bool:
        if self.db_available is not None:
            return bool(self.db_available)
        return _db_configured()

    def record(self, rec: AuditRecord) -> None:
        if self.backend in ("file", "both"):
            self._ensure_dir()
            try:
                with self.file_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
            except OSError as exc:
                sys.stderr.write(f"[audit warn] write failed: {exc}\n")

        if self.backend in ("db", "both") and self._db_enabled():
            try:
                # Lazy import: keep the JSONL-only path free of psycopg.
                from tools.kca.db import insert_tool_audit  # type: ignore
            except Exception:
                try:
                    from db import insert_tool_audit  # type: ignore
                except Exception as exc:
                    sys.stderr.write(f"[audit warn] db module unavailable: {exc}\n")
                    return
            try:
                insert_tool_audit(rec.to_dict())
            except Exception as exc:  # pragma: no cover - best-effort DB
                sys.stderr.write(f"[audit warn] db insert failed: {exc}\n")

    def log_policy_decision(
        self,
        *,
        tool: str,
        operation: str,
        decision: str,
        skill_name: str | None = None,
        mode: str = "default",
        policy_profile: str = "default",
        args: dict | None = None,
        audit_required: bool = False,
        job_id: str | None = None,
        extra: dict | None = None,
    ) -> AuditRecord:
        rec = AuditRecord(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            session_id=self.session_id,
            skill_name=skill_name,
            tool_name=tool,
            operation=operation,
            decision=decision,
            mode=mode,
            policy_profile=policy_profile,
            audit_required=audit_required,
            args_hash=_hash_args(args),
            job_id=job_id,
            extra=extra,
        )
        self.record(rec)
        return rec


def log_policy_decision(
    *,
    tool: str,
    operation: str,
    decision: str,
    skill_name: str | None = None,
    mode: str = "default",
    policy_profile: str = "default",
    args: dict | None = None,
    audit_required: bool = False,
    job_id: str | None = None,
    extra: dict | None = None,
    backend: str | None = None,
) -> AuditRecord:
    """Module-level shortcut that auto-selects backend based on env."""
    if backend is None:
        backend = "both" if _db_configured() else "file"
    logger = AuditLogger(backend=backend)
    return logger.log_policy_decision(
        tool=tool,
        operation=operation,
        decision=decision,
        skill_name=skill_name,
        mode=mode,
        policy_profile=policy_profile,
        args=args,
        audit_required=audit_required,
        job_id=job_id,
        extra=extra,
    )
