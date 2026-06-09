/**
 * Typed Supabase data client.
 *
 * Read-only by design. Every mutation in M8 flows through
 * `services/decision_api/` so the M7 permission policy stays authoritative.
 *
 * Types are intentionally narrow — they only describe the columns the UI
 * actually reads, not the full schema. Generated types via
 * `supabase gen types` is a future M9+ optimisation.
 */
import { supabase } from "./supabase";

export type Uuid = string;

export interface Project {
  id: Uuid;
  name: string;
  kind: string | null;
  description: string | null;
  created_at: string;
}

export interface Competition {
  id: Uuid;
  project_id: Uuid;
  platform: string;
  slug: string;
  title: string | null;
  repo_url: string | null;
  default_branch: string | null;
  created_at: string;
  // M12-T002 additive columns. Nullable in older rows.
  competition_type?: string | null;
  deadline?: string | null;
  submission_format?: unknown | null;
}

// M12-T002 team identity (read-only in M12).
export interface Team {
  id: Uuid;
  competition_id: Uuid | null;
  name: string;
  created_at: string;
}

export interface TeamMembership {
  id: Uuid;
  team_id: Uuid;
  user_id: string;
  role: string;
  created_at: string;
}

export interface AgentJob {
  id: Uuid;
  project_id: Uuid;
  competition_id: Uuid | null;
  status: string;
  prompt: string | null;
  model: string | null;
  policy: Record<string, unknown> | null;
  turns_used: number | null;
  cost_usd: number | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  otel_trace_id: string | null;
}

export interface AgentJobEvent {
  id: number;
  job_id: Uuid;
  event_type: string;
  turn_number: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  event_data: Record<string, unknown> | null;
  created_at: string;
}

export interface AgentTelemetrySpan {
  id: number;
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  job_id: Uuid | null;
  kind: string;
  name: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  attributes: Record<string, unknown> | null;
  status: string;
  error: string | null;
}

export interface Experiment {
  id: Uuid;
  project_id: Uuid;
  competition_id: Uuid | null;
  job_id: Uuid | null;
  hypothesis: string | null;
  branch: string | null;
  status: string | null;
  config: Record<string, unknown> | null;
  created_at: string;
}

