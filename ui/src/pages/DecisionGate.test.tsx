import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { DecisionGate } from "./DecisionGate";

const mkDecision = (op: string) => ({
  id: "dec-1",
  project_id: "p",
  job_id: "00000000-0000-0000-0000-000000000abc",
  decision_type: op,
  prompt: "submit?",
  options: null,
  status: "pending",
  rationale: null,
  requested_by: "kca",
  created_at: "2026-05-22T10:00:00Z",
  decided_at: null,
});

let _decision = mkDecision("kaggle_submit");

vi.mock("../lib/db", () => ({
  db: {
    getDecision: vi.fn(async () => _decision),
    getJob: vi.fn(async () => ({
      id: _decision.job_id,
      project_id: "p",
      competition_id: null,
      status: "paused",
      prompt: null,
      model: "sonnet",
      policy: { policy_profile: "default" },
      turns_used: 5,
      cost_usd: 0.5,
      error: null,
      started_at: "2026-05-22T09:00:00Z",
      finished_at: null,
      created_at: "2026-05-22T09:00:00Z",
      otel_trace_id: null,
    })),
    listReviewsForJob: vi.fn(async () => []),
    listToolAudit: vi.fn(async () => []),
  },
}));

function renderAt(id: string): void {
  render(
    <MemoryRouter initialEntries={[`/approvals/${id}`]}>
      <Routes>
        <Route path="/approvals/:id" element={<DecisionGate />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DecisionGate", () => {
  beforeEach(() => {
    _decision = mkDecision("kaggle_submit");
  });

  it("uses RED-DESTRUCTIVE button for SUBMISSION ops", async () => {
    _decision = mkDecision("kaggle_submit");
    renderAt("dec-1");
    await waitFor(() => screen.getByTestId("approve-btn"));
    const btn = screen.getByTestId("approve-btn");
    expect(btn.className).toMatch(/bg-red-600/);
  });

  it("uses AMBER-CAUTION button for non-submission ops", async () => {
    _decision = mkDecision("external_fetch");
    renderAt("dec-1");
    await waitFor(() => screen.getByTestId("approve-btn"));
    const btn = screen.getByTestId("approve-btn");
    expect(btn.className).toMatch(/bg-amber-500/);
  });

  it("disables Reject below 8 chars and enables at 8+", async () => {
    renderAt("dec-1");
    await waitFor(() => screen.getByTestId("reject-btn"));
    const rejectBtn = screen.getByTestId("reject-btn") as HTMLButtonElement;
    expect(rejectBtn.disabled).toBe(true);
    const reason = screen.getByPlaceholderText(
      /why are you taking this action/,
    ) as HTMLInputElement;
    fireEvent.change(reason, { target: { value: "12345" } });
    expect(rejectBtn.disabled).toBe(true);
    fireEvent.change(reason, { target: { value: "1234567890" } });
    expect(rejectBtn.disabled).toBe(false);
  });
});
