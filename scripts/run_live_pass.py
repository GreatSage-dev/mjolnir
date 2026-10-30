"""Run a full 5-Arm x 10-Task Live Telemetry Pass against NVIDIA Nemotron & Tavily.

Loads `NEBIUS_API_KEY` (or `NVIDIA_API_KEY`) and `TAVILY_API_KEY` from `.env` or
environment variables, executes all 5 experimental arms across all 10 locked-test
sandbox tasks, preserves `artifacts/deterministic_5arm_benchmark.json`, and saves
the complete live API telemetry receipts to `artifacts/live_5arm_telemetry.json`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mjolnir import load_dotenv_file
from mjolnir.benchmark import run_five_arm_suite


def main() -> int:
    load_dotenv_file()
    report = run_five_arm_suite(update_latest=False)
    print(f"Generated At       : {report['generated_at']}")
    print(f"Wall Clock Duration: {report['wall_clock_duration_ms']} ms")
    print(f"Headline Metrics   : {report['headline_metrics']}")
    print("-" * 108)
    for arm in report["arms"]:
        neb_modes = sorted(
            {s["nebius_call"]["mode"] for rec in arm["receipts"] for s in rec["steps"]}
        )
        tav_modes = sorted(
            {
                s["tavily_call"]["source_mode"]
                for rec in arm["receipts"]
                for s in rec["steps"]
                if s["tavily_call"]
            }
        )
        print(
            f"{arm['strategy_id']:22s} | solved={arm['solved_count']:2d}/10 "
            f"({arm['solve_rate_pct']:5.1f}%) | api={arm['api_shift_solved']} "
            f"| logic={arm['logic_solved']} | cost/fix=${arm['cost_per_verified_fix_usd'] or 0:.6f} "
            f"| avg={arm['avg_latency_ms']:7.1f}ms | neb={neb_modes} | tav={tav_modes}"
        )
    print("-" * 108)
    print(f"Saved live telemetry receipt -> {ROOT_DIR / 'artifacts' / 'live_5arm_telemetry.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
