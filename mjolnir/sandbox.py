"""Deterministic Sandbox & Anti-Cheat Test Verifier for MJOLNIR.

Enforces:
1. Read-only test lock + SHA-256 integrity check (prevents reward hacking / test deletion).
2. Subprocess timeout governor (prevents infinite hangs).
3. 3-line structural error distillation (eliminates terminal context bloat).
4. Deterministic classification: KNOWLEDGE_GAP (API/symbol drift) vs REASONING_GAP (logic bug).
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


KNOWLEDGE_GAP = "KNOWLEDGE_GAP"
REASONING_GAP = "REASONING_GAP"
SYNTAX_GAP = "SYNTAX_GAP"
NONE_GAP = "NONE"


@dataclass
class ErrorReceipt:
    """3-line structural error distillation from a sandbox execution."""

    error_type: str
    error_message: str
    failing_location: str
    missing_symbol: str
    diagnostic_category: str
    distilled_3_lines: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SandboxReceipt:
    """Immutable deterministic receipt produced by running code against locked tests."""

    passed: bool
    exit_code: int
    duration_ms: float
    test_integrity_verified: bool
    test_sha256: str
    patch_sha256: str
    unified_diff: str
    raw_stdout: str
    raw_stderr: str
    error_receipt: Optional[ErrorReceipt]

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.error_receipt is not None:
            data["error_receipt"] = self.error_receipt.to_dict()
        return data


def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_unified_diff(original_code: str, patched_code: str, filename: str = "solution.py") -> str:
    orig_lines = original_code.splitlines(keepends=True)
    patch_lines = patched_code.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        patch_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )
    return "".join(diff)


def classify_and_distill_error(stderr_text: str, stdout_text: str) -> ErrorReceipt:
    """Distill noisy test runner output into a 3-line receipt and classify the root gap."""
    combined = (stderr_text or "") + "\n" + (stdout_text or "")
    lines = [line.strip() for line in combined.splitlines() if line.strip()]

    # Locate Python exception line (e.g. AttributeError: ..., ImportError: ..., AssertionError: ...)
    exc_pattern = re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning)):\s*(.*)$"
    )
    error_type = "RuntimeError"
    error_message = "Test suite exited with non-zero status"

    for line in reversed(lines):
        match = exc_pattern.match(line)
        if match:
            error_type = match.group(1)
            error_message = match.group(2).strip()
            break

    # Locate file & line number in traceback
    loc_pattern = re.compile(r'File "([^"]+)", line (\d+), in ([A-Za-z0-9_<>\-]+)')
    locations = loc_pattern.findall(combined)
    if locations:
        fname, lineno, func = locations[-1]
        base_fname = os.path.basename(fname)
        failing_location = f"{base_fname}:L{lineno} in {func}"
    else:
        failing_location = "solution.py:L1"

    # Extract missing/deprecated symbol if present
    missing_symbol = ""
    sym_patterns = [
        r"has no attribute '([^']+)'",
        r"cannot import name '([^']+)'",
        r"No module named '([^']+)'",
        r"got an unexpected keyword argument '([^']+)'",
        r"missing \d+ required positional argument[s]?: '([^']+)'",
        r"'([^']+)' is deprecated",
        r"DeprecatedAPIError:\s*([^\s:]+)",
    ]
    for pat in sym_patterns:
        m = re.search(pat, error_message)
        if m:
            missing_symbol = m.group(1)
            break

    # Deterministic classification rule:
    # Knowledge Gap: API/symbol/signature mismatch (AttributeError, ImportError, ModuleNotFoundError,
    # DeprecationWarning, or unexpected keyword argument TypeError).
    # Reasoning Gap: AssertionError, ValueError, IndexError, KeyError, ZeroDivisionError (logic/edge-case).
    knowledge_exceptions = {
        "AttributeError",
        "ImportError",
        "ModuleNotFoundError",
        "DeprecationWarning",
        "DeprecatedAPIError",
    }
    if error_type in knowledge_exceptions:
        category = KNOWLEDGE_GAP
    elif error_type == "TypeError" and (
        "unexpected keyword argument" in error_message
        or "required positional argument" in error_message
        or "takes " in error_message
    ):
        category = KNOWLEDGE_GAP
    elif error_type in {"SyntaxError", "IndentationError"}:
        category = SYNTAX_GAP
    else:
        category = REASONING_GAP

    distilled = (
        f"LOCATION : {failing_location}\n"
        f"FAILURE  : {error_type}: {error_message}\n"
        f"DIAGNOSIS: {category}"
        + (f" (symbol='{missing_symbol}')" if missing_symbol else "")
    )

    return ErrorReceipt(
        error_type=error_type,
        error_message=error_message,
        failing_location=failing_location,
        missing_symbol=missing_symbol,
        diagnostic_category=category,
        distilled_3_lines=distilled,
    )


def run_in_locked_sandbox(
    original_code: str,
    candidate_code: str,
    test_code: str,
    timeout_sec: float = 6.0,
    extra_files: Optional[dict[str, str]] = None,
) -> SandboxReceipt:
    """Execute candidate_code against a strictly locked test_code in an isolated directory.

    Verifies SHA-256 of test_code before and after execution so the candidate code
    can never tamper with or overwrite the test suite.
    """
    expected_test_sha = compute_sha256(test_code)
    patch_sha = compute_sha256(candidate_code)
    u_diff = compute_unified_diff(original_code, candidate_code, "solution.py")

    temp_dir = tempfile.mkdtemp(prefix="mjolnir_sbx_")
    temp_root = Path(temp_dir).resolve()
    try:
        sol_path = temp_root / "solution.py"
        test_path = temp_root / "test_solution.py"

        if extra_files:
            for rel_name, file_body in extra_files.items():
                if not rel_name or os.path.isabs(rel_name):
                    raise ValueError(f"Invalid sandbox extra_files path: {rel_name!r}")
                target = (temp_root / rel_name).resolve()
                if not target.is_relative_to(temp_root) or target.name in {"test_solution.py", "solution.py"}:
                    raise ValueError(f"Disallowed sandbox extra_files target: {rel_name!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(file_body.encode("utf-8"))

        sol_path.write_bytes(candidate_code.encode("utf-8"))
        test_path.write_bytes(test_code.encode("utf-8"))

        # Lock test_solution.py as read-only
        os.chmod(test_path, stat.S_IREAD)

        t0 = time.perf_counter()
        proc = subprocess.Popen(
            [sys.executable, str(test_path)],
            cwd=str(temp_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "PYTHONPATH": str(temp_root),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        try:
            out_bytes, err_bytes = proc.communicate(timeout=timeout_sec)
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            exit_code = proc.returncode
            stdout_str = out_bytes.decode("utf-8", errors="replace")
            stderr_str = err_bytes.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            proc.kill()
            out_bytes, _ = proc.communicate()
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            exit_code = 124
            stdout_str = out_bytes.decode("utf-8", errors="replace") if out_bytes else ""
            stderr_str = f"TimeoutError: Execution exceeded {timeout_sec}s governor limit"

        # Verify test file integrity after execution (Anti-Cheat Check on raw bytes + symlink guard)
        if test_path.exists() and test_path.is_file() and not test_path.is_symlink():
            actual_test_sha = hashlib.sha256(test_path.read_bytes()).hexdigest()
            integrity_ok = actual_test_sha == expected_test_sha
        else:
            integrity_ok = False

        if not integrity_ok:
            exit_code = 99
            stderr_str += "\nSecurityViolationError: Candidate attempted to modify locked test file."

        passed = (exit_code == 0) and integrity_ok
        err_receipt = (
            None if passed else classify_and_distill_error(stderr_str, stdout_str)
        )

        return SandboxReceipt(
            passed=passed,
            exit_code=exit_code,
            duration_ms=duration_ms,
            test_integrity_verified=integrity_ok,
            test_sha256=expected_test_sha[:16],
            patch_sha256=patch_sha[:16],
            unified_diff=u_diff,
            raw_stdout=stdout_str,
            raw_stderr=stderr_str,
            error_receipt=err_receipt,
        )
    finally:
        # Restore write permission on test_path so tempdir cleanup succeeds on Windows
        try:
            test_path = Path(temp_dir) / "test_solution.py"
            if test_path.exists():
                os.chmod(test_path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        shutil.rmtree(temp_dir, ignore_errors=True)
