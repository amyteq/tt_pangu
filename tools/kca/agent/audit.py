"""Audit logger: records policy decisions for tool executions to JSONL/DB."""

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
    return _repo_root() / ".agent" / "audit.jsonl"


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


@dataclass
class AuditLogger:
    backend: str = "file"  # "file" | "db" | "both"
    file_path: Path = field(default_factory=_default_audit_path)
    db_available: bool = False
    session_id: str = field(default_factory=lambda: _SESSION_ID)

    def _ensure_dir(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            sys.stderr.write(f"[audit warn] mkdir failed: {exc}\n")

    def record(self, rec: AuditRecord) -> None:
        if self.backend in ("file", "both"):
            self._ensure_dir()
            try:
                with self.file_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
            except OSError as exc:
                sys.stderr.write(f"[audit warn] write failed: {exc}\n")

        if self.backend in ("db", "both") and self.db_available:
            try:
                from db import append_job_event  # type: ignore

                append_job_event(
                    job_id=str(uuid.UUID(int=0)),
                    event_type="tool_audit",
                    event_data=rec.to_dict(),
                )
            except Exception as exc:
                sys.stderr.write(f"[audit warn] db append failed: {exc}\n")

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
        )
        self.record(rec)
        return rec
