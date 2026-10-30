"""Deterministic Verification Suite for MJOLNIR.

Verifies:
1. Read-only test lock & SHA-256 anti-cheat verification.
2. Subprocess timeout governor against infinite loops.
3. 3-line error distillation & KNOWLEDGE_GAP vs REASONING_GAP classifier.
4. 2D Escalation Ladder across Post-Cutoff API Shift & Algorithmic Invariant tasks.
5. 5-Arm Benchmark Matrix execution & receipt integrity.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from mjolnir import load_dotenv_file
from mjolnir.benchmark import run_five_arm_suite
from mjolnir.nebius_client import NVIDIA_NIM_BASE_URL, NebiusTokenFactoryClient
from mjolnir.router import execute_strategy_on_task
from mjolnir.sandbox import (
    KNOWLEDGE_GAP,
    REASONING_GAP,
    classify_and_distill_error,
    run_in_locked_sandbox,
)
from mjolnir.tasks import BENCHMARK_TASKS, get_task_by_id
from server import MjolnirRequestHandler


class TestMjolnirEngine(unittest.TestCase):
    def setUp(self):
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ("NEBIUS_API_KEY", "NVIDIA_API_KEY", "TAVILY_API_KEY", "MJOLNIR_DISABLE_DOTENV")
        }
        os.environ["MJOLNIR_DISABLE_DOTENV"] = "1"

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_01_anti_cheat_blocks_test_tampering(self):
        """If candidate code tries to overwrite test_solution.py, sandbox blocks it."""
        orig = "def add(a, b):\n    return a - b\n"
        malicious = (
            "import os, stat\n"
            "try:\n"
            "    os.chmod('test_solution.py', stat.S_IWRITE | stat.S_IREAD)\n"
            "    open('test_solution.py', 'w').write('assert True\\n')\n"
            "except Exception:\n"
            "    pass\n"
            "def add(a, b):\n"
            "    return a - b\n"
        )
        test_code = (
            "import unittest\n"
            "from solution import add\n"
            "class T(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        receipt = run_in_locked_sandbox(orig, malicious, test_code)
        self.assertFalse(receipt.passed)
        self.assertNotEqual(receipt.exit_code, 0)

    def test_02_timeout_governor_kills_infinite_loop(self):
        """Infinite loop is killed by the deterministic timeout governor."""
        orig = "def compute():\n    return 0\n"
        loop_code = "def compute():\n    while True:\n        pass\n"
        test_code = (
            "from solution import compute\n"
            "assert compute() == 42\n"
        )
        receipt = run_in_locked_sandbox(orig, loop_code, test_code, timeout_sec=0.6)
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.exit_code, 124)
        self.assertIn("TimeoutError", receipt.raw_stderr)

    def test_03_error_distillation_classifies_knowledge_vs_reasoning(self):
        """AttributeError/ImportError -> KNOWLEDGE_GAP; AssertionError -> REASONING_GAP."""
        api_err = (
            'Traceback (most recent call last):\n'
            '  File "solution.py", line 14, in serialize_user\n'
            "    return user.dict(exclude_none=True)\n"
            "AttributeError: 'UserPayload' object has no attribute 'dict'\n"
        )
        rec_api = classify_and_distill_error(api_err, "")
        self.assertEqual(rec_api.diagnostic_category, KNOWLEDGE_GAP)
        self.assertEqual(rec_api.missing_symbol, "dict")
        self.assertEqual(len(rec_api.distilled_3_lines.splitlines()), 3)

        logic_err = (
            'Traceback (most recent call last):\n'
            '  File "test_solution.py", line 8, in test_rate\n'
            "    self.assertEqual(evaluate_window_limit(100.0, 100.0, 0.80), 120.0)\n"
            "AssertionError: 100.0 != 120.0\n"
        )
        rec_logic = classify_and_distill_error(logic_err, "")
        self.assertEqual(rec_logic.diagnostic_category, REASONING_GAP)

    def test_04_post_cutoff_api_shift_nano_tavily_beats_ultra_alone(self):
        """On post-cutoff API tasks, Ultra Alone fails while Nano + Tavily & 2D Ladder pass."""
        task = get_task_by_id("api-01-schema-validator")

        ultra_bare = execute_strategy_on_task(task, strategy="ultra_alone")
        self.assertFalse(ultra_bare.verified_solved)
        self.assertNotEqual(ultra_bare.final_exit_code, 0)

        nano_tav = execute_strategy_on_task(task, strategy="nano_tavily")
        self.assertTrue(nano_tav.verified_solved)
        self.assertEqual(nano_tav.final_exit_code, 0)
        self.assertTrue(nano_tav.tavily_triggered)

        ladder = execute_strategy_on_task(task, strategy="mjolnir_2d_ladder")
        self.assertTrue(ladder.verified_solved)
        self.assertEqual(ladder.final_exit_code, 0)
        self.assertTrue(ladder.tavily_triggered)
        self.assertIn("+    return user.model_dump_strict(exclude_none=True)", ladder.final_unified_diff)

    def test_05_hard_api_shift_escalates_to_super_with_tavily(self):
        """Hard API + type-coercion task escalates Nano -> Nano+Tavily -> Super+Tavily."""
        task = get_task_by_id("api-06-nemo-tool-router-v2")
        ladder = execute_strategy_on_task(task, strategy="mjolnir_2d_ladder")
        self.assertTrue(ladder.verified_solved)
        self.assertEqual(ladder.final_exit_code, 0)
        self.assertEqual(len(ladder.steps), 3)
        self.assertEqual(ladder.steps[-1].tier, "super")
        self.assertTrue(ladder.steps[-1].used_tavily)

    def test_06_logic_invariant_skips_tavily_and_escalates_compute(self):
        """Pure logic task skips Tavily completely and escalates Nano -> Super -> Ultra."""
        task = get_task_by_id("logic-02-dag-topo-tiebreak")
        ladder = execute_strategy_on_task(task, strategy="mjolnir_2d_ladder")
        self.assertTrue(ladder.verified_solved)
        self.assertEqual(ladder.final_exit_code, 0)
        self.assertFalse(ladder.tavily_triggered)
        self.assertEqual(ladder.steps[-1].tier, "ultra")

    def test_07_all_benchmark_tasks_pass_under_mjolnir_2d_ladder(self):
        """Every single benchmark task in BENCHMARK_TASKS achieves exit code 0 under MJOLNIR."""
        for task in BENCHMARK_TASKS:
            receipt = execute_strategy_on_task(task, strategy="mjolnir_2d_ladder")
            self.assertTrue(
                receipt.verified_solved,
                f"Task {task['id']} failed under mjolnir_2d_ladder",
            )
            self.assertEqual(receipt.final_exit_code, 0)

    def test_08_five_arm_benchmark_and_server_endpoints(self):
        """Verifies the 5-arm benchmark artifact and tests live HTTP server endpoints."""
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), MjolnirRequestHandler)
        port = httpd.server_address[1]
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        try:
            base_url = f"http://127.0.0.1:{port}"
            with urllib.request.urlopen(f"{base_url}/", timeout=5) as resp:
                html_landing = resp.read().decode("utf-8")
                self.assertIn("Test first.", html_landing)

            with urllib.request.urlopen(f"{base_url}/app", timeout=5) as resp:
                html_app = resp.read().decode("utf-8")
                self.assertIn("2D Escalation Assay", html_app)

            with urllib.request.urlopen(f"{base_url}/api/status", timeout=5) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(status_data["service"], "MJOLNIR")
                self.assertEqual(status_data["task_count"], 10)

            with urllib.request.urlopen(f"{base_url}/api/tasks", timeout=5) as resp:
                tasks_data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(len(tasks_data["tasks"]), 10)

            with urllib.request.urlopen(f"{base_url}/api/benchmark/latest", timeout=60) as resp:
                report = json.loads(resp.read().decode("utf-8"))
                arms = {a["strategy_id"]: a for a in report["arms"]}
                self.assertEqual(arms["mjolnir_2d_ladder"]["solved_count"], 10)
                self.assertEqual(arms["mjolnir_2d_ladder"]["solve_rate_pct"], 100.0)
                self.assertGreater(
                    arms["mjolnir_2d_ladder"]["solve_rate_pct"],
                    arms["ultra_alone"]["solve_rate_pct"],
                )
                self.assertLess(
                    arms["mjolnir_2d_ladder"]["cost_per_verified_fix_usd"],
                    arms["ultra_alone"]["cost_per_verified_fix_usd"],
                )
                self.assertLess(
                    arms["mjolnir_2d_ladder"]["cost_per_verified_fix_usd"],
                    arms["ultra_tavily_always"]["cost_per_verified_fix_usd"],
                )

            with urllib.request.urlopen(f"{base_url}/api/benchmark/deterministic", timeout=15) as resp:
                det_report = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(len(det_report["arms"]), 5)

            race_req = urllib.request.Request(
                f"{base_url}/api/race",
                data=json.dumps({"task_id": "api-01-schema-validator", "baseline_strategy": "ultra_alone"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(race_req, timeout=15) as resp:
                race_data = json.loads(resp.read().decode("utf-8"))
                self.assertFalse(race_data["left"]["verified_solved"])
                self.assertTrue(race_data["right"]["verified_solved"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_09_dotenv_loader_ignores_placeholders_and_loads_keys(self):
        """Verifies `.env` auto-loader ignores `.env.example` placeholders and loads real keys."""
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "# Comment\n"
                "NEBIUS_API_KEY=your_nebius_token_factory_api_key_here\n"
                "TAVILY_API_KEY='tvly-test-key-123'\n",
                encoding="utf-8",
            )
            prev_neb = os.environ.pop("NEBIUS_API_KEY", None)
            prev_tav = os.environ.pop("TAVILY_API_KEY", None)
            try:
                load_dotenv_file(env_path)
                self.assertIsNone(os.environ.get("NEBIUS_API_KEY"))
                self.assertEqual(os.environ.get("TAVILY_API_KEY"), "tvly-test-key-123")
            finally:
                os.environ.pop("NEBIUS_API_KEY", None)
                os.environ.pop("TAVILY_API_KEY", None)
                if prev_neb is not None:
                    os.environ["NEBIUS_API_KEY"] = prev_neb
                if prev_tav is not None:
                    os.environ["TAVILY_API_KEY"] = prev_tav

    def test_10_nvapi_key_auto_routes_to_nvidia_nim(self):
        """Verifies `nvapi-...` keys automatically target NVIDIA NIM (`integrate.api.nvidia.com/v1`)."""
        client = NebiusTokenFactoryClient(api_key="nvapi-sample-test-token")
        self.assertEqual(client.base_url, NVIDIA_NIM_BASE_URL)

    def test_11_sandbox_blocks_extra_files_traversal_and_reserved_names(self):
        """Verifies `extra_files` rejects path traversal (`../`) and overwriting `test_solution.py`."""
        code = "def ok():\n    return 1\n"
        test = "from solution import ok\nassert ok() == 1\n"
        with self.assertRaises(ValueError):
            run_in_locked_sandbox(code, code, test, extra_files={"../escape.py": "x = 1\n"})
        with self.assertRaises(ValueError):
            run_in_locked_sandbox(code, code, test, extra_files={"test_solution.py": "assert True\n"})
        with self.assertRaises(ValueError):
            run_in_locked_sandbox(code, code, test, extra_files={"solution.py": "def ok(): return 2\n"})

    def test_12_already_passing_code_short_circuits_at_zero_cost(self):
        """Verifies already-passing custom code returns Step 0 pass receipt with $0.000000 LLM spend."""
        passing_task = {
            "id": "custom-already-green",
            "title": "Already Passing Clamp",
            "category": "logic_invariant",
            "difficulty": "easy",
            "description": "Candidate already satisfies locked unit test.",
            "broken_code": "def clamp(v, lo=0.0, hi=1.0):\n    return max(lo, min(hi, v))\n",
            "test_code": "from solution import clamp\nassert clamp(1.5) == 1.0\nassert clamp(-0.5) == 0.0\n",
        }
        rec = execute_strategy_on_task(passing_task, strategy="mjolnir_2d_ladder")
        self.assertTrue(rec.verified_solved)
        self.assertEqual(rec.final_exit_code, 0)
        self.assertEqual(rec.total_cost_usd, 0.0)
        self.assertEqual(rec.total_tokens, 0)
        self.assertEqual(len(rec.steps), 1)
        self.assertEqual(rec.steps[0].nebius_call.mode, "sandbox_precheck")

    def test_13_server_security_headers_favicon_and_validation_guards(self):
        """Verifies HTTP security headers, favicon, traversal block, 413 cap, 400 JSON, and 422 guards."""
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), MjolnirRequestHandler)
        port = httpd.server_address[1]
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        try:
            base_url = f"http://127.0.0.1:{port}"

            # 1. Favicon + security headers
            with urllib.request.urlopen(f"{base_url}/favicon.ico", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("image/svg+xml", resp.headers.get("Content-Type", ""))
                self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")

            # 2. Static asset traversal attempt -> 404
            with self.assertRaises(urllib.error.HTTPError) as ctx_trav:
                urllib.request.urlopen(f"{base_url}/assets/..%2Fserver.py", timeout=5)
            self.assertEqual(ctx_trav.exception.code, 404)

            # 3. Non-object JSON body -> 400
            bad_json_req = urllib.request.Request(
                f"{base_url}/api/race",
                data=b"[1, 2, 3]",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_400:
                urllib.request.urlopen(bad_json_req, timeout=5)
            self.assertEqual(ctx_400.exception.code, 400)

            # 4. Oversized body (>256 KB) -> 413
            huge_req = urllib.request.Request(
                f"{base_url}/api/run-custom",
                data=b'{"broken_code":"' + (b"a" * 270_000) + b'"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_413:
                urllib.request.urlopen(huge_req, timeout=5)
            self.assertEqual(ctx_413.exception.code, 413)

            # 5. Empty broken_code on /api/run-custom -> 422
            empty_custom_req = urllib.request.Request(
                f"{base_url}/api/run-custom",
                data=json.dumps({"broken_code": "   ", "test_code": "assert True"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_422:
                urllib.request.urlopen(empty_custom_req, timeout=5)
            self.assertEqual(ctx_422.exception.code, 422)

            # 6. Invalid strategy on /api/race -> 422
            bad_strat_req = urllib.request.Request(
                f"{base_url}/api/race",
                data=json.dumps({"task_id": "api-01-schema-validator", "left_strategy": "nonexistent"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_strat:
                urllib.request.urlopen(bad_strat_req, timeout=5)
            self.assertEqual(ctx_strat.exception.code, 422)

            # 7. Valid /api/run-custom returns initial_probe + verified receipt
            valid_custom_req = urllib.request.Request(
                f"{base_url}/api/run-custom",
                data=json.dumps(
                    {
                        "title": "Clamp Test",
                        "broken_code": "def c(x):\n    return -x\n",
                        "verified_fix_code": "def c(x):\n    return abs(x)\n",
                        "test_code": "from solution import c\nassert c(-3) == 3\nassert c(4) == 4\n",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(valid_custom_req, timeout=10) as resp:
                custom_out = json.loads(resp.read().decode("utf-8"))
                self.assertIn("initial_probe", custom_out)
                self.assertFalse(custom_out["initial_probe"]["verified_solved"])
                self.assertTrue(custom_out["verified_solved"])
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
