"""MJOLNIR: Autonomous Coding Agent & 2D Escalation Engine on Nebius Token Factory."""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "1.0.0"

_PLACEHOLDER_VALUES = {
    "",
    "your_nebius_token_factory_api_key_here",
    "tvly-your_tavily_api_key_here",
}


def load_dotenv_file(dotenv_path: Path | None = None) -> None:
    """Load key=value pairs from repo `.env` into `os.environ` without external deps."""
    if dotenv_path is None and os.environ.get("MJOLNIR_DISABLE_DOTENV") == "1":
        return
    target = dotenv_path or (Path(__file__).resolve().parent.parent / ".env")
    if not target.is_file():
        return
    try:
        for raw_line in target.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"').strip()
            if not key or val in _PLACEHOLDER_VALUES:
                continue
            if not os.environ.get(key):
                os.environ[key] = val
    except Exception:
        pass


load_dotenv_file()

