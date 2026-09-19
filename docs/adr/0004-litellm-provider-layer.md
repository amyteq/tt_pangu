# ADR-0004: LiteLLM as unified LLM provider layer

Status: accepted  
Date: 2026-05-19  
Decided in: `docs/meeting-notes/2026-05-19-r1.md`

---

## Context

The platform's `AgentWorker` needs to call LLMs for research, code generation, debugging, and analysis. Initial prototypes used `anthropic.Anthropic()` directly, creating a hard dependency on the Anthropic SDK and Claude models.

The user explicitly does not want vendor lock-in. Kaggle competition work benefits from:
- Switching models per task type (Claude for coding, GPT-4o for review)
- Using cheap local models (vLLM/Ollama) for log triage and summaries
- Ensembling outputs from multiple providers
- Controlling cost by routing cheap tasks to cheaper models

## Decision

Use **LiteLLM** (`pip install litellm`) as the single interface to all LLM providers.

```python
import litellm

response = litellm.completion(
    model=job_policy.model,          # "claude-sonnet-4-6" | "gpt-4o" | "ollama/qwen2.5"
    messages=messages,
    tools=TOOL_SCHEMAS,              # OpenAI tool schema format
    temperature=job_policy.temperature,
    top_p=job_policy.top_p,
    max_tokens=8192,
)
```

LiteLLM normalises all provider responses to OpenAI format, so `AgentWorker` never needs provider-specific branches.

## Tool schema format

All tool definitions (`TOOL_SCHEMAS`) use the **OpenAI tool schema format**, which LiteLLM accepts for all providers (translates to Anthropic format internally):

```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    }
}
```

## Sampling parameters per job type

Each job type has a recommended parameter profile. These are stored in `JobPolicy` and passed verbatim to `litellm.completion()`.

| job_type | model (default) | temperature | top_p | notes |
|---|---|---|---|---|
| `research` | claude-sonnet-4-6 | 0.8 | 0.95 | Creative, divergent; explore more possibilities |
| `implement` | claude-sonnet-4-6 | 0.2 | 0.90 | Precise code; minimize variance |
| `experiment` | claude-sonnet-4-6 | 0.1 | 0.90 | Reproducible; near-deterministic |
| `debug` | claude-sonnet-4-6 | 0.3 | 0.90 | Careful analysis; some exploration |
| `eval` | claude-sonnet-4-6 | 0.5 | 0.90 | Analytical but exploratory |
| `prepare_submission` | claude-sonnet-4-6 | 0.1 | 0.90 | Very conservative |
| `review` | gpt-4o | 0.3 | 0.90 | Independent reviewer; different provider |
| `log_triage` | ollama/qwen2.5 | 0.3 | 0.90 | Cheap local; no API cost |

`min_p` is provider-dependent; use only when the model supports it (check litellm docs).

## Model router (M6 full implementation)

For M3, `model` is a static field in `JobPolicy` set at job creation time.

M6 will add a model router that automatically selects the model based on:
- `task_complexity` (simple / hard / critical)
- `cost_budget_remaining`
- `available_providers` (which API keys are configured)
- Competition-specific policy overrides

## Cost tracking

LiteLLM exposes cost per call via:
```python
cost = litellm.completion_cost(completion_response=response)
# or via callback
litellm.success_callback = ["langfuse"]  # optional; OTEL in ADR-0007
```

`BudgetTracker` in `src/worker/budget.py` uses `litellm.completion_cost()` instead of the manual per-model lookup table from M3-T004.

## Supported providers (tested/planned)

| Provider | litellm model string | Notes |
|---|---|---|
| Anthropic Claude | `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001` | Primary |
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `o3` | Secondary / reviewer |
| Google | `gemini/gemini-2.0-flash` | Optional |
| Groq | `groq/llama-3.3-70b-versatile` | Fast, cheap |
| vLLM local | `hosted_vllm/qwen2.5-72b` | Local GPU (RTX 3090/4090) |
| Ollama local | `ollama/qwen2.5`, `ollama/llama3` | Lightweight local |

## Consequences

- **Positive:** One interface for all providers; easy to A/B test models per task.
- **Positive:** Cost tracking unified through `litellm.completion_cost()`.
- **Positive:** OTEL integration available via LiteLLM callbacks (ADR-0007).
- **Negative:** LiteLLM is a third-party dependency (~30 transitive deps — within limit).
- **Negative:** Some advanced provider features (extended thinking, prompt caching) may require provider-specific params passed through `extra_body` or `litellm_extra_params`.
- **Mitigation:** Keep tool schemas in OpenAI format; document provider quirks in `docs/tooling/litellm-provider-notes.md` as they arise.

## Migration note for M3

M3-T003 (`src/worker/tools.py`) should define `TOOL_SCHEMAS` in OpenAI format from the start. M3-T004 (`src/worker/worker.py`) should use `litellm.completion()` instead of `anthropic.Anthropic()`. `MockAnthropicClient` should be renamed to `MockLiteLLMClient` and return OpenAI-format responses.
