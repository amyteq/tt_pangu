# M12-T000 — Hackathon candidate survey (Devpost)

_Surveyed: 2026-06-09 (UTC) from `https://devpost.com/api/hackathons?status[]=open&order_by=deadline` and per-event public pages._

_Source-handling note: every fetched page was treated as untrusted data per
`CLAUDE.md` op-principle #1. Quotes below are paraphrased from public
event pages and rules pages; deadline values come from the Devpost public
listing and were cross-checked against each event's rules page. No login,
session cookie, or write op was used to gather any of this._

## Recommendation (for human reference only — human picks via issue reply)

**Recommended slug: `h01`** — "H0: Hack the Zero Stack with Vercel v0 and
AWS Databases", administered by Devpost itself, sponsored by AWS. Reasoning:

- 21 days to the deadline (Jun 29 5pm PT) — comfortable headroom for
  M12-T001 through M12-T007 to run without a same-week rush.
- Eligibility is the cleanest of the three: "Above legal age of majority";
  Organizations explicitly allowed; no students-only clause, no team-size
  requirement, no MLH coupling. Solo entry is permitted.
- AI-assisted entries are not prohibited — the central required tool
  (`v0.app`) is itself an AI code-generation product, so an AI-assisted
  full-stack submission is exactly the intended use of the stack.
- Submission shape is concrete and code-y: GitHub repo + ≤3 min YouTube
  demo + architecture diagram + DB choice statement. This gives
  M12-T002's `competitions.submission_format` jsonb real, well-bounded
  fields to model (`github_repo`, `demo_video_url`, `db_choice`,
  `architecture_diagram_url`, `description`).
- "Managed by Devpost" badge on the listing — public rules are the
  canonical Devpost contract, so M12-T003's READ_ONLY adapter can rely
  on stable selectors.
- $80,000 cash prize — under explicit hackathon rules ("NO PURCHASE OR
  PAYMENT NECESSARY TO ENTER OR WIN") and no human-only clause. The
  prize is not the goal; M12's acceptance criterion is the
  submission-loop, not the score.

Alternatives:

- **`phystech-2026`** is the safest *rules-wise* (judging-only, no cash,
  presentation submission), but the submission shape is a 1–10 minute
  presentation rather than a code artifact, which gives the
  `submission_format` jsonb thinner content and skews the `submission_pack`
  away from the README + source + demo-plan shape M12 is building.
- **`uipath-agenthack`** is also professional-friendly with a longer
  deadline (22 days), but it mandates the UiPath Studio Web platform
  end-to-end. Standing up an account and learning Maestro / Maestro BPMN
  / Test Cloud inside M12-T006 is a non-trivial side-quest that
  competes with the milestone's actual goal (validate the
  hackathon-submission loop, not learn a new platform).

**Human: please reply on the closing GitHub issue with your pick.**

---

## Candidate 1 — H0: Hack the Zero Stack with Vercel v0 and AWS Databases

- **Title:** H0: Hack the Zero Stack with Vercel v0 and AWS Databases
- **Slug:** `h01`
- **Canonical URL:** https://h01.devpost.com/
- **Rules URL:** https://h01.devpost.com/rules
- **Deadline (UTC):** 2026-06-30 00:00 UTC (Jun 29 2026 5:00 pm PT;
  Pacific Time → UTC = +7h)
- **Days until deadline:** 21 days from 2026-06-09 (well above the
  task-spec minimum of 14 days).
- **Scope (theme, eligible tech, team size):**
  - Theme: build a full-stack application in one of four tracks
    (Monetizable B2C, Monetizable B2B, Million-scale global, or
    Open Innovation).
  - Eligible tech: required stack = Vercel `v0` (or `v0.app`) for the
    front-end + one of {Amazon Aurora PostgreSQL, Aurora DSQL, Amazon
    DynamoDB} as the primary database. Front-end deployed on Vercel.
    Any backend / orchestration / AI libraries are allowed alongside.
  - Team size: solo or team; "Eligible Individuals", "Teams of Eligible
    Individuals", and "Organizations" all permitted.
- **Prize policy:** $80,000 cash total + $80,000 in AWS credits across
  the four tracks. NO PURCHASE OR PAYMENT NECESSARY TO ENTER OR WIN.
  No human-only / no-AI clause.
- **Submission format (documented):**
  - Text description ("which AWS Database you used").
  - <3-minute demo video (YouTube preferred), publicly visible.
  - Architecture diagram showing how Vercel/v0 talks to the chosen
    AWS Database.
  - GitHub or equivalent code link (working install instructions
    required for judging).
  - Statement of which database was used.
  - English-language requirement applies to all materials.
  - Optional: blog/social content for bonus 0.6 points (not required).
