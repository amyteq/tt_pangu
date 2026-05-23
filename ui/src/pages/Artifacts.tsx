import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, Spinner, Table } from "../ui";
import { db, type Artifact } from "../lib/db";

export function Artifacts(): JSX.Element {
  const [rows, setRows] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [jobFilter, setJobFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  useEffect(() => {
    db.listArtifacts(200)
      .then(setRows)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (kindFilter && r.kind !== kindFilter) return false;
      if (jobFilter) {
        const md = r.metadata ?? {};
        const jid = (md as { job_id?: string }).job_id ?? "";
        if (!jid.includes(jobFilter)) return false;
      }
      return true;
    });
  }, [rows, kindFilter, jobFilter]);

  if (loading) return <Spinner />;

  return (
    <Card title="Artifacts">
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <label>
          Kind:&nbsp;
          <input
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            placeholder="(any)"
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          />
        </label>
        <label>
          Job:&nbsp;
          <input
            value={jobFilter}
            onChange={(e) => setJobFilter(e.target.value)}
            placeholder="(any)"
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          />
        </label>
        <span className="ml-auto text-xs text-slate-500">
          {filtered.length} artifacts
        </span>
      </div>
      <Table
        rows={filtered}
        columns={[
          {
            key: "path",
            header: "Path",
            render: (a) => (
              <Link
                className="text-indigo-700 hover:underline"
                to={`/artifacts/${a.id}`}
              >
                {a.storage_path}
              </Link>
            ),
          },
          { key: "kind", header: "Kind", render: (a) => a.kind },
          {
            key: "size",
            header: "Size",
            align: "right",
            render: (a) =>
              a.byte_size != null ? `${a.byte_size.toLocaleString()} B` : "—",
          },
          {
            key: "hash",
            header: "sha256",
            render: (a) =>
              a.content_hash ? a.content_hash.slice(0, 12) : "—",
          },
          {
            key: "created",
            header: "Created",
            render: (a) => a.created_at.slice(0, 19),
          },
        ]}
        empty={<Empty>No artifacts.</Empty>}
      />
    </Card>
  );
}
