# ADR-0014: UI Stack — Vite + React + TypeScript

## Status

Accepted (M8).

## Context

M8 ships the first human-facing surface on top of the M2–M7 control plane. The target user is an operator/dev who runs Kaggle/CTF experiments locally and needs to approve gated operations, inspect runs, browse research and artifacts, and watch the audit trail.

Two viable shapes were considered:

- **A) Next.js (app router)** — file-based routing, React Server Components, API routes baked in.
- **B) Vite + React + React Router** — pure SPA, no SSR, no API routes.

> Note on numbering: the M8 loop prompt named this ADR "0011" but `0011-local-model-endpoints.md` already exists. The next free slot is `0014`, which is what we use here.

## Decision

**B — Vite + React + React Router.**

Rationale:

- The product is an operator/dev workbench, not a public site. SEO and SSR are non-goals; first paint over a few KB of HTML is good enough.
- Backend writes already live in `tools/kca/*` and `src/worker/`. The UI does not need API routes — it talks to Supabase for reads and to a small Python/FastAPI action service (`services/decision_api/`, M8-T009) for writes. That service is the only path that can mutate `human_decisions` rows, and it re-uses the existing `tools/kca/decisions.py` so the M7 `permission_policy` resolution stays authoritative.
- Vite's dev loop (HMR, no compile-stage gymnastics) matches the Claude Code editing cadence better than Next's RSC/route-tree dance.
- Smaller dependency surface to keep safe with the M7 permission policy: we do not introduce a server runtime we have to harden against SSR-side data leaks.

## Consequences

- All authenticated mutations go through `services/decision_api/` (or future Supabase RPC functions). The browser bundle **never** holds a service-role key; it uses the anon key + RLS, and writes via the action service over `/api/*`.
- Server-rendered features (social previews, SEO landing pages) are explicitly out of scope for M8. If we need them later, we can either move to Next.js or front the SPA with a tiny edge renderer.
- `pnpm` is the package manager (Vite scaffolds support it cleanly and the CI job in M8-T011 standardises on it).
- TypeScript is strict (`tsc --noEmit --strict` is part of CI).
- Tailwind CSS provides styling primitives without a design-system dep; raw Tailwind + Headless UI is sufficient for the M8 page set.
- Test stack: Vitest + React Testing Library for unit, Playwright for e2e.

## Alternatives considered

- **Next.js app router** — rejected per the rationale above. We may revisit if M9+ needs SSR/edge.
- **Remix** — similar trade-offs to Next; the SSR benefits do not apply to an internal operator UI.
- **Svelte / SolidJS** — smaller community, less Claude Code editing inertia in this codebase, and the team has more React experience.
