"""OpenTelemetry-style instrumentation for the M6 worker (ADR-0013).

This is a minimal in-house tracer that mirrors the small slice of the
OTEL SDK surface we actually use — start_span, end, attributes, context
manager. Three exporters are supported:

- console : stderr, one line per finished span.
- sqlite  : append to KCA_OTEL_SQLITE_PATH (default `.agent/telemetry.sqlite`).
- supabase: best-effort `db.record_span(...)`; failures log to stderr.

The full opentelemetry SDK is a heavy install for what we need today and
isn't on the env image; switching to it later is a drop-in because the
exporter contract is identical (kind/name/attrs/started_at/ended_at).
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------------

_ENV_ENABLED = "KCA_OTEL_ENABLED"
_ENV_EXPORTERS = "KCA_OTEL_EXPORTERS"
_ENV_SQLITE_PATH = "KCA_OTEL_SQLITE_PATH"
_ENV_MIN_DURATION_MS = "KCA_OTEL_MIN_DURATION_MS"

_DEFAULT_SQLITE_PATH = ".agent/telemetry.sqlite"


def _enabled() -> bool:
    return os.environ.get(_ENV_ENABLED, "0").strip() == "1"


def _exporters() -> list[str]:
    raw = os.environ.get(_ENV_EXPORTERS, "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _min_duration_ms() -> int:
    try:
        return int(os.environ.get(_ENV_MIN_DURATION_MS, "0"))
    except ValueError:
        return 0


def _sqlite_path() -> str:
    return os.environ.get(_ENV_SQLITE_PATH, _DEFAULT_SQLITE_PATH)


def _trace_id() -> str:
    return secrets.token_hex(16)  # 32 hex chars


def _span_id() -> str:
    return secrets.token_hex(8)  # 16 hex chars


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


# ---------------------------------------------------------------------------
# Span
# ---------------------------------------------------------------------------


class Span:
    """Minimal mutable span object."""

    def __init__(
        self,
        *,
        kind: str,
        name: str,
        trace_id: str,
        parent_span_id: str | None,
        job_id: str | None,
        tracer: "Tracer",
    ) -> None:
        self.trace_id = trace_id
        self.span_id = _span_id()
        self.parent_span_id = parent_span_id
        self.job_id = job_id
        self.kind = kind
        self.name = name
        self.attributes: dict[str, Any] = {}
        self.started_at = _now()
        self._started_monotonic = time.monotonic()
        self.ended_at: _dt.datetime | None = None
        self.duration_ms: int | None = None
        self.status = "ok"
        self.error: str | None = None
        self._tracer = tracer
        self._closed = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_attributes(self, mapping: dict[str, Any]) -> None:
        self.attributes.update(mapping)

    def set_status_error(self, message: str) -> None:
        self.status = "error"
        self.error = message

    def end(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.ended_at = _now()
        self.duration_ms = int((time.monotonic() - self._started_monotonic) * 1000)
        self._tracer._export(self)


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class Tracer:
    def __init__(self, job_id: str | None = None, trace_id: str | None = None) -> None:
        self.job_id = job_id
        self.trace_id = trace_id or _trace_id()
        self._stack: list[Span] = []
        self._exporters: list[str] = _exporters()
        self._enabled = _enabled() and bool(self._exporters)
        self.root_span_id: str | None = None

    def is_enabled(self) -> bool:
        return self._enabled

    def start_span(self, *, kind: str, name: str) -> Span:
        parent = self._stack[-1] if self._stack else None
        span = Span(
            kind=kind,
            name=name,
            trace_id=self.trace_id,
            parent_span_id=parent.span_id if parent else None,
            job_id=self.job_id,
            tracer=self,
        )
        self._stack.append(span)
        if self.root_span_id is None:
            self.root_span_id = span.span_id
        return span

    @contextlib.contextmanager
    def span(self, *, kind: str, name: str):
        span = self.start_span(kind=kind, name=name)
        try:
            yield span
        except Exception as exc:
            span.set_status_error(str(exc))
            raise
        finally:
            # Pop and end.
            try:
                self._stack.remove(span)
            except ValueError:
                pass
            span.end()

    # ---- exporters ------------------------------------------------------

    def _export(self, span: Span) -> None:
        if not self._enabled:
            return
        min_ms = _min_duration_ms()
        if span.duration_ms is not None and span.duration_ms < min_ms:
            return
        for ex in self._exporters:
            try:
                if ex == "console":
                    _export_console(span)
                elif ex == "sqlite":
                    _export_sqlite(span)
                elif ex == "supabase":
                    _export_supabase(span)
                # unknown exporter names are ignored silently
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[telemetry] exporter {ex!r} failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------


def _export_console(span: Span) -> None:
    attrs = json.dumps(span.attributes, default=str, ensure_ascii=False)
    print(
        f"kind={span.kind} name={span.name} duration_ms={span.duration_ms} status={span.status} attrs={attrs}",
        file=sys.stderr,
    )


_SQLITE_INIT_SQL = """
CREATE TABLE IF NOT EXISTS spans (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id        TEXT NOT NULL,
  span_id         TEXT NOT NULL,
  parent_span_id  TEXT,
  job_id          TEXT,
  kind            TEXT NOT NULL,
  name            TEXT NOT NULL,
  started_at      TEXT NOT NULL,
  ended_at        TEXT,
  duration_ms     INTEGER,
  attributes      TEXT NOT NULL DEFAULT '{}',
  status          TEXT NOT NULL DEFAULT 'ok',
  error           TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_kind  ON spans(kind);
CREATE INDEX IF NOT EXISTS idx_spans_job   ON spans(job_id);
"""


def _export_sqlite(span: Span) -> None:
    path = Path(_sqlite_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_SQLITE_INIT_SQL)
        conn.execute(
            """
            INSERT INTO spans
              (trace_id, span_id, parent_span_id, job_id, kind, name,
               started_at, ended_at, duration_ms, attributes, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span.trace_id,
                span.span_id,
                span.parent_span_id,
                span.job_id,
                span.kind,
                span.name,
                span.started_at.isoformat(),
                span.ended_at.isoformat() if span.ended_at else None,
                span.duration_ms,
                json.dumps(span.attributes, default=str),
                span.status,
                span.error,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _export_supabase(span: Span) -> None:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
        import db as _db
    except Exception as exc:
        print(f"[telemetry.supabase] db import failed: {exc}", file=sys.stderr)
        return
    _db.record_span(
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        job_id=span.job_id,
        kind=span.kind,
        name=span.name,
        started_at=span.started_at,
        ended_at=span.ended_at,
        duration_ms=span.duration_ms,
        attributes=span.attributes,
        status=span.status,
        error=span.error,
    )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def start_job_span(tracer: Tracer, job_id: str, prompt: str) -> Span:
    span = tracer.start_span(kind="job", name="agent_worker.run")
    span.set_attributes({"job_id": job_id, "prompt_preview": (prompt or "")[:80]})
    return span


@contextlib.contextmanager
def with_turn_span(tracer: Tracer, turn_n: int):
    with tracer.span(kind="turn", name=f"turn[{turn_n}]") as span:
        span.set_attribute("turn", turn_n)
        yield span


@contextlib.contextmanager
def with_tool_span(tracer: Tracer, tool_name: str, tool_input: dict | None = None):
    with tracer.span(kind="tool", name=f"tool.{tool_name}") as span:
        span.set_attribute("tool", tool_name)
        if tool_input is not None:
            span.set_attribute("input_keys", sorted(tool_input.keys()))
        yield span


@contextlib.contextmanager
def with_review_span(tracer: Tracer, target_op: str):
    with tracer.span(kind="review", name=f"review.{target_op}") as span:
        span.set_attribute("target_op", target_op)
        yield span


@contextlib.contextmanager
def with_probe_span(tracer: Tracer, endpoint_name: str):
    with tracer.span(kind="local_probe", name=f"probe.{endpoint_name}") as span:
        span.set_attribute("endpoint", endpoint_name)
        yield span


@contextlib.contextmanager
def with_local_call_span(tracer: Tracer, endpoint_name: str, model: str):
    with tracer.span(kind="llm", name=f"local_call.{endpoint_name}") as span:
        span.set_attribute("endpoint", endpoint_name)
        span.set_attribute("model", model)
        yield span


def build_tracer(job_id: str | None = None) -> Tracer:
    return Tracer(job_id=job_id)
