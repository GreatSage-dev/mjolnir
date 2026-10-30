"""Vercel Serverless Function entry point for MJOLNIR API."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Resolve root directory
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Re-point server directory paths
import server

server.ROOT_DIR = ROOT_DIR
server.STATIC_DIR = ROOT_DIR / "static"
server.ARTIFACTS_DIR = ROOT_DIR / "artifacts"

from server import MjolnirRequestHandler


class handler(MjolnirRequestHandler):
    """Vercel serverless request handler inheriting MjolnirRequestHandler."""

    def _normalize_path(self) -> None:
        p = self.path
        if p.startswith("/api/index.py"):
            p = p[len("/api/index.py"):]
        if not p.startswith("/"):
            p = "/" + p
        if not p.startswith("/api") and p in {
            "/status",
            "/tasks",
            "/benchmark/latest",
            "/benchmark/live",
            "/benchmark/deterministic",
            "/race",
            "/run-custom",
            "/benchmark/run",
        }:
            p = "/api" + p
        self.path = p

    def do_GET(self) -> None:  # noqa: N802
        self._normalize_path()
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        self._normalize_path()
        super().do_POST()
