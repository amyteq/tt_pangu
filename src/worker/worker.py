"""AgentWorker — agentic tool loop powered by LiteLLM (ADR-0004)."""
from __future__ import annotations

import json
import time
import types
from pathlib import Path

from src.worker._types import JobPolicy, WorkerResult
from src.worker.tools import TOOL_SCHEMAS, ToolExecutor, ApprovalRequired
from src.worker.budget import BudgetTracker


# ---------------------------------------------------------------------------
# Mock LiteLLM client for dry_run tests
# ---------------------------------------------------------------------------

def _make_usage(prompt_tokens: int, completion_tokens: int):
    return types.SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _make_tool_calls_response(tool_name: str, tool_input: dict,
                               prompt_tokens: int = 50, completion_tokens: int = 20):
    tc = types.SimpleNamespace(
        id=f"call_{tool_name}",
        type="function",
        function=types.SimpleNamespace(
            name=tool_name,
            arguments=json.dumps(tool_input),
        ),
    )
    msg = types.SimpleNamespace(
        content=None,
        tool_calls=[tc],
    )
    choice = types.SimpleNamespace(
        message=msg,
        finish_reason="tool_calls",
    )
    return types.SimpleNamespace(
        choices=[choice],
        usage=_make_usage(prompt_tokens, completion_tokens),
    )


def _make_stop_response(text: str, prompt_tokens: int = 30, completion_tokens: int = 10):
    msg = types.SimpleNamespace(
        content=text,
        tool_calls=None,
    )
    choice = types.SimpleNamespace(
        message=msg,
        finish_reason="stop",
    )
    return types.SimpleNamespace(
        choices=[choice],
        usage=_make_usage(prompt_tokens, completion_tokens),
    )


class MockLiteLLMClient:
    """Deterministic LiteLLM mock. Never calls any real API."""

    def __init__(self, scenario: str = "two_turns"):
        self._turn = 0
        self._scenario = scenario

    def completion(self, **kwargs) -> object:
        self._turn += 1
        if self._scenario == "two_turns":
            if self._turn == 1:
                return _make_tool_calls_response("read_file", {"path": "README.md"}, 50, 20)
            return _make_stop_response("dry run complete", 30, 10)
        if self._scenario == "infinite_tool":
            return _make_tool_calls_response("read_file", {"path": "README.md"}, 100, 50)
        raise ValueError(f"unknown scenario: {self._scenario}")


# ---------------------------------------------------------------------------
# AgentWorker
# ---------------------------------------------------------------------------

