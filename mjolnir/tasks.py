"""Real Runnable Task Suite for MJOLNIR (Post-Cutoff API Shifts + Logic Invariants).

Every task contains:
- `broken_code`: Initial buggy code that fails the locked test suite.
- `test_code`: Strictly locked, read-only unit test executed in an isolated Python subprocess.
- `extra_files`: Real Python library modules mounted in the sandbox to enforce 2026 API signatures.
- `tavily_doc`: Verified migration specification & target domains for the 3-stage Tavily pipeline.
- `ungrounded_attempt_code`: What an ungrounded model produces from stale pre-cutoff priors.
- `verified_fix_code`: Reference solution that passes all locked test assertions (`exit code 0`).
"""

from __future__ import annotations


BENCHMARK_TASKS: list[dict] = [
    # =========================================================================
    # GROUP A: POST-CUTOFF API SHIFT TASKS (Knowledge Gap -> Triggers Tavily)
    # =========================================================================
    {
        "id": "api-01-schema-validator",
        "title": "SchemaGuard v3: Post-Cutoff Validator Decorator & Dump API",
        "category": "api_shift",
        "difficulty": "medium",
        "description": (
            "Migrate `serialize_user` from legacy `schemaguard` v1 (`.dict()`) "
            "to the 2026 `schemaguard` v3 strict serialization API while excluding `None` fields."
        ),
        "extra_files": {
            "schemaguard.py": (
                "class BaseSchema:\n"
                "    def __init__(self, **kwargs):\n"
                "        for k, v in kwargs.items():\n"
                "            setattr(self, k, v)\n"
                "        if hasattr(self, '__post_validate__'):\n"
                "            self.__post_validate__()\n"
                "    def model_dump_strict(self, *, exclude_none: bool = False) -> dict:\n"
                "        out = {}\n"
                "        for k, v in self.__dict__.items():\n"
                "            if exclude_none and v is None:\n"
                "                continue\n"
                "            out[k] = v\n"
                "        return out\n"
            )
        },
        "broken_code": (
            "from schemaguard import BaseSchema\n\n"
            "class UserPayload(BaseSchema):\n"
            "    def __init__(self, username: str, quota: int, tag: str = None):\n"
            "        super().__init__(username=username.strip().lower(), quota=quota, tag=tag)\n"
            "        if self.quota < 0:\n"
            "            raise ValueError('quota must be non-negative')\n\n"
            "def serialize_user(username: str, quota: int, tag: str = None) -> dict:\n"
            "    user = UserPayload(username=username, quota=quota, tag=tag)\n"
            "    return user.dict(exclude_none=True)\n"
        ),
        "ungrounded_attempt_code": (
            "from schemaguard import BaseSchema\n\n"
            "class UserPayload(BaseSchema):\n"
            "    def __init__(self, username: str, quota: int, tag: str = None):\n"
            "        super().__init__(username=username.strip().lower(), quota=quota, tag=tag)\n"
            "        if self.quota < 0:\n"
            "            raise ValueError('quota must be non-negative')\n\n"
            "def serialize_user(username: str, quota: int, tag: str = None) -> dict:\n"
            "    user = UserPayload(username=username, quota=quota, tag=tag)\n"
            "    return user.model_dump(exclude_none=True)\n"
        ),
        "verified_fix_code": (
            "from schemaguard import BaseSchema\n\n"
            "class UserPayload(BaseSchema):\n"
            "    def __init__(self, username: str, quota: int, tag: str = None):\n"
            "        super().__init__(username=username.strip().lower(), quota=quota, tag=tag)\n"
            "        if self.quota < 0:\n"
            "            raise ValueError('quota must be non-negative')\n\n"
            "def serialize_user(username: str, quota: int, tag: str = None) -> dict:\n"
            "    user = UserPayload(username=username, quota=quota, tag=tag)\n"
            "    return user.model_dump_strict(exclude_none=True)\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import serialize_user\n\n"
            "class TestSchemaGuard(unittest.TestCase):\n"
            "    def test_serialize_excludes_none(self):\n"
            "        res = serialize_user('  Alice ', 100, None)\n"
            "        self.assertEqual(res, {'username': 'alice', 'quota': 100})\n"
            "    def test_serialize_with_tag(self):\n"
            "        res = serialize_user('Bob', 50, 'admin')\n"
            "        self.assertEqual(res, {'username': 'bob', 'quota': 50, 'tag': 'admin'})\n"
            "    def test_negative_quota_raises(self):\n"
            "        with self.assertRaises(ValueError):\n"
            "            serialize_user('Eve', -1)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "SchemaGuard v3 BaseSchema dict model_dump_strict exclude_none migration 2026",
            "domains": ["docs.pydantic.dev", "github.com"],
            "urls": [
                "https://docs.pydantic.dev/latest/migration/#model-dump-strict",
                "https://github.com/schemaguard/schemaguard/releases/tag/v3.0.0",
            ],
            "migration_spec": (
                "### SchemaGuard v3.0 Breaking Change (2026 Release)\n"
                "- Removed `.dict()` and `.model_dump()` from `BaseSchema`.\n"
                "- Replacement: Call `instance.model_dump_strict(*, exclude_none: bool = False) -> dict`.\n"
                "- Note: `exclude_none` is a keyword-only argument."
            ),
        },
    },
    {
        "id": "api-02-nebius-stream-cursor",
        "title": "Nebius SSE Stream: 2026 Resumable Cursor Handshake",
        "category": "api_shift",
        "difficulty": "medium",
        "description": (
            "Update `consume_token_stream` to use the 2026 `nebius_sse` v2 resumable stream API "
            "instead of the removed legacy `connect_stream` helper."
        ),
        "extra_files": {
            "nebius_sse.py": (
                "def open_resumable_stream(endpoint: str, *, resume_cursor: str = '0', timeout_ms: int = 5000) -> list[dict]:\n"
                "    if not endpoint.startswith('https://'):\n"
                "        raise ValueError('HTTPS required')\n"
                "    base = [{'id': '1', 'token': 'Hello'}, {'id': '2', 'token': ' '}, {'id': '3', 'token': 'World'}]\n"
                "    return [pkt for pkt in base if int(pkt['id']) > int(resume_cursor)]\n"
            )
        },
        "broken_code": (
            "import nebius_sse\n\n"
            "def consume_token_stream(endpoint: str, last_id: str = '0') -> str:\n"
            "    packets = nebius_sse.connect_stream(endpoint, last_event_id=last_id)\n"
            "    return ''.join(p['token'] for p in packets)\n"
        ),
        "ungrounded_attempt_code": (
            "import nebius_sse\n\n"
            "def consume_token_stream(endpoint: str, last_id: str = '0') -> str:\n"
            "    packets = nebius_sse.create_stream(endpoint, cursor=last_id)\n"
            "    return ''.join(p['token'] for p in packets)\n"
        ),
        "verified_fix_code": (
            "import nebius_sse\n\n"
            "def consume_token_stream(endpoint: str, last_id: str = '0') -> str:\n"
            "    packets = nebius_sse.open_resumable_stream(endpoint, resume_cursor=last_id)\n"
            "    return ''.join(p['token'] for p in packets)\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import consume_token_stream\n\n"
            "class TestNebiusSSE(unittest.TestCase):\n"
            "    def test_full_stream(self):\n"
            "        out = consume_token_stream('https://api.tokenfactory.nebius.com/v1/stream', '0')\n"
            "        self.assertEqual(out, 'Hello World')\n"
            "    def test_resumed_stream(self):\n"
            "        out = consume_token_stream('https://api.tokenfactory.nebius.com/v1/stream', '1')\n"
            "        self.assertEqual(out, ' World')\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "nebius_sse connect_stream open_resumable_stream resume_cursor API reference",
            "domains": ["docs.nebius.com", "github.com"],
            "urls": [
                "https://docs.nebius.com/token-factory/streaming-sse-v2",
            ],
            "migration_spec": (
                "### `nebius_sse` v2.0 Migration Guide\n"
                "- Deprecated and removed: `nebius_sse.connect_stream(endpoint, last_event_id=...)`\n"
                "- New signature: `nebius_sse.open_resumable_stream(endpoint: str, *, resume_cursor: str = '0', timeout_ms: int = 5000)`"
            ),
        },
    },
    {
        "id": "api-03-frameflow-groupby",
        "title": "FrameFlow 2026: Deterministic GroupBy Aggregation API",
        "category": "api_shift",
        "difficulty": "medium",
        "description": (
            "Migrate `summarize_region_spend` from removed `df.groupby(col).agg_sum(target)` "
            "to the 2026 `frameflow` v2 grouped aggregation API while preserving first-seen region order."
        ),
        "extra_files": {
            "frameflow.py": (
                "class GroupedFrame:\n"
                "    def __init__(self, rows, key_col, maintain_order):\n"
                "        self.rows = rows\n"
                "        self.key_col = key_col\n"
                "        self.maintain_order = maintain_order\n"
                "    def sum_column(self, target_col: str) -> dict:\n"
                "        totals = {}\n"
                "        for r in self.rows:\n"
                "            k = r[self.key_col]\n"
                "            totals[k] = round(totals.get(k, 0.0) + float(r[target_col]), 4)\n"
                "        if not self.maintain_order:\n"
                "            return dict(sorted(totals.items()))\n"
                "        return totals\n\n"
                "class DataFrame:\n"
                "    def __init__(self, rows: list[dict]):\n"
                "        self.rows = rows\n"
                "    def group_by_key(self, key_col: str, *, maintain_order: bool = False) -> GroupedFrame:\n"
                "        return GroupedFrame(self.rows, key_col, maintain_order)\n"
            )
        },
        "broken_code": (
            "from frameflow import DataFrame\n\n"
            "def summarize_region_spend(records: list[dict]) -> dict:\n"
            "    df = DataFrame(records)\n"
            "    return df.groupby('region').agg_sum('cost')\n"
        ),
        "ungrounded_attempt_code": (
            "from frameflow import DataFrame\n\n"
            "def summarize_region_spend(records: list[dict]) -> dict:\n"
            "    df = DataFrame(records)\n"
            "    return df.group_by('region').sum('cost')\n"
        ),
        "verified_fix_code": (
            "from frameflow import DataFrame\n\n"
            "def summarize_region_spend(records: list[dict]) -> dict:\n"
            "    df = DataFrame(records)\n"
            "    return df.group_by_key('region', maintain_order=True).sum_column('cost')\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import summarize_region_spend\n\n"
            "class TestFrameFlow(unittest.TestCase):\n"
            "    def test_preserves_insertion_order_and_sums(self):\n"
            "        data = [\n"
            "            {'region': 'eu-north1', 'cost': 12.5},\n"
            "            {'region': 'us-central1', 'cost': 8.0},\n"
            "            {'region': 'eu-north1', 'cost': 7.5},\n"
            "        ]\n"
            "        res = summarize_region_spend(data)\n"
            "        self.assertEqual(list(res.keys()), ['eu-north1', 'us-central1'])\n"
            "        self.assertEqual(res['eu-north1'], 20.0)\n"
            "        self.assertEqual(res['us-central1'], 8.0)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "frameflow DataFrame groupby group_by_key maintain_order sum_column 2026",
            "domains": ["docs.pola.rs", "github.com"],
            "urls": [
                "https://docs.pola.rs/releases/upgrade/2026-groupby-key/",
            ],
            "migration_spec": (
                "### FrameFlow 2026 Breaking API Change\n"
                "- `df.groupby()` and `.agg_sum()` were removed.\n"
                "- Use `df.group_by_key(key_col: str, *, maintain_order: bool = False)` followed by `.sum_column(target_col: str)`.\n"
                "- Pass `maintain_order=True` to preserve first-seen key order."
            ),
        },
    },
    {
        "id": "api-04-vector-hybrid-query",
        "title": "VecStore 2026: Hybrid Dense+BM25 Search Signature",
        "category": "api_shift",
        "difficulty": "medium",
        "description": (
            "Fix `hybrid_retrieve` after `vecstore` v4 removed `VectorIndex.query(vec, alpha=..., limit=...)` "
            "in favor of its 2026 keyword-only hybrid retrieval method."
        ),
        "extra_files": {
            "vecstore.py": (
                "class VectorIndex:\n"
                "    def __init__(self, docs: list[dict]):\n"
                "        self.docs = docs\n"
                "    def query_hybrid(self, *, dense_vector: list[float], fusion_weight: float = 0.5, top_k: int = 3) -> list[str]:\n"
                "        if not (0.0 <= fusion_weight <= 1.0):\n"
                "            raise ValueError('fusion_weight must be in [0, 1]')\n"
                "        scored = sorted(\n"
                "            self.docs,\n"
                "            key=lambda d: fusion_weight * d['dense'] + (1.0 - fusion_weight) * d['lexical'],\n"
                "            reverse=True,\n"
                "        )\n"
                "        return [d['id'] for d in scored[:top_k]]\n"
            )
        },
        "broken_code": (
            "from vecstore import VectorIndex\n\n"
            "def hybrid_retrieve(docs: list[dict], vec: list[float], weight: float, k: int = 2) -> list[str]:\n"
            "    idx = VectorIndex(docs)\n"
            "    return idx.query(vec, alpha=weight, limit=k)\n"
        ),
        "ungrounded_attempt_code": (
            "from vecstore import VectorIndex\n\n"
            "def hybrid_retrieve(docs: list[dict], vec: list[float], weight: float, k: int = 2) -> list[str]:\n"
            "    idx = VectorIndex(docs)\n"
            "    return idx.hybrid_search(vector=vec, alpha=weight, top_k=k)\n"
        ),
        "verified_fix_code": (
            "from vecstore import VectorIndex\n\n"
            "def hybrid_retrieve(docs: list[dict], vec: list[float], weight: float, k: int = 2) -> list[str]:\n"
            "    idx = VectorIndex(docs)\n"
            "    return idx.query_hybrid(dense_vector=vec, fusion_weight=weight, top_k=k)\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import hybrid_retrieve\n\n"
            "class TestVecStore(unittest.TestCase):\n"
            "    def test_hybrid_ranking(self):\n"
            "        docs = [\n"
            "            {'id': 'doc_a', 'dense': 0.9, 'lexical': 0.2},\n"
            "            {'id': 'doc_b', 'dense': 0.4, 'lexical': 0.95},\n"
            "            {'id': 'doc_c', 'dense': 0.7, 'lexical': 0.7},\n"
            "        ]\n"
            "        res = hybrid_retrieve(docs, [0.1, 0.2], 0.8, k=2)\n"
            "        self.assertEqual(res, ['doc_a', 'doc_c'])\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "vecstore v4 VectorIndex query query_hybrid dense_vector fusion_weight top_k",
            "domains": ["docs.pinecone.io", "qdrant.tech"],
            "urls": [
                "https://qdrant.tech/documentation/concepts/hybrid-queries-v4/",
            ],
            "migration_spec": (
                "### VecStore v4.0 Migration Note\n"
                "- Removed `VectorIndex.query(vec, alpha=..., limit=...)`.\n"
                "- Replaced with keyword-only `VectorIndex.query_hybrid(*, dense_vector: list[float], fusion_weight: float = 0.5, top_k: int = 3) -> list[str]`."
            ),
        },
    },
    {
        "id": "api-05-token-guard-hmac",
        "title": "CryptoSeal 2026: Constant-Time Envelope Verification",
        "category": "api_shift",
        "difficulty": "medium",
        "description": (
            "Update `verify_webhook_envelope` from deprecated `cryptoseal.verify_hmac(payload, sig, secret)` "
            "to the 2026 `cryptoseal` v2 bytes-strict envelope verification API."
        ),
        "extra_files": {
            "cryptoseal.py": (
                "import hashlib\nimport hmac\n\n"
                "def verify_envelope_v2(*, payload_bytes: bytes, signature_hex: str, key_bytes: bytes) -> bool:\n"
                "    if not isinstance(payload_bytes, bytes) or not isinstance(key_bytes, bytes):\n"
                "        raise TypeError('payload_bytes and key_bytes must be bytes')\n"
                "    expected = hmac.new(key_bytes, payload_bytes, hashlib.sha256).hexdigest()\n"
                "    return hmac.compare_digest(expected, signature_hex)\n"
            )
        },
        "broken_code": (
            "import cryptoseal\n\n"
            "def verify_webhook_envelope(body: str, signature: str, secret: str) -> bool:\n"
            "    return cryptoseal.verify_hmac(body, signature, secret)\n"
        ),
        "ungrounded_attempt_code": (
            "import cryptoseal\n\n"
            "def verify_webhook_envelope(body: str, signature: str, secret: str) -> bool:\n"
            "    return cryptoseal.verify_signature(body.encode(), signature, secret.encode())\n"
        ),
        "verified_fix_code": (
            "import cryptoseal\n\n"
            "def verify_webhook_envelope(body: str, signature: str, secret: str) -> bool:\n"
            "    return cryptoseal.verify_envelope_v2(\n"
            "        payload_bytes=body.encode('utf-8'),\n"
            "        signature_hex=signature,\n"
            "        key_bytes=secret.encode('utf-8'),\n"
            "    )\n"
        ),
        "test_code": (
            "import hashlib, hmac, unittest\n"
            "from solution import verify_webhook_envelope\n\n"
            "class TestCryptoSeal(unittest.TestCase):\n"
            "    def test_valid_and_invalid_signature(self):\n"
            "        body = '{\"event\":\"invoice.paid\"}'\n"
            "        secret = 'nebius_secret_key'\n"
            "        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()\n"
            "        self.assertTrue(verify_webhook_envelope(body, sig, secret))\n"
            "        self.assertFalse(verify_webhook_envelope(body, '00' * 32, secret))\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "cryptoseal verify_hmac verify_envelope_v2 payload_bytes signature_hex key_bytes",
            "domains": ["cryptography.io", "github.com"],
            "urls": [
                "https://cryptography.io/en/latest/changelog/#v2026-envelope-v2",
            ],
            "migration_spec": (
                "### CryptoSeal 2026 Security Upgrade\n"
                "- `verify_hmac(str, str, str)` has been removed to prevent encoding ambiguity.\n"
                "- Use `cryptoseal.verify_envelope_v2(*, payload_bytes: bytes, signature_hex: str, key_bytes: bytes) -> bool`."
            ),
        },
    },
    {
        "id": "api-06-nemo-tool-router-v2",
        "title": "NeMo ToolSpec 2026: Strict JSON Schema & Call Binding",
        "category": "api_shift",
        "difficulty": "hard",
        "description": (
            "Migrate `dispatch_agent_tool` to the 2026 `nemo_toolspec` v2 API AND enforce "
            "type coercion for integer parameters before invoking the registered callable."
        ),
        "extra_files": {
            "nemo_toolspec.py": (
                "class ToolRegistryV2:\n"
                "    def __init__(self):\n"
                "        self._tools = {}\n"
                "    def register_callable(self, *, tool_name: str, fn, int_fields: list[str] = None):\n"
                "        self._tools[tool_name] = (fn, set(int_fields or []))\n"
                "    def invoke_strict(self, *, tool_name: str, payload: dict):\n"
                "        if tool_name not in self._tools:\n"
                "            raise KeyError(f'Unknown tool: {tool_name}')\n"
                "        fn, int_fields = self._tools[tool_name]\n"
                "        for field in int_fields:\n"
                "            if field in payload and not isinstance(payload[field], int):\n"
                "                raise TypeError(f'Field {field} must be coerced to int before invoke_strict')\n"
                "        return fn(**payload)\n"
            )
        },
        "broken_code": (
            "from nemo_toolspec import ToolRegistryV2\n\n"
            "def dispatch_agent_tool(tool_name: str, fn, raw_args: dict, int_keys: list[str]) -> any:\n"
            "    reg = ToolRegistryV2()\n"
            "    reg.add_tool(tool_name, fn)\n"
            "    return reg.execute(tool_name, raw_args)\n"
        ),
        "partial_attempt_code": (
            "from nemo_toolspec import ToolRegistryV2\n\n"
            "def dispatch_agent_tool(tool_name: str, fn, raw_args: dict, int_keys: list[str]) -> any:\n"
            "    reg = ToolRegistryV2()\n"
            "    reg.register_callable(tool_name=tool_name, fn=fn, int_fields=int_keys)\n"
            "    return reg.invoke_strict(tool_name=tool_name, payload=raw_args)\n"
        ),
        "ungrounded_attempt_code": (
            "from nemo_toolspec import ToolRegistryV2\n\n"
            "def dispatch_agent_tool(tool_name: str, fn, raw_args: dict, int_keys: list[str]) -> any:\n"
            "    reg = ToolRegistryV2()\n"
            "    reg.register(tool_name, fn)\n"
            "    return reg.call(tool_name, **raw_args)\n"
        ),
        "verified_fix_code": (
            "from nemo_toolspec import ToolRegistryV2\n\n"
            "def dispatch_agent_tool(tool_name: str, fn, raw_args: dict, int_keys: list[str]) -> any:\n"
            "    reg = ToolRegistryV2()\n"
            "    reg.register_callable(tool_name=tool_name, fn=fn, int_fields=int_keys)\n"
            "    coerced = dict(raw_args)\n"
            "    for k in int_keys:\n"
            "        if k in coerced and coerced[k] is not None:\n"
            "            coerced[k] = int(coerced[k])\n"
            "    return reg.invoke_strict(tool_name=tool_name, payload=coerced)\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import dispatch_agent_tool\n\n"
            "class TestNeMoToolSpec(unittest.TestCase):\n"
            "    def test_coerces_string_ints_and_invokes(self):\n"
            "        def scale_cluster(nodes: int, region: str) -> str:\n"
            "            return f'{region}:{nodes * 2}'\n"
            "        out = dispatch_agent_tool(\n"
            "            'scale_cluster',\n"
            "            scale_cluster,\n"
            "            {'nodes': '4', 'region': 'eu-north1'},\n"
            "            ['nodes'],\n"
            "        )\n"
            "        self.assertEqual(out, 'eu-north1:8')\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "nemo_toolspec ToolRegistryV2 register_callable invoke_strict int_fields",
            "domains": ["docs.nvidia.com", "github.com"],
            "urls": [
                "https://docs.nvidia.com/nemo/agent-toolkit/2026/tool-registry-v2.html",
            ],
            "migration_spec": (
                "### NeMo ToolSpec v2 (`ToolRegistryV2`)\n"
                "- Replaced `add_tool` / `execute` with keyword-only methods:\n"
                "  1. `reg.register_callable(*, tool_name: str, fn, int_fields: list[str] = None)`\n"
                "  2. `reg.invoke_strict(*, tool_name: str, payload: dict)`\n"
                "- IMPORTANT: `invoke_strict` raises `TypeError` if any key in `int_fields` is still a `str`; caller must cast `int(payload[k])` prior to `invoke_strict`."
            ),
        },
    },

    # =========================================================================
    # GROUP B: PURE ALGORITHMIC / LOGIC INVARIANT TASKS (Reasoning Gap -> Super/Ultra)
    # =========================================================================
    {
        "id": "logic-01-sliding-rate-limiter",
        "title": "Nebius Dynamic 15-Min Window Rate Governor",
        "category": "logic_invariant",
        "difficulty": "medium",
        "noise_sensitive": True,
        "description": (
            "Fix `evaluate_window_limit(current_limit, base_limit, usage_ratio)`: "
            "Scale up by 1.2x if usage_ratio >= 0.80 (capped at 20x base_limit); "
            "scale down by dividing by 1.5 if usage_ratio <= 0.50 (floored at base_limit)."
        ),
        "extra_files": {},
        "broken_code": (
            "def evaluate_window_limit(current_limit: float, base_limit: float, usage_ratio: float) -> float:\n"
            "    if usage_ratio > 0.80:\n"
            "        return current_limit * 1.2\n"
            "    elif usage_ratio < 0.50:\n"
            "        return current_limit / 1.5\n"
            "    return current_limit\n"
        ),
        "ungrounded_attempt_code": (
            "def evaluate_window_limit(current_limit: float, base_limit: float, usage_ratio: float) -> float:\n"
            "    if usage_ratio >= 0.80:\n"
            "        return min(current_limit * 1.2, base_limit * 20.0)\n"
            "    elif usage_ratio <= 0.50:\n"
            "        return round(current_limit / 1.5, 2)\n"
            "    return round(current_limit, 2)\n"
        ),
        "verified_fix_code": (
            "def evaluate_window_limit(current_limit: float, base_limit: float, usage_ratio: float) -> float:\n"
            "    if usage_ratio >= 0.80:\n"
            "        new_limit = min(current_limit * 1.2, base_limit * 20.0)\n"
            "    elif usage_ratio <= 0.50:\n"
            "        new_limit = max(current_limit / 1.5, base_limit)\n"
            "    else:\n"
            "        new_limit = current_limit\n"
            "    return round(new_limit, 2)\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import evaluate_window_limit\n\n"
            "class TestRateGovernor(unittest.TestCase):\n"
            "    def test_boundary_scale_up_and_ceiling(self):\n"
            "        self.assertEqual(evaluate_window_limit(100.0, 100.0, 0.80), 120.0)\n"
            "        self.assertEqual(evaluate_window_limit(1950.0, 100.0, 0.95), 2000.0)\n"
            "    def test_boundary_scale_down_and_floor(self):\n"
            "        self.assertEqual(evaluate_window_limit(150.0, 100.0, 0.50), 100.0)\n"
            "        self.assertEqual(evaluate_window_limit(110.0, 100.0, 0.20), 100.0)\n"
            "    def test_steady_state(self):\n"
            "        self.assertEqual(evaluate_window_limit(300.0, 100.0, 0.65), 300.0)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "rate limit token bucket sliding window algorithm generic",
            "domains": ["en.wikipedia.org"],
            "urls": ["https://en.wikipedia.org/wiki/Token_bucket"],
            "migration_spec": "Generic token bucket rate limiting article (unrelated to exact floor/ceiling invariant).",
        },
    },
    {
        "id": "logic-02-dag-topo-tiebreak",
        "title": "Deterministic Lexicographical Topological Scheduler",
        "category": "logic_invariant",
        "difficulty": "hard",
        "requires_ultra": True,
        "noise_sensitive": True,
        "description": (
            "Fix `schedule_dag(tasks, deps)` so independent ready tasks are always emitted in "
            "lexicographical order, and raise `ValueError('Cycle detected')` if a dependency cycle exists."
        ),
        "extra_files": {},
        "broken_code": (
            "def schedule_dag(tasks: list[str], deps: list[tuple[str, str]]) -> list[str]:\n"
            "    # deps: (prerequisite, dependent)\n"
            "    order = []\n"
            "    for t in tasks:\n"
            "        if t not in order:\n"
            "            order.append(t)\n"
            "    return order\n"
        ),
        "ungrounded_attempt_code": (
            "from collections import deque\n\n"
            "def schedule_dag(tasks: list[str], deps: list[tuple[str, str]]) -> list[str]:\n"
            "    indeg = {t: 0 for t in tasks}\n"
            "    adj = {t: [] for t in tasks}\n"
            "    for u, v in deps:\n"
            "        adj[u].append(v)\n"
            "        indeg[v] += 1\n"
            "    q = deque([t for t in tasks if indeg[t] == 0])\n"
            "    res = []\n"
            "    while q:\n"
            "        curr = q.popleft()\n"
            "        res.append(curr)\n"
            "        for nxt in adj[curr]:\n"
            "            indeg[nxt] -= 1\n"
            "            if indeg[nxt] == 0:\n"
            "                q.append(nxt)\n"
            "    return res\n"
        ),
        "verified_fix_code": (
            "import heapq\n\n"
            "def schedule_dag(tasks: list[str], deps: list[tuple[str, str]]) -> list[str]:\n"
            "    indeg = {t: 0 for t in tasks}\n"
            "    adj = {t: [] for t in tasks}\n"
            "    for u, v in deps:\n"
            "        adj[u].append(v)\n"
            "        indeg[v] += 1\n"
            "    heap = [t for t, d in indeg.items() if d == 0]\n"
            "    heapq.heapify(heap)\n"
            "    order = []\n"
            "    while heap:\n"
            "        curr = heapq.heappop(heap)\n"
            "        order.append(curr)\n"
            "        for nxt in adj[curr]:\n"
            "            indeg[nxt] -= 1\n"
            "            if indeg[nxt] == 0:\n"
            "                heapq.heappush(heap, nxt)\n"
            "    if len(order) != len(tasks):\n"
            "        raise ValueError('Cycle detected')\n"
            "    return order\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import schedule_dag\n\n"
            "class TestDagScheduler(unittest.TestCase):\n"
            "    def test_lexicographical_tie_break(self):\n"
            "        tasks = ['compile', 'lint', 'audit', 'deploy']\n"
            "        deps = [('lint', 'deploy'), ('compile', 'deploy'), ('audit', 'compile')]\n"
            "        self.assertEqual(schedule_dag(tasks, deps), ['audit', 'compile', 'lint', 'deploy'])\n"
            "    def test_cycle_raises_value_error(self):\n"
            "        with self.assertRaises(ValueError):\n"
            "            schedule_dag(['a', 'b'], [('a', 'b'), ('b', 'a')])\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "topological sort graph theory overview",
            "domains": ["en.wikipedia.org"],
            "urls": ["https://en.wikipedia.org/wiki/Topological_sorting"],
            "migration_spec": "Standard FIFO Kahn's algorithm overview without heap tie-breaking.",
        },
    },
    {
        "id": "logic-03-exact-basis-points-ledger",
        "title": "Integer-Exact Basis Points Fee Split Ledger",
        "category": "logic_invariant",
        "difficulty": "medium",
        "description": (
            "Fix `allocate_payouts(total_cents, weights)` so integer cents are distributed "
            "proportionally using the Largest Remainder Method, guaranteeing `sum(payouts) == total_cents`."
        ),
        "extra_files": {},
        "broken_code": (
            "def allocate_payouts(total_cents: int, weights: list[int]) -> list[int]:\n"
            "    s = sum(weights)\n"
            "    return [int(round(total_cents * (w / s))) for w in weights]\n"
        ),
        "ungrounded_attempt_code": (
            "def allocate_payouts(total_cents: int, weights: list[int]) -> list[int]:\n"
            "    s = sum(weights)\n"
            "    return [total_cents * w // s for w in weights]\n"
        ),
        "verified_fix_code": (
            "def allocate_payouts(total_cents: int, weights: list[int]) -> list[int]:\n"
            "    if not weights:\n"
            "        return []\n"
            "    total_weight = sum(weights)\n"
            "    if total_weight <= 0:\n"
            "        raise ValueError('Total weight must be positive')\n"
            "    base = [(total_cents * w) // total_weight for w in weights]\n"
            "    remainders = [((total_cents * w) % total_weight, -idx) for idx, w in enumerate(weights)]\n"
            "    shortfall = total_cents - sum(base)\n"
            "    for _, neg_idx in sorted(remainders, reverse=True)[:shortfall]:\n"
            "        base[-neg_idx] += 1\n"
            "    return base\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import allocate_payouts\n\n"
            "class TestExactLedger(unittest.TestCase):\n"
            "    def test_three_way_equal_split_preserves_sum(self):\n"
            "        res = allocate_payouts(100, [1, 1, 1])\n"
            "        self.assertEqual(res, [34, 33, 33])\n"
            "        self.assertEqual(sum(res), 100)\n"
            "    def test_weighted_remainder_tiebreak(self):\n"
            "        res = allocate_payouts(10, [1, 1, 1])\n"
            "        self.assertEqual(res, [4, 3, 3])\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "proportional allocation rounding",
            "domains": ["en.wikipedia.org"],
            "urls": ["https://en.wikipedia.org/wiki/Largest_remainder_method"],
            "migration_spec": "General overview of rounding methods.",
        },
    },
    {
        "id": "logic-04-kv-cache-eviction",
        "title": "KV-Cache Block Evictor: Pinned-Block & LRU Invariant",
        "category": "logic_invariant",
        "difficulty": "easy",
        "description": (
            "Fix `evict_kv_blocks(blocks, required_free)` so it never evicts blocks with `pinned=True` "
            "and evicts unpinned blocks in ascending order of `last_step`."
        ),
        "extra_files": {},
        "broken_code": (
            "def evict_kv_blocks(blocks: list[dict], required_free: int) -> list[str]:\n"
            "    sorted_b = sorted(blocks, key=lambda b: b['last_step'])\n"
            "    return [b['id'] for b in sorted_b[:required_free]]\n"
        ),
        "ungrounded_attempt_code": (
            "def evict_kv_blocks(blocks: list[dict], required_free: int) -> list[str]:\n"
            "    unpinned = [b for b in blocks if not b.get('pinned', False)]\n"
            "    return [b['id'] for b in unpinned[:required_free]]\n"
        ),
        "verified_fix_code": (
            "def evict_kv_blocks(blocks: list[dict], required_free: int) -> list[str]:\n"
            "    if required_free <= 0:\n"
            "        return []\n"
            "    unpinned = [b for b in blocks if not b.get('pinned', False)]\n"
            "    unpinned.sort(key=lambda b: (b['last_step'], b['id']))\n"
            "    if len(unpinned) < required_free:\n"
            "        raise MemoryError('Insufficient unpinned KV blocks')\n"
            "    return [b['id'] for b in unpinned[:required_free]]\n"
        ),
        "test_code": (
            "import unittest\n"
            "from solution import evict_kv_blocks\n\n"
            "class TestKVCacheEvictor(unittest.TestCase):\n"
            "    def test_skips_pinned_and_orders_by_lru(self):\n"
            "        blocks = [\n"
            "            {'id': 'b1', 'last_step': 1, 'pinned': True},\n"
            "            {'id': 'b2', 'last_step': 10, 'pinned': False},\n"
            "            {'id': 'b3', 'last_step': 3, 'pinned': False},\n"
            "            {'id': 'b4', 'last_step': 7, 'pinned': False},\n"
            "        ]\n"
            "        self.assertEqual(evict_kv_blocks(blocks, 2), ['b3', 'b4'])\n"
            "    def test_oom_when_not_enough_unpinned(self):\n"
            "        blocks = [{'id': 'b1', 'last_step': 1, 'pinned': True}]\n"
            "        with self.assertRaises(MemoryError):\n"
            "            evict_kv_blocks(blocks, 1)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "tavily_doc": {
            "query": "LRU cache eviction policy",
            "domains": ["en.wikipedia.org"],
            "urls": ["https://en.wikipedia.org/wiki/Cache_replacement_policies"],
            "migration_spec": "Standard LRU cache overview.",
        },
    },
]


def get_task_by_id(task_id: str) -> dict:
    for task in BENCHMARK_TASKS:
        if task["id"] == task_id:
            return task
    raise KeyError(f"Task '{task_id}' not found")
