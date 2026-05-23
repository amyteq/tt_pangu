import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, Empty, Spinner, Table } from "../ui";
import { db, type HumanDecision } from "../lib/db";

export function ApprovalInbox(): JSX.Element {
  const [rows, setRows] = useState<HumanDecision[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    db.listPendingDecisions()
      .then(setRows)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  return (
    <Card title="Approval Inbox">
      <Table
        rows={rows}
        columns={[
          {
            key: "operation",
            header: "Operation",
            render: (d) => (
              <Link
                className="text-indigo-700 hover:underline"
                to={`/approvals/${d.id}`}
              >
                {d.decision_type}
              </Link>
            ),
          },
          {
            key: "run",
            header: "Job",
            render: (d) =>
              d.job_id ? (
                <Link
                  to={`/runs/${d.job_id}`}
                  className="text-indigo-700 hover:underline"
                >
                  {d.job_id.slice(0, 8)}
                </Link>
              ) : (
                "—"
              ),
          },
          {
            key: "requested",
            header: "Requested",
            render: (d) => d.created_at.slice(0, 19),
          },
          {
            key: "status",
            header: "Status",
            render: (d) => <Badge color="amber">{d.status}</Badge>,
          },
        ]}
        empty={<Empty>No pending decisions — inbox is clear.</Empty>}
      />
    </Card>
  );
}
