import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, Spinner, Table, Badge } from "../ui";
import { db, type AgentJob } from "../lib/db";

export function Runs(): JSX.Element {
  const [jobs, setJobs] = useState<AgentJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    db.listRecentRuns(50)
      .then(setJobs)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  return (
    <Card title="Recent runs">
      <Table
        rows={jobs}
        columns={[
          {
            key: "id",
            header: "Job",
            render: (j) => (
              <Link
                to={`/runs/${j.id}`}
                className="text-indigo-700 hover:underline"
              >
                {j.id.slice(0, 8)}
              </Link>
            ),
          },
          {
            key: "status",
            header: "Status",
            render: (j) => <Badge>{j.status}</Badge>,
          },
          { key: "model", header: "Model", render: (j) => j.model ?? "—" },
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
          {
            key: "created",
            header: "Created",
            render: (j) => j.created_at.slice(0, 19),
          },
        ]}
        empty={<Empty>No runs.</Empty>}
      />
    </Card>
  );
}