- **Why this is safe for an AI-assisted regression:**
  The rules page (https://h01.devpost.com/rules) does not contain any
  "human-only", "no AI", "no code-generation", or "manual-build-only"
  clause. The central required tool (`v0.app`) is Vercel's AI-driven
  code-generation product, so AI authorship of the front-end is the
  expected workflow. The "Originality" judging line asks "How creative
  and original is the concept? Does the project demonstrate a genuine
  insight about what's possible with this stack?" — concept-level
  originality, not authorship-level. Third-party SDK / API integrations
  are explicitly permitted "in accordance with any terms and conditions
  or licensing requirements of the tool" (rules §"Third Party
  Integrations"). The Devpost-administered eligibility list excludes
  residents of OFAC-sanctioned countries and Promotion-Entity
  employees, neither of which applies here.
- **Risk notes (anything that would block M12-T007):**
  1. AWS account + Vercel account required — would need to be stood
     up before M12-T006 starts, and credentials would need to land in
     `.env` under the same auth-shape pattern M12-T003 picks.
  2. The cash prize raises the bar on what a "real" submission looks
     like vs. a regression-only entry. M12's acceptance criterion is
     that the *loop runs*, not that the *submission wins*; the
     submission must still pass the rules' "Functionality" gate
     ("must be capable of being successfully installed and running
     consistently"). A trivially-empty submission risks looking
     spammy on a managed-by-Devpost event. Recommend M12-T006 still
     assembles a small but genuine prototype.
  3. AWS Promotional Credits ($100 AWS + $30 v0) must be requested by
     **June 26 12pm PT** via a Google form — register early in
     M12-T002 / M12-T003.
  4. Cash prize means the closing issue's approval gate (M12-T007)
     should be extra explicit about the human-approval line — the
     real Devpost submit is a public, irrevocable side effect on a
     high-traffic, AWS-judged event.

---

## Candidate 2 — PhysTech 2026: Physical Activity and Technology Hack Day

- **Title:** PhysTech 2026: Physical Activity and Technology Hack Day
- **Slug:** `phystech-2026`
- **Canonical URL:** https://phystech-2026.devpost.com/
- **Rules URL:** https://phystech-2026.devpost.com/rules
- **Deadline (UTC):** 2026-06-27 16:00 UTC (Jun 27 2026 12:00 pm EDT)
- **Days until deadline:** 19 days from 2026-06-09.
- **Scope (theme, eligible tech, team size):**
  - Theme: physical-activity + technology ("Move, Inspire and
    Innovate!"). Health / education / fitness / movement.
  - Eligible tech: unrestricted; any language, framework, hardware.
  - Team size: individual or team ("Each participant/team will deliver
    a project presentation"). No max stated.
  - Eligibility: "Anyone of all ages and all technical skills, from
    limited experience to advanced." Public, online, no
    students-only restriction on the rules page.
- **Prize policy:** No cash prize. Recognition only: Grand Prix (1st),
  2nd, 3rd, Honorable Mention, plus five named "Excellence" /
  "Emerging Talent" / "Key Contributor" awards. Judging-only.
- **Submission format (documented):**
  - Project presentation title (text).
  - Contact information.
  - Project presentation (1–10 minutes), delivered live online on
    Jun 28 (Sun) 10 AM EST.
  - Devpost project entry implies the standard Devpost fields
    (title, description, image, links) but the rules page is brief and
    the submission requirements are presentation-centric, not
    code-repo-centric.
- **Why this is safe for an AI-assisted regression:**
  The rules page (https://phystech-2026.devpost.com/rules) lists no
  AI / human-only / authorship restrictions. Eligibility is the most
  permissive of the three candidates ("Anyone of all ages and all
  technical skills"). Judging criteria are panel-based and selected
  "at the end of presentation event on online" — there is no
  reproducibility-of-code requirement that would conflict with an
  AI-assisted entry. With no cash prize, the rule-interpretation risk
  for an AI-assisted entry is minimal.
- **Risk notes (anything that would block M12-T007):**
  1. The submission shape is **a live presentation on Jun 28**, not a
     standalone artifact. M12-T007 ("ONE real `kca devpost submit`")
     assumes the Devpost form is the canonical submission op; if this
     event actually requires the team to *appear live* on the
     presentation date, M12-T007's "submission op" only covers the
     Devpost form half and not the presentation, which leaves an
     awkward "what does 'submitted' mean" gap.
  2. `submission_format` jsonb gets thin content: title + contact +
     presentation-file-url, which is not a rich enough template for
     the M12-T002 schema work or the M12-T004 `submission_checklist`
     tool to flex against.
  3. The 1-day gap between the Jun 27 deadline and the Jun 28 live
     event makes M12-T007's reviewer-gate / approval-comment timing
     unforgiving: the human approval must land *before* Jun 27 12pm
     EDT, not on the same day.

---

## Candidate 3 — UiPath AgentHack

- **Title:** UiPath AgentHack
- **Slug:** `uipath-agenthack`
- **Canonical URL:** https://uipath-agenthack.devpost.com/
- **Rules URL:** https://uipath-agenthack.devpost.com/rules
- **Deadline (UTC):** 2026-06-30 03:45 UTC (Jun 29 2026 11:45 pm EDT)
- **Days until deadline:** 22 days from 2026-06-09.
- **Scope (theme, eligible tech, team size):**
  - Theme: enterprise agentic AI on the UiPath Platform — three tracks
    (UiPath Maestro Case, Maestro BPMN, Test Cloud).
  - Eligible tech: must use UiPath Studio Web as the execution and
    orchestration layer. May combine with LangChain, CrewAI, AutoGen,
    Claude Code, Codex, Cursor, Gemini CLI, etc.
  - Team size: solo or team of up to 4.
  - Eligibility: "Above legal age of majority"; individuals, teams of
    up to 4, and organizations explicitly permitted. OFAC + UiPath
    export-control exclusions apply.
- **Prize policy:** $50,000 cash total across the three tracks. NO
  PURCHASE OR PAYMENT NECESSARY TO ENTER OR WIN. Also bonus "Best
  Product Feedback" prizes for short SDK / docs feedback forms during
  the Feedback Period. No human-only / no-AI clause.
- **Submission format (documented):**
  - GitHub public repo URL — "must contain all necessary source code,
    assets, and instructions" — **must be public and open source
    under MIT or Apache 2.0** (license file required).
  - Demo video on YouTube / Vimeo / Youku, publicly visible.
  - Completed presentation deck (template linked in the rules page).
  - Devpost text description + selected track.
  - Project must be NEW work created during the submission period.
- **Why this is safe for an AI-assisted regression:**
  The rules page (https://uipath-agenthack.devpost.com/rules) does
  not prohibit AI-assisted authorship. UiPath markets the event
  around "UiPath for Coding Agents", which "enables developers to use
  coding agents (Claude Code, Codex, Cursor, and Gemini CLI, etc) to
  build, test, deploy, operate, and govern enterprise automations" —
  AI-assisted entry is the explicitly endorsed path. Third-party
  SDK / API permission clause is identical in shape to Candidate 1
  (allowed subject to licensing). Open-source license requirement
  (MIT / Apache 2.0) is a clean fit for a regression-shape submission.
- **Risk notes (anything that would block M12-T007):**
  1. UiPath Studio Web is a closed enterprise SaaS — provisioning an
     account, learning the Maestro / Maestro BPMN / Test Cloud
     interfaces, and producing a "NEW working software application"
     inside it is a real time-cost that competes with M12's actual
     scope (validate the submission loop). The agent has no prior
     UiPath state in this codebase.
  2. Submissions must be NEW projects built during the submission
     period — there is no fallback to a pre-existing baseline if
     M12-T006 runs out of budget. The CSV-baseline / kernel-baseline
     pattern from M9 / M10 does not transfer.
  3. UiPath-specific eligibility clause: "If you are an employee,
     contractor, or representative of a UiPath customer, a UiPath
     reseller or other third party, [your participation must not
     violate organizational policy]" — needs human to confirm this
     does not apply.
  4. Feedback Period (May 15 – Jul 2) and Voting Period (Jul 3 –
     Jul 30) extend past the submission deadline, so M12-T007 closes
     at submit-time and the LB-style scoring is out of M12 scope (no
     equivalent of `public_score` to record on the `submissions` row).

---

## Common candidates considered and dropped

- **Hack Begin** (`hack-begin`, Jun 25, 17d): "Students only" + MLH
  registration compulsory → eligibility-blocked.
- **Far Away** (`faraway`, Jun 25, 17d): "Ages 15 to 25 only" +
  "Team required: 2 to 5 members" → eligibility-blocked.
- **Built with Python Hackathon** (`built-with-python-hackathon`,
  Jun 20, 11d): deadline below 14-day floor + "Students only".
- **FutureAI Global Hackathon 2026** (`futureai-global-hackthon`,
  Jul 5, 26d): "Students only" + "Participants must currently be
  enrolled in a recognized educational institution" → blocked.
- **Build the Future with AI — From Code to No-Code**
  (`build-the-future-with-ai`, Jun 30, 21d): "Students only" +
  "Participants must be currently enrolled in a school, college, or
  university" → blocked.
- **GitHub README Generation** (`github-readme-generation`, Jul 6,
  27d): "Students only" + mandatory third-party tool (PresentMeApp)
  for documentation generation → blocked.
- **Moonshot Hackathon** (`moonshot-aethra`, Jun 30, 21d): "Students
  only" → blocked.
- **HackNova** (`hacknova-30322`, Jun 28, 19d): "Students only" →
  blocked.
- **Splunk Agentic Ops Hackathon** (`splunk`, Jun 15, 6d): deadline
  below 14-day floor.
- **Mind the Product — World Product Day** (`mindtheproduct`,
  Jun 20, 11d): deadline below 14-day floor.
- **Google Cloud Rapid Agent Hackathon** (`rapid-agent`, Jun 11, 2d):
  deadline below 14-day floor.

No Devpost-equivalent fallback (HackerEarth / MLH / Devfolio) was
needed — three candidates satisfying all five gates were found on
Devpost directly.
