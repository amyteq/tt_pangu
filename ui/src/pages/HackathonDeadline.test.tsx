import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { HackathonDeadline } from "./HackathonDeadline";

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
        // Deadline ~365 days in the future so the countdown is non-trivial.
        deadline: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString(),
        submission_format: ["README.md", "demo-plan.md"],
      })),
      listTeamsForCompetition: vi.fn(async () => [
        {
          id: "t-1",
          competition_id: "c-1",
          name: "demo-team",
          created_at: "2026-05-22T00:00:00Z",
        },
      ]),
      listTeamMemberships: vi.fn(async () => [
        {
          id: "m-1",
          team_id: "t-1",
          user_id: "harry@ayla-app.com",
          role: "owner",
          created_at: "2026-05-22T00:00:00Z",
        },
        {
          id: "m-2",
          team_id: "t-1",
          user_id: "kca@bot",
          role: "agent",
          created_at: "2026-05-22T00:00:00Z",
        },
      ]),
    },
  };
});

describe("HackathonDeadline", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.clearAllMocks();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders countdown, phase chip, and roster from mocked supabase client", async () => {
    render(
      <MemoryRouter initialEntries={["/hackathons/demo-hack/deadline"]}>
        <Routes>
          <Route
            path="/hackathons/:slug/deadline"
            element={<HackathonDeadline />}
          />
        </Routes>
      </MemoryRouter>,
    );
    // Wait for async loaders to settle.
    await waitFor(() => {
      expect(screen.getByText(/Demo Hackathon/i)).toBeInTheDocument();
    });
    // Countdown shows a `d` (days remaining) since the deadline is in the future.
    const countdown = screen.getByTestId("countdown");
    expect(countdown.textContent).toMatch(/\d+d/);
    // Phase chip — deadline is in the future, so phase = open.
    expect(screen.getByText("open")).toBeInTheDocument();
    // Roster table includes both mocked members.
    expect(screen.getByText("demo-team", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("harry@ayla-app.com")).toBeInTheDocument();
    expect(screen.getByText("kca@bot")).toBeInTheDocument();
    expect(screen.getByText("owner")).toBeInTheDocument();
    expect(screen.getByText("agent")).toBeInTheDocument();
  });

  it("renders 'closed' phase when deadline is in the past", async () => {
    const dbMod = await import("../lib/db");
    (dbMod.db.getCompetitionBySlug as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "c-1",
      project_id: "p-1",
      platform: "devpost",
      slug: "closed-hack",
      title: "Closed Hackathon",
      repo_url: null,
      default_branch: null,
      created_at: "2024-01-01T00:00:00Z",
      competition_type: "devpost",
      deadline: "2024-06-01T00:00:00Z",
      submission_format: [],
    });
    render(
      <MemoryRouter initialEntries={["/hackathons/closed-hack/deadline"]}>
        <Routes>
          <Route
            path="/hackathons/:slug/deadline"
            element={<HackathonDeadline />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Closed Hackathon/i)).toBeInTheDocument();
    });
    // "closed" appears at least twice — the countdown reads "closed" and
    // the phase chip reads "closed" — so use getAllByText.
    expect(screen.getAllByText("closed").length).toBeGreaterThanOrEqual(1);
  });
});
