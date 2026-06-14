<!--
Use this template for every PR. The closeout checklist is load-bearing —
PRs missing tests/evidence/safety notes will be sent back for revision.
See docs/engineering-practice.md for the full model.
-->

## Summary

<!-- 1–3 bullets: what changed and why. Link the issue(s) this closes. -->

Closes #

## Tests run

<!-- Paste the commands you ran and the result. Failing tests are not "skipped" — they are blockers. -->

- [ ] `python -m pytest tests/ services/decision_api/tests -v`
- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `pnpm -C ui install --frozen-lockfile`
- [ ] `pnpm -C ui lint`
- [ ] `pnpm -C ui typecheck`
- [ ] `pnpm -C ui build`
- [ ] `pnpm -C ui run test --run`
- [ ] (if applicable) live-DB tests against the local `supabase-db` container

## Docs / inventory impact

- [ ] Updated `docs/` for any behaviour or interface change
- [ ] Updated `PROJECT_STATE.md` / `docs/milestones/README.md` if a milestone or status changed
- [ ] Updated ADR under `docs/adr/` if an architectural decision was made
- [ ] No doc update needed (explain why)

## Evidence

<!-- Links to test runs, CI artifacts, screenshots, audit-log entries, docs/evidence/* files. -->

## Schema / RLS / secrets impact

- [ ] No DB migration introduced
- [ ] Introduces / modifies migration under `supabase/migrations/` — migration is reversible and reviewed
- [ ] No new secret read / write surface
- [ ] Touches secrets handling, sandbox/hook policy, or permission model — `area:security` label applied and reviewer pinged

## Remote side effects

- [ ] None — local-only change
- [ ] Live Kaggle call (submit / kernel push / dataset / model upload) — explicit approval recorded on the closing issue
- [ ] Remote Supabase write — explicit approval recorded
- [ ] Other remote write (gh label sync, gh issue/PR mass edit, release publish) — explain and link approval

## Risks and follow-ups

<!-- Known gaps, deferred work, follow-up issues to file. -->

---

🤖 If a Claude Code agent prepared this PR, it cited evidence and acceptance criteria from the closing issue.
