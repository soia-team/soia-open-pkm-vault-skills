"""Smoke tests for a freshly scaffolded skill repository."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BaselineTest(unittest.TestCase):
    def run_tool(self, script: str, *args: str) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--root", str(ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_strict_audit(self) -> None:
        self.run_tool("audit_skills.py", "--strict")

    def test_catalog_is_current(self) -> None:
        self.run_tool("generate_skill_catalog.py", "--check")


if __name__ == "__main__":
    unittest.main()
