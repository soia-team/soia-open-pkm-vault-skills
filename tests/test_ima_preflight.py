import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-bootstrap-vault-ima/scripts/preflight_sync.py"


class ImaPreflightTests(unittest.TestCase):
    def run_preflight(self, vault, prefix, check=True):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(vault), "--path-prefix", prefix],
            check=check, capture_output=True, text=True,
        )

    def test_public_explicit_subdirectory_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            folder = vault / "20_资料库/10_主题知识/云端公开"
            folder.mkdir(parents=True)
            (folder / "方法.md").write_text(
                "---\ntags: [资料库, 长期知识]\nsensitivity: public\n---\n安全内容\n",
                encoding="utf-8",
            )
            payload = json.loads(self.run_preflight(vault, "20_资料库/10_主题知识/云端公开").stdout)
            self.assertTrue(payload["ready"])
            self.assertEqual(payload["sensitivity"], {"public": 1})

    def test_missing_private_secret_and_attachment_fail_without_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            folder = vault / "20_资料库/10_主题知识/候选"
            folder.mkdir(parents=True)
            (folder / "missing.md").write_text("no frontmatter\n", encoding="utf-8")
            (folder / "private.md").write_text("---\nsensitivity: private\n---\nprivate\n", encoding="utf-8")
            marker = "SECRET_MARKER_123456"
            (folder / "unsafe.md").write_text(
                f"---\nsensitivity: internal\n---\npassword: {marker}\n", encoding="utf-8"
            )
            (folder / "attachment.pdf").write_bytes(b"pdf")
            result = self.run_preflight(vault, "20_资料库/10_主题知识/候选", check=False)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(marker, result.stdout)
            codes = {item["code"] for item in json.loads(result.stdout)["issues"]}
            self.assertIn("missing_or_invalid_sensitivity", codes)
            self.assertIn("sensitivity_blocked:private", codes)
            self.assertIn("possible_secret_value", codes)
            self.assertIn("unclassified_non_markdown", codes)

    def test_broad_and_import_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "20_资料库/10_主题知识").mkdir(parents=True)
            broad = self.run_preflight(vault, "20_资料库", check=False)
            self.assertNotEqual(broad.returncode, 0)
            imported = self.run_preflight(vault, "20_资料库/10_融合分类/公开", check=False)
            self.assertNotEqual(imported.returncode, 0)


if __name__ == "__main__":
    unittest.main()
