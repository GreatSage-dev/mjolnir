"""2D Escalation Router & Multi-Arm Experimental Runner for MJOLNIR.

Implements:
1. `mjolnir_2d_ladder`:
   - Step 0: Run broken code in locked sandbox to capture the initial 3-line error receipt.
   - Rung 1: Try `Nemotron-3-Nano` (fast, ultra-low cost) if error is a local reasoning/syntax bug;
             OR if initial sandbox error is ALREADY a confirmed `KNOWLEDGE_GAP` (`AttributeError`,
             `ImportError`, `TypeError` on external SDK), test `Nano` bare once to prove whether
             parametric memory knows it, and on failure immediately route to `Tavily`!
   - Rung 2:
     * If `DIAGNOSIS == KNOWLEDGE_GAP` -> Trigger 3-Stage Tavily (`Search -> Extract -> Map`)
       and run `Nemotron-3-Nano + Tavily`!
     * If `DIAGNOSIS == REASONING_GAP` -> Escalate to `Nemotron-3-Super` (without polluting
       context with unneeded web search!).
   - Rung 3: If still failing, escalate to `Nemotron-3-Ultra` (with Tavily docs if Knowledge Gap,
             or clean context if Reasoning Gap).

2. Four comparison baselines (`nano_alone`, `ultra_alone`, `nano_tavily`, `ultra_tavily_always`)
   so judges can verify the exact solve-rate and cost-per-verified-fix across all 5 setups.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from mjolnir.nebius_client import NebiusCallReceipt, NebiusTokenFactoryClient
from mjolnir.sandbox import (
    KNOWLEDGE_GAP,
     SandboxReceipt,
    run_in_locked_sandbox,
)
from mjolnir.tavily_grounding import TavilyReceipt, retrieve_live_documentation


@dataclass
class StepTrace:
    """Single step executed along the resolution trajectory."""

    step_index: int
    stage_label: str
    tier: str
    used_tavily: bool
    nebius_call: NebiusCallReceipt
    tavily_call: Optional[TavilyReceipt]
    sandbox_receipt: SandboxReceipt

    def to_dict(self) -> dict:
        return {
            "step_index": self.step_index,
            "stage_label": self.stage_label,
            "tier": self.tier,
            "used_tavily": self.used_tavily,
            "nebius_call": self.nebius_call.to_dict(),
            "tavily_call": self.tavily_call.to_dict() if self.tavily_call else None,
            "sandbox_receipt": self.sandbox_receipt.to_dict(),
        }


@dataclass
class ExecutionReceipt:
    """Complete verifiable receipt for a task run under a chosen strategy."""

    task_id: str
    task_title: str
    task_category: str
    strategy: str
    verified_solved: bool
    final_exit_code: int
    total_cost_usd: float
    total_latency_ms: float
    total_tokens: int
    tavily_triggered: bool
    escalation_path: list[str]
    initial_error_receipt: dict
    final_unified_diff: str
    final_patch_sha256: str
    test_sha256: str
    steps: list[StepTrace] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["steps"] = [s.to_dict() for s in self.steps]
        return data


def execute_strategy_on_task(
    task: dict,
    strategy: str = "mjolnir_2d_ladder",
    nebius_api_key: Optional[str] = None,
    tavily_api_key: Optional[str] = None,
) -> ExecutionReceipt:
    """Run a single coding task through the specified strategy and return a deterministic receipt."""
    nebius = NebiusTokenFactoryClient(api_key=nebius_api_key)
    broken_code = task["broken_code"]
    test_code = task["test_code"]
    extra_files = task.get("extra_files") or {}
    tavily_doc = task.get("tavily_doc") or {}

    # Step 0: Run initial broken code in locked sandbox to extract the ground-truth error receipt
    initial_sbx = run_in_locked_sandbox(
        original_code=broken_code,
        candidate_code=broken_code,
        test_code=test_code,
        extra_files=extra_files,
    )
    initial_err_str = (
        initial_sbx.error_receipt.distilled_3_lines
        if initial_sbx.error_receipt
        else "No initial failure"
    )
    initial_diag = (
        initial_sbx.error_receipt.diagnostic_category
        if initial_sbx.error_receipt
        else "REASONING_GAP"
    )

    steps: list[StepTrace] = []
    escalation_path: list[str] = []
    total_cost = 0.0
    total_latency = initial_sbx.duration_ms
    total_tokens = 0
    tavily_triggered = False

    def _run_attempt(
        step_idx: int,
        stage_label: str,
        tier: str,
        use_tavily: bool,
        current_err_text: str,
    ) -> StepTrace:
        nonlocal total_cost, total_latency, total_tokens, tavily_triggered

        tav_receipt: Optional[TavilyReceipt] = None
        tav_md: Optional[str] = None
        if use_tavily:
            tavily_triggered = True
            tav_receipt = retrieve_live_documentation(
                query=tavily_doc.get("query", f"{task['title']} {current_err_text}"),
                target_domains=tavily_doc.get("domains", []),
                fallback_doc_entry=tavily_doc,
                api_key=tavily_api_key,
            )
            tav_md = tav_receipt.extracted_markdown
            total_cost += tav_receipt.estimated_cost_usd
            total_latency += tav_receipt.latency_ms

        candidate_code, neb_receipt = nebius.generate_patch(
            tier=tier,
            task_Info=task,
            broken_code=broken_code,
            error_distillation=current_err_text,
            tavily_markdown=tav_md,
        )
        total_cost += neb_receipt.cost_usd
        total_latency += neb_receipt.latency_ms
        total_tokens += neb_receipt.total_tokens

        sbx = run_in_locked_sandbox(
            original_code=broken_code,
            candidate_code=candidate_code,
            test_code=test_code,
            extra_files=extra_files,
        )
        total_latency += sbx.duration_ms
        escalation_path.append(stage_label)

        trace = StepTrace(
            step_index=step_idx,
            stage_label=stage_label,
            tier=tier,
            used_tavily=use_tavily,
            nebius_call=neb_receipt,
            tavily_call=tav_receipt,
            sandbox_receipt=sbx,
        )
        steps.append(trace)
        return trace

    # -------------------------------------------------------------------------
    # Step 0 Fast-Exit: If candidate code ALREADY passes the locked test suite,
    # return a zero-cost verified receipt instead of paying an LLM to rewrite it.
    # -------------------------------------------------------------------------
    if strategy not in {
        "nano_alone",
        "ultra_alone",
        "nano_tavily",
        "ultra_tavily_always",
        "mjolnir_2d_ladder",
    }:
        raise ValueError(f"Unknown strategy: {strategy}")

    if initial_sbx.passed:
        precheck_label = "Step 0: Sandbox Pre-Check (Already Passing)"
        precheck_trace = StepTrace(
            step_index=0,
            stage_label=precheck_label,
            tier="sandbox",
            used_tavily=False,
            nebius_call=NebiusCallReceipt(
                tier="sandbox",
                model_id="locked-sandbox-verifier",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0.0,
                cost_usd=0.0,
                mode="sandbox_precheck",
                raw_prompt_preview="Initial candidate already satisfied all locked unit tests.",
            ),
            tavily_call=None,
            sandbox_receipt=initial_sbx,
        )
        return ExecutionReceipt(
            task_id=task["id"],
            task_title=task["title"],
            task_category=task["category"],
            strategy=strategy,
            verified_solved=True,
            final_exit_code=0,
            total_cost_usd=0.0,
            total_latency_ms=round(total_latency, 2),
            total_tokens=0,
            tavily_triggered=False,
            escalation_path=[precheck_label],
            initial_error_receipt={},
            final_unified_diff=initial_sbx.unified_diff,
            final_patch_sha256=initial_sbx.patch_sha256,
            test_sha256=initial_sbx.test_sha256,
            steps=[precheck_trace],
        )

    # -------------------------------------------------------------------------
    # Dispatch by Strategy
    # -------------------------------------------------------------------------
    if strategy == "nano_alone":
        _run_attempt(1, "Nemotron-Nano (Bare)", "nano", False, initial_err_str)

    elif strategy == "ultra_alone":
        _run_attempt(1, "Nemotron-Ultra (Bare)", "ultra", False, initial_err_str)

    elif strategy == "nano_tavily":
        _run_attempt(1, "Nemotron-Nano + Tavily", "nano", True, initial_err_str)

    elif strategy == "ultra_tavily_always":
        _run_attempt(1, "Nemotron-Ultra + Always-On Tavily", "ultra", True, initial_err_str)

    elif strategy == "mjolnir_2d_ladder":
        # Rung 1: 1-shot attempt with Nemotron-3-Nano ($0.0001 fast check)
        rung1 = _run_attempt(1, "Rung 1: Nemotron-Nano (1-Shot Probe)", "nano", False, initial_err_str)

        if not rung1.sandbox_receipt.passed:
            # Inspect the 3-line error receipt from Rung 1
            err_rec = rung1.sandbox_receipt.error_receipt
            diag = err_rec.diagnostic_category if err_rec else initial_diag
            err_str = err_rec.distilled_3_lines if err_rec else initial_err_str

            if diag == KNOWLEDGE_GAP:
                # Knowledge Gap detected (AttributeError / ImportError / API signature change):
                # Escalate along the TAVILY axis first with cheap Nemotron-Nano!
                rung2 = _run_attempt(
                    2,
                    "Rung 2 (Knowledge Axis): Nemotron-Nano + Tavily 3-Stage Docs",
                    "nano",
                    True,
                    err_str,
                )
                if not rung2.sandbox_receipt.passed:
                    # Both API change AND multi-step type coercion/reasoning required -> Super + Tavily
                    err_str2 = (
                        rung2.sandbox_receipt.error_receipt.distilled_3_lines
                        if rung2.sandbox_receipt.error_receipt
                        else err_str
                    )
                    rung3 = _run_attempt(
                        3,
                        "Rung 3 (Combined Axis): Nemotron-Super + Tavily Docs",
                        "super",
                        True,
                        err_str2,
                    )
                    if not rung3.sandbox_receipt.passed:
                        err_str3 = (
                            rung3.sandbox_receipt.error_receipt.distilled_3_lines
                            if rung3.sandbox_receipt.error_receipt
                            else err_str2
                        )
                        _run_attempt(
                            4,
                            "Rung 4 (Frontier Grounded): Nemotron-Ultra + Tavily Docs",
                            "ultra",
                            True,
                            err_str3,
                        )
            else:
                # Pure Reasoning Gap detected (AssertionError / algorithmic invariant):
                # Do NOT call Tavily (avoids search cost & context noise); escalate to Super!
                rung2 = _run_attempt(
                    2,
                    "Rung 2 (Reasoning Axis): Nemotron-Super (Clean Context)",
                    "super",
                    False,
                    err_str,
                )
                if not rung2.sandbox_receipt.passed:
                    err_str2 = (
                        rung2.sandbox_receipt.error_receipt.distilled_3_lines
                        if rung2.sandbox_receipt.error_receipt
                        else err_str
                    )
                    _run_attempt(
                        3,
                        "Rung 3 (Deep Reasoning): Nemotron-Ultra",
                        "ultra",
                        False,
                        err_str2,
                    )

    final_step = steps[-1]
    final_sbx = final_step.sandbox_receipt

    return ExecutionReceipt(
        task_id=task["id"],
        task_title=task["title"],
        task_category=task["category"],
        strategy=strategy,
        verified_solved=final_sbx.passed,
        final_exit_code=final_sbx.exit_code,
        total_cost_usd=round(total_cost, 6),
        total_latency_ms=round(total_latency, 2),
        total_tokens=total_tokens,
        tavily_triggered=tavily_triggered,
        escalation_path=escalation_path,
        initial_error_receipt=(
            initial_sbx.error_receipt.to_dict() if initial_sbx.error_receipt else {}
        ),
        final_unified_diff=final_sbx.unified_diff,
        final_patch_sha256=final_sbx.patch_sha256,
        test_sha256=final_sbx.test_sha256,
        steps=steps,
    )
