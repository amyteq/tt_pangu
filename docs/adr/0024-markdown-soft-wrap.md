# ADR-0024: Markdown is soft-wrapped, in files and in agent-written GitHub text

- Status: Accepted
- Date: 2026-09-16
- Amended: 2026-09-17 — Enforcement, which now names the mechanism and declines the repo-wide backfill ([issue #210](https://github.com/amyteq/tt_pangu/issues/210)); Decision's exemption list, which now states what is machine-recognisable and matches the checker ([PR #226](https://github.com/amyteq/tt_pangu/pull/226) review, finding F008); and Enforcement again, for the renderer-backed check `--fix` now runs on its own output before writing a file (same review, round 2)
- Amended: 2026-09-18 — Enforcement, which now records which renderer the gate targets, which one it verifies with, what it does where the two disagree, and the two shapes the verification refuses rather than judges (same review, round 3, findings F001 and F007)
- Amended: 2026-09-18 — Enforcement, which now states that those two shapes are recognised from parsed HTML rather than from patterns matched against it (same review, round 4, findings F007 and F018)
- Deciders: @harrysun2006 (repo owner)
- Related: [PR #208 review](https://github.com/amyteq/tt_pangu/pull/208#issuecomment-5696699389), [issue #207](https://github.com/amyteq/tt_pangu/issues/207), [issue #210](https://github.com/amyteq/tt_pangu/issues/210)

## Context

Markdown in this repository is written by agents as often as by humans, and the two produce different line discipline. `CLAUDE.md`, `README.md` and the ADRs are soft-wrapped: one paragraph is one physical line, and the renderer wraps it. Several agent-written files and GitHub comments instead arrived hard-wrapped at roughly 80 columns, with a newline inside every paragraph.

Hard wrapping looks tidy in a fixed-width editor and bad everywhere else. GitHub wraps to the reader's viewport, so a paragraph that was wrapped at 80 renders ragged at any other width, on a phone, in a side-by-side diff, and in the PR conversation column. It also makes diffs noisy: changing one word reflows the rest of the paragraph and rewrites lines that did not change, which buries the real edit in a review.

Two smaller hazards travel with the same problem. A `---` placed directly under a non-blank line is not a horizontal rule at all — CommonMark parses it as a setext H2, so the paragraph above it silently renders as a heading. And a hard-wrapped line inside a table cell or a list item breaks the construct rather than continuing it.

The repo owner raised all of this against PR #208 and asked for it to be enforced repo-wide rather than fixed one file at a time.

## Decision

**Markdown is soft-wrapped.** One paragraph, list item, table row or heading is one physical line, with no hard line break inside it. Let the renderer wrap.

This binds:

- every `.md` file in the repository, including `*_zh.md` sidecars;
- every GitHub body an agent writes: PR descriptions, PR and issue comments, review and disposition reports, discussion posts, and release notes.

Two consequential rules follow:

- **Leave a blank line before every `---`.** Without it the preceding paragraph becomes a setext H2. This matters most for the signature separators in [`at-review-pr` report templates](../../.claude/skills/at-review-pr/references/reports.md), where the line above the rule is prose.
- **Never hard-wrap inside a table row, a list item, or a link.** A wrapped table row stops being a table.

Exempt, because line breaks are semantic there: fenced code blocks and their contents, YAML frontmatter, indented code blocks, and HTML blocks. A diff, log excerpt or file listing reproduced verbatim is exempt too — but it has to be fenced or indented four spaces to qualify. That is what makes it a block at all, to a reader and to `scripts/check_md_wrap.py` alike; verbatim text pasted as bare paragraph lines is indistinguishable from hard-wrapped prose, and gets reflowed like it.

One line break inside a paragraph is authored rather than incidental: a line ending in two or more spaces, or in a backslash, is an explicit CommonMark hard break. That is honoured, and the line it introduces is left alone.

## Enforcement

Enforcement is asymmetric, and honest about it:

- **Repository `.md` files** are checked mechanically by `scripts/check_md_wrap.py`, which detects exactly the two violation classes above — a paragraph, list item or table row split across physical lines, and a `---` without a preceding blank line — and nothing else. `--fix` rejoins them; it is whitespace only, and on a compliant file its output is byte-identical to its input.
- **`--fix` proves that, rather than asserting it.** The checker recognises Markdown blocks with hand-written rules, not a parser, and the [PR #226](https://github.com/amyteq/tt_pangu/pull/226) review found real cases where those rules flattened a nested fence, a tab-indented child list or a lazy blockquote continuation. So every rewrite is now rendered with `markdown-it-py` next to the original and compared the way a browser resolves HTML — whitespace collapsed outside `<pre>`, `<textarea>`, `<script>` and `<style>`, byte for byte inside them. A file whose rendering would change is reported as `REFUSED, not rewritten` and left untouched, and `--fix` exits 1. The one sanctioned exception is the `---` repair, which changes rendering on purpose and is instead held to the rule that a setext heading may disappear but never appear.
- **`--check` stays standard-library only, `--fix` does not.** The CI job installs nothing, and a check that never writes cannot corrupt anything; `markdown-it-py` is imported on the `--fix` path alone (it is in the `dev` extra in `pyproject.toml`, and a unit test parses the module's imports to keep it there). Without it `--fix` refuses to run and exits 2 instead of writing with a warning, because a warning in an agent's log is not a safety net.
- **The renderer this gate targets and the renderer it verifies with are different programs, deliberately.** The target is GitHub's, which is [cmark-gfm](https://github.com/github/cmark-gfm) — that is where these files are read, and it is what the rules above are about. The verifier is `markdown-it-py`, because `--fix` has to be able to refuse on any machine an agent runs it on, and a pure-Python package always installs while a C extension does not. They agree on everything in this repository; the one construct where they are known to differ is an ATX-looking table header over a delimiter row (`# a | b` over `--- | ---`), which markdown-it reads as a two-column table and cmark-gfm as a heading plus a paragraph. **Where the two disagree the checker does nothing** — it reports no violation and rewrites nothing — so a disagreement costs a missed wrap, never a damaged file. No tracked file contains that shape today. Swapping the verifier to `cmarkgfm` (which is on PyPI, with wheels) was considered and declined for now: it buys nothing measurable here, it re-opens the question of whether raw HTML is rendered or omitted in the comparison, and it would mean re-proving the #210 reflow under a second parser. If exactness against GitHub later matters, the additive move is to require *both* parsers to agree, not to switch.
- **The verification has a stated boundary, and `--fix` prints it.** The comparison resolves whitespace the way a browser does, so it rests on knowing where a browser preserves whitespace. Two things defeat that and are therefore refused outright rather than verified: a CSS `white-space` value that keeps line breaks (`<span style="white-space: pre">` makes a source newline visible, and the canonicalised HTML would compare equal anyway), and rendered output that leaves a `<pre>`, `<textarea>`, `<script>` or `<style>` unclosed, which preformats everything after it where the comparison cannot see it. Beyond those, what remains is one parser's reading of CommonMark+GFM — not GitHub's — and `--fix` says so on every run instead of implying more.
- **Both boundary shapes are recognised from parsed HTML, not from patterns matched against it.** The rendered output goes through `html.parser` (standard library, so `--check` stays dependency-free), and only real elements count: a `style` attribute is read however it is written, quoted or not, while `<pre>` named inside a comment or inside `<script>`, `<style>` or `<textarea>` content is text and opens nothing. Both errors were live defects — a valid unquoted `style=white-space:pre` slipped past a quoted-value pattern and `--fix` joined across a newline the reader can see, and a comment mentioning `<pre>` was counted as an unclosed element and made a compliant file unfixable. Regular expressions over serialized HTML produced both, which is why they no longer decide either question.
- **GitHub comment bodies cannot be linted** — nothing runs between an agent and the GitHub API. There the rule holds because it is written down here, in `CLAUDE.md`, and in the report templates that agents load before publishing.

**The gate is scoped, not repo-wide.** The `markdown soft wrap (ADR-0024)` job in `.github/workflows/test.yml` checks two sets: every `.md` file a pull request changes, and an always-checked allowlist of the instruction files agents load into context — 86 today — `CLAUDE.md`, `CLAUDE_zh.md`, `AGENTS.md`, `README.md`, `PROJECT_STATE.md`, `.claude/skills/**`, `.claude/agents/`, `.kca/skills/**`, `.agents/**`, the root of `docs/`, `docs/adr/` and `docs/instructions/`. A wrap defect in that set costs every agent session, which is why it is checked whether or not a change touches it. Run the same check locally with `python scripts/check_md_wrap.py --changed origin/main`.

**The historical backfill is declined.** Converting the rest of the repository's hard-wrapped Markdown — roughly 405 tracked files outside the allowlist — was considered in [#210](https://github.com/amyteq/tt_pangu/issues/210) and rejected by the owner: "do not explode the radius due to back fill on existing md files". Those files are valid history, they are not loaded into agent context, and reflowing them would produce a very large diff for no reading benefit. They become compliant if and when a change touches them, through the changed-files half of the gate. The allowlist reflow itself landed in #210 — 51 files, 2,380 rejoined blocks, proven whitespace-only by `check_md_wrap.py --equivalence`.

Three paths are exempt from the gate in every mode, declared once in `scripts/check_md_wrap.py` and repeated here:

- `worklogs/**` — machine-generated session dumps (`scripts/worklogs_dump.sh` under a systemd user timer). A gate here would fail on commits no human wrote.
- `logs/**` — the same dump pipeline; append-only run archives, not authored prose.
- `**/external/**` — verbatim third-party text, where reflowing would edit a quotation.

**"Required check" is not available on this repository.** Branch protection and rulesets both return HTTP 403 — "Upgrade to GitHub Pro or make this repository public" — and the owner confirmed on 2026-09-17 that this repository will do neither. The job therefore surfaces as an ordinary check-run, and blocking rests on the existing merge convention: merge only when the head commit's check-runs are completed and none failed.

## Consequences

Paragraph-level diffs get bigger — a one-word edit now shows the whole paragraph as changed. That is the accepted cost: `git diff --word-diff` reads well on soft-wrapped text, and the alternative is the reflow noise described above, which is worse because it hides which words actually changed.

Editors need soft wrap turned on to read these files comfortably. That is a per-developer setting, not a repository concern.

## Alternatives considered

**Hard wrap at 80 or 100 columns, enforced by a formatter.** Mechanically enforceable in files, and conventional in some projects. Rejected because it cannot apply to GitHub comments at all, which is where the owner first hit the problem, and because it produces exactly the reflow noise described above.

**Leave it to individual judgement.** This is the status quo that produced the inconsistency. Rejected: the mix is the problem, not either style on its own.