export interface Run {
  id: Uuid;
  experiment_id: Uuid;
  job_id: Uuid | null;
  run_dir: string | null;
  command: string | null;
  status: string | null;
  metrics: Record<string, number> | null;
  artifact_paths: unknown | null;
  analysis: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface Submission {
  id: Uuid;
  competition_id: Uuid;
  run_id: Uuid | null;
  job_id: Uuid | null;
  file_path: string;
  cv_score: number | null;
  public_lb_score: number | null;
  status: string;
  note: string | null;
  submitted_at: string | null;
  created_at: string;
}

export interface ResearchItem {
  id: Uuid;
  project_id: Uuid;
  competition_id: Uuid | null;
  url: string;
  title: string | null;
  source_kind: string | null;
  trust: string;
  summary: string | null;
  fetched_at: string | null;
  created_at: string;
}

export interface ResearchCitation {
  id: Uuid;
  research_item_id: Uuid;
  run_id: Uuid | null;
  experiment_id: Uuid | null;
  job_id: Uuid | null;
  quote: string | null;
  page_anchor: string | null;
  created_at: string;
}

export interface HumanDecision {
  id: Uuid;
  project_id: Uuid;
  job_id: Uuid | null;
  decision_type: string;
  prompt: string;
  options: unknown;
  status: string;
  rationale: string | null;
  requested_by: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface AgentReview {
  id: Uuid;
  job_id: Uuid;
  run_id: Uuid | null;
  reviewer_model: string;
  reviewer_kind: string;
  target_op: string | null;
  verdict: string;
  rationale: string | null;
  evidence: Record<string, unknown> | null;
  cost_usd: number;
  created_at: string;
}

export interface Artifact {
  id: Uuid;
  project_id: Uuid;
  kind: string;
  storage_path: string;
  content_hash: string | null;
  byte_size: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface AgentToolAudit {
  id: number;
  ts: string;
  session_id: Uuid;
  job_id: Uuid | null;
  skill_name: string | null;
  tool_name: string;
  operation: string;
  decision: "allow" | "ask" | "deny";
  mode: string;
  policy_profile: string;
  audit_required: boolean;
  args_hash: string;
  extra: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Thenable = PromiseLike<{ data: unknown; error: unknown }> & { maybeSingle?: () => any };

async function rows<T>(query: Thenable): Promise<T[]> {
  const { data, error } = await query;
  if (error) throw error;
  return (data as T[] | null) ?? [];
}

async function maybeOne<T>(query: Thenable): Promise<T | null> {
  if (typeof query.maybeSingle !== "function") {
    throw new Error("maybeOne requires a query supporting maybeSingle()");
  }
  const { data, error } = await query.maybeSingle();
  if (error) throw error;
  return (data as T) ?? null;
}

export const db = {
  // Projects
  listProjects(limit = 50): Promise<Project[]> {
    return rows<Project>(
      supabase
        .from("projects")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  getProject(id: Uuid): Promise<Project | null> {
    return maybeOne<Project>(supabase.from("projects").select("*").eq("id", id));
  },

  // Competitions
  listCompetitions(limit = 50): Promise<Competition[]> {
    return rows<Competition>(
      supabase
        .from("competitions")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  getCompetitionBySlug(slug: string): Promise<Competition | null> {
    return maybeOne<Competition>(
      supabase.from("competitions").select("*").eq("slug", slug),
    );
  },

  // M12 — teams + memberships (read-only)
  listTeamsForCompetition(competitionId: Uuid): Promise<Team[]> {
    return rows<Team>(
      supabase
        .from("teams")
        .select("*")
        .eq("competition_id", competitionId)
        .order("created_at", { ascending: true }),
    );
  },
  listTeamMemberships(teamId: Uuid): Promise<TeamMembership[]> {
    return rows<TeamMembership>(
      supabase
        .from("team_memberships")
        .select("*")
        .eq("team_id", teamId)
        .order("created_at", { ascending: true }),
    );
  },
  getRun(runId: Uuid): Promise<Run | null> {
    return maybeOne<Run>(
      supabase.from("experiment_runs").select("*").eq("id", runId),
    );
  },

  // Runs / jobs
  listRecentRuns(limit = 20): Promise<AgentJob[]> {
    return rows<AgentJob>(
      supabase
        .from("agent_jobs")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  listInflightJobs(): Promise<AgentJob[]> {
    return rows<AgentJob>(
      supabase
        .from("agent_jobs")
        .select("*")
        .in("status", ["queued", "running", "paused"])
        .order("created_at", { ascending: false }),
    );
  },
  listRunsForCompetition(
    competitionId: Uuid,
    limit = 50,
  ): Promise<Run[]> {
    return rows<Run>(
      supabase
        .from("experiment_runs")
        .select("*")
        .eq("competition_id", competitionId)
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  getJob(id: Uuid): Promise<AgentJob | null> {
    return maybeOne<AgentJob>(supabase.from("agent_jobs").select("*").eq("id", id));
  },
  listJobEvents(jobId: Uuid, limit = 200): Promise<AgentJobEvent[]> {
    return rows<AgentJobEvent>(
      supabase
        .from("agent_job_events")
        .select("*")
        .eq("job_id", jobId)
        .order("id", { ascending: true })
        .limit(limit),
    );
  },
  listJobSpans(jobId: Uuid): Promise<AgentTelemetrySpan[]> {
    return rows<AgentTelemetrySpan>(
      supabase
        .from("agent_telemetry_spans")
        .select("*")
        .eq("job_id", jobId)
        .order("started_at", { ascending: true }),
    );
  },

  // Experiments
  listExperiments(limit = 50): Promise<Experiment[]> {
    return rows<Experiment>(
      supabase
        .from("experiments")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  listRunsForExperiment(experimentId: Uuid): Promise<Run[]> {
    return rows<Run>(
      supabase
        .from("experiment_runs")
        .select("*")
        .eq("experiment_id", experimentId)
        .order("created_at", { ascending: false }),
    );
  },
  listSubmissions(limit = 50): Promise<Submission[]> {
    return rows<Submission>(
      supabase
        .from("submissions")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },

  // Research
  listResearchItems(limit = 50): Promise<ResearchItem[]> {
    return rows<ResearchItem>(
      supabase
        .from("research_items")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  listCitationsForRun(runId: Uuid): Promise<ResearchCitation[]> {
    return rows<ResearchCitation>(
      supabase
        .from("research_citations")
        .select("*")
        .eq("run_id", runId)
        .order("created_at", { ascending: false }),
    );
  },

  // Decisions + reviews
  listPendingDecisions(): Promise<HumanDecision[]> {
    return rows<HumanDecision>(
      supabase
        .from("human_decisions")
        .select("*")
        .eq("status", "pending")
        .order("created_at", { ascending: true }),
    );
  },
  listRecentDecisions(limit = 10): Promise<HumanDecision[]> {
    return rows<HumanDecision>(
      supabase
        .from("human_decisions")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  getDecision(id: Uuid): Promise<HumanDecision | null> {
    return maybeOne<HumanDecision>(
      supabase.from("human_decisions").select("*").eq("id", id),
    );
  },
  listReviewsForJob(jobId: Uuid): Promise<AgentReview[]> {
    return rows<AgentReview>(
      supabase
        .from("agent_reviews")
        .select("*")
        .eq("job_id", jobId)
        .order("created_at", { ascending: false }),
    );
  },

  // Artifacts
  listArtifacts(limit = 100): Promise<Artifact[]> {
    return rows<Artifact>(
      supabase
        .from("artifacts")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(limit),
    );
  },
  getArtifact(id: Uuid): Promise<Artifact | null> {
    return maybeOne<Artifact>(supabase.from("artifacts").select("*").eq("id", id));
  },

  // Tool audit
  listToolAudit(jobId?: Uuid, limit = 50): Promise<AgentToolAudit[]> {
    let q = supabase
      .from("agent_tool_audit")
      .select("*")
      .order("ts", { ascending: false })
      .limit(limit);
    if (jobId) q = q.eq("job_id", jobId);
    return rows<AgentToolAudit>(q);
  },
};
