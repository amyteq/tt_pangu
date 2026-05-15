---
name: ctf-sandbox
description: Use for authorized CTF challenge solving only: local challenge analysis, sandboxed exploitation, solver scripts, flags, and writeups within explicitly provided scope.
---

# CTF Sandbox Workflow

Use this workflow only for explicitly authorized CTF challenges, local labs, or target scopes provided by the human.

## Safety scope

Allowed:

- Analyze local challenge files.
- Run challenge containers or binaries provided for the CTF.
- Interact with explicitly provided CTF endpoints.
- Write solver scripts and educational writeups.

Not allowed:

- Scan public IP ranges or unrelated domains.
- Attack third-party systems.
- Steal or exfiltrate real credentials.
- Deploy malware, persistence, or destructive payloads.
- Use CTF techniques outside the authorized scope.

## Workflow

1. Restate the authorized scope and target.
2. Inventory files, services, ports, and constraints.
3. Identify category: crypto, pwn, web, reversing, forensics, misc, OSINT, etc.
4. Form hypotheses and run minimal safe checks.
5. Keep commands and outputs logged.
6. Build a solver or exploit only within the challenge scope.
7. Produce a concise writeup with root cause, steps, flag, and mitigation idea if relevant.

If scope is unclear, ask the human to define the CTF target before running security tooling.
