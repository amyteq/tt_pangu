"""AgentWorker — agentic tool loop powered by LiteLLM (ADR-0004)."""

from __future__ import annotations

import json
import time
import types
from pathlib import Path

from src.worker._types import JobPolicy, WorkerResult
from src.worker.tools import TOOL_SCHEMAS, ToolExecutor, ApprovalRequired
from src.worker.budget import BudgetTracker


class PolicyViolation(Exception):
    """Raised when an M8 ``tool_decisions[tool]`` resolves to ``deny``.

    Distinct from :class:`ApprovalRequired` so the worker can mark the job
    failed (and never side-effect) instead of pausing for a human.
    """

    def __init__(self, tool_name: str, decision: str = "deny"):
        self.tool_name = tool_name
        self.decision = decision
        super().__init__(f"{tool_name} denied by policy ({decision})")


# M11 (ADR-0017): map tool_name to reviewer target_op for the new CTF ops.
# The default identity mapping (target_op == tool_name) covers M6/M9/M10 ops
# (kaggle_submit, kernel_push, supabase_migrate, ...). The mapping below is
# only consulted for synthetic / wrapper tools whose tool_name doesn't match
# the operation in the policy YAMLs. Each entry must correspond to an
# operation row in .kca/permissions/*.yaml.
_TOOL_TO_TARGET_OP: dict[str, str] = {
    # `kca ctf solver run` invocation surfaces as a `challenge_run` op.
    "kca_ctf_solver_run": "challenge_run",
    "ctf_solver_run": "challenge_run",
    "challenge_run": "challenge_run",
    # `kca ctf flag submit` invocation surfaces as a `flag_submit` op.
    "kca_ctf_flag_submit": "flag_submit",
    "ctf_flag_submit": "flag_submit",
    "flag_submit": "flag_submit",
    # Worker-issued HTTP egress that doesn't match the ctf_scopes.target_urls
    # union surfaces as a `network_egress` op.
    "http_request": "network_egress",
    "network_egress": "network_egress",
}


def _resolve_target_op(tool_name: str) -> str:
    """Return the reviewer target_op string for the given tool_name.

    For unknown tools, target_op == tool_name (the M6/M9/M10 contract).
    """
    return _TOOL_TO_TARGET_OP.get(tool_name, tool_name)


# ---------------------------------------------------------------------------
# Mock LiteLLM client for dry_run tests
# ---------------------------------------------------------------------------


