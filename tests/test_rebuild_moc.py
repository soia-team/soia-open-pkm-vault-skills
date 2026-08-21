"""Safety regressions for incremental and explicit full MOC synchronization."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "soia-pkm-organize-article-moc"
    / "scripts"
    / "rebuild_moc.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("rebuild_moc", SCRIPT)
assert SPEC and SPEC.loader
rebuild_moc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rebuild_moc
SPEC.loader.exec_module(rebuild_moc)


class RebuildMocTests(unittest.TestCase):
    def make_vault(self, root: Path, topics: list[str]) -> tuple[Path, Path, Path]:
        vault = root / "vault"
        articles = vault / "Articles"
        moc = articles / "_MOC"
        note = articles / "2026" / "08" / "new-note.md"
        note.parent.mkdir(parents=True)
        moc.mkdir(parents=True)
        (moc / ".categories.json").write_text(
            json.dumps({"Category": ["Known"]}, ensure_ascii=False), encoding="utf-8"
        )
        topic_yaml = ", ".join(f'"[[{topic}]]"' for topic in topics)
        note.write_text(
            "---\n"
            f"topics: [{topic_yaml}]\n"
            'captured_at: "2026-08-21 10:00"\n'
            "---\n\n"
            "# New title\n",
            encoding="utf-8",
        )
        return vault, moc, note

    def run_script(self, vault: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(vault), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_no_mode_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault, moc, _ = self.make_vault(Path(temporary), ["Known"])
            sentinel = moc / "manual.md"
            sentinel.write_text("keep", encoding="utf-8")
            result = self.run_script(vault)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_single_article_upserts_only_affected_mocs_and_preserves_existing_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault, moc, note = self.make_vault(Path(temporary), ["Known"])
            topic = moc / "Category" / "Known.md"
            topic.parent.mkdir(parents=True)
            topic.write_text(
                "---\ntags: [MOC]\ntopic: Known\nlevel: 2\n"
                'parent: "[[Category]]"\nupdated: 2026-08-20\n---\n\n'
                "# MOC · Known\n\n> 上级：[[Category]]\n\n"
                "## 文章列表（共 1 篇）\n\n"
                "- [[existing-note]] — Existing title\n\n"
                "## 手工说明\n\n"
                "保留这段人工内容。\n"
                "- [[manual-reference]] — This is not an article placement\n",
                encoding="utf-8",
            )
            parent = moc / "Category.md"
            parent.write_text(
                "---\ntags: [MOC]\ncategory: Category\nlevel: 1\n"
                "updated: 2026-08-20\n---\n\n# MOC · Category\n\n"
                "## Known（1 篇）→ [[Category/Known]]\n\n"
                "- [[existing-note]] — Existing title\n",
                encoding="utf-8",
            )

            result = self.run_script(vault, "--article", str(note))
            self.assertEqual(result.returncode, 0, result.stderr)
            topic_text = topic.read_text(encoding="utf-8")
            parent_text = parent.read_text(encoding="utf-8")
            self.assertIn("## 文章列表（共 2 篇）", topic_text)
            self.assertIn("[[new-note]] — New title", topic_text)
            self.assertIn("[[existing-note]] — Existing title", topic_text)
            self.assertIn("保留这段人工内容。", topic_text)
            self.assertIn("[[manual-reference]]", topic_text)
            self.assertIn("## Known（2 篇）", parent_text)
            self.assertIn("[[new-note]] — New title", parent_text)

            second = self.run_script(vault, "--article", str(note))
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(topic.read_text(encoding="utf-8").count("[[new-note]]"), 1)

    def test_unknown_topic_blocks_single_article_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault, moc, note = self.make_vault(Path(temporary), ["Unknown"])
            sentinel = moc / "manual.md"
            sentinel.write_text("keep", encoding="utf-8")
            result = self.run_script(vault, "--article", str(note))
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown topics", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_full_rebuild_preflight_blocks_unknown_topics_before_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault, moc, _ = self.make_vault(Path(temporary), ["Known", "Unknown"])
            sentinel = moc / "manual.md"
            sentinel.write_text("keep", encoding="utf-8")
            result = self.run_script(vault, "--full-rebuild")
            self.assertEqual(result.returncode, 2)
            self.assertIn("blocked before clearing", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_full_rebuild_dry_run_never_clears_moc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault, moc, _ = self.make_vault(Path(temporary), ["Known"])
            sentinel = moc / "manual.md"
            sentinel.write_text("keep", encoding="utf-8")
            result = self.run_script(vault, "--full-rebuild", "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("_MOC was not changed", result.stdout)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_explicit_full_rebuild_regenerates_known_topics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault, moc, _ = self.make_vault(Path(temporary), ["Known"])
            sentinel = moc / "obsolete.md"
            sentinel.write_text("obsolete", encoding="utf-8")
            result = self.run_script(vault, "--full-rebuild", "--date", "2026-08-21")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists())
            topic = (moc / "Category" / "Known.md").read_text(encoding="utf-8")
            parent = (moc / "Category.md").read_text(encoding="utf-8")
            self.assertIn("[[new-note]] — New title", topic)
            self.assertIn("## Known（1 篇）", parent)

    def test_staged_generation_failure_retains_live_moc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            live = Path(temporary) / "Articles" / "_MOC"
            live.mkdir(parents=True)
            sentinel = live / "manual.md"
            sentinel.write_text("keep", encoding="utf-8")
            rebuild_moc.MOC_DIR = live
            rebuild_moc.TODAY = "2026-08-21"
            with mock.patch.object(rebuild_moc, "generate_level2", side_effect=OSError("injected")):
                with self.assertRaisesRegex(OSError, "injected"):
                    rebuild_moc.full_rebuild_transaction({})
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(live.parent.glob("._MOC.*")), [])


if __name__ == "__main__":
    unittest.main()
