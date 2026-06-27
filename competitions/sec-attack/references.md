# References — sec-attack

> Each: title / URL or path / one-line note / trust level. Trust: **[SDK]** authoritative (source-read) ·
> **[official]** Kaggle/partner · **[community]** blog/video · **[⚠]** unverified.

## SDK (authoritative — read 2026-06-26)
- `aicomp-sdk` 3.1.2 (PyPI) — the competition framework ("JED"). Install `pip install aicomp-sdk==3.1.2`. **[SDK]**
- `scoring.py` — exact metric (`SEVERITY_W`, `ATTACK_ELITE_RAW=200000`, normalization). **[SDK]**
- `core/predicates.py` — the 4 predicates, severities, exfil decode-detection, breach rule. **[SDK]**
- `core/cells.py` — cell signature → the unique-cell breadth lever. **[SDK]**
- `attacks/contracts.py` · `core/env/api.py` — `AttackAlgorithmBase`, `AttackCandidate`, `AttackRunConfig`, env protocol. **[SDK]**
- `attacks/baselines/attacker_goexplore.py` — the reference Go-Explore attacker (our starting point). **[SDK]**
- `attacks/baselines/{attack_random,guardrail_rules}.py` · `guardrails/{base,optimal}.py` — floor attacker + guardrails. **[SDK]**
- `agents/{factory,deterministic_agent}.py` — agent selection + the naive vulnerable agent's injection triggers. **[SDK]**
- `fixtures/{web_corpus.json (19,679 pages),mail_seed.json,file_seed/secret.txt}` — the untrusted-content seeds. **[SDK]**

## Kaggle
- Competition: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks **[official, JS-rendered ⚠]**
- Data / Rules / Code / Discussion subpages — JS-rendered; not fully fetchable via plain HTTP. **[⚠]**

## Docs / repo
- JED docs: https://mbhatt1.github.io/competitionscratch/ — `GETTING_STARTED`, `KAGGLE_REDTEAM_GUIDE`, `SCORING`, `API_REFERENCE`. **[official]**
- Repo: https://github.com/mbhatt1/competitionscratch (MIT). **[official]**

## Discussions / notebooks (to read once pages render)
- Official starter: `martynaplomecka/getting-started-notebook`. **[community ⚠]**
- Community kernels: `yaroslavkholmirzayev/…`, `nikitagajbhiye30/…`, `boristown/…`, `gdataranger/jed-attack-dgx-spark-gb10`. **[community ⚠]**
- Video "The 0-Second Bypass: Evaluating 1,000,000 Policies Offline (Kaggle AI Agent Security)" — suggests the
  offline-enumeration meta. https://www.youtube.com/watch?v=-bQmcUlUfKg **[community ⚠]**

## Papers / background
- NIST CAISI blog — insights from a large-scale agent red-teaming competition. **[official-adjacent]**
- arXiv 2507.20526 — security challenges in AI agent deployment (related, different contest). **[community]**

## Internal notes
- `research.md` (mechanics) · `strategy.md` (ideas/challenges/techniques) · `notes.md` (canonical notes) · `notes_zh.md` (中文镜像) · `rules.md`.
- Reusable: `competitions/_shared/insights.md` (offline gate must match online metric); CLAUDE.md CTF boundary.

## Memory
- `project_kca_yaml_core.md`, `feedback_local_arena_harry_arch.md`, `reference_snorlax_compute.md` (GPU for real-agent runs).
