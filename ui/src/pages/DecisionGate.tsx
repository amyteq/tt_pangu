import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, Empty, Spinner, Table } from "../ui";
import {
  db,
  type AgentJob,
  type AgentReview,
  type AgentToolAudit,
  type HumanDecision,
} from "../lib/db";

const SUBMISSION_OPERATIONS = new Set([
  "kaggle_submit",
  "kernel_push",
  "supabase_migrate",
  "git_push",
]);

async function callApi(
  decisionId: string,
  action: "approve" | "reject" | "ask-improve",
  body: object,
): Promise<Response> {
  const token = readApiToken();
  return fetch(`/api/decision/${decisionId}/${action}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Decision-Api-Token": token } : {}),
    },
    body: JSON.stringify(body),
  });
}

function readApiToken(): string | null {
  // Same-origin cookie set out-of-band by `kca ui login`.
  const m = document.cookie.match(/kca_api_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

interface MetaState {
  decision: HumanDecision | null;
  job: AgentJob | null;
  reviews: AgentReview[];
  audit: AgentToolAudit[];
  artifactPreview: { kind: "text" | "binary" | "none"; body: string };
}

export function DecisionGate(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [state, setState] = useState<MetaState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"approve" | "reject" | "ask" | null>(null);
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let live = true;
    (async () => {
      try {
        const decision = await db.getDecision(id);
        const job = decision?.job_id ? await db.getJob(decision.job_id) : null;
        const reviews = decision?.job_id
          ? await db.listReviewsForJob(decision.job_id)
          : [];
        const audit = decision?.job_id
          ? await db.listToolAudit(decision.job_id, 20)
          : [];
        if (!live) return;
        setState({
          decision,
          job,
          reviews,
          audit,
          artifactPreview: { kind: "none", body: "" },
        });
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [id]);

  const isSubmission = useMemo(() => {
    if (!state?.decision) return false;
    return SUBMISSION_OPERATIONS.has(state.decision.decision_type);
  }, [state]);

  const rejectDisabled = reason.trim().length < 8;
  const feedbackDisabled = feedback.trim().length < 1;

  async function doApprove(): Promise<void> {
    if (!id) return;
    setBusy("approve");
    try {
      const r = await callApi(id, "approve", { reason: reason || undefined });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      nav("/approvals");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doReject(): Promise<void> {
    if (!id || rejectDisabled) return;
    setBusy("reject");
    try {
      const r = await callApi(id, "reject", { reason });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      nav("/approvals");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function doAskImprove(): Promise<void> {
    if (!id || feedbackDisabled) return;
    setBusy("ask");
    try {
      const r = await callApi(id, "ask-improve", { feedback });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      nav("/approvals");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Spinner />;
  if (!state || !state.decision) {
    return (
      <Card>
        <Empty>Decision not found.</Empty>
      </Card>
    );
  }

  const { decision, job, reviews, audit } = state;
  const policyProfile =
    (job?.policy as { policy_profile?: string } | null)?.policy_profile ??
    "default";

  return (
    <div className="space-y-4">
      <Card title={`Decision ${decision.id.slice(0, 8)}`}>
        <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
          <div>
            <dt className="text-xs text-slate-500">operation</dt>
            <dd>{decision.decision_type}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">status</dt>
            <dd>
              <Badge color="amber">{decision.status}</Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">policy profile</dt>
            <dd>{policyProfile}</dd>
          </div>
          {job && (
            <>
              <div>
                <dt className="text-xs text-slate-500">cost ($)</dt>
                <dd>{(job.cost_usd ?? 0).toFixed(4)}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">turns</dt>
                <dd>{job.turns_used ?? 0}</dd>
              </div>
            </>
          )}
        </dl>
      </Card>

      {reviews.length > 0 && (
        <Card title="Reviewer">
          {reviews.map((r) => (
            <div key={r.id} className="rounded border border-slate-100 p-2 text-sm">
              <Badge
                color={
                  r.verdict === "approve"
                    ? "green"
                    : r.verdict === "reject"
                      ? "red"
                      : "slate"
                }
              >
                {r.verdict}
              </Badge>
              <span className="ml-2 text-xs text-slate-500">
                {r.reviewer_model}
              </span>
              {r.rationale && (
                <p className="mt-1 text-xs text-slate-700">{r.rationale}</p>
              )}
            </div>
          ))}
        </Card>
      )}

      <Card title="Recent tool audit (last 20)">
        <Table
          rows={audit}
          columns={[
            { key: "ts", header: "ts", render: (a) => a.ts.slice(11, 19) },
            { key: "tool", header: "Tool", render: (a) => a.tool_name },
            {
              key: "decision",
              header: "Decision",
              render: (a) => (
                <Badge
                  color={
                    a.decision === "allow"
                      ? "green"
                      : a.decision === "deny"
                        ? "red"
                        : "amber"
                  }
                >
                  {a.decision}
                </Badge>
              ),
            },
          ]}
          empty={<Empty>No audit rows yet.</Empty>}
        />
      </Card>

      <Card title="Actions">
        {error && (
          <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        <label className="text-xs text-slate-500">
          Reason (required for reject, min 8 chars)
        </label>
        <input
          className="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-sm"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="why are you taking this action?"
        />

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            data-testid="approve-btn"
            variant={isSubmission ? "danger" : "caution"}
            onClick={doApprove}
            disabled={busy !== null}
          >
            {busy === "approve" ? <Spinner /> : "Approve"}
          </Button>
          <Button
            data-testid="reject-btn"
            variant="default"
            onClick={doReject}
            disabled={busy !== null || rejectDisabled}
          >
            {busy === "reject" ? <Spinner /> : "Reject"}
          </Button>
        </div>

        <div className="mt-6 border-t border-slate-100 pt-4">
          <label className="text-xs text-slate-500">
            Feedback to the agent (ask-improve)
          </label>
          <textarea
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-sm"
            rows={3}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="describe what to change for the next iteration"
          />
          <Button
            variant="primary"
            className="mt-2"
            onClick={doAskImprove}
            disabled={busy !== null || feedbackDisabled}
            data-testid="ask-improve-btn"
          >
            {busy === "ask" ? <Spinner /> : "Ask agent to improve"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
