from __future__ import annotations

from dataclasses import dataclass
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SUPPORTED_LANGUAGES = {"python"}
DEFAULT_TIMEOUT_SECONDS = 5


@dataclass
class TestResult:
    name: str
    passed: bool
    stdout: str
    stderr: str
    expected: str | None = None
    actual: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "expected": self.expected,
            "actual": self.actual,
            "error": self.error,
        }


def run_code(
    code: str,
    language: str = "python",
    tests: list[dict[str, Any]] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    language = language.lower().strip()
    if language not in SUPPORTED_LANGUAGES:
        return {
            "language": language,
            "passed": False,
            "results": [],
            "error": f"Unsupported language '{language}'. Python execution is available now.",
        }

    tests = tests or [{"name": "Run program", "code": ""}]
    results = [_run_python_test(code, test, timeout_seconds).to_dict() for test in tests]

    return {
        "language": language,
        "passed": all(result["passed"] for result in results),
        "results": results,
    }


def _run_python_test(code: str, test: dict[str, Any], timeout_seconds: int) -> TestResult:
    name = str(test.get("name") or "Unnamed test")
    test_code = str(test.get("code") or "")
    expected = test.get("expected")

    runner_code = code
    if test_code:
        runner_code = _build_python_runner(code, test_code)

    with tempfile.TemporaryDirectory(prefix="eureka_run_") as tmp_dir:
        path = Path(tmp_dir) / "main.py"
        path.write_text(runner_code, encoding="utf-8")

        try:
            completed = subprocess.run(
                [sys.executable, str(path)],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=max(1, timeout_seconds),
                env={"PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                name=name,
                passed=False,
                stdout="",
                stderr="",
                expected=str(expected) if expected is not None else None,
                error=f"Timed out after {timeout_seconds} seconds.",
            )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    passed = completed.returncode == 0
    actual = stdout

    if expected is not None:
        expected_text = str(expected).strip()
        passed = passed and stdout == expected_text
        return TestResult(
            name=name,
            passed=passed,
            stdout=stdout,
            stderr=stderr,
            expected=expected_text,
            actual=actual,
            error=None if passed else stderr or f"Expected {expected_text!r}, got {actual!r}.",
        )

    return TestResult(
        name=name,
        passed=passed,
        stdout=stdout,
        stderr=stderr,
        error=None if passed else stderr or "Program exited with an error.",
    )


def _build_python_runner(code: str, test_code: str) -> str:
    return f"""
{code}

# Test harness
import io as __eureka_io
import sys as __eureka_sys

__eureka_real_stdout = __eureka_sys.stdout
__eureka_capture = __eureka_io.StringIO()
__eureka_sys.stdout = __eureka_capture
try:
{_indent(test_code, "    ")}
finally:
    __eureka_sys.stdout = __eureka_real_stdout
    __eureka_output = __eureka_capture.getvalue()
    if __eureka_output:
        print(__eureka_output, end="")
"""


def _indent(code: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" if line else prefix.rstrip() for line in code.splitlines())