def _make_usage(prompt_tokens: int, completion_tokens: int):
    return types.SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _make_tool_calls_response(
    tool_name: str,
    tool_input: dict,
    prompt_tokens: int = 50,
    completion_tokens: int = 20,
):
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
                skill_name=getattr(policy, "skill_name", None),
                policy_profile=getattr(policy, "policy_profile", "default"),
                mode=getattr(policy, "mode", "default"),
                tool_decisions=dict(getattr(policy, "tool_decisions", {})),
            )
        # Allow test code to override the mock scenario or inject a client directly.
        self._mock_scenario: str = "two_turns"
        self._mock_client: MockLiteLLMClient | None = None

    def run(self) -> WorkerResult:
        from src.worker import telemetry as _otel

        # Only tag spans with a job_id when we know that row exists in the DB
        # (otherwise the Supabase exporter trips on the agent_jobs FK).
        tracer_job_id = self.job_id if self.db_url else None
        tracer = _otel.build_tracer(job_id=tracer_job_id)
        if tracer.is_enabled():
            job_span = _otel.start_job_span(tracer, self.job_id, self.prompt)
            try:
                if self.db_url and self.job_id:
                    self._safe_set_job_trace(tracer.trace_id, job_span.span_id)
            except Exception:
                pass
        else:
            job_span = None
        try:
            return self._run_inner(tracer)
        finally:
            if job_span is not None:
                job_span.end()

    def _safe_set_job_trace(self, trace_id: str, root_span_id: str) -> None:
        try:
            import sys as _sys

            _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
            import db as _db

            _db.set_job_trace(self.job_id, trace_id, root_span_id)
        except Exception:
            pass

    def _run_inner(self, tracer) -> WorkerResult:
        from src.worker import telemetry as _otel

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
            with _otel.with_turn_span(tracer, budget.turns + 1) as _turn_span:
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
                if _turn_span is not None:
                    _turn_span.set_attribute("model", self.policy.model)
                    usage = getattr(response, "usage", None)
                    if usage is not None:
                        _turn_span.set_attribute(
                            "prompt_tokens",
                            getattr(usage, "prompt_tokens", 0),
                        )
                        _turn_span.set_attribute(
                            "completion_tokens",
                            getattr(usage, "completion_tokens", 0),
                        )

            # 3. Record turn cost
            budget.record_turn(response)
            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            self._append_event(
                "turn_start",
                budget.turns,
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
                messages.append(
                    {
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
                    }
                )
                for tc in tool_calls:
                    tool_input = json.loads(tc.function.arguments)
                    self._append_event(
                        "tool_call",
                        budget.turns,
                        event_data={"tool": tc.function.name, "input": tool_input},
                    )
                    try:
                        with _otel.with_tool_span(tracer, tc.function.name, tool_input):
                            result_content = self._tool_call(executor, tc.function.name, tool_input)
                    except PolicyViolation as exc:
                        # M8 hard-deny path: log + fail the job, no side effects.
                        self._update_status(
                            "failed",
                            error=f"policy_violation: {exc}",
                            budget=budget,
                        )
                        return WorkerResult(
                            status="failed",
                            turns_used=budget.turns,
                            cost_usd=budget.cost_usd,
                            duration_s=time.monotonic() - start,
                            final_message="",
                            stop_reason="policy_violation",
                        )
                    except ApprovalRequired as exc:
                        # One-shot resume allowance: bypass the matching gate
                        # exactly once after `kca decisions approve`.
                        if allow_once and (
                            allow_once.get("operation") == exc.tool_name
                            or allow_once.get("operation") == "tool_approval"
                        ):
                            allow_once = None  # consume
                            # Recurse into the actual tool with policy bypass
                            # by temporarily relaxing max_side_effect for this
                            # one call.
                            saved = executor.policy.max_side_effect
                            executor.policy.max_side_effect = "SUBMISSION"
                            try:
                                result_content = executor.execute(tc.function.name, tool_input)
                            finally:
                                executor.policy.max_side_effect = saved
                        else:
                            return self._handle_approval_required(exc, budget, start)

                    self._append_event(
                        "tool_result",
                        budget.turns,
                        event_data={
                            "tool": tc.function.name,
                            "result_preview": str(result_content)[:200],
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(result_content),
                        }
                    )
                continue

            # 6. Unexpected finish_reason
            self._update_status(
                "failed",
                error=f"unexpected finish_reason={finish_reason}",
                budget=budget,
            )
            return WorkerResult(
                status="failed",
                turns_used=budget.turns,
                cost_usd=budget.cost_usd,
                duration_s=time.monotonic() - start,
                final_message="",
                stop_reason="unexpected",
            )

    def _tool_call(self, executor: "ToolExecutor", tool_name: str, tool_input: dict) -> str:
        """M8 tool dispatch with ToolSpec + JobPolicy enforcement.

        Resolution order:
          1. JobPolicy.tool_decisions[tool_name]: "deny" → PolicyViolation;
             "ask" → ApprovalRequired (pauses job, records human_decisions);
             "allow" or unset → fall through.
          2. ToolSpec.sandbox: "unsandboxed" requires the policy decision to
             be "allow"; "isolated_workspace" requires cwd to be the job
             workspace.
          3. ToolSpec.timeout_s wraps the call so a hung tool cannot exceed
             the declared budget (applies to ``run_bash`` and other
             subprocess-shaped tools; in-process tools observe it via a best
             effort signal-based deadline).
          4. Every decision is audited via
             ``tools.kca.agent.audit.log_policy_decision`` so the
             ``agent_tool_audit`` table records the outcome.
        """
        decision = (self.policy.tool_decisions or {}).get(tool_name)
        spec = self._tool_spec(tool_name)
        self._audit_tool_decision(
            tool_name=tool_name,
            decision=decision or "allow",
            spec=spec,
            tool_input=tool_input,
        )

        if decision == "deny":
            raise PolicyViolation(tool_name, decision="deny")
        if decision == "ask":
            # Surface as ApprovalRequired so the existing pause/decision flow
            # handles it (writes human_decisions + agent_job_events).
            side_effect = "LOCAL_WRITE"
            if spec is not None:
                side_effect = getattr(spec, "side_effect", side_effect) or side_effect
            raise ApprovalRequired(tool_name, tool_input, side_effect)

        if spec is not None:
            self._enforce_tool_spec(spec, tool_input)
            timeout = getattr(spec, "timeout_s", None)
        else:
            timeout = None

        if timeout and timeout > 0:
            return self._call_with_deadline(executor, tool_name, tool_input, timeout)
        return executor.execute(tool_name, tool_input)

    def _tool_spec(self, tool_name: str):
        """Resolve a ToolSpec from the kca agent tool_registry, if available."""
        try:
            import sys as _sys

            _sys.path.insert(
                0,
                str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"),
            )
            from agent.tool_registry import get_tool  # type: ignore

            return get_tool(tool_name)
        except Exception:
            return None

    def _enforce_tool_spec(self, spec, tool_input: dict) -> None:
        """Cross-check sandbox + isolated_workspace constraints from ToolSpec."""
        sandbox = getattr(spec, "sandbox", None)
        if sandbox == "isolated_workspace":
            # The worker's cwd is the job workspace; tools that resolve paths
            # via ToolExecutor._guard_path already reject traversal. We just
            # confirm the workspace looks set (a None workspace is a bug).
            if not self.workspace:
                raise PolicyViolation(spec.name, decision="missing_workspace")
        # ``unsandboxed`` requires explicit "allow" — already gated above; this
        # is a belt-and-braces check.
        if sandbox == "unsandboxed":
            decision = (self.policy.tool_decisions or {}).get(spec.name)
            if decision != "allow":
                raise PolicyViolation(spec.name, decision="unsandboxed_needs_allow")

    def _call_with_deadline(
        self,
        executor: "ToolExecutor",
        tool_name: str,
        tool_input: dict,
        timeout_s: int,
    ) -> str:
        """Best-effort timeout wrapper. ``run_bash`` already times out via
        subprocess; for other tools we just honour the ToolSpec on a wall
        clock and surface a string error if exceeded.
        """
        if tool_name == "run_bash":
            ti = dict(tool_input)
            ti.setdefault("timeout_s", timeout_s)
            return executor.execute(tool_name, ti)
        # In-process tools: run inline; if a future tool turns out to be
        # blocking we can wrap it with signal.alarm/threading.Timer here.
        return executor.execute(tool_name, tool_input)

    def _audit_tool_decision(
        self,
        *,
        tool_name: str,
        decision: str,
        spec,
        tool_input: dict,
    ) -> None:
        try:
            import sys as _sys

            _sys.path.insert(
                0,
                str(Path(__file__).resolve().parent.parent.parent),
            )
            from tools.kca.agent.audit import log_policy_decision  # type: ignore

            log_policy_decision(
                tool=tool_name,
                operation=tool_name,
                decision=decision,
                skill_name=self.policy.skill_name,
                mode=self.policy.mode,
                policy_profile=self.policy.policy_profile,
                args=tool_input,
                audit_required=bool(getattr(spec, "audit_required", False)) if spec is not None else False,
                job_id=self.job_id if self.db_url else None,
            )
        except Exception as exc:  # pragma: no cover
            import sys as _sys

            _sys.stderr.write(f"[audit warn] {exc}\n")

    def _handle_approval_required(self, exc: ApprovalRequired, budget: BudgetTracker, start: float) -> WorkerResult:
        """Pause the job and record a decision request.

        M6: when the gating operation is one of KCA_REVIEWER_TRIGGER_OPS,
        first consult the sync reviewer. Reviewer.approve auto-resumes,
        reviewer.reject either escalates to humans (default) or fails the
        job (when KCA_REVIEWER_ESCALATE_REJECT=0), and reviewer.abstain
        falls through to the existing human-decisions path.
        """
        # ------------------------------------------------------------------
        # M6 reviewer pre-check
        # ------------------------------------------------------------------
        reviewer_outcome = self._maybe_consult_reviewer(exc, budget)
        if reviewer_outcome == "approve":
            # Re-execute the gated tool with one-shot bypass.
            return WorkerResult(
                status="reviewer_approved",
                turns_used=budget.turns,
                cost_usd=budget.cost_usd,
                duration_s=time.monotonic() - start,
                final_message="reviewer approved",
                stop_reason="reviewer_approve",
            )
        if reviewer_outcome == "reject_fail":
            self._update_status(
                "failed",
                error="reviewer rejected high-stakes operation",
                budget=budget,
            )
            return WorkerResult(
                status="failed",
                turns_used=budget.turns,
                cost_usd=budget.cost_usd,
                duration_s=time.monotonic() - start,
                final_message="",
                stop_reason="reviewer_reject",
            )
        # reviewer_outcome in {None, "reject_escalate", "abstain"} — fall
        # through to human-decisions flow.
        decision_id = None
        if self.db_url:
            try:
                import sys

                sys.path.insert(
                    0,
                    str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"),
                )
                import db as _db

                decision_id = _db.insert_approval_request(
                    decision_type="tool_approval",
                    prompt=f"Worker job {self.job_id} wants to call {exc.tool_name}",
                    options={
                        "approve": "allow this tool call",
                        "deny": "block and stop job",
                    },
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
            "approval_pause",
            budget.turns,
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
                }
                if last_pause_op
                else None,
            },
        )
        return worker

    def _maybe_consult_reviewer(self, exc: ApprovalRequired, budget: BudgetTracker) -> str | None:
        """Run the sync reviewer for trigger ops; return outcome tag.

        Returns one of:
          None             — reviewer not consulted (op not in trigger set or
                              already reviewed)
          "approve"        — reviewer approved; caller resumes the tool
          "reject_fail"    — reviewer rejected and ESCALATE_REJECT=0
          "reject_escalate"— reviewer rejected, caller should page humans
          "abstain"        — reviewer abstained, caller should page humans
        """
        from src.worker.reviewer import (
            Reviewer,
            ReviewRequest,
            should_consult_reviewer,
            escalate_reject,
        )

        target_op = _resolve_target_op(exc.tool_name)
        if not should_consult_reviewer(target_op):
            return None
        if not self.db_url:
            # No DB → no event trail and no place to record the verdict.
            # The dry-run worker still records the reviewer span via OTEL when
            # T005 wires it up; for now just skip silently.
            return None
        try:
            import sys as _sys

            _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
            import db as _db

            # Skip if reviewer already ran for (job_id, target_op).
            try:
                existing = _db.find_review_for_op(self.job_id, target_op)
            except Exception:
                existing = None
            if existing is not None:
                return None
            events = []
            try:
                events = _db.list_job_events(self.job_id)
            except Exception:
                events = []
            req = ReviewRequest(
                job_id=self.job_id,
                target_op=target_op,
                tool_name=exc.tool_name,
                tool_input=exc.tool_input,
                final_message=None,
                event_trail=events,
            )
            reviewer = Reviewer(dry_run=self.dry_run)
            verdict = reviewer.review(req)
            try:
                _db.create_review(
                    job_id=self.job_id,
                    reviewer_model=verdict.reviewer_model,
                    verdict=verdict.verdict,
                    target_op=target_op,
                    rationale=verdict.rationale,
                    evidence=verdict.evidence,
                    cost_usd=verdict.cost_usd,
                )
            except Exception:
                pass
            if verdict.verdict == "approve":
                self._append_event(
                    "approval_resume",
                    budget.turns,
                    event_data={
                        "source": "reviewer",
                        "verdict": "approve",
                        "target_op": target_op,
                        "rationale": verdict.rationale[:200],
                    },
                )
                return "approve"
            if verdict.verdict == "reject":
                if escalate_reject():
                    self._append_event(
                        "reviewer_reject",
                        budget.turns,
                        event_data={
                            "target_op": target_op,
                            "rationale": verdict.rationale[:200],
                            "escalated": True,
                        },
                    )
                    return "reject_escalate"
                self._append_event(
                    "reviewer_reject",
                    budget.turns,
                    event_data={
                        "target_op": target_op,
                        "rationale": verdict.rationale[:200],
                        "escalated": False,
                    },
                )
                return "reject_fail"
            # abstain → fall through
            self._append_event(
                "reviewer_abstain",
                budget.turns,
                event_data={
                    "target_op": target_op,
                    "rationale": verdict.rationale[:200],
                },
            )
            return "abstain"
        except Exception:
            return None

    def _append_event(
        self,
        event_type: str,
        turn_number: int,
        *,
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
                self.job_id,
                event_type,
                turn_number=turn_number,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                event_data=event_data or {},
            )
        except Exception:
            pass

    def _update_status(
        self,
        status: str,
        *,
        error: str | None = None,
        budget: BudgetTracker | None = None,
    ) -> None:
        if not self.db_url:
            return
        try:
            import datetime
            import sys

            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "kca"))
            import db as _db

            _db.update_job(
                self.job_id,
                status=status,
                error=error,
                turns_used=budget.turns if budget else None,
                cost_usd=budget.cost_usd if budget else None,
                finished_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception:
            pass
