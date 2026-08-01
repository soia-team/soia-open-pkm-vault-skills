import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-extract-vault-knowledge/scripts/knowledge_manifest.py"


class ExtractVaultKnowledgeTests(unittest.TestCase):
    def run_cmd(self, vault, *args, check=True):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--vault", str(vault)],
            check=check, capture_output=True, text=True,
        )

    def test_plan_verify_and_source_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            source = vault / "30_日志与思考/审计.md"
            source.parent.mkdir(parents=True)
            source.write_text("# frozen evidence\n", encoding="utf-8")
            target = vault / "20_资料库/20_规范与手册/安全基线.md"
            self.run_cmd(
                vault, "plan", "--manifest", "30_日志与思考/plan.json",
                "--source", "30_日志与思考/审计.md",
                "--target", "20_资料库/20_规范与手册/安全基线.md",
                "--type", "checklist", "--sensitivity", "internal",
            )
            missing = self.run_cmd(vault, "verify", "--manifest", "30_日志与思考/plan.json", check=False)
            self.assertEqual(json.loads(missing.stdout)["issues"][0]["code"], "target_missing")
            target.parent.mkdir(parents=True)
            target.write_text(
                "---\ntags: [资料库, 长期知识, 安全]\ntitle: AI 安全基线\n"
                "type: checklist\nknowledge_state: stable\nsensitivity: internal\n"
                "created: 2026-08-01\nupdated: 2026-08-01\n"
                "source: \"[[30_日志与思考/审计]]\"\n---\n\n## 方法\n最小权限。\n",
                encoding="utf-8",
            )
            verified = self.run_cmd(vault, "verify", "--manifest", "30_日志与思考/plan.json")
            self.assertTrue(json.loads(verified.stdout)["verified"])
            source.write_text("drift\n", encoding="utf-8")
            drifted = self.run_cmd(vault, "verify", "--manifest", "30_日志与思考/plan.json", check=False)
            self.assertTrue(any(item["code"] == "source_drift" for item in json.loads(drifted.stdout)["issues"]))

    def test_target_collision_and_unsafe_path_are_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "source.md").write_text("source\n", encoding="utf-8")
            target = vault / "20_资料库/目标.md"
            target.parent.mkdir()
            target.write_text("existing\n", encoding="utf-8")
            planned = self.run_cmd(
                vault, "plan", "--manifest", "plan.json", "--source", "source.md",
                "--target", "20_资料库/目标.md",
            )
            self.assertFalse(json.loads(planned.stdout)["ready_to_write"])
            unsafe = self.run_cmd(
                vault, "plan", "--manifest", "other.json", "--source", "source.md",
                "--target", "../outside.md", check=False,
            )
            self.assertNotEqual(unsafe.returncode, 0)


if __name__ == "__main__":
    unittest.main()
