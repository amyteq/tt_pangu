# `competitions/_templates/` legacy files

These four scaffolding files were moved out of [`../../_templates/`](../../_templates/) so a fresh competition slug does not carry a rolling-state markdown surface on day one.

Per [`../../POLICY.md`](../../POLICY.md), the rolling-state class — `tracking.md`, `tasks.md`, `submissions.md`, `strategy.md`, `notes*.md`, `explore.md`, `research.md`, `references.md` — belongs in the competition tracking issue, not in `competitions/<slug>/`. Keeping empty scaffolds in the template invited the sprawl the policy was written to prevent.

The files are kept here — not deleted — because [#195](https://github.com/amyteq/tt_pangu/issues/195) *"Non-negotiable"* says archive rather than delete: `git mv` preserves the history that `git log --follow` would otherwise lose.

Do not copy these into a new competition. Existing competitions still carry their own rolling-state markdown; [#195](https://github.com/amyteq/tt_pangu/issues/195) AC2 archives those in a separate pass.

Filed under [#195](https://github.com/amyteq/tt_pangu/issues/195) AC3 (*"`competitions/_templates/` starts a new competition with the reduced file set"*).
