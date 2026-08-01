import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "soia-pkm-maintain-vault-health" / "scripts"
MAP_SCRIPT = SCRIPT_DIR / "gen_vault_map.py"
sys.path.insert(0, str(SCRIPT_DIR))

from lint_vault import (  # noqa: E402
    DEFAULT_EXCLUDE,
    check_dead_links,
    clean_wikilink_target,
    collect_all_files,
    collect_md_files,
)


TEST_TAG = "资料库"


class CleanWikilinkTargetTests(unittest.TestCase):
    def test_alias_anchor_and_windows_paths(self):
        self.assertEqual(clean_wikilink_target(r"a\|b"), "a")
        self.assertEqual(clean_wikilink_target("a#heading|b"), "a")
        self.assertEqual(clean_wikilink_target("#heading"), "")
        self.assertEqual(clean_wikilink_target(r"folder\note|alias"), r"folder\note")


class DirectDeadLinkTests(unittest.TestCase):
    def test_table_alias_and_attachment_are_checked_against_real_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "一本书.md").write_text("# Book\n", encoding="utf-8")
            (vault / "图.png").write_bytes(b"png")
            (vault / "阅读.md").write_text(
                "[[一本书\\|书]] ![[图.png]] [[缺失.pdf]]\n", encoding="utf-8"
            )
            markdown = collect_md_files(str(vault))
            targets = collect_all_files(str(vault))
            dead = check_dead_links(str(vault), markdown, targets)
            self.assertEqual(dead, [("阅读.md", "缺失.pdf")])

    def test_hidden_paths_and_external_symlinks_are_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            outside = root / "outside.md"
            outside.write_text("[[private-target]]\n", encoding="utf-8")
            (vault / "linked.md").symlink_to(outside)
            hidden = vault / ".private"
            hidden.mkdir()
            (hidden / "secret.md").write_text("[[hidden-target]]\n", encoding="utf-8")
            self.assertEqual(collect_md_files(str(vault)), [])
            self.assertEqual(collect_all_files(str(vault)), [])

    def test_map_skips_symlink_tree_and_rejects_symlink_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            outside_dir = root / "outside"
            vault.mkdir()
            outside_dir.mkdir()
            (outside_dir / "private-name.md").write_text("private\n", encoding="utf-8")
            (vault / "linked-dir").symlink_to(outside_dir, target_is_directory=True)
            preview = root / "preview.md"
            subprocess.run(
                [sys.executable, str(MAP_SCRIPT), "--vault", str(vault), "--output", str(preview)],
                check=True, capture_output=True,
            )
            self.assertNotIn("private-name", preview.read_text(encoding="utf-8"))

            target = root / "outside-map.md"
            target.write_text("safe\n", encoding="utf-8")
            default = vault / DEFAULT_EXCLUDE[0]
            default.parent.mkdir(parents=True)
            default.symlink_to(target)
            rejected = subprocess.run(
                [sys.executable, str(MAP_SCRIPT), "--vault", str(vault)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "safe\n")


class LintConfigurationTests(unittest.TestCase):
    def run_lint(self, vault, config_text="", *args):
        config = vault / "config.yml"
        config.write_text(config_text, encoding="utf-8")
        env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("SOIA_") and key != "OBSIDIAN_VAULT"
        }
        env["HOME"] = str(vault)
        env["SOIA_PKM_VAULT_HEALTH_CONFIG_FILE"] = str(config)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "lint_vault.py"), "--vault", str(vault), "--json", *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return json.loads(result.stdout)

    def write_note(self, vault, name, tag=TEST_TAG, body=""):
        path = vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\ntags: [{tag}]\n---\n{body}", encoding="utf-8")

    def test_tag_policy_is_not_assumed(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "note.md", "CustomerTag")
            payload = self.run_lint(vault)
            self.assertFalse(payload["tag_policy_configured"])
            self.assertEqual(payload["summary"]["tag_drift"], 0)

    def test_configured_tags_apply_and_cli_overrides(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "configured.md", "Configured")
            self.write_note(vault, "command.md", "Command")
            payload = self.run_lint(vault, "env:\n  SOIA_LINT_TAGS: 'Configured'\n")
            self.assertTrue(payload["tag_policy_configured"])
            self.assertEqual(payload["tag_drift"], [{"file": "command.md", "tag": "Command"}])
            payload = self.run_lint(vault, "env:\n  SOIA_LINT_TAGS: 'Configured'\n", "--tags", "Command")
            self.assertEqual(payload["tag_drift"], [{"file": "configured.md", "tag": "Configured"}])

    def test_configured_exclude_and_cli_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "configured.md", body="[[missing-configured]]")
            self.write_note(vault, "command.md", body="[[missing-command]]")
            payload = self.run_lint(vault, "env:\n  SOIA_LINT_EXCLUDE: 'configured.md'\n")
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["command.md"])
            payload = self.run_lint(vault, "", "--exclude", "command.md")
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["configured.md"])

    def test_exclude_additions_extend_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, DEFAULT_EXCLUDE[0], body="[[missing-default]]")
            self.write_note(vault, "visible.md", body="[[missing-visible]]")
            payload = self.run_lint(vault)
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["visible.md"])

    def test_relative_wikilinks_and_code_spans(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "AGENTS.md")
            self.write_note(vault, "articles/2026/05/post.md")
            self.write_note(
                vault, "system/manual.md", body="[[../AGENTS]] [[../articles/2026/05/post]] `[[example]]`\n```yaml\n[[also-example]]\n```\n"
            )
            self.write_note(vault, "system/broken.md", body="[[../articles/2026/post]]")
            payload = self.run_lint(vault)
            dead = {(item["file"], item["target"]) for item in payload["dead_links"]}
            self.assertEqual(dead, {("system/broken.md", "../articles/2026/post")})


if __name__ == "__main__":
    unittest.main()
