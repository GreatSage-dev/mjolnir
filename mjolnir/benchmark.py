"""5-Arm Experimental Benchmark Runner for MJOLNIR.

Runs all benchmark tasks across the 5 experimental arms:
1. `nano_alone`          : NVIDIA Nemotron-3-Nano (Bare)
2. `ultra_alone`         : NVIDIA Nemotron-3-Ultra (Bare, no live web docs)
3. `nano_tavily`         : NVIDIA Nemotron-3-Nano + Tavily Live Docs
4. `ultra_tavily_always` : NVIDIA Nemotron-3-Ultra + Always-On Indiscriminate Tavily
5. `mjolnir_2d_ladder`   : MJOLNIR Selective 2D Escalation Engine (Nano -> Tavily / Super -> Ultra)
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from mjolnir.router import execute_strategy_on_task
from mjolnir.tasks import BENCHMARK_TASKS


EXPERIMENTAL_ARMS = [
    {
        "id": "nano_alone",
        "label": "Nemotron-Nano (Bare)",
        "description": "Fast & cheap 1-shot attempt without live docs or escalation.",
    },
    {
        "id": "ultra_alone",
        "label": "Nemotron-Ultra (Bare)",
        "description": "Always calls largest frontier model without live Tavily docs.",
    },
    {
        "id": "nano_tavily",
        "label": "Nemotron-Nano + Tavily",
        "description": "Small model paired with 3-stage Tavily documentation retrieval.",
    },
    {
        "id": "ultra_tavily_always",
        "label": "Nemotron-Ultra + Always-On Tavily",
        "description": "Largest model + indiscriminate web search on every task.",
    },
    {
        "id": "mjolnir_2d_ladder",
        "label": "MJOLNIR 2D Escalation Engine",
        "description": "Selective Error-Triggered Tavily + Tiered Nemotron (Nano -> Super -> Ultra).",
    },
]


def run_five_arm_suite(
    nebius_api_key: Optional[str] = None,
    tavily_api_key: Optional[str] = None,
    update_latest: bool = True,
) -> dict:
    """Execute all tasks across all 5 experimental arms and compute summary metrics."""
    t0 = time.perf_counter()
    arm_summaries = []
    task_matrix: dict[str, dict[str, dict]] = {t["id"]: {} for t in BENCHMARK_TASKS}
    is_live = bool(
        nebius_api_key
        or tavily_api_key
        or os.environ.get("NEBIUS_API_KEY")
        or os.environ.get("NVIDIA_API_KEY")
        or os.environ.get("TAVILY_API_KEY")
    )

    for arm in EXPERIMENTAL_ARMS:
        strat_id = arm["id"]
        solved_count = 0
        api_solved = 0
        api_total = 0
        logic_solved = 0
        logic_total = 0
        total_cost = 0.0
        total_latency = 0.0
        total_tokens = 0
        tavily_calls = 0
        receipts = []

        def _exec_one(t_item: dict):
            return t_item, execute_strategy_on_task(
                t_item,
                strategy=strat_id,
                nebius_api_key=nebius_api_key,
                tavily_api_key=tavily_api_key,
            )

        if is_live:
            with ThreadPoolExecutor(max_workers=2) as pool:
                ordered_pairs = list(pool.map(_exec_one, BENCHMARK_TASKS))
        else:
            ordered_pairs = [_exec_one(t) for t in BENCHMARK_TASKS]

        for task, rec in ordered_pairs:
            rec_dict = rec.to_dict()
            receipts.append(rec_dict)
            task_matrix[task["id"]][strat_id] = rec_dict

            if task["category"] == "api_shift":
                api_total += 1
                if rec.verified_solved:
                    api_solved += 1
            else:
                logic_total += 1
                if rec.verified_solved:
                    logic_solved += 1

            if rec.verified_solved:
                solved_count += 1
            total_cost += rec.total_cost_usd
            total_latency += rec.total_latency_ms
            total_tokens += rec.total_tokens
            if rec.tavily_triggered:
                tavily_calls += 1

        n_tasks = len(BENCHMARK_TASKS)
        solve_rate_pct = round((solved_count / n_tasks) * 100.0, 1) if n_tasks else 0.0
        cost_per_verified_fix = (
            round(total_cost / solved_count, 6) if solved_count > 0 else None
        )

        arm_summaries.append(
            {
                "strategy_id": strat_id,
                "label": arm["label"],
                "description": arm["description"],
                "total_tasks": n_tasks,
                "solved_count": solved_count,
                "solve_rate_pct": solve_rate_pct,
                "api_shift_solved": f"{api_solved}/{api_total}",
                "logic_solved": f"{logic_solved}/{logic_total}",
                "total_cost_usd": round(total_cost, 6),
                "cost_per_verified_fix_usd": cost_per_verified_fix,
                "avg_latency_ms": round(total_latency / n_tasks, 1) if n_tasks else 0.0,
                "total_tokens": total_tokens,
                "tavily_calls": tavily_calls,
                "receipts": receipts,
            }
        )

    # Calculate headline savings vs Ultra+Tavily Always-On and vs Ultra Alone
    mjolnir_arm = next(a for a in arm_summaries if a["strategy_id"] == "mjolnir_2d_ladder")
    ultra_always = next(a for a in arm_summaries if a["strategy_id"] == "ultra_tavily_always")
    ultra_bare = next(a for a in arm_summaries if a["strategy_id"] == "ultra_alone")

    savings_vs_always_pct = 0.0
    if (
        mjolnir_arm["cost_per_verified_fix_usd"]
        and ultra_always["cost_per_verified_fix_usd"]
    ):
        savings_vs_always_pct = round(
            (
                1.0
                - (
                    mjolnir_arm["cost_per_verified_fix_usd"]
                    / ultra_always["cost_per_verified_fix_usd"]
                )
            )
            * 100.0,
            1,
        )

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_clock_duration_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        "headline_metrics": {
            "mjolnir_solve_rate_pct": mjolnir_arm["solve_rate_pct"],
            "ultra_bare_solve_rate_pct": ultra_bare["solve_rate_pct"],
            "mjolnir_cost_per_fix_usd": mjolnir_arm["cost_per_verified_fix_usd"],
            "ultra_always_cost_per_fix_usd": ultra_always["cost_per_verified_fix_usd"],
            "cost_reduction_vs_ultra_always_pct": savings_vs_always_pct,
        },
        "arms": arm_summaries,
        "task_matrix": task_matrix,
    }

    out_dir = Path(__file__).resolve().parent.parent / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_path = out_dir / "latest_5arm_benchmark.json"
    det_backup = out_dir / "deterministic_5arm_benchmark.json"
    if is_live and latest_path.exists() and not det_backup.exists():
        det_backup.write_text(latest_path.read_text(encoding="utf-8"), encoding="utf-8")

    serialized = json.dumps(report, indent=2)
    if is_live:
        (out_dir / "live_5arm_telemetry.json").write_text(serialized, encoding="utf-8")
        if update_latest:
            latest_path.write_text(serialized, encoding="utf-8")
    else:
        latest_path.write_text(serialized, encoding="utf-8")
        det_backup.write_text(serialized, encoding="utf-8")
    return report
