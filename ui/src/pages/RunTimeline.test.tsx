import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RunTimeline } from "./RunTimeline";

vi.mock("../lib/db", () => {
  const start = "2026-05-22T10:00:00Z";
  return {
    db: {
      getJob: vi.fn(async () => ({
        id: "00000000-0000-0000-0000-000000000000",
        project_id: "p",
        competition_id: null,
        status: "succeeded",
        prompt: null,
        model: "sonnet",
        policy: { skill_name: "triage-log" },
        turns_used: 2,
        cost_usd: 0.001,
        error: null,
        started_at: start,
        finished_at: "2026-05-22T10:00:05Z",
        created_at: start,
        otel_trace_id: "trace-1",
      })),
      listJobEvents: vi.fn(async () => [
        {
          id: 1,
          job_id: "00000000-0000-0000-0000-000000000000",
          event_type: "tool_call",
          turn_number: 1,
          input_tokens: 50,
          output_tokens: 20,
          cost_usd: 0.0005,
          event_data: { tool: "read_file" },
          created_at: start,
        },
      ]),
      listJobSpans: vi.fn(async () => [
        {
          id: 1,
          trace_id: "trace-1",
          span_id: "s1",
          parent_span_id: null,
          job_id: "00000000-0000-0000-0000-000000000000",
          kind: "job",
          name: "job",
          started_at: start,
          ended_at: "2026-05-22T10:00:05Z",
          duration_ms: 5000,
          attributes: {},
          status: "ok",
          error: null,
        },
        {
          id: 2,
          trace_id: "trace-1",
          span_id: "s2",
          parent_span_id: "s1",
          job_id: "00000000-0000-0000-0000-000000000000",
          kind: "tool",
          name: "read_file",
          started_at: "2026-05-22T10:00:01Z",
          ended_at: "2026-05-22T10:00:02Z",
          duration_ms: 1000,
          attributes: {},
          status: "ok",
          error: null,
        },
        {
          id: 3,
          trace_id: "trace-1",
          span_id: "s3",
          parent_span_id: "s1",
          job_id: "00000000-0000-0000-0000-000000000000",
          kind: "turn",
          name: "turn",
          started_at: "2026-05-22T10:00:00Z",
          ended_at: "2026-05-22T10:00:01Z",
          duration_ms: 1000,
          attributes: {},
          status: "ok",
          error: null,
        },
      ]),
    },
  };
});

describe("RunTimeline", () => {
  it("renders 3 mock spans into the swim-lane", async () => {
    render(
      <MemoryRouter initialEntries={["/runs/00000000-0000-0000-0000-000000000000"]}>
        <Routes>
          <Route path="/runs/:jobId" element={<RunTimeline />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("swim-lane")).toBeInTheDocument();
    });
    const lane = screen.getByTestId("swim-lane");
    const rects = lane.querySelectorAll("rect");
    expect(rects.length).toBe(3);
    expect(screen.getByText(/Spans/i)).toBeInTheDocument();
    expect(screen.getByText(/Event log/i)).toBeInTheDocument();
  });
});
