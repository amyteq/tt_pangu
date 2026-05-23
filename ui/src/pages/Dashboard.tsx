import { useEffect, useState } from "react";
import { Card, Empty, Spinner, Table, Badge } from "../ui";
import { db, type Project, type Competition, type AgentJob, type HumanDecision } from "../lib/db";

function Pill({ status }: { status: string }): JSX.Element {
  const color =
    status === "approved" || status === "succeeded"
      ? "green"
      : status === "rejected" || status === "failed"
        ? "red"
        : status === "pending" || status === "paused" || status === "running" || status === "queued"
          ? "amber"
          : "slate";
  return <Badge color={color}>{status}</Badge>;
}

export function Dashboard(): JSX.Element {
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [jobs, setJobs] = useState<AgentJob[]>([]);
  const [decisions, setDecisions] = useState<HumanDecision[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const [p, c, j, d] = await Promise.all([
          db.listProjects(),
          db.listCompetitions(),
          db.listInflightJobs(),
          db.listRecentDecisions(10),
        ]);
        if (!live) return;
        setProjects(p);
        setCompetitions(c);
        setJobs(j);
        setDecisions(d);
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner />
        Loading dashboard…
      </div>
    );
  }
  if (error) {
    return <Empty>Failed to load: {error}</Empty>;
  }

  return (
    <div className="space-y-6">
      <Card title="Projects">
        {projects.length === 0 ? (
          <Empty>No projects yet.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <div
                key={p.id}
                className="rounded border border-slate-200 p-3"
              >
                <h3 className="font-semibold">{p.name}</h3>
                <p className="text-xs text-slate-500">{p.kind ?? "general"}</p>
                <p className="mt-1 text-xs text-slate-600">{p.description}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Active competitions">
        <Table
          rows={competitions}
          columns={[
            { key: "slug", header: "Slug", render: (c) => c.slug },
            { key: "title", header: "Name", render: (c) => c.title ?? "—" },
            {
              key: "repo",
              header: "Repo",
              render: (c) =>
                c.repo_url ? (
                  <a
                    className="text-indigo-700 hover:underline"
                    href={c.repo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {c.repo_url}
                  </a>
                ) : (
                  "—"
                ),
            },
            { key: "platform", header: "Platform", render: (c) => c.platform },
          ]}
          empty={<Empty>No active competitions.</Empty>}
        />
      </Card>

      <Card title="Inflight runs">
        <Table
          rows={jobs}
          columns={[
            { key: "id", header: "Job", render: (j) => j.id.slice(0, 8) },
            { key: "model", header: "Model", render: (j) => j.model ?? "—" },
            {
              key: "status",
              header: "Status",
              render: (j) => <Pill status={j.status} />,
            },
            {
              key: "started_at",
              header: "Started",
              render: (j) => j.started_at?.slice(0, 19) ?? "—",
            },
            {
              key: "turns",
              header: "Turns",
              align: "right",
              render: (j) => j.turns_used ?? 0,
            },
            {
              key: "cost",
              header: "Cost ($)",
              align: "right",
              render: (j) => (j.cost_usd ?? 0).toFixed(4),
            },
          ]}
          empty={<Empty>No inflight runs.</Empty>}
        />
      </Card>

      <Card title="Recent decisions">
        <Table
          rows={decisions}
          columns={[
            {
              key: "type",
              header: "Operation",
              render: (d) => d.decision_type,
            },
            {
              key: "status",
              header: "Status",
              render: (d) => <Pill status={d.status} />,
            },
            {
              key: "requested_by",
              header: "By",
              render: (d) => d.requested_by ?? "—",
            },
            {
              key: "created",
              header: "Requested",
              render: (d) => d.created_at.slice(0, 19),
            },
          ]}
          empty={<Empty>No decisions recorded.</Empty>}
        />
      </Card>
    </div>
  );
}
