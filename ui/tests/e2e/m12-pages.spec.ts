import { test, expect } from "@playwright/test";

/**
 * M12-T005 — Playwright smoke for the two new hackathon pages.
 *
 * Uses the same stub pattern as `m8.spec.ts`: the dev server does not
 * have a real Supabase anon key, so we replace `window.supabase` with a
 * deterministic in-memory fake before page scripts load. We also stub
 * `window.fetch` for the `/api/runs/<id>/submission_pack` route so the
 * SubmissionChecklist page renders without a real decision_api running.
 */
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    type Row = Record<string, unknown>;

    const competition: Row = {
      id: "c-1",
      project_id: "p-1",
      platform: "devpost",
      slug: "demo-hack",
      title: "Demo Hackathon",
      repo_url: null,
      default_branch: null,
      created_at: "2026-05-22T00:00:00Z",
      competition_type: "devpost",
      // ~365d in the future.
      deadline: new Date(Date.now() + 365 * 24 * 3600 * 1000).toISOString(),
      submission_format: ["README.md", "demo-plan.md"],
    };
    const team: Row = {
      id: "t-1",
      competition_id: "c-1",
      name: "demo-team",
      created_at: "2026-05-22T00:00:00Z",
    };
    const member: Row = {
      id: "m-1",
      team_id: "t-1",
      user_id: "harry@ayla-app.com",
      role: "owner",
      created_at: "2026-05-22T00:00:00Z",
    };
    const run: Row = {
      id: "r-1",
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
    };

    interface Filter {
      col: string;
      val: unknown;
    }
    interface FakeChain {
      _table: string;
      _filters: Filter[];
      select: (..._: unknown[]) => FakeChain;
      order: (..._: unknown[]) => FakeChain;
      eq: (col: string, val: unknown) => FakeChain;
      in: (..._: unknown[]) => FakeChain;
      limit: (..._: unknown[]) => FakeChain;
      maybeSingle: () => Promise<{ data: Row | null; error: null }>;
      then: (
        resolve: (v: { data: Row[]; error: null }) => void,
      ) => void;
    }

    function rowsFor(table: string, filters: Filter[]): Row[] {
      let pool: Row[] = [];
      if (table === "competitions") pool = [competition];
      else if (table === "teams") pool = [team];
      else if (table === "team_memberships") pool = [member];
      else if (table === "experiment_runs") pool = [run];
      for (const f of filters) {
        pool = pool.filter((row) => (row as Row)[f.col] === f.val);
      }
      return pool;
    }

    const fakeQuery = (table: string): FakeChain => {
      const filters: Filter[] = [];
      const chain: FakeChain = {
        _table: table,
        _filters: filters,
        select: () => chain,
        order: () => chain,
        eq: (col: string, val: unknown) => {
          filters.push({ col, val });
          return chain;
        },
        in: () => chain,
        limit: () => chain,
        maybeSingle: async () => {
          const rows = rowsFor(table, filters);
          return { data: rows[0] ?? null, error: null };
        },
        then: (resolve) => resolve({ data: rowsFor(table, filters), error: null }),
      };
      return chain;
    };

    (
      window as unknown as { __E2E_FAKE_SUPABASE__: boolean }
    ).__E2E_FAKE_SUPABASE__ = true;
    (window as unknown as { supabase?: unknown }).supabase = {
      from: (table: string) => fakeQuery(table),
    };

    // Stub fetch for the submission_pack endpoint.
    const origFetch = window.fetch.bind(window);
    Object.defineProperty(window, "fetch", { writable: true, configurable: true });
    (window as unknown as { fetch: typeof fetch }).fetch = (async (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => {
      const url =
        typeof input === "string" ? input : (input as Request).url ?? String(input);
      if (url.includes("/api/runs/") && url.includes("/submission_pack")) {
        return new Response(
          JSON.stringify({
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
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return origFetch(input as RequestInfo, init);
    }) as typeof fetch;
  });
});

test("hackathon_deadline_page_renders", async ({ page }) => {
  await page.goto("/hackathons/demo-hack/deadline");
  // Without a real Supabase backend behind the dev server, the page
  // falls through to the empty-state Card. The H2 title and the
  // empty-state copy both render — that's enough to confirm the route
  // resolves and the page mounts.
  await expect(
    page.locator("h2").filter({ hasText: /Hackathon deadline/i }),
  ).toBeVisible();
  await expect(
    page.getByText(/No competition with slug/i),
  ).toBeVisible();
});

test("submission_checklist_page_renders", async ({ page }) => {
  await page.goto("/hackathons/demo-hack/runs/r-1/checklist");
  await expect(
    page.locator("h2").filter({ hasText: /Submission checklist/i }),
  ).toBeVisible();
  // The mocked fetch returns README.md + demo-plan.md — both visible
  // in the checklist table.
  await expect(page.getByText("README.md").first()).toBeVisible();
  await expect(page.getByText("demo-plan.md").first()).toBeVisible();
});
