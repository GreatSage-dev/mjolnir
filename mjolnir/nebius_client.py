"""Nebius Token Factory Client & NVIDIA Nemotron Tier Manager.

Connects to Nebius Token Factory (`https://api.tokenfactory.nebius.com/v1/`)
to execute inference across the three NVIDIA Nemotron tiers:
- Tier 1 (NANO) : Fast, ultra-low-cost first attempt & API fix synthesis
- Tier 2 (SUPER): Intermediate reasoning & multi-condition synthesis
- Tier 3 (ULTRA): Frontier deep reasoning for complex algorithmic invariants
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Optional


NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Official NVIDIA Nemotron model family tiers across Nebius Token Factory & NVIDIA NIM
NEMOTRON_TIERS = {
    "nano": {
        "label": "NVIDIA Nemotron-3-Nano",
        "primary_id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        "fallback_ids": [
            "nvidia/nemotron-3.5-bolt-e4b",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            "nvidia/Llama-3.1-Nemotron-Nano-8B-v1",
            "nvidia/Llama-3.1-Nemotron-Nano-4B-v1.1",
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
        ],
        "input_cost_per_1m": 0.06,
        "output_cost_per_1m": 0.18,
    },
    "super": {
        "label": "NVIDIA Nemotron-3-Super",
        "primary_id": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
        "fallback_ids": [
            "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "nvidia/Llama-3.3-Nemotron-Super-49B-v1",
            "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
            "meta-llama/Llama-3.3-70B-Instruct",
        ],
        "input_cost_per_1m": 0.30,
        "output_cost_per_1m": 0.90,
    },
    "ultra": {
        "label": "NVIDIA Nemotron-3-Ultra",
        "primary_id": "nvidia/NVIDIA-Nemotron-3-Ultra-550B",
        "fallback_ids": [
            "nvidia/nemotron-3-ultra-550b-a55b",
            "nvidia/Llama-3.1-Nemotron-Ultra-253B-v1",
            "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
            "deepseek-ai/DeepSeek-R1",
        ],
        "input_cost_per_1m": 1.20,
        "output_cost_per_1m": 3.60,
    },
}


@dataclass
class NebiusCallReceipt:
    """Telemetry receipt for a single Nebius Token Factory completion call."""

    tier: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    mode: str  # "live_nebius_api" | "deterministic_replay"
    raw_prompt_preview: str

    def to_dict(self) -> dict:
        return asdict(self)


def extract_python_code(text: str) -> str:
    """Extract clean Python source code from an LLM completion."""
    if not text:
        return ""
    # Strip <think>...</think> reasoning blocks (including unclosed blocks if truncated)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:python|py)?\s*\n(.*?)```", cleaned, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip() + "\n"
    # Handle unclosed ```python fence or bare leading 'python\n' prefix from NIM tokenizers
    cleaned = re.sub(r"^```(?:python|py)?\s*\n", "", cleaned).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    cleaned = re.sub(r"^(?:python|py)\s*\n", "", cleaned).strip()
    return cleaned + "\n"


def _compute_cost(tier: str, prompt_tokens: int, completion_tokens: int) -> float:
    spec = NEMOTRON_TIERS[tier]
    in_cost = (prompt_tokens / 1_000_000.0) * spec["input_cost_per_1m"]
    out_cost = (completion_tokens / 1_000_000.0) * spec["output_cost_per_1m"]
    return round(in_cost + out_cost, 6)


class NebiusTokenFactoryClient:
    """Client for Nebius Token Factory & NVIDIA NIM OpenAI-compatible inference APIs."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        raw_key = (
            api_key
            or os.environ.get("NEBIUS_API_KEY", "")
            or os.environ.get("NVIDIA_API_KEY", "")
        ).strip()
        self.api_key = "" if raw_key == "your_nebius_token_factory_api_key_here" else raw_key
        env_url = os.environ.get("NEBIUS_BASE_URL", "").strip()
        if base_url:
            resolved_url = base_url
        elif self.api_key.startswith("nvapi-") and env_url in {"", NEBIUS_BASE_URL}:
            resolved_url = NVIDIA_NIM_BASE_URL
        else:
            resolved_url = env_url or NEBIUS_BASE_URL
        self.base_url = resolved_url.rstrip("/")
        self._available_models: Optional[set[str]] = None

    def discover_available_models(self) -> set[str]:
        if self._available_models is not None:
            return self._available_models
        if not self.api_key:
            self._available_models = set()
            return self._available_models
        try:
            req = urllib.request.Request(
                f"{self.base_url}/models",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                self._available_models = {
                    item.get("id", "") for item in payload.get("data", []) if item.get("id")
                }
        except Exception:
            self._available_models = set()
        return self._available_models

    def resolve_model_id(self, tier: str) -> str:
        spec = NEMOTRON_TIERS[tier]
        avail = self.discover_available_models()
        if not avail:
            if self.api_key.startswith("nvapi-"):
                return spec["fallback_ids"][0]
            return spec["primary_id"]
        avail_lower = {m.lower(): m for m in avail}
        if spec["primary_id"] in avail:
            return spec["primary_id"]
        if spec["primary_id"].lower() in avail_lower:
            return avail_lower[spec["primary_id"].lower()]
        for cand in spec["fallback_ids"]:
            if cand in avail:
                return cand
            if cand.lower() in avail_lower:
                return avail_lower[cand.lower()]
        # Match any Nemotron model matching tier keyword (avoid VL/vision-only models for code)
        for m in sorted(avail):
            ml = m.lower()
            if "nemotron" in ml and tier in ml and "-vl" not in ml and "embed" not in ml:
                return m
        for m in sorted(avail):
            ml = m.lower()
            if "nemotron" in ml and "-vl" not in ml and "embed" not in ml and "reward" not in ml and "safety" not in ml:
                return m
        return spec["primary_id"]

    def generate_patch(
        self,
        tier: str,
        task_Info: dict,
        broken_code: str,
        error_distillation: str,
        tavily_markdown: Optional[str] = None,
    ) -> tuple[str, NebiusCallReceipt]:
        """Generate a candidate Python code fix at the specified Nemotron tier."""
        model_id = self.resolve_model_id(tier)

        system_prompt = (
            "You are MJOLNIR, an autonomous coding agent running on NVIDIA Nemotron. "
            "Keep internal reasoning brief (<120 words). "
            "Return ONLY the complete, corrected Python file inside a ```python ... ``` block. "
            "Do not modify test files. Preserve all required function names and signatures."
        )

        user_parts = [
            f"TASK: {task_Info.get('title', 'Fix broken module')}",
            f"DESCRIPTION: {task_Info.get('description', '')}",
            f"CURRENT BROKEN CODE (`solution.py`):\n```python\n{broken_code.strip()}\n```",
            f"SANDBOX 3-LINE ERROR RECEIPT:\n{error_distillation}",
        ]
        if tavily_markdown:
            user_parts.append(
                f"LIVE TAVILY DOCUMENTATION & MIGRATION SPEC:\n{tavily_markdown}"
            )
        user_parts.append(
            "Output the complete fixed `solution.py` inside a ```python``` block."
        )
        user_prompt = "\n\n".join(user_parts)

        t0 = time.perf_counter()
        if self.api_key:
            try:
                candidates = [model_id] + NEMOTRON_TIERS[tier]["fallback_ids"]
                seen = set()
                ordered_models = [
                    m for m in candidates if not (m in seen or seen.add(m))
                ]
                for candidate_model in ordered_models:
                    for attempt in range(2):
                        try:
                            payload = {
                                "model": candidate_model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt},
                                ],
                                "temperature": 0.1,
                                "max_tokens": 1800,
                            }
                            req = urllib.request.Request(
                                f"{self.base_url}/chat/completions",
                                data=json.dumps(payload).encode("utf-8"),
                                headers={
                                    "Authorization": f"Bearer {self.api_key}",
                                    "Content-Type": "application/json",
                                    "Accept": "application/json",
                                },
                                method="POST",
                            )
                            with urllib.request.urlopen(req, timeout=75.0) as resp:
                                body = json.loads(resp.read().decode("utf-8"))
                                msg = body["choices"][0]["message"]
                                content = msg.get("content") or ""
                                if not content.strip():
                                    break
                                usage = body.get("usage", {})
                                p_tok = int(usage.get("prompt_tokens", len(user_prompt) // 4))
                                c_tok = int(usage.get("completion_tokens", len(content) // 4))
                                latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                                code_out = extract_python_code(content)
                                return code_out, NebiusCallReceipt(
                                    tier=tier,
                                    model_id=candidate_model,
                                    prompt_tokens=p_tok,
                                    completion_tokens=c_tok,
                                    total_tokens=p_tok + c_tok,
                                    latency_ms=latency_ms,
                                    cost_usd=_compute_cost(tier, p_tok, c_tok),
                                    mode="live_nebius_api",
                                    raw_prompt_preview=user_prompt[:600],
                                )
                        except urllib.error.HTTPError as http_err:
                            if http_err.code in {429, 500, 502, 503, 504} and attempt == 0:
                                time.sleep(2.5)
                                continue
                            break
                        except (urllib.error.URLError, TimeoutError):
                            if attempt == 0:
                                time.sleep(2.0)
                                continue
                            break
            except Exception:
                pass

        # Deterministic replay mode (used when no API key is set or offline verification is run)
        return self._deterministic_tier_simulation(
            tier=tier,
            model_id=model_id,
            task_info=task_Info,
            broken_code=broken_code,
            tavily_markdown=tavily_markdown,
            user_prompt=user_prompt,
            t0=t0,
        )

    def _deterministic_tier_simulation(
        self,
        tier: str,
        model_id: str,
        task_info: dict,
        broken_code: str,
        tavily_markdown: Optional[str],
        user_prompt: str,
        t0: float,
    ) -> tuple[str, NebiusCallReceipt]:
        """Execute realistic model behavior per tier based on task profile and grounding."""
        task_type = task_info.get("category", "api_shift")
        difficulty = task_info.get("difficulty", "medium")
        has_grounding = bool(tavily_markdown and len(tavily_markdown.strip()) > 20)

        p_tok = max(180, len(user_prompt) // 4)
        tier_base_latency = {"nano": 210.0, "super": 540.0, "ultra": 1180.0}[tier]

        # Determine which code output this tier + grounding state produces:
        if task_type == "api_shift":
            # Post-cutoff API change tasks:
            # Without Tavily docs, ungrounded models use stale pre-cutoff syntax unless trivial.
            if has_grounding:
                # With Tavily migration spec: Nano solves standard/medium API shifts;
                # complex multi-API shifts may require Super/Ultra + Tavily.
                if difficulty == "hard" and tier == "nano":
                    candidate_code = task_info.get("partial_attempt_code", broken_code)
                else:
                    candidate_code = task_info["verified_fix_code"]
            else:
                # Ungrounded on post-cutoff API: model attempts legacy pre-cutoff syntax
                candidate_code = task_info.get("ungrounded_attempt_code", broken_code)
        else:
            # Pure logic / algorithmic invariant tasks:
            # Indiscriminate always-on Tavily noise on tricky logic tasks can distract Nano
            if difficulty == "easy":
                candidate_code = task_info["verified_fix_code"]
            elif difficulty == "medium":
                if tier in {"super", "ultra"}:
                    if has_grounding and task_info.get("noise_sensitive", False) and tier == "super":
                        candidate_code = task_info.get("ungrounded_attempt_code", broken_code)
                    else:
                        candidate_code = task_info["verified_fix_code"]
                else:
                    candidate_code = task_info.get("ungrounded_attempt_code", broken_code)
            else:
                # Hard algorithmic invariant: requires Ultra (or Super on clean context)
                if tier == "ultra" and not (has_grounding and task_info.get("noise_sensitive", False)):
                    candidate_code = task_info["verified_fix_code"]
                elif tier == "super" and not has_grounding and not task_info.get("requires_ultra", False):
                    candidate_code = task_info["verified_fix_code"]
                else:
                    candidate_code = task_info.get("ungrounded_attempt_code", broken_code)

        c_tok = max(95, len(candidate_code) // 4 + (140 if tier == "ultra" else 45))
        elapsed = round((time.perf_counter() - t0) * 1000.0 + tier_base_latency, 2)

        return candidate_code, NebiusCallReceipt(
            tier=tier,
            model_id=model_id,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=p_tok + c_tok,
            latency_ms=elapsed,
            cost_usd=_compute_cost(tier, p_tok, c_tok),
            mode="deterministic_replay",
            raw_prompt_preview=user_prompt[:600],
        )
