# Model Routing Strategy

## Goals
- Use the strongest model only when it changes outcomes.
- Use cheaper/faster models for routine coding and summarization.
- Keep provider choice explicit and auditable.
- Measure task success, not only token cost.

## Recommended routing tiers

### Tier 1: Routine local/cheap tasks
Use local vLLM/Ollama models or inexpensive hosted models for:
- Log summarization.
- Extracting metrics from training output.
- Drafting experiment notes.
- Simple code comments or boilerplate.
- Batch idea generation.

### Tier 2: Default coding worker
Use Claude Sonnet or equivalent strong coding model for:
- Reading codebase context.
- Implementing experiments.
- Writing tests.
- Fixing ordinary failures.
- Producing patches.

### Tier 3: Hard reasoning / senior reviewer
Use Claude Opus or GPT-5.5 for:
- Competition strategy.
- Complex debugging.
- Validation design.
- Architecture decisions.
- Independent review of a proposed solution.

### Tier 4: Expensive escalation
Use GPT-5.5 Pro or another premium model only for:
- High-value final review before major submission.
- A blocking issue that cheaper models failed to resolve.
- Deep reasoning tasks with clear expected payoff.

## Required logging
Every agent run should log:
- Model and provider.
- Task category.
- Input/output token estimates or provider usage data.
- Wall-clock time.
- Tool calls.
- Result summary.
- Human verdict where available.
- Cost estimate.

## Stop conditions
- Maximum iteration count reached.
- Budget threshold reached.
- No validation improvement after N experiments.
- Human approval required.
- Safety hook denial.
