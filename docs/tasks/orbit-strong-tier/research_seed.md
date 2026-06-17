# Research seed notes for OW-P0-RESEARCH-001

These notes are starting points only. Claude Code must verify them from the local repo, Kaggle, or read-only API before using them as project facts.

## Kuni05 public source candidate

Potential Kaggle Code reference:

```text
kuni05/lb-1240-5-orbit-wars-producer-agent-submission
URL: https://www.kaggle.com/code/kuni05/lb-1240-5-orbit-wars-producer-agent-submission
```

Suggested read-only pull:

```bash
kaggle kernels pull kuni05/lb-1240-5-orbit-wars-producer-agent-submission \
  -p competitions/orbit-wars/sources/kuni05_producer_agent -m
```

Use for system study and attribution. Do not label derived public-source submission as from-scratch.

## Matchmaking starting hypothesis

Kaggle simulation competitions generally pair submissions against opponents with similar skill rating, but Orbit live data should be analyzed empirically. New submissions may have high uncertainty, so first episodes can appear mixed. Do not assume a weak-to-strong curriculum without evidence.

## Identity mapping starting hypothesis

Kaggle has both stable username and mutable display/profile name. Orbit replay `info.TeamNames` may show display/profile/team names rather than account usernames. Existing Orbit tooling should map seats by `submissionId` and reward matching rather than string matching only.

Known issue to verify:

```text
flyingfox == harrysun2006 profile/display name
```
