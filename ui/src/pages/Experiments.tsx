import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, Spinner, Table, Badge } from "../ui";
import {
  db,
  type Experiment,
  type Run,
  type Submission,
} from "../lib/db";

type SortKey = "ts" | "cv" | "lb";
type SortDir = "asc" | "desc";

interface Row {
  experiment: Experiment;
  bestCv: number | null;
  lastLb: number | null;
  lastRun: Run | null;
  lastSubmission: Submission | null;
}

export function Experiments(): JSX.Element {
  const [exps, setExps] = useState<Experiment[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [submittedOnly, setSubmittedOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(0);
  const pageSize = 25;
  const [sortKey, setSortKey] = useState<SortKey>("ts");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const [e, s] = await Promise.all([
          db.listExperiments(200),
          db.listSubmissions(200),
        ]);
        if (!live) return;
        setExps(e);
        setSubs(s);
        // Fetch runs for each experiment (parallel, capped).
        const allRuns: Run[] = [];
        for (const exp of e.slice(0, 200)) {
          try {
            const r = await db.listRunsForExperiment(exp.id);
            allRuns.push(...r);
          } catch {
            /* ignore */
          }
        }
        if (live) setRuns(allRuns);
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const rows = useMemo<Row[]>(() => {
    return exps.map((exp) => {
      const expRuns = runs.filter((r) => r.experiment_id === exp.id);
      const expSubs = subs.filter((s) =>
        expRuns.some((r) => r.id === s.run_id),
      );
      const cvs = expRuns
        .map((r) => (r.metrics ?? {})["cv_score"])
        .filter((v): v is number => typeof v === "number");
      const bestCv = cvs.length ? Math.max(...cvs) : null;
      const lastSub =
        expSubs.length > 0
          ? [...expSubs].sort((a, b) =>
              (b.created_at ?? "").localeCompare(a.created_at ?? ""),
            )[0]
          : null;
      const lastLb = lastSub?.public_lb_score ?? null;
      const lastRun =
        expRuns.length > 0
          ? [...expRuns].sort((a, b) =>
              (b.created_at ?? "").localeCompare(a.created_at ?? ""),
            )[0]
          : null;
      return {
        experiment: exp,
        bestCv,
        lastLb,
        lastRun,
        lastSubmission: lastSub,
      };
    });
  }, [exps, runs, subs]);

  const filtered = useMemo(() => {
    let out = rows;
    if (submittedOnly) out = out.filter((r) => r.lastSubmission);
    if (statusFilter)
      out = out.filter((r) => (r.experiment.status ?? "") === statusFilter);
    return out;
  }, [rows, submittedOnly, statusFilter]);

  const sorted = useMemo(() => {
    const out = [...filtered];
    out.sort((a, b) => {
      let av: number | string = "";
      let bv: number | string = "";
      if (sortKey === "ts") {
        av = a.experiment.created_at;
        bv = b.experiment.created_at;
      } else if (sortKey === "cv") {
        av = a.bestCv ?? -Infinity;
        bv = b.bestCv ?? -Infinity;
      } else if (sortKey === "lb") {
        av = a.lastLb ?? -Infinity;
        bv = b.lastLb ?? -Infinity;
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return out;
  }, [filtered, sortKey, sortDir]);

  const pageRows = sorted.slice(page * pageSize, (page + 1) * pageSize);

  function toggleSort(key: SortKey): void {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "ts" ? "desc" : "desc");
    }
    setPage(0);
  }

  if (loading) return <Spinner />;

  const arrow = (k: SortKey): string =>
    sortKey === k ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <Card title="Experiments">
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <label className="inline-flex items-center gap-1">
          <input
            type="checkbox"
            checked={submittedOnly}
            onChange={(e) => setSubmittedOnly(e.target.checked)}
          />
          submitted only
        </label>
        <label className="inline-flex items-center gap-1">
          status:
          <input
            type="text"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            placeholder="(any)"
            className="rounded border border-slate-200 px-2 py-1 text-xs"
          />
        </label>
        <span className="ml-auto text-xs text-slate-500">
          {filtered.length} experiments
        </span>
      </div>
      <Table
        rows={pageRows}
        columns={[
          {
            key: "id",
            header: "Experiment",
            render: (r) => (
              <Link
                className="text-indigo-700 hover:underline"
                to={`/experiments/${r.experiment.id}`}
              >
                {r.experiment.id.slice(0, 8)}
              </Link>
            ),
          },
          {
            key: "hyp",
            header: "Hypothesis",
            render: (r) => r.experiment.hypothesis ?? "—",
          },
          {
            key: "ts",
            header: <>Created{arrow("ts")}</>,
            sortable: true,
            onSort: () => toggleSort("ts"),
            render: (r) => r.experiment.created_at.slice(0, 10),
          },
          {
            key: "cv",
            header: <>CV{arrow("cv")}</>,
            sortable: true,
            onSort: () => toggleSort("cv"),
            align: "right",
            render: (r) => (r.bestCv == null ? "—" : r.bestCv.toFixed(4)),
          },
          {
            key: "lb",
            header: <>LB{arrow("lb")}</>,
            sortable: true,
            onSort: () => toggleSort("lb"),
            align: "right",
            render: (r) => (r.lastLb == null ? "—" : r.lastLb.toFixed(4)),
          },
          {
            key: "status",
            header: "Status",
            render: (r) => <Badge>{r.experiment.status ?? "—"}</Badge>,
          },
          {
            key: "last",
            header: "Last run",
            render: (r) =>
              r.lastRun?.job_id ? (
                <Link
                  className="text-indigo-700 hover:underline"
                  to={`/runs/${r.lastRun.job_id}`}
                >
                  open
                </Link>
              ) : (
                "—"
              ),
          },
        ]}
        empty={<Empty>No experiments match the filters.</Empty>}
      />
      {sorted.length > pageSize && (
        <div className="mt-2 flex justify-between text-xs text-slate-500">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            ← prev
          </button>
          <span>
            page {page + 1} / {Math.ceil(sorted.length / pageSize)}
          </span>
          <button
            type="button"
            disabled={(page + 1) * pageSize >= sorted.length}
            onClick={() => setPage((p) => p + 1)}
          >
            next →
          </button>
        </div>
      )}
    </Card>
  );
}
