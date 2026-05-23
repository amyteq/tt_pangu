import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Card, Empty, Spinner, Table } from "../ui";
import {
  db,
  type AgentJob,
  type AgentJobEvent,
  type AgentTelemetrySpan,
} from "../lib/db";

const EVENT_TYPES = [
  "tool_call",
  "tool_result",
  "decision_request",
  "approval_pause",
  "reviewer_reject",
  "review_verdict",
  "budget_warning",
  "error",
];

function SpanLane({
  spans,
  jobStart,
}: {
  spans: AgentTelemetrySpan[];
  jobStart: number;
}): JSX.Element {
  if (spans.length === 0) return <Empty>No spans for this job.</Empty>;
  const ends = spans.map((s) =>
    s.ended_at ? new Date(s.ended_at).getTime() : Date.now(),
  );
  const maxEnd = Math.max(...ends);
  const dur = Math.max(1, maxEnd - jobStart);
  const groups = Array.from(new Set(spans.map((s) => s.kind || s.name)));
  const width = 800;
  const rowHeight = 22;
  const padding = 4;

  return (
    <svg
      data-testid="swim-lane"
      width={width}
      height={groups.length * rowHeight + 2 * padding}
      role="img"
      aria-label="run timeline swim-lane"
      className="rounded border border-slate-200 bg-white"
    >
      {groups.map((g, i) => (
        <g key={g} transform={`translate(0, ${padding + i * rowHeight})`}>
          <text x={2} y={14} className="fill-slate-500 text-[10px]">
            {g}
          </text>
          {spans
            .filter((s) => (s.kind || s.name) === g)
            .map((s, j) => {
              const start = new Date(s.started_at).getTime();
              const end = s.ended_at
                ? new Date(s.ended_at).getTime()
                : start + 100;
              const x = 60 + ((start - jobStart) / dur) * (width - 80);
              const w = Math.max(2, ((end - start) / dur) * (width - 80));
              const fill =
                s.status === "error"
                  ? "#fca5a5"
                  : s.ended_at
                    ? "#86efac"
                    : "#fde68a";
              return (
                <g key={j}>
                  <rect
                    x={x}
                    y={2}
                    width={w}
                    height={rowHeight - 6}
                    fill={fill}
                  >
                    <title>
                      {s.name} • {s.duration_ms ?? 0}ms •{" "}
                      {JSON.stringify(s.attributes ?? {})}
                    </title>
                  </rect>
                </g>
              );
            })}
        </g>
      ))}
    </svg>
  );
}

function EventLog({ events }: { events: AgentJobEvent[] }): JSX.Element {
  const [filter, setFilter] = useState<string>("");
  const [page, setPage] = useState(0);
  const pageSize = 25;
  const filtered = useMemo(
    () => (filter ? events.filter((e) => e.event_type === filter) : events),
    [events, filter],
  );
  const pageRows = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const [open, setOpen] = useState<Record<number, boolean>>({});

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-slate-500">Filter:</label>
        <select
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(0);
          }}
          className="rounded border border-slate-200 px-2 py-1 text-sm"
        >
          <option value="">all</option>
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <span className="text-xs text-slate-500">
          {filtered.length} events
        </span>
      </div>
      <Table
        rows={pageRows}
        columns={[
          {
            key: "ts",
            header: "ts",
            render: (e) => e.created_at.slice(11, 19),
          },
          {
            key: "type",
            header: "type",
            render: (e) => <Badge>{e.event_type}</Badge>,
          },
          {
            key: "summary",
            header: "summary",
            render: (e) => {
              const ed = (e.event_data ?? {}) as Record<string, unknown>;
              const summary =
                String(ed.tool ?? ed.operation ?? ed.verdict ?? "");
              return (
                <button
                  type="button"
                  className="text-left text-slate-700 hover:text-slate-900"
                  onClick={() =>
                    setOpen((o) => ({ ...o, [e.id]: !o[e.id] }))
                  }
                >
                  {summary || "—"}
                  {open[e.id] && (
                    <pre className="mt-1 max-w-lg overflow-x-auto rounded bg-slate-50 p-2 text-[11px]">
                      {JSON.stringify(e.event_data, null, 2)}
                    </pre>
                  )}
                </button>
              );
            },
          },
        ]}
        empty={<Empty>No events.</Empty>}
      />
      {filtered.length > pageSize && (
        <div className="flex justify-between text-xs text-slate-500">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="disabled:opacity-50"
          >
            ← prev
          </button>
          <span>
            page {page + 1} / {Math.ceil(filtered.length / pageSize)}
          </span>
          <button
            type="button"
            disabled={(page + 1) * pageSize >= filtered.length}
            onClick={() => setPage((p) => p + 1)}
            className="disabled:opacity-50"
          >
            next →
          </button>
        </div>
      )}
    </div>
  );
}

export function RunTimeline(): JSX.Element {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<AgentJob | null>(null);
  const [events, setEvents] = useState<AgentJobEvent[]>([]);
  const [spans, setSpans] = useState<AgentTelemetrySpan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) return;
    let live = true;
    (async () => {
      try {
        const [j, e, s] = await Promise.all([
          db.getJob(jobId),
          db.listJobEvents(jobId),
          db.listJobSpans(jobId),
        ]);
        if (!live) return;
        setJob(j);
        setEvents(e);
        setSpans(s);
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [jobId]);

  if (loading) return <Spinner />;
  if (!job) {
    return (
      <Card>
        <Empty>
          Job not found.{" "}
          <Link to="/runs" className="text-indigo-700 hover:underline">
            ← back to runs
          </Link>
        </Empty>
      </Card>
    );
  }

  const jobStart = job.started_at
    ? new Date(job.started_at).getTime()
    : new Date(job.created_at).getTime();

  return (
    <div className="space-y-4">
      <Card title="Job summary">
        <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-500">skill</dt>
            <dd>
              {(job.policy as { skill_name?: string } | null)?.skill_name ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">status</dt>
            <dd>
              <Badge>{job.status}</Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">turns</dt>
            <dd>{job.turns_used ?? 0}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">cost ($)</dt>
            <dd>{(job.cost_usd ?? 0).toFixed(4)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">started</dt>
            <dd>{job.started_at?.slice(0, 19) ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">ended</dt>
            <dd>{job.finished_at?.slice(0, 19) ?? "—"}</dd>
          </div>
        </dl>
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="Spans" className="lg:col-span-2">
          <SpanLane spans={spans} jobStart={jobStart} />
        </Card>
        <Card title="Event log">
          <EventLog events={events} />
        </Card>
      </div>
    </div>
  );
}
