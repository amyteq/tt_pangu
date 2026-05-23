import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Dashboard } from "./Dashboard";

vi.mock("../lib/db", () => {
  return {
    db: {
      listProjects: vi.fn(async () => [
        {
          id: "p1",
          name: "demo",
          kind: "kaggle",
          description: "demo project",
          created_at: "2026-05-22T00:00:00Z",
        },
      ]),
      listCompetitions: vi.fn(async () => [
        {
          id: "c1",
          project_id: "p1",
          platform: "kaggle",
          slug: "spaceship-titanic",
          title: "Spaceship Titanic",
          repo_url: null,
          default_branch: null,
          created_at: "2026-05-22T00:00:00Z",
        },
      ]),
      listInflightJobs: vi.fn(async () => [
        {
          id: "00000000-0000-0000-0000-000000000abc",
          project_id: "p1",
          competition_id: null,
          status: "running",
          prompt: null,
          model: "sonnet",
          policy: null,
          turns_used: 3,
          cost_usd: 0.12,
          error: null,
          started_at: "2026-05-22T10:00:00Z",
          finished_at: null,
          created_at: "2026-05-22T10:00:00Z",
          otel_trace_id: null,
        },
      ]),
      listRecentDecisions: vi.fn(async () => [
        {
          id: "d1",
          project_id: "p1",
          job_id: null,
          decision_type: "kaggle_submit",
          prompt: "ok?",
          options: null,
          status: "pending",
          rationale: null,
          requested_by: "kca",
          created_at: "2026-05-22T11:00:00Z",
          decided_at: null,
        },
      ]),
    },
  };
});

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the four sections from mock data", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Projects/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Active competitions/i)).toBeInTheDocument();
    expect(screen.getByText(/Inflight runs/i)).toBeInTheDocument();
    expect(screen.getByText(/Recent decisions/i)).toBeInTheDocument();
    // mock data flows through
    expect(screen.getByText("demo")).toBeInTheDocument();
    expect(screen.getByText("spaceship-titanic")).toBeInTheDocument();
  });
});
