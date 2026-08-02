import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-manage-vault-lifecycle/scripts/vault_structure_plan.py"


class VaultStructurePlanTests(unittest.TestCase):
    def run_tool(self, vault: Path, manifest: str, command: str, *extra: str):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), command, "--vault", str(vault), "--manifest", manifest, *extra],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_plan_apply_verify_numbers_semantic_dirs_and_deletes_safe_empty_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            scope = vault / "20_资料库/90_历史导入/10_主题"
            (scope / "1.旧格式").mkdir(parents=True)
            (scope / "未编号").mkdir()
            (scope / "未编号/.metion").mkdir()
            (scope / "2021").mkdir()
            (scope / "_resources").mkdir()
            (scope / "1.旧格式/说明.md").write_text("stable\n", encoding="utf-8")
            (scope / "未编号/资料.md").write_text("content\n", encoding="utf-8")
            (scope / "未编号/.metion/file_sort.config").write_text("state\n", encoding="utf-8")
            (scope / "2021/日记.md").write_text("date\n", encoding="utf-8")
            (scope / "_resources/image.png").write_bytes(b"png")
            (scope / "空.md").write_text("---\ntags: [资料库]\n---\n", encoding="utf-8")
            cleanup = vault / "20_资料库/10_融合分类/旧"
            cleanup.mkdir(parents=True)
            (cleanup / ".DS_Store").write_bytes(b"metadata")
            root_metadata = vault / "20_资料库/.DS_Store"
            root_metadata.write_bytes(b"root metadata")
            (cleanup / "空目录").mkdir()
            manifest = "run/structure.json"
            plan = self.run_tool(
                vault,
                manifest,
                "plan",
                "--scope",
                "20_资料库/90_历史导入",
                "--cleanup-root",
                "20_资料库/10_融合分类",
                "--cleanup-file",
                "20_资料库/.DS_Store",
            )
            payload = json.loads(plan.stdout)
            self.assertTrue(payload["ready_to_apply"])
            data = json.loads((vault / manifest).read_text(encoding="utf-8"))
            self.assertGreaterEqual(data["summary"]["directory_renames"], 2)
            self.assertGreaterEqual(data["summary"]["delete_files"], 2)
            self.run_tool(vault, manifest, "apply")
            verified = json.loads(self.run_tool(vault, manifest, "verify").stdout)
            self.assertTrue(verified["verified"])
            self.assertTrue((scope / "10_旧格式/说明.md").is_file())
            self.assertTrue((scope / "20_未编号/资料.md").is_file())
            self.assertTrue((scope / "20_未编号/.metion/file_sort.config").is_file())
            self.assertTrue((scope / "2021/日记.md").is_file())
            self.assertFalse((scope / "空.md").exists())
            self.assertFalse((cleanup / ".DS_Store").exists())
            self.assertFalse(root_metadata.exists())
            self.assertFalse((cleanup / "空目录").exists())


if __name__ == "__main__":
    unittest.main()
