import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Experiments } from "./Experiments";

vi.mock("../lib/db", () => {
  const exps = [
    {
      id: "e1",
      project_id: "p",
      competition_id: "c",
      job_id: null,
      hypothesis: "A",
      branch: "a",
      status: "succeeded",
      config: null,
      created_at: "2026-05-22T10:00:00Z",
    },
    {
      id: "e2",
      project_id: "p",
      competition_id: "c",
      job_id: null,
      hypothesis: "B",
      branch: "b",
      status: "succeeded",
      config: null,
      created_at: "2026-05-22T09:00:00Z",
    },
  ];
  return {
    db: {
      listExperiments: vi.fn(async () => exps),
      listSubmissions: vi.fn(async () => [
        {
          id: "s1",
          competition_id: "c",
          run_id: "r1",
          job_id: null,
          file_path: "/a",
          cv_score: 0.6,
          public_lb_score: 0.55,
          status: "submitted",
          note: null,
          submitted_at: null,
          created_at: "2026-05-22T10:00:00Z",
        },
      ]),
      listRunsForExperiment: vi.fn(async (id: string) =>
        id === "e1"
          ? [
              {
                id: "r1",
                experiment_id: "e1",
                job_id: "j1",
                run_dir: null,
                command: null,
                status: "succeeded",
                metrics: { cv_score: 0.62 },
                artifact_paths: null,
                analysis: null,
                started_at: null,
                finished_at: null,
                created_at: "2026-05-22T10:00:00Z",
              },
            ]
          : [
              {
                id: "r2",
                experiment_id: "e2",
                job_id: "j2",
                run_dir: null,
                command: null,
                status: "succeeded",
                metrics: { cv_score: 0.45 },
                artifact_paths: null,
                analysis: null,
                started_at: null,
                finished_at: null,
                created_at: "2026-05-22T09:00:00Z",
              },
            ],
      ),
    },
  };
});

describe("Experiments", () => {
  it("renders the columns and sorts by CV when clicked", async () => {
    render(
      <MemoryRouter>
        <Experiments />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/2 experiments/i)).toBeInTheDocument();
    });
    // Columns present (Experiments appears in title + column header → use getAll).
    expect(screen.getAllByText(/Experiment/i).length).toBeGreaterThan(1);
    expect(screen.getByText(/Hypothesis/i)).toBeInTheDocument();
    expect(screen.getByText(/^Created/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /CV/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /LB/ })).toBeInTheDocument();
    // Default sort: by ts desc, so e1 (10:00) first, e2 (09:00) second
    let rowsText = screen
      .getAllByRole("row")
      .map((r) => r.textContent ?? "");
    expect(rowsText[1]).toMatch(/e1/);
    expect(rowsText[2]).toMatch(/e2/);
    // Click CV header twice to flip to ascending (then descending again).
    const cvBtn = screen.getByRole("button", { name: /CV/i });
    fireEvent.click(cvBtn);
    fireEvent.click(cvBtn);
    rowsText = screen
      .getAllByRole("row")
      .map((r) => r.textContent ?? "");
    expect(rowsText[1]).toMatch(/e2/);
    expect(rowsText[2]).toMatch(/e1/);
  });
});
