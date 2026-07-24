#!/usr/bin/env python3
"""Contract tests for family-navigation staleness registration and checks."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (
    REPO_ROOT
    / "skills"
    / "soia-pkm-alipan-curator"
    / "scripts"
    / "check_family_nav_staleness.py"
)


def directory(parent: str, name: str, number: int) -> dict[str, object]:
    return {
        "path": parent,
        "name": name,
        "id": f"dir-{number}",
        "dir": True,
        "size": None,
    }


def file(
    parent: str, name: str, number: int, size: int, *, mtime: str | None = None
) -> dict[str, object]:
    row: dict[str, object] = {
        "path": parent,
        "name": name,
        "id": f"file-{number}",
        "dir": False,
        "size": size,
    }
    if mtime is not None:
        row["mtime"] = mtime
    return row


class CheckFamilyNavStalenessTests(unittest.TestCase):
    def write_scan(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def register(
        self,
        registry: Path,
        scan: Path,
        *,
        guide_id: str = "family-learning",
        generated_at: str = "2026-07-24T10:00:00+08:00",
    ) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "register",
            "--registry",
            str(registry),
            "--guide-id",
            guide_id,
            "--scope-root",
            "/family",
            "--scan",
            str(scan),
            "--nav-file-path",
            "/family/01_先看这里",
            "--generated-at",
            generated_at,
        )

    def check(
        self, registry: Path, scan: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "check",
            "--registry",
            str(registry),
            "--scan",
            str(scan),
            "--json",
            *extra,
        )

    def baseline_rows(self) -> list[dict[str, object]]:
        return [
            directory("/family", "10_数学", 1),
            file(
                "/family/10_数学",
                "第01课.mp4",
                2,
                100,
                mtime="2026-07-20T08:00:00+08:00",
            ),
            directory("/family", "01_先看这里", 3),
            file(
                "/family/01_先看这里",
                "01_家庭学习导航.xlsx",
                4,
                999,
                mtime="2026-07-24T10:00:00+08:00",
            ),
            directory("/other", "不相关", 5),
            file("/other/不相关", "ignore.bin", 6, 500),
        ]

    def test_register_filters_scope_and_excludes_navigation_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scan = root / "scan.jsonl"
            registry = root / "registry.json"
            self.write_scan(scan, self.baseline_rows())

            result = self.register(registry, scan)

            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(registry.read_text(encoding="utf-8"))
        self.assertEqual(
            document["guides"]["family-learning"]["fingerprint"],
            {
                "file_count": 1,
                "dir_count": 1,
                "total_size": 100,
                "max_mtime": "2026-07-20T08:00:00+08:00",
            },
        )

    def test_check_reports_fresh_for_same_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scan = root / "scan.jsonl"
            registry = root / "registry.json"
            self.write_scan(scan, self.baseline_rows())
            self.assertEqual(self.register(registry, scan).returncode, 0)

            result = self.check(registry, scan)

        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)["guides"][0]
        self.assertEqual(record["status"], "fresh")
        self.assertEqual(record["diff"], {})

    def test_check_reports_file_count_and_byte_changes_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_scan = root / "baseline.jsonl"
            current_scan = root / "current.jsonl"
            registry = root / "registry.json"
            self.write_scan(baseline_scan, self.baseline_rows())
            self.assertEqual(self.register(registry, baseline_scan).returncode, 0)
            changed = self.baseline_rows()
            changed.append(file("/family/10_数学", "第02课.mp4", 7, 200))
            self.write_scan(current_scan, changed)

            result = self.check(registry, current_scan)

        self.assertEqual(result.returncode, 1, result.stderr)
        record = json.loads(result.stdout)["guides"][0]
        self.assertEqual(record["status"], "stale")
        self.assertEqual(
            record["diff"]["file_count"], {"baseline": 1, "current": 2}
        )
        self.assertEqual(
            record["diff"]["total_size"], {"baseline": 100, "current": 300}
        )

    def test_check_reports_unknown_when_scan_does_not_cover_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_scan = root / "baseline.jsonl"
            unrelated_scan = root / "unrelated.jsonl"
            registry = root / "registry.json"
            self.write_scan(baseline_scan, self.baseline_rows())
            self.assertEqual(self.register(registry, baseline_scan).returncode, 0)
            self.write_scan(
                unrelated_scan,
                [directory("/other", "不相关", 10), file("/other/不相关", "x", 11, 1)],
            )

            result = self.check(registry, unrelated_scan)

        self.assertEqual(result.returncode, 2, result.stderr)
        record = json.loads(result.stdout)["guides"][0]
        self.assertEqual(record["status"], "unknown")
        self.assertIsNone(record["current"])
        self.assertIn("scan 未覆盖", record["diff"]["reason"])

    def test_register_overwrites_existing_guide(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_scan = root / "first.jsonl"
            second_scan = root / "second.jsonl"
            registry = root / "registry.json"
            self.write_scan(first_scan, self.baseline_rows())
            self.assertEqual(
                self.register(
                    registry,
                    first_scan,
                    generated_at="2026-07-23T10:00:00+08:00",
                ).returncode,
                0,
            )
            changed = self.baseline_rows()
            changed.append(file("/family/10_数学", "第02课.mp4", 7, 200))
            self.write_scan(second_scan, changed)

            result = self.register(
                registry,
                second_scan,
                generated_at="2026-07-24T11:00:00+08:00",
            )
            document = json.loads(registry.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        guide = document["guides"]["family-learning"]
        self.assertEqual(guide["generated_at"], "2026-07-24T11:00:00+08:00")
        self.assertEqual(guide["fingerprint"]["file_count"], 2)
        self.assertEqual(guide["fingerprint"]["total_size"], 300)
        self.assertEqual(len(document["guides"]), 1)

    def test_both_commands_reject_aggregated_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_scan = root / "baseline.jsonl"
            aggregate_scan = root / "aggregate.jsonl"
            registry = root / "registry.json"
            self.write_scan(baseline_scan, self.baseline_rows())
            self.assertEqual(self.register(registry, baseline_scan).returncode, 0)
            self.write_scan(
                aggregate_scan,
                [
                    {
                        **directory("/family", "聚合区", 20),
                        "agg_files": 10,
                        "agg_size": 1000,
                    }
                ],
            )

            register_result = self.register(registry, aggregate_scan)
            check_result = self.check(registry, aggregate_scan)

        self.assertEqual(register_result.returncode, 2)
        self.assertIn("aggregated", register_result.stderr)
        self.assertEqual(check_result.returncode, 2)
        self.assertIn("aggregated", check_result.stderr)
        self.assertNotIn("Traceback", register_result.stderr)
        self.assertNotIn("Traceback", check_result.stderr)

    def test_missing_registry_is_created_for_register_and_rejected_for_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scan = root / "scan.jsonl"
            registry = root / "missing" / "registry.json"
            other_registry = root / "absent.json"
            self.write_scan(scan, self.baseline_rows())

            register_result = self.register(registry, scan)
            registry_created = registry.exists()
            check_result = self.check(other_registry, scan)

        self.assertEqual(register_result.returncode, 0, register_result.stderr)
        self.assertTrue(registry_created)
        self.assertEqual(check_result.returncode, 2)
        self.assertIn("registry does not exist", check_result.stderr)
        self.assertNotIn("Traceback", check_result.stderr)


if __name__ == "__main__":
    unittest.main()
