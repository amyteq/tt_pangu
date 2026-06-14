# M8-T000: UI stack ADR + scaffold (Vite + React + TS + Tailwind)

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 0; extracted here for the double-layer convention.

## Goal
Decide and document the UI stack, then scaffold the `ui/` workspace with
Vite + React + TypeScript + Tailwind + `@supabase/supabase-js`.

## Read first
1. `docs/milestones/README.md` (M8 section — stack constraints + planned capabilities)
2. `docs/milestones/m7/handoff.md` (M7 → M8 handoff, M7 follow-ups)
3. `docs/architecture/kca-cli-architecture.md` (the surface M8 calls into)
4. `docs/adr/` (latest ADRs — match style)
5. `pyproject.toml` (kca entry point + dev deps)
6. `.claude/settings.json` (permissions allow-list for npm/pnpm/node/vite)

## Scope / Files / Implementation guidance

### Step 1 — Write `docs/adr/ADR-0011-ui-stack.md`
- Status: Accepted.
- Context: M8 needs a TypeScript-first React surface developed in Claude
  Code, talking to the existing Supabase control plane. Two viable shapes:
    A) Next.js app router (file-based routing, RSC, API routes).
    B) Vite + React + React Router (pure SPA, no SSR).
- Decision: **Vite + React + React Router**. Rationale:
    - The product is an operator/dev workbench, not a public site; SEO
      and SSR are non-goals.
    - Backend writes already live in `tools/kca/*` + `src/worker/`;
      the UI does not need API routes.
    - Faster cold-start dev loop matches the Claude Code editing cadence.
    - Smaller surface to keep safe with the M7 permission policy.
- Consequences:
    - All authenticated mutations go through Supabase RPC functions or
      a small Python action service (M9+). The browser never holds a
      service-role key.
    - Server-rendered features (e.g. social previews) are explicitly
      out of scope for M8.

### Step 2 — Scaffold `ui/`
```bash
mkdir -p ui
cd ui
pnpm create vite . --template react-ts
pnpm add @supabase/supabase-js react-router-dom recharts clsx
pnpm add -D tailwindcss postcss autoprefixer @types/node \
  @testing-library/react @testing-library/jest-dom vitest jsdom \
  @playwright/test
pnpm exec tailwindcss init -p
```

### Step 3 — Wire Tailwind + base CSS
- `ui/tailwind.config.js`: content `["./index.html", "./src/**/*.{ts,tsx}"]`.
- `ui/src/index.css`: `@tailwind base; @tailwind components; @tailwind utilities;`
- Replace the Vite template `App.tsx` with a placeholder
  `<h1 className="p-4 text-2xl">kaggle-code-agent</h1>` so the smoke test
  has something to assert on.

### Step 4 — Supabase client stub (read-only)
`ui/src/lib/supabase.ts`:
```ts
import { createClient } from "@supabase/supabase-js";
const url  = import.meta.env.VITE_SUPABASE_URL  ?? "http://localhost:54321";
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
export const supabase = createClient(url, anon, {
  auth: { persistSession: false },
});
```

`ui/.env.example`:
```
VITE_SUPABASE_URL=http://localhost:54321
VITE_SUPABASE_ANON_KEY=replace_me
```

Confirm `ui/.env*` is in the repo-level `.gitignore`.

### Step 5 — Wire the root package scripts
`ui/package.json` scripts: `dev`, `build`, `preview`, `lint`, `test`,
`typecheck` (= `tsc --noEmit`).

## Acceptance criteria
- `cd ui && pnpm install` → 0 errors
- `cd ui && pnpm typecheck` → 0 errors
- `cd ui && pnpm build` → builds to `ui/dist`
- `cd ui && pnpm dev &` → serves on `:5173`
- `curl -s http://localhost:5173/` → HTML containing the placeholder
- `pkill -f "vite" || true` (clean up dev server)
- `test -f docs/adr/ADR-0011-ui-stack.md`
- `grep -q "Vite + React" docs/adr/ADR-0011-ui-stack.md`
- `python -m pytest tests/ -v -m "not db"` → 0 failures (UI scaffold must
  not break Python tests)

Report: pnpm install summary, build output size, typecheck status, ADR path.

## Stop condition
Stop after 30 turns.
