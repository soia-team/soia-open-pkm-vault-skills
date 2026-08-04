import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "skills/soia-pkm-bootstrap-vault-base/scripts/init_vault.py"
OBSIDIAN = ROOT / "skills/soia-pkm-bootstrap-vault-obsidian/scripts/configure_obsidian.py"
HEALTH = ROOT / "skills/soia-pkm-maintain-vault-health/scripts/lint_vault.py"


class BootstrapBaseTests(unittest.TestCase):
    def test_plan_apply_idempotence_and_no_obsidian(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            plan = subprocess.run([sys.executable, str(BASE), str(vault)], check=True, capture_output=True, text=True)
            self.assertFalse(vault.exists())
            self.assertTrue(json.loads(plan.stdout)["ready"])
            subprocess.run([sys.executable, str(BASE), str(vault), "--apply"], check=True, capture_output=True)
            self.assertTrue((vault / "AGENTS.md").is_file())
            self.assertTrue((vault / "00_Obsidian系统/AGENTS.md").is_file())
            self.assertTrue((vault / "10_工作台/00_Inbox/AGENTS.md").is_file())
            self.assertTrue((vault / "20_资料库/10_主题知识/AGENTS.md").is_file())
            self.assertTrue((vault / "20_资料库/20_规范与手册/AGENTS.md").is_file())
            self.assertTrue((vault / "20_资料库/30_学习指南/AGENTS.md").is_file())
            self.assertTrue((vault / "00_模板/资料库/长期知识模板.md").is_file())
            self.assertFalse(any(vault.rglob("*.base")))
            self.assertFalse((vault / ".obsidian").exists())
            marker = "\nCUSTOM\n"
            agents = vault / "AGENTS.md"
            agents.write_text(agents.read_text(encoding="utf-8") + marker, encoding="utf-8")
            subprocess.run([sys.executable, str(BASE), str(vault), "--apply"], check=True, capture_output=True)
            self.assertTrue(agents.read_text(encoding="utf-8").endswith(marker))
            checked = subprocess.run([sys.executable, str(BASE), str(vault), "--check"], check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(checked.stdout)["check_passed"])
            linted = subprocess.run(
                [sys.executable, str(HEALTH), "--vault", str(vault), "--json"],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(linted.stdout)["dead_links"], [])

    def test_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "bad.json"
            config.write_text(json.dumps({"schema_version": 2, "extends_default": False, "directories": ["../escape"], "files": []}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(BASE), str(root / "vault"), "--config", str(config)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_file_directory_plan_conflict_blocks_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            config = root / "conflict.json"
            config.write_text(json.dumps({
                "schema_version": 2,
                "extends_default": False,
                "directories": ["same/child"],
                "files": [{"path": "same", "content": "file\n"}],
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(BASE), str(vault), "--config", str(config), "--apply"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(vault.exists())

    def test_schema_v1_directory_parts_are_compatible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            config = root / "legacy.json"
            config.write_text(json.dumps({
                "schema_version": 1,
                "extends_default": False,
                "directories": [{"parts": ["10_Workbench", "00_Inbox"]}],
                "files": [],
            }), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(BASE), str(vault), "--config", str(config), "--apply"],
                check=True, capture_output=True,
            )
            self.assertTrue((vault / "10_Workbench/00_Inbox").is_dir())
            self.assertFalse((vault / "{'parts': ['10_Workbench', '00_Inbox']}").exists())


class BootstrapObsidianTests(unittest.TestCase):
    def test_dry_run_merge_apply_check_and_preserve_unknowns(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            obsidian = vault / ".obsidian"
            obsidian.mkdir(parents=True)
            (obsidian / "core-plugins.json").write_text('{"search":true,"sync":false}\n', encoding="utf-8")
            (obsidian / "appearance.json").write_text('{"cssTheme":"Custom","enabledCssSnippets":["mine"]}\n', encoding="utf-8")
            plan = subprocess.run([sys.executable, str(OBSIDIAN), str(vault), "--link-format", "relative"], check=True, capture_output=True, text=True)
            self.assertFalse((obsidian / "snippets/wide-page.css").exists())
            self.assertTrue(json.loads(plan.stdout)["ready"])
            applied = subprocess.run([sys.executable, str(OBSIDIAN), str(vault), "--link-format", "relative", "--apply"], check=True, capture_output=True, text=True)
            payload = json.loads(applied.stdout)
            self.assertGreaterEqual(payload["applied"]["backed_up"], 2)
            self.assertEqual(json.loads((obsidian / "core-plugins.json").read_text()), {"search": True, "sync": False, "bases": True})
            appearance = json.loads((obsidian / "appearance.json").read_text())
            self.assertEqual(appearance["cssTheme"], "Custom")
            self.assertEqual(appearance["enabledCssSnippets"], ["mine", "wide-page"])
            self.assertTrue((vault / "10_工作台/10_总控/工作台.base").is_file())
            self.assertTrue((vault / "20_资料库/资料库.base").is_file())
            self.assertTrue((vault / "90_系统归档/10_工作台历史/工作台历史.base").is_file())
            check = subprocess.run([sys.executable, str(OBSIDIAN), str(vault), "--link-format", "relative", "--check"], check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(check.stdout)["check_passed"])
            linted = subprocess.run(
                [sys.executable, str(HEALTH), "--vault", str(vault), "--json"],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(linted.stdout)["dead_links"], [])

    def test_css_drift_is_not_overwritten_without_force(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            css = vault / ".obsidian/snippets/wide-page.css"
            css.parent.mkdir(parents=True)
            css.write_text("customer css\n", encoding="utf-8")
            subprocess.run([sys.executable, str(OBSIDIAN), str(vault), "--apply"], check=True, capture_output=True)
            self.assertEqual(css.read_text(encoding="utf-8"), "customer css\n")

    def test_legacy_core_plugin_list_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            obsidian = vault / ".obsidian"
            obsidian.mkdir(parents=True)
            (obsidian / "core-plugins.json").write_text('["search"]\n', encoding="utf-8")
            subprocess.run(
                [sys.executable, str(OBSIDIAN), str(vault), "--no-enable-wide-page", "--apply"],
                check=True, capture_output=True,
            )
            self.assertEqual(json.loads((obsidian / "core-plugins.json").read_text()), ["search", "bases"])
            self.assertFalse((obsidian / "snippets/wide-page.css").exists())

    def test_temp_and_directory_symlinks_do_not_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            outside = root / "outside.txt"
            outside.write_text("safe\n", encoding="utf-8")
            config = root / "minimal.json"
            config.write_text(json.dumps({
                "schema_version": 2,
                "extends_default": False,
                "directories": [],
                "files": [{"path": "note.md", "content": "note\n", "mode": "create_only"}],
            }), encoding="utf-8")
            (vault / "note.md.tmp").symlink_to(outside)
            subprocess.run([sys.executable, str(BASE), str(vault), "--config", str(config), "--apply"], check=True, capture_output=True)
            self.assertEqual(outside.read_text(encoding="utf-8"), "safe\n")

            obsidian = vault / ".obsidian"
            obsidian.mkdir()
            (obsidian / "snippets").symlink_to(root)
            rejected = subprocess.run([sys.executable, str(OBSIDIAN), str(vault)], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(outside.read_text(encoding="utf-8"), "safe\n")


if __name__ == "__main__":
    unittest.main()
