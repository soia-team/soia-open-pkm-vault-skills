import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "soia-pkm-maintain" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from lint_vault import check_dead_links, clean_wikilink_target, collect_md_files  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
