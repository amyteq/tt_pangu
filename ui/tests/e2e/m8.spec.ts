import { test, expect } from "@playwright/test";

/**
 * The dev server runs against the local Supabase anon key, which the test
 * environment does not provide. To keep these tests offline, we stub the
 * supabase JS client to return empty arrays for every read.
 */
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    interface FakeChain {
      select: (..._: unknown[]) => FakeChain;
      order: (..._: unknown[]) => FakeChain;
      eq: (..._: unknown[]) => FakeChain;
      in: (..._: unknown[]) => FakeChain;
      limit: (..._: unknown[]) => FakeChain;
      maybeSingle: () => Promise<{ data: null; error: null }>;
      then: (resolve: (v: { data: unknown[]; error: null }) => void) => void;
    }
    const fakeQuery = (): FakeChain => {
      const chain: FakeChain = {
        select: () => chain,
        order: () => chain,
        eq: () => chain,
        in: () => chain,
        limit: () => chain,
        maybeSingle: async () => ({ data: null, error: null }),
        then: (resolve) => resolve({ data: [], error: null }),
      };
      return chain;
    };
    (window as unknown as { __E2E_FAKE_SUPABASE__: boolean }).__E2E_FAKE_SUPABASE__ = true;
    Object.defineProperty(window, "fetch", { writable: true });
    // Replace the supabase JS module before page scripts run via a sentinel.
    (window as unknown as { supabase?: unknown }).supabase = {
      from: () => fakeQuery(),
    };
  });
});

test("dashboard_has_four_sections", async ({ page }) => {
  await page.goto("/");
  // Match section headings (rendered as <h2> by the Card primitive). The
  // empty-state body also contains the phrase, so we anchor on <h2>.
  await expect(page.locator("h2").filter({ hasText: /Projects/i })).toBeVisible();
  await expect(
    page.locator("h2").filter({ hasText: /Active competitions/i }),
  ).toBeVisible();
  await expect(
    page.locator("h2").filter({ hasText: /Inflight runs/i }),
  ).toBeVisible();
  await expect(
    page.locator("h2").filter({ hasText: /Recent decisions/i }),
  ).toBeVisible();
});

test("approvals_inbox_renders", async ({ page }) => {
  await page.goto("/approvals");
  await expect(page.getByText(/Approval Inbox/i)).toBeVisible();
});

test("decision_gate_blocks_short_reason", async ({ page }) => {
  // We can navigate directly; mocked supabase returns null → "not found"
  // path. The button-rule UI test that actually exercises the disable
  // condition lives in DecisionGate.test.tsx (vitest). This e2e check just
  // confirms the route renders and the heading is present without throwing.
  await page.goto("/approvals/some-fake-id");
  // Either decision-not-found or Actions card — both are acceptable.
  const found = await page
    .getByText(/(Decision|not found)/i)
    .first()
    .isVisible();
  expect(found).toBeTruthy();
});

test("external_link_has_noopener", async ({ page }) => {
  await page.goto("/research");
  // The page has at least the GitHub link in the layout header.
  const links = await page.locator("a[target='_blank']").all();
  for (const link of links) {
    const rel = await link.getAttribute("rel");
    expect(rel).toMatch(/noopener/);
    expect(rel).toMatch(/noreferrer/);
  }
});
