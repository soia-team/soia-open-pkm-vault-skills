import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-manage-vault-lifecycle/scripts/vault_index_verify.py"


class VaultIndexVerifyTests(unittest.TestCase):
    def run_tool(self, vault: Path):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--vault", str(vault)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_base_and_map_are_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "20_资料库/10_主题知识").mkdir(parents=True)
            (vault / "20_资料库/20_规范与手册").mkdir(parents=True)
            (vault / "20_资料库/30_学习指南").mkdir(parents=True)
            (vault / "20_资料库/10_主题知识/知识.md").write_text("x\n", encoding="utf-8")
            (vault / "20_资料库/资料库.base").write_text(
                'filters:\n  - file.inFolder("20_资料库/10_主题知识")\n'
                '  - file.inFolder("20_资料库/20_规范与手册")\n'
                '  - file.inFolder("20_资料库/30_学习指南")\n',
                encoding="utf-8",
            )
            # Visible files: 2 (.base + map) plus the note; visible dirs: 4.
            (vault / "20_资料库/OB知识库地图.md").write_text(
                "---\nupdated: 2026-08-02\n---\n\n> 全库约 3 文件 / 4 目录 / 0.0GB。\n",
                encoding="utf-8",
            )
            result = self.run_tool(vault)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["verified"])

    def test_missing_base_root_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "20_资料库").mkdir(parents=True)
            (vault / "20_资料库/资料库.base").write_text(
                'filters:\n  - file.inFolder("20_资料库/20_不存在")\n', encoding="utf-8"
            )
            (vault / "20_资料库/OB知识库地图.md").write_text(
                "---\nupdated: 2026-08-02\n---\n\n> 全库约 2 文件 / 1 目录 / 0.0GB。\n", encoding="utf-8"
            )
            result = self.run_tool(vault)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("base_root_missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
