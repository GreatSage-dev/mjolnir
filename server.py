"""MJOLNIR HTTP Server & REST API.

Zero-dependency multi-threaded server (`ThreadingHTTPServer`) exposing:
- GET  /                     -> Interactive Split-Screen & 5-Arm Proof UI
- GET  /api/tasks            -> Full benchmark task catalog + locked tests
- GET  /api/benchmark/latest -> Instant pre-verified 5-arm benchmark ledger
- POST /api/race             -> Live Split-Screen Race (`ultra_alone` vs `mjolnir_2d_ladder`)
- POST /api/run-custom       -> Run MJOLNIR on custom user-supplied Python code & locked test
- POST /api/benchmark/run    -> Re-run full 5-arm experiment across all tasks
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from mjolnir import load_dotenv_file
from mjolnir.benchmark import run_five_arm_suite
from mjolnir.nebius_client import NEMOTRON_TIERS
from mjolnir.router import execute_strategy_on_task
from mjolnir.sandbox import run_in_locked_sandbox
from mjolnir.tasks import BENCHMARK_TASKS, get_task_by_id


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

MAX_BODY_BYTES = 262_144  # 256 KB strict cap on incoming JSON payloads
MAX_CUSTOM_CODE_CHARS = 65_536  # 64 KB cap per custom code/test file
VALID_STRATEGIES = {
    "nano_alone",
    "ultra_alone",
    "nano_tavily",
    "ultra_tavily_always",
    "mjolnir_2d_ladder",
}
FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    b'<rect width="16" height="16" rx="3" fill="#0d2a1c"/>'
    b'<path d="M2.5 4h11v3.5H9.2v5.5H6.8V7.5H2.5V4Z" fill="#f6e016"/>'
    b"</svg>"
)


class RequestBodyError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def ensure_initial_benchmark() -> dict:
    latest_file = ARTIFACTS_DIR / "latest_5arm_benchmark.json"
    if latest_file.exists():
        try:
            return json.loads(latest_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return run_five_arm_suite()


class MjolnirRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        # Quiet concise logging
        pass

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> dict:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_len)
        except ValueError as exc:
            raise RequestBodyError("Invalid Content-Length header", status=400) from exc
        if length < 0:
            raise RequestBodyError("Negative Content-Length header", status=400)
        if length == 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise RequestBodyError(
                f"Request body exceeds maximum size of {MAX_BODY_BYTES} bytes",
                status=413,
            )
        try:
            raw = self.rfile.read(length).decode("utf-8", errors="strict")
            parsed = json.loads(raw) if raw else {}
        except UnicodeDecodeError as exc:
            raise RequestBodyError("Request body must be valid UTF-8", status=400) from exc
        except json.JSONDecodeError as exc:
            raise RequestBodyError(f"Malformed JSON body: {exc.msg}", status=400) from exc
        if not isinstance(parsed, dict):
            raise RequestBodyError("JSON request body must be an object", status=400)
        return parsed

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/favicon.ico":
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(FAVICON_SVG)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(FAVICON_SVG)
            return

        if path in {"/", "/index.html"}:
            html_file = STATIC_DIR / "index.html"
            if not html_file.exists():
                self._send_json({"error": "UI file missing"}, status=404)
                return
            raw = html_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(raw)
            return

        if path in {"/app", "/app.html"}:
            app_file = STATIC_DIR / "app.html"
            if not app_file.exists():
                self._send_json({"error": "App screen missing"}, status=404)
                return
            raw = app_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(raw)
            return

        if path.startswith("/assets/"):
            rel_name = path[len("/assets/"):]
            assets_root = (STATIC_DIR / "assets").resolve()
            asset_file = (assets_root / rel_name).resolve()
            if not asset_file.is_relative_to(assets_root) or not asset_file.is_file():
                self._send_json({"error": "Asset not found"}, status=404)
                return
            mime_map = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
                ".mp4": "video/mp4",
                ".webm": "video/webm",
            }
            ctype = mime_map.get(asset_file.suffix.lower(), "application/octet-stream")
            raw = asset_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(raw)
            return

        if path == "/api/status":
            load_dotenv_file()
            active_key = (
                os.environ.get("NEBIUS_API_KEY")
                or os.environ.get("NVIDIA_API_KEY")
                or ""
            ).strip()
            endpoint_url = (
                "https://integrate.api.nvidia.com/v1"
                if active_key.startswith("nvapi-")
                else os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
            )
            self._send_json(
                {
                    "service": "MJOLNIR",
                    "version": "1.0.0",
                    "nebius_endpoint": endpoint_url,
                    "nebius_key_configured": bool(active_key),
                    "tavily_key_configured": bool(os.environ.get("TAVILY_API_KEY")),
                    "nemotron_tiers": NEMOTRON_TIERS,
                    "task_count": len(BENCHMARK_TASKS),
                }
            )
            return

        if path == "/api/tasks":
            tasks_out = [
                {
                    "id": t["id"],
                    "title": t["title"],
                    "category": t["category"],
                    "difficulty": t["difficulty"],
                    "description": t["description"],
                    "broken_code": t["broken_code"],
                    "test_code": t["test_code"],
                    "tavily_doc": t.get("tavily_doc", {}),
                }
                for t in BENCHMARK_TASKS
            ]
            self._send_json({"tasks": tasks_out})
            return

        if path == "/api/benchmark/latest":
            report = ensure_initial_benchmark()
            self._send_json(report)
            return

        if path == "/api/benchmark/live":
            live_file = ARTIFACTS_DIR / "live_5arm_telemetry.json"
            if not live_file.exists():
                self._send_json({"error": "No live telemetry captured yet"}, status=404)
                return
            self._send_json(json.loads(live_file.read_text(encoding="utf-8")))
            return

        if path == "/api/benchmark/deterministic":
            det_file = ARTIFACTS_DIR / "deterministic_5arm_benchmark.json"
            if det_file.exists():
                self._send_json(json.loads(det_file.read_text(encoding="utf-8")))
                return
            self._send_json(ensure_initial_benchmark())
            return

        self._send_json({"error": f"Unknown route: {path}"}, status=404)

    def do_POST(self) -> None:
        load_dotenv_file()
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_body()
        except RequestBodyError as exc:
            self._send_json({"error": str(exc)}, status=exc.status)
            return

        nebius_key = (
            (body.get("nebius_api_key") if isinstance(body.get("nebius_api_key"), str) else "")
            or os.environ.get("NEBIUS_API_KEY")
            or os.environ.get("NVIDIA_API_KEY")
            or ""
        ).strip() or None
        tavily_key = (
            (body.get("tavily_api_key") if isinstance(body.get("tavily_api_key"), str) else "")
            or os.environ.get("TAVILY_API_KEY")
            or ""
        ).strip() or None

        if path == "/api/race":
            task_id = body.get("task_id") or BENCHMARK_TASKS[0]["id"]
            left_strategy = body.get("left_strategy") or body.get("baseline_strategy") or "ultra_alone"
            right_strategy = body.get("right_strategy") or "mjolnir_2d_ladder"
            if left_strategy not in VALID_STRATEGIES or right_strategy not in VALID_STRATEGIES:
                self._send_json(
                    {"error": f"Strategy must be one of {sorted(VALID_STRATEGIES)}"},
                    status=422,
                )
                return
            try:
                task = get_task_by_id(str(task_id))
            except KeyError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return

            left_rec = execute_strategy_on_task(
                task,
                strategy=left_strategy,
                nebius_api_key=nebius_key,
                tavily_api_key=tavily_key,
            )
            right_rec = execute_strategy_on_task(
                task,
                strategy=right_strategy,
                nebius_api_key=nebius_key,
                tavily_api_key=tavily_key,
            )
            cost_ratio = (
                round(left_rec.total_cost_usd / right_rec.total_cost_usd, 1)
                if right_rec.total_cost_usd > 0
                else 1.0
            )
            self._send_json(
                {
                    "task": {
                        "id": task["id"],
                        "title": task["title"],
                        "category": task["category"],
                        "description": task["description"],
                        "broken_code": task["broken_code"],
                        "test_code": task["test_code"],
                    },
                    "left": left_rec.to_dict(),
                    "right": right_rec.to_dict(),
                    "comparison": {
                        "cost_multiple_saved": cost_ratio,
                        "left_solved": left_rec.verified_solved,
                        "right_solved": right_rec.verified_solved,
                    },
                }
            )
            return

        if path == "/api/benchmark/run":
            report = run_five_arm_suite(
                nebius_api_key=nebius_key,
                tavily_api_key=tavily_key,
            )
            self._send_json(report)
            return

        if path == "/api/run-custom":
            raw_broken = body.get("broken_code")
            raw_test = body.get("test_code")
            if not isinstance(raw_broken, str) or not raw_broken.strip():
                self._send_json(
                    {"error": "Candidate code (solution.py) cannot be empty."},
                    status=422,
                )
                return
            if not isinstance(raw_test, str) or not raw_test.strip():
                self._send_json(
                    {"error": "Locked unit test (test_solution.py) cannot be empty."},
                    status=422,
                )
                return
            if len(raw_broken) > MAX_CUSTOM_CODE_CHARS or len(raw_test) > MAX_CUSTOM_CODE_CHARS:
                self._send_json(
                    {"error": f"Custom code and test files must each be <= {MAX_CUSTOM_CODE_CHARS} characters."},
                    status=413,
                )
                return

            title = str(body.get("title") or "Custom Sandbox Verification Task")[:120]
            category = body.get("category") if body.get("category") in {"api_shift", "logic_invariant"} else "logic_invariant"
            initial_sbx = run_in_locked_sandbox(
                original_code=raw_broken,
                candidate_code=raw_broken,
                test_code=raw_test,
            )
            initial_probe_dict = {
                "task_id": "custom-sandbox-task",
                "task_title": title,
                "task_category": category,
                "strategy": "initial_unpatched_probe",
                "verified_solved": initial_sbx.passed,
                "final_exit_code": initial_sbx.exit_code,
                "total_cost_usd": 0.0,
                "total_latency_ms": initial_sbx.duration_ms,
                "total_tokens": 0,
                "tavily_triggered": False,
                "escalation_path": ["Submitted Candidate (Unpatched)"],
                "initial_error_receipt": (
                    initial_sbx.error_receipt.to_dict() if initial_sbx.error_receipt else {}
                ),
                "final_unified_diff": "",
                "final_patch_sha256": initial_sbx.patch_sha256,
                "test_sha256": initial_sbx.test_sha256,
                "steps": [
                    {
                        "step_index": 0,
                        "stage_label": "Rung 0: Submitted Candidate (Before Repair)",
                        "tier": "unpatched",
                        "used_tavily": False,
                        "nebius_call": {
                            "tier": "unpatched",
                            "model_id": "locked-sandbox-probe",
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "latency_ms": 0.0,
                            "cost_usd": 0.0,
                            "mode": "sandbox_probe",
                            "raw_prompt_preview": "",
                        },
                        "tavily_call": None,
                        "sandbox_receipt": initial_sbx.to_dict(),
                    }
                ],
            }

            custom_task = {
                "id": "custom-sandbox-task",
                "title": title,
                "category": category,
                "difficulty": "medium",
                "description": str(body.get("description") or "User-provided code and locked unit test.")[:500],
                "broken_code": raw_broken,
                "test_code": raw_test,
                "ungrounded_attempt_code": raw_broken,
                "verified_fix_code": str(body.get("verified_fix_code") or raw_broken),
                "extra_files": {},
                "tavily_doc": {
                    "query": str(body.get("tavily_query") or title)[:200],
                    "domains": [],
                    "urls": [],
                    "migration_spec": str(body.get("tavily_hint") or "")[:2000],
                },
            }
            rec = execute_strategy_on_task(
                custom_task,
                strategy="mjolnir_2d_ladder",
                nebius_api_key=nebius_key,
                tavily_api_key=tavily_key,
            )
            out = rec.to_dict()
            out["initial_probe"] = initial_probe_dict
            self._send_json(out)
            return

        self._send_json({"error": f"Unknown POST route: {path}"}, status=404)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    ensure_initial_benchmark()
    httpd = ThreadingHTTPServer((host, port), MjolnirRequestHandler)
    print(f"MJOLNIR Server listening on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    port_num = int(os.environ.get("PORT", "8080"))
    run_server(port=port_num)
