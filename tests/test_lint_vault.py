import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "soia-pkm-maintain" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from lint_vault import (  # noqa: E402
    DEFAULT_EXCLUDE,
    DEFAULT_TAGS,
    check_dead_links,
    clean_wikilink_target,
    collect_md_files,
)


class CleanWikilinkTargetTests(unittest.TestCase):
    def test_removes_escaped_table_alias_separator(self):
        self.assertEqual(clean_wikilink_target(r"a\|b"), "a")

    def test_removes_regular_alias(self):
        self.assertEqual(clean_wikilink_target("a|b"), "a")

    def test_removes_anchor(self):
        self.assertEqual(clean_wikilink_target("a#heading"), "a")

    def test_removes_anchor_and_alias(self):
        self.assertEqual(clean_wikilink_target("a#heading|b"), "a")

    def test_keeps_plain_target(self):
        self.assertEqual(clean_wikilink_target("a"), "a")

    def test_returns_empty_for_anchor_only_link(self):
        self.assertEqual(clean_wikilink_target("#heading"), "")

    def test_keeps_windows_path_backslashes(self):
        self.assertEqual(clean_wikilink_target(r"folder\note|alias"), r"folder\note")


class EscapedTableWikilinkLintTests(unittest.TestCase):
    def test_escaped_alias_in_table_is_not_a_dead_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "一本书看懂经济学.md").write_text("# Book\n", encoding="utf-8")
            (vault / "阅读记录.md").write_text(
                "| 书名 | 作者 | 状态 |\n"
                "| --- | --- | --- |\n"
                "| [[一本书看懂经济学\\|一本书看懂经济学]] | 庆裕 | 🔖 在读 |\n",
                encoding="utf-8",
            )

            files = collect_md_files(str(vault))
            self.assertEqual(check_dead_links(str(vault), files, files), [])


class LintConfigurationTests(unittest.TestCase):
    def run_lint(self, vault, config_text="", *args):
        config = vault / "config.yml"
        config.write_text(config_text, encoding="utf-8")
        env = os.environ.copy()
        env["SOIA_PKM_MAINTAIN_CONFIG_FILE"] = str(config)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "lint_vault.py"), "--vault", str(vault), "--json", *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return json.loads(result.stdout)

    def write_note(self, vault, name, tag, body=""):
        path = vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\ntags: [{tag}]\n---\n{body}", encoding="utf-8")

    def test_configured_tags_apply_and_cli_overrides_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "configured.md", "Configured")
            self.write_note(vault, "command.md", "Command")
            config = "env:\n  SOIA_LINT_TAGS: 'Configured'\n"

            payload = self.run_lint(vault, config)
            self.assertEqual(payload["summary"]["tag_drift"], 1)
            self.assertEqual(payload["tag_drift"][0]["tag"], "Command")

            payload = self.run_lint(vault, config, "--tags", "Command")
            self.assertEqual(payload["summary"]["tag_drift"], 1)
            self.assertEqual(payload["tag_drift"][0]["tag"], "Configured")

    def test_tag_additions_extend_defaults_and_cli_replaces_config_addition(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "default.md", DEFAULT_TAGS[0])
            self.write_note(vault, "config-add.md", "ConfiguredExtra")
            self.write_note(vault, "cli-add.md", "CliExtra")
            config = "env:\n  SOIA_LINT_TAGS_ADD: 'ConfiguredExtra'\n"

            payload = self.run_lint(vault, config)
            self.assertEqual(payload["summary"]["tag_drift"], 1)
            self.assertEqual(payload["tag_drift"][0]["tag"], "CliExtra")

            payload = self.run_lint(vault, config, "--tags-add", "CliExtra")
            self.assertEqual(payload["summary"]["tag_drift"], 1)
            self.assertEqual(payload["tag_drift"][0]["tag"], "ConfiguredExtra")

    def test_tags_fall_back_to_defaults_without_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "default.md", DEFAULT_TAGS[0])
            self.write_note(vault, "other.md", "Other")

            payload = self.run_lint(vault)
            self.assertEqual(payload["summary"]["tag_drift"], 1)
            self.assertEqual(payload["tag_drift"][0]["tag"], "Other")

    def test_configured_exclude_applies_and_cli_overrides_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, "configured.md", DEFAULT_TAGS[0], "[[missing-configured]]")
            self.write_note(vault, "command.md", DEFAULT_TAGS[0], "[[missing-command]]")
            config = "env:\n  SOIA_LINT_EXCLUDE: 'configured.md'\n"

            payload = self.run_lint(vault, config)
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["command.md"])

            payload = self.run_lint(vault, config, "--exclude", "command.md")
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["configured.md"])

    def test_exclude_additions_extend_defaults_and_cli_replaces_config_addition(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            self.write_note(vault, DEFAULT_EXCLUDE[0], DEFAULT_TAGS[0], "[[missing-default]]")
            self.write_note(vault, "config-add.md", DEFAULT_TAGS[0], "[[missing-config-add]]")
            self.write_note(vault, "cli-add.md", DEFAULT_TAGS[0], "[[missing-cli-add]]")
            config = "env:\n  SOIA_LINT_EXCLUDE_ADD: 'config-add.md'\n"

            payload = self.run_lint(vault, config)
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["cli-add.md"])

            payload = self.run_lint(vault, config, "--exclude-add", "cli-add.md")
            self.assertEqual([item["file"] for item in payload["dead_links"]], ["config-add.md"])


if __name__ == "__main__":
    unittest.main()
