import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, Empty, Spinner, Table } from "../ui";
import { db, type Run } from "../lib/db";

export function RunDetail(): JSX.Element {
  const { experimentId } = useParams<{ experimentId: string }>();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!experimentId) return;
    db.listRunsForExperiment(experimentId)
      .then(setRuns)
      .finally(() => setLoading(false));
  }, [experimentId]);

  if (loading) return <Spinner />;

  return (
    <Card title={`Experiment ${experimentId?.slice(0, 8) ?? ""}`}>
      <Table
        rows={runs.flatMap((r) =>
          Object.entries(r.metrics ?? {}).map(([k, v]) => ({
            runId: r.id,
            ts: r.created_at,
            key: k,
            value: v,
            jobId: r.job_id,
            artifactPaths: r.artifact_paths,
          })),
        )}
        columns={[
          { key: "ts", header: "ts", render: (m) => m.ts.slice(0, 19) },
          { key: "metric", header: "Metric", render: (m) => m.key },
          {
            key: "val",
            header: "Value",
            align: "right",
            render: (m) =>
              typeof m.value === "number" ? m.value.toFixed(4) : String(m.value),
          },
          {
            key: "run",
            header: "Job",
            render: (m) =>
              m.jobId ? (
                <Link
                  className="text-indigo-700 hover:underline"
                  to={`/runs/${m.jobId}`}
                >
                  {m.jobId.slice(0, 8)}
                </Link>
              ) : (
                "—"
              ),
          },
        ]}
        empty={<Empty>No metrics recorded.</Empty>}
      />
    </Card>
  );
}
