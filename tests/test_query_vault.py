import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-query-vault/scripts/query_vault.py"


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


class QueryVaultTests(unittest.TestCase):
    def run_query(self, vault, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(vault), *args, "--json"], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_chinese_ranking_frontmatter_backlinks_and_no_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            for zone in ("10_工作台", "20_资料库", "30_日志", "90_归档"):
                (vault / zone).mkdir()
            (vault / "10_工作台/当前.md").write_text("---\ntags: [工作台]\nstatus: active\n---\n知识库重构\n", encoding="utf-8")
            (vault / "20_资料库/方法.md").write_text("---\ntags: [资料库]\n---\n知识库方法 [[当前]]\n", encoding="utf-8")
            (vault / "90_归档/旧.md").write_text("知识库旧状态\n", encoding="utf-8")
            before = tree_hash(vault)
            payload = self.run_query(vault, "--query", "知识库")
            self.assertEqual(payload["matches"][0]["layer"], "current")
            self.assertEqual(before, tree_hash(vault))
            tags = self.run_query(vault, "--mode", "tag", "--query", "资料库")
            self.assertEqual(tags["matches"][0]["path"], "20_资料库/方法.md")
            fm = self.run_query(vault, "--mode", "frontmatter", "--field", "status", "--query", "active")
            self.assertEqual(fm["match_count"], 1)
            links = self.run_query(vault, "--mode", "backlinks", "--query", "当前")
            self.assertEqual(links["matches"][0]["path"], "20_资料库/方法.md")

    def test_truncation_and_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            for index in range(3):
                (vault / f"n{index}.md").write_text("same\n", encoding="utf-8")
            payload = self.run_query(vault, "--query", "same", "--limit", "2")
            self.assertTrue(payload["truncated"])
            inventory = self.run_query(vault, "--mode", "inventory")
            self.assertEqual(inventory["scanned_files"], 3)
            self.assertEqual(inventory["inventory"]["zones"]["<vault-root>"], 3)
            self.assertEqual(inventory["inventory"]["extensions"][".md"], 3)

    def test_external_symlink_is_not_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            outside = root / "private.md"
            outside.write_text("EXTERNAL_SECRET_MARKER\n", encoding="utf-8")
            (vault / "linked.md").symlink_to(outside)
            payload = self.run_query(vault, "--query", "EXTERNAL_SECRET_MARKER")
            self.assertEqual(payload["match_count"], 0)

    def test_path_filters_multiline_tags_and_no_snippets(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            curated = vault / "20_资料库/10_主题知识"
            imported = vault / "20_资料库/10_融合分类"
            curated.mkdir(parents=True)
            imported.mkdir(parents=True)
            (curated / "方法.md").write_text(
                "---\ntags:\n  - 资料库\n  - 长期知识\n---\npassword policy: rotate safely\n",
                encoding="utf-8",
            )
            (imported / "旧记录.md").write_text("password value: PRIVATE_VALUE\n", encoding="utf-8")

            tagged = self.run_query(vault, "--mode", "tag", "--query", "长期知识")
            self.assertEqual(tagged["match_count"], 1)
            self.assertEqual(tagged["matches"][0]["layer"], "stable")

            imported_result = self.run_query(
                vault,
                "--query", "PRIVATE_VALUE",
                "--path-prefix", "20_资料库/10_融合分类",
                "--no-snippets",
            )
            self.assertEqual(imported_result["match_count"], 1)
            self.assertEqual(imported_result["matches"][0]["layer"], "imported")
            self.assertIsNone(imported_result["matches"][0]["snippet"])

            scoped = self.run_query(
                vault,
                "--query", "password",
                "--path-prefix", "20_资料库",
                "--exclude-prefix", "20_资料库/10_融合分类",
                "--no-snippets",
            )
            self.assertEqual(scoped["match_count"], 1)
            self.assertEqual(scoped["matches"][0]["path"], "20_资料库/10_主题知识/方法.md")
            self.assertIsNone(scoped["matches"][0]["snippet"])
            self.assertFalse(scoped["snippets"])

            inventory = self.run_query(
                vault, "--mode", "inventory", "--path-prefix", "20_资料库/10_主题知识"
            )
            self.assertEqual(inventory["scanned_files"], 1)

    def test_unsafe_path_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", temporary, "--query", "x", "--path-prefix", "../outside", "--json"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_path_backlink_does_not_match_same_basename_elsewhere(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "a").mkdir()
            (vault / "b").mkdir()
            (vault / "a/同名.md").write_text("a\n", encoding="utf-8")
            (vault / "b/同名.md").write_text("b\n", encoding="utf-8")
            (vault / "链接.md").write_text("[[b/同名]]\n", encoding="utf-8")
            exact = self.run_query(vault, "--mode", "backlinks", "--query", "a/同名")
            self.assertEqual(exact["match_count"], 0)
            basename = self.run_query(vault, "--mode", "backlinks", "--query", "同名")
            self.assertEqual(basename["match_count"], 0)
            other = self.run_query(vault, "--mode", "backlinks", "--query", "b/同名")
            self.assertEqual(other["matches"][0]["path"], "链接.md")

    def test_requirement_and_code_files_are_searchable(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            requirement = vault / "20_资料库/20_规范与手册/接口需求.yaml"
            source = vault / "60_开源项目/示例项目/PolicyController.java"
            unusual = vault / "60_开源项目/示例项目/验收.feature"
            requirement.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            requirement.write_text("acceptance: policy detail returns R.SUCC\n", encoding="utf-8")
            source.write_text("@RequestMapping(\"/policy\")\nclass PolicyController {}\n", encoding="utf-8")
            unusual.write_text("Scenario: policy detail\n", encoding="utf-8")

            yaml_result = self.run_query(vault, "--mode", "content", "--query", "R.SUCC")
            self.assertEqual(yaml_result["matches"][0]["path"], "20_资料库/20_规范与手册/接口需求.yaml")

            java_result = self.run_query(vault, "--mode", "content", "--query", "@RequestMapping")
            self.assertEqual(java_result["matches"][0]["path"], "60_开源项目/示例项目/PolicyController.java")

            feature_result = self.run_query(
                vault, "--mode", "content", "--query", "Scenario", "--include-ext", ".feature"
            )
            self.assertEqual(feature_result["matches"][0]["path"], "60_开源项目/示例项目/验收.feature")
            self.assertIn(".java", feature_result["searchable_extensions"])
            self.assertIn(".feature", feature_result["searchable_extensions"])


if __name__ == "__main__":
    unittest.main()
