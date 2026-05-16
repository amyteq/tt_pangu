# ADR-0002: Hybrid Worker and Model Routing

## Status
Accepted as initial direction.

## Decision
Use a hybrid architecture:
- Python-first competition worker for Kaggle/ML/CTF execution.
- TypeScript/Supabase-compatible control plane and future UI.
- Claude Agent SDK as the default production coding worker harness.
- Claude Code CLI/Desktop for interactive development and dogfooding.
- Optional model router for OpenAI, Claude, and local vLLM/Ollama models.

## Rationale
Kaggle and ML workflows are Python-heavy and require notebooks, data processing, evaluation scripts, and model training. Product UI and control-plane logic are more naturally TypeScript/Supabase/Lovable-friendly. Splitting these concerns reduces friction.

Claude Agent SDK provides a mature coding-agent harness with file tools, command execution, code editing, project instructions, skills, hooks, and programmatic control. Local and OpenAI-compatible models remain useful as reviewers, summarizers, cheap subagents, or future alternatives.

## Initial model routing policy
- Claude Sonnet: default coding loop, refactors, test fixes, medium-complexity experiments.
- Claude Opus: difficult architecture, complex debugging, high-value final reasoning, hard Kaggle strategy decisions.
- GPT-5.5 / Codex: alternate reviewer, coding benchmark comparison, independent solution proposals, hard terminal tasks.
- GPT-5.5 Pro: expensive escalation only for high-value final reviews or very difficult reasoning.
- Local vLLM/Ollama models: low-cost/private subagents for log summarization, boilerplate generation, batch hypothesis generation, and simple static checks.

## Consequences
The worker must support model routing and must log token usage, model choice, task type, result quality, and cost. The system should remain provider-agnostic at the orchestration level while using Claude Agent SDK as the initial core implementation.
