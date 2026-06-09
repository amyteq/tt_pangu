/**
 * SubmissionChecklist — M12-T005.
 *
 * Route: `/hackathons/:slug/runs/:run_id/checklist`.
 *
 * Reads:
 *  - `competitions.submission_format` (jsonb) for the slug.
 *  - The `experiment_runs` row for the run_id (so we can show its status).
 *  - `GET /api/runs/<run_id>/submission_pack` — the READ_ONLY endpoint added
 *    in M12-T005 step 3. That endpoint mirrors the shape of
 *    `tools/kca/submission_checklist.py::build_checklist`, so the UI and
 *    the worker render the same list.
 *
 * Renders: a checklist table — one row per item with status badge
 * (todo / done / blocked) and an evidence cell linking to the file under
 * `runs/<slug>/<run_id>/submission_pack/`.
 *
 * Status is **inferred**, not mutable, in M12 (per the task spec
 * non-goals). Mutation is a follow-up.
 */
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Badge, Card, Empty, Spinner, Table } from "../ui";
import { db, type Competition, type Run } from "../lib/db";

export interface ChecklistItem {
  item: string;
  status: "done" | "todo" | "blocked";
  evidence: string;
}

interface SubmissionPackResponse {
  ok: boolean;
  run_id: string;
  slug?: string;
  checklist: ChecklistItem[];
  error?: string;
}

function statusBadge(status: ChecklistItem["status"]): JSX.Element {
  const color =
    status === "done" ? "green" : status === "blocked" ? "red" : "amber";
  return <Badge color={color}>{status}</Badge>;
}

async function fetchSubmissionPack(
  runId: string,
): Promise<SubmissionPackResponse | null> {
  try {
    const token = readApiToken();
    const res = await fetch(`/api/runs/${runId}/submission_pack`, {
      headers: {
        ...(token ? { "X-Decision-Api-Token": token } : {}),
      },
    });
    if (!res.ok) return null;
    return (await res.json()) as SubmissionPackResponse;
  } catch {
    return null;
  }
}

function readApiToken(): string | null {
  const m = document.cookie.match(/kca_api_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export function SubmissionChecklist(): JSX.Element {
  const { slug = "", run_id: runId = "" } = useParams<{
    slug: string;
    run_id: string;
  }>();
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [pack, setPack] = useState<SubmissionPackResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [packError, setPackError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setPackError(null);
    Promise.all([
      db.getCompetitionBySlug(slug),
      db.getRun(runId),
      fetchSubmissionPack(runId),
    ])
      .then(([c, r, p]) => {
        if (!live) return;
        setCompetition(c);
        setRun(r);
        setPack(p);
        if (!p) {
          setPackError("Submission-pack endpoint unreachable.");
        } else if (!p.ok) {
          setPackError(p.error ?? "Submission-pack endpoint returned an error.");
        }
      })
      .catch((err) => {
        if (live) setPackError(String(err));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [slug, runId]);

  const rows: ChecklistItem[] = useMemo(() => pack?.checklist ?? [], [pack]);
  const completion = useMemo(() => {
    if (rows.length === 0) return null;
    const done = rows.filter((r) => r.status === "done").length;
    return { done, total: rows.length };
  }, [rows]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <Card title="Submission checklist">
        <div className="mb-3 flex flex-wrap items-baseline gap-3 text-sm">
          <span>
            Competition:{" "}
            <span className="font-mono">
              {competition?.slug ?? slug}
            </span>
          </span>
          <span>
            Run:{" "}
            <span className="font-mono">{runId.slice(0, 8) || "—"}</span>
          </span>
          {run?.status && <Badge color="indigo">{run.status}</Badge>}
          {completion && (
            <span data-testid="completion" className="text-slate-600">
              {completion.done}/{completion.total} complete
            </span>
          )}
        </div>
        {packError && (
          <div className="mb-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
            {packError}
          </div>
        )}
        <Table
          rows={rows}
          columns={[
            {
              key: "item",
              header: "Item",
              render: (r) => <span className="font-mono text-xs">{r.item}</span>,
            },
            {
              key: "status",
              header: "Status",
              render: (r) => statusBadge(r.status),
            },
            {
              key: "evidence",
              header: "Evidence",
              render: (r) =>
                r.evidence ? (
                  <span className="font-mono text-xs text-slate-700">
                    {r.evidence}
                  </span>
                ) : (
                  <span className="text-xs text-slate-400">—</span>
                ),
            },
          ]}
          empty={
            <Empty>
              No submission_pack items yet — run the hackathon-experiment-loop
              skill to assemble the pack.
            </Empty>
          }
        />
      </Card>
    </div>
  );
}
