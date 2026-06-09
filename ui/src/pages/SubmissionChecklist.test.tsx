import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SubmissionChecklist } from "./SubmissionChecklist";

vi.mock("../lib/db", () => {
  return {
    db: {
      getCompetitionBySlug: vi.fn(async (slug: string) => ({
        id: "c-1",
        project_id: "p-1",
        platform: "devpost",
        slug,
        title: "Demo Hackathon",
        repo_url: null,
        default_branch: null,
        created_at: "2026-05-22T00:00:00Z",
        competition_type: "devpost",
        deadline: "2027-01-01T00:00:00Z",
        submission_format: ["README.md", "demo-plan.md"],
      })),
      getRun: vi.fn(async (id: string) => ({
        id,
        experiment_id: "e-1",
        job_id: null,
        run_dir: null,
        command: null,
        status: "succeeded",
        metrics: { checklist_completion: 0.5 },
        artifact_paths: null,
        analysis: null,
        started_at: null,
        finished_at: null,
        created_at: "2026-05-22T00:00:00Z",
      })),
    },
  };
});

describe("SubmissionChecklist", () => {
  const fetchPayload = {
    ok: true,
    run_id: "r-1",
    slug: "demo-hack",
    checklist: [
      {
        item: "README.md",
        status: "done",
        evidence: "runs/demo-hack/r-1/submission_pack/README.md",
      },
      { item: "demo-plan.md", status: "todo", evidence: "" },
      { item: "source/", status: "todo", evidence: "" },
      {
        item: "submission-checklist.json",
        status: "blocked",
        evidence: "",
      },
    ],
  };

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => fetchPayload,
      })) as unknown as typeof fetch,
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders the expected checklist rows from a mocked supabase + api client", async () => {
    render(
      <MemoryRouter
        initialEntries={["/hackathons/demo-hack/runs/r-1/checklist"]}
      >
        <Routes>
          <Route
            path="/hackathons/:slug/runs/:run_id/checklist"
            element={<SubmissionChecklist />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Submission checklist/i)).toBeInTheDocument();
    });
    // All four checklist items render.
    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("demo-plan.md")).toBeInTheDocument();
    expect(screen.getByText("source/")).toBeInTheDocument();
    expect(screen.getByText("submission-checklist.json")).toBeInTheDocument();
    // Status badges include done, todo, blocked.
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getAllByText("todo").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("blocked")).toBeInTheDocument();
    // Evidence cell for the done item links to the file under
    // submission_pack.
    expect(
      screen.getByText(/runs\/demo-hack\/r-1\/submission_pack\/README.md/),
    ).toBeInTheDocument();
    // Completion counter reads 1/4.
    const completion = screen.getByTestId("completion");
    expect(completion.textContent).toMatch(/1\/4/);
  });

  it("surfaces an error when the submission_pack endpoint is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }) as unknown as typeof fetch,
    );
    render(
      <MemoryRouter
        initialEntries={["/hackathons/demo-hack/runs/r-1/checklist"]}
      >
        <Routes>
          <Route
            path="/hackathons/:slug/runs/:run_id/checklist"
            element={<SubmissionChecklist />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(
        screen.getByText(/Submission-pack endpoint unreachable/i),
      ).toBeInTheDocument();
    });
  });
});
