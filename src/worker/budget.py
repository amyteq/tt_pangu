from __future__ import annotations

import time

from src.worker._types import JobPolicy

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
_DEFAULT_PRICING = (3.0, 15.0)


class BudgetTracker:
    def __init__(
        self,
        policy: JobPolicy,
        model: str = "claude-sonnet-4-6",
        started_at: float | None = None,
    ):
        self.policy = policy
        self.model = model
        self.started_at = started_at or time.monotonic()
        self.turns = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0

    def record_turn(self, response_or_input, output_tokens: int | None = None) -> None:
        """Record one turn from either a response object or explicit token counts.

        Accepts:
          record_turn(response)                  — extracts tokens from response.usage
          record_turn(input_tokens, output_tokens) — explicit counts (mock/test path)
        """
        if output_tokens is not None:
            # Explicit integer path (test/mock)
            in_tok = int(response_or_input)
            out_tok = int(output_tokens)
        else:
            # Response object path (real litellm or mock returning response object)
            resp = response_or_input
            usage = getattr(resp, "usage", None)
            if usage is not None:
                in_tok = getattr(usage, "prompt_tokens", 0) or 0
                out_tok = getattr(usage, "completion_tokens", 0) or 0
            else:
                in_tok = out_tok = 0
            # Try litellm.completion_cost for accurate per-provider pricing.
            try:
                import litellm

                self.cost_usd += litellm.completion_cost(completion_response=resp)
                self.turns += 1
                self.input_tokens += in_tok
                self.output_tokens += out_tok
                return
            except Exception:
                pass  # fall through to manual pricing

        self.turns += 1
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        in_price, out_price = MODEL_PRICING.get(self.model, _DEFAULT_PRICING)
        self.cost_usd += (in_tok * in_price + out_tok * out_price) / 1_000_000

    def check_limits(self) -> str | None:
        if self.turns >= self.policy.max_turns:
            return "max_turns"
        if self.cost_usd >= self.policy.max_cost_usd:
            return "max_cost_usd"
        elapsed = time.monotonic() - self.started_at
        if elapsed >= self.policy.max_runtime_s:
            return "max_runtime_s"
        return None

    @property
    def summary(self) -> dict:
        return {
            "turns": self.turns,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "elapsed_s": round(time.monotonic() - self.started_at, 2),
        }