class AgentWorker:
    """Competition agent worker using LiteLLM as the provider layer (ADR-0004)."""

    def __init__(
        self,
        job_id: str,
        prompt: str,
        policy: JobPolicy,
        workspace: Path,
        db_url: str | None = None,
        model: str | None = None,
        dry_run: bool = False,
        resume_state: dict | None = None,
    ):
        self.job_id = job_id
        self.prompt = prompt
        self.policy = policy
        self.workspace = Path(workspace)
        self.db_url = db_url
        self.dry_run = dry_run
        # Optional resume state: {turns_used, cost_usd, last_msg, allow_once}
        self.resume_state = resume_state or {}
        # model kwarg overrides policy.model when given
        if model is not None:
            self.policy = JobPolicy(
                max_turns=policy.max_turns,
                max_cost_usd=policy.max_cost_usd,
                max_runtime_s=policy.max_runtime_s,
                allowed_tool_patterns=policy.allowed_tool_patterns,
                model=model,
                temperature=policy.temperature,
                top_p=policy.top_p,
                min_p=policy.min_p,
                approval_gates=policy.approval_gates,
                max_side_effect=policy.max_side_effect,
            )
        # Allow test code to override the mock scenario or inject a client directly.
        self._mock_scenario: str = "two_turns"
        self._mock_client: MockLiteLLMClient | None = None

    def run(self) -> WorkerResult:
        if self._mock_client is not None:
            client = self._mock_client
        elif self.dry_run:
            client = MockLiteLLMClient(scenario=self._mock_scenario)
        else:
            client = None
        budget = BudgetTracker(self.policy, model=self.policy.model)
        # Seed from resume_state so cumulative turns/cost roll forward.
        if self.resume_state:
            budget.turns = int(self.resume_state.get("turns_used") or 0)
            budget.cost_usd = float(self.resume_state.get("cost_usd") or 0.0)
        executor = ToolExecutor(self.workspace, self.policy)
        # One-shot allowlist for the paused tool_input from a prior pause.
        allow_once = (self.resume_state or {}).get("allow_once") or None
        messages: list[dict] = [{"role": "user", "content": self.prompt}]
        start = time.monotonic()

        while True:
            # 1. Pre-turn budget check
            stop_reason = budget.check_limits()
            if stop_reason:
                self._update_status("failed", error=stop_reason, budget=budget)
                return WorkerResult(
                    status="budget_stop",
                    turns_used=budget.turns,
                    cost_usd=budget.cost_usd,
                    duration_s=time.monotonic() - start,
                    final_message="",
                    stop_reason=stop_reason,
                )

            # 2. LiteLLM call (OpenAI format for all providers)
            extra: dict = {} if self.policy.min_p is None else {"min_p": self.policy.min_p}
            if client is not None:
                response = client.completion(
                    model=self.policy.model,
                    max_tokens=8192,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                    temperature=self.policy.temperature,
                    top_p=self.policy.top_p,
                    **extra,
                )
            else:
                import litellm
                response = litellm.completion(
                    model=self.policy.model,
                    max_tokens=8192,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                    temperature=self.policy.temperature,
                    top_p=self.policy.top_p,
                    **extra,
                )

            # 3. Record turn cost
            budget.record_turn(response)
            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            self._append_event(
                "turn_start", budget.turns,
                input_tokens=getattr(response.usage, "prompt_tokens", 0),
                output_tokens=getattr(response.usage, "completion_tokens", 0),
                cost_usd=budget.cost_usd,
                event_data={"finish_reason": finish_reason},
            )

            # 4. stop → job done
            if finish_reason == "stop":
                final_text = msg.content or ""
                self._update_status("succeeded", budget=budget)
                return WorkerResult(
                    status="done",
                    turns_used=budget.turns,
                    cost_usd=budget.cost_usd,
                    duration_s=time.monotonic() - start,
                    final_message=final_text,
                    stop_reason="end_turn",
                )

            # 5. tool_calls → execute each tool
            if finish_reason == "tool_calls":
                tool_calls = msg.tool_calls or []
                # Append assistant turn with tool_calls (OpenAI message format)
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })
                for tc in tool_calls:
                    tool_input = json.loads(tc.function.arguments)
                    self._append_event(
                        "tool_call", budget.turns,
                        event_data={"tool": tc.function.name, "input": tool_input},
                    )
                    try:
                        result_content = executor.execute(tc.function.name, tool_input)
                    except ApprovalRequired as exc:
                        # One-shot resume allowance: bypass the matching gate
                        # exactly once after `kca decisions approve`.
                        if (
                            allow_once
                            and (
                                allow_once.get("operation") == exc.tool_name
                                or allow_once.get("operation") == "tool_approval"
                            )
                        ):
                            allow_once = None  # consume
                            # Recurse into the actual tool with policy bypass
                            # by temporarily relaxing max_side_effect for this
                            # one call.
                            saved = executor.policy.max_side_effect
                            executor.policy.max_side_effect = "SUBMISSION"
                            try:
                                result_content = executor.execute(
                                    tc.function.name, tool_input
                                )
                            finally:
                                executor.policy.max_side_effect = saved
                        else:
                            return self._handle_approval_required(exc, budget, start)

                    self._append_event(
                        "tool_result", budget.turns,
                        event_data={
                            "tool": tc.function.name,
                            "result_preview": str(result_content)[:200],
                        },
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result_content),
                    })
                continue

            # 6. Unexpected finish_reason
            self._update_status(
                "failed", error=f"unexpected finish_reason={finish_reason}", budget=budget
            )
            return WorkerResult(
                status="failed",
                turns_used=budget.turns,
                cost_usd=budget.cost_usd,
                duration_s=time.monotonic() - start,
                final_message="",
                stop_reason="unexpected",
            )

    def _handle_approval_required(
        self, exc: ApprovalRequired, budget: BudgetTracker, start: float
    ) -> WorkerResult:
        """Pause the job and record a decision request."""
        decision_id = None
        if self.db_url:
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
                import db as _db
                decision_id = _db.insert_approval_request(
                    decision_type="tool_approval",
                    prompt=f"Worker job {self.job_id} wants to call {exc.tool_name}",
                    options={"approve": "allow this tool call", "deny": "block and stop job"},
                    job_id=self.job_id,
                )
                _db.update_job(
                    self.job_id,
                    status="paused",
                    turns_used=budget.turns,
                    cost_usd=budget.cost_usd,
                )
            except Exception:
                pass
        self._append_event(
            "approval_pause", budget.turns,
            event_data={
                "tool": exc.tool_name,
                "operation": exc.tool_name,
                "tool_input": exc.tool_input,
                "side_effect": exc.side_effect,
                "decision_id": decision_id,
            },
        )
        import sys
        print(
            f"JOB PAUSED — run `kca decisions approve --id {decision_id}` to resume",
            file=sys.stderr,
        )
        return WorkerResult(
            status="paused",
            turns_used=budget.turns,
            cost_usd=budget.cost_usd,
            duration_s=time.monotonic() - start,
            final_message=f"Waiting for approval: decision_id={decision_id}",
            stop_reason="approval_required",
        )

    @classmethod
    def resume(
        cls,
        job_id: str,
        *,
        workspace: Path,
        policy: JobPolicy | None = None,
        db_url: str | None = None,
        dry_run: bool = False,
    ) -> "AgentWorker":
        """Construct an AgentWorker primed from prior agent_job_events.

        Reads the job row + events; reconstructs (turns_used, cost_usd) and
        seeds a one-shot approval allowlist for the paused tool_input so the
        next gate check passes once.
        """
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
        import db as _db
        job = _db.get_job(job_id)
        events = _db.list_job_events(job_id)
        turns = int(job.get("turns_used") or 0)
        cost = float(job.get("cost_usd") or 0)
        last_pause_input = None
        last_pause_op = None
        # Walk events: the most recent approval_pause defines the next-resume
        # allowlist entry, unless followed by an approval_resume already
        # consumed in a previous resume attempt.
        for ev in events:
            t = ev.get("event_type")
            ed = ev.get("event_data") or {}
            if isinstance(ed, str):
                try:
                    ed = json.loads(ed)
                except Exception:
                    ed = {}
            if t == "approval_pause":
                last_pause_input = ed.get("tool_input")
                last_pause_op = ed.get("operation") or ed.get("tool")
            elif t == "approval_resume":
                # Resume consumed; clear pending allowance.
                last_pause_input = None
                last_pause_op = None
        prompt = job.get("prompt") or ""
        policy = policy or JobPolicy()
        worker = cls(
            job_id=job_id,
            prompt=prompt,
            policy=policy,
            workspace=workspace,
            db_url=db_url,
            dry_run=dry_run,
            resume_state={
                "turns_used": turns,
                "cost_usd": cost,
                "allow_once": {
                    "operation": last_pause_op,
                    "tool_input": last_pause_input,
                } if last_pause_op else None,
            },
        )
        return worker

    def _append_event(
        self, event_type: str, turn_number: int, *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
        event_data: dict | None = None,
    ) -> None:
        if not self.db_url:
            return
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
            import db as _db
            _db.append_job_event(
                self.job_id, event_type, turn_number=turn_number,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cost_usd=cost_usd, event_data=event_data or {},
            )
        except Exception:
            pass

    def _update_status(
        self, status: str, *, error: str | None = None, budget: BudgetTracker | None = None
    ) -> None:
        if not self.db_url:
            return
        try:
            import datetime
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
            import db as _db
            _db.update_job(
                self.job_id, status=status, error=error,
                turns_used=budget.turns if budget else None,
                cost_usd=budget.cost_usd if budget else None,
                finished_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception:
            pass
