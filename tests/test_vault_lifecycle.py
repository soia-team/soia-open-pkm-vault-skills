import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-manage-vault-lifecycle/scripts/vault_lifecycle.py"


class VaultLifecycleTests(unittest.TestCase):
    def run_cmd(self, vault, *args, check=True):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--vault", str(vault)],
            check=check, capture_output=True, text=True,
        )

    def test_plan_apply_verify_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "10_工作台").mkdir()
            source = vault / "10_工作台/task.md"
            source.write_text("---\nstatus: done\n---\n# Task\n", encoding="utf-8")
            (vault / "index.md").write_text("[[task]]\n", encoding="utf-8")
            manifest = "30_日志/manifest.json"
            result = self.run_cmd(vault, "plan", "--manifest", manifest, "--move", "10_工作台/task.md::90_归档/task.md")
            self.assertTrue(json.loads(result.stdout)["ready_to_apply"])
            data = json.loads((vault / manifest).read_text(encoding="utf-8"))
            self.assertEqual(data["actions"][0]["incoming_refs"], ["index.md"])
            self.run_cmd(vault, "apply", "--manifest", manifest)
            self.run_cmd(vault, "verify", "--manifest", manifest)
            self.run_cmd(vault, "rollback", "--manifest", manifest)
            self.assertTrue(source.is_file())

    def test_open_items_and_unknown_status_block_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "note.md").write_text("---\nstatus: 自定义\n---\n- [ ] open\n", encoding="utf-8")
            manifest = "manifest.json"
            result = self.run_cmd(vault, "plan", "--manifest", manifest, "--move", "note.md::archive/note.md")
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ready_to_apply"])
            applied = self.run_cmd(vault, "apply", "--manifest", manifest, check=False)
            self.assertNotEqual(applied.returncode, 0)

    def test_explicit_flags_allow_historical_items_and_preserve_unknown_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "note.md").write_text(
                "---\nstatus: public\n---\n- [ ] historical item\n", encoding="utf-8"
            )
            result = self.run_cmd(
                vault,
                "plan",
                "--manifest", "manifest.json",
                "--move", "note.md::archive/note.md",
                "--allow-open-items",
                "--allow-unknown-status",
            )
            payload = json.loads(result.stdout)
            manifest = json.loads((vault / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["ready_to_apply"])
            self.assertEqual(manifest["actions"][0]["status"], "public")
            self.assertEqual(manifest["actions"][0]["open_items"], 1)
            self.assertEqual(manifest["actions"][0]["blockers"], [])

    def test_conflict_and_path_escape_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "a.md").write_text("a", encoding="utf-8")
            (vault / "b.md").write_text("b", encoding="utf-8")
            blocked = self.run_cmd(vault, "plan", "--manifest", "m.json", "--move", "a.md::b.md")
            self.assertFalse(json.loads(blocked.stdout)["ready_to_apply"])
            escaped = self.run_cmd(vault, "plan", "--manifest", "m2.json", "--move", "a.md::../outside.md", check=False)
            self.assertNotEqual(escaped.returncode, 0)

    def test_existing_manifest_and_duplicate_paths_are_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "a.md").write_text("a", encoding="utf-8")
            manifest = vault / "manifest.json"
            manifest.write_text("preserve me\n", encoding="utf-8")
            existing = self.run_cmd(vault, "plan", "--manifest", "manifest.json", "--move", "a.md::x.md", check=False)
            self.assertNotEqual(existing.returncode, 0)
            self.assertEqual(manifest.read_text(encoding="utf-8"), "preserve me\n")

            manifest.unlink()
            duplicate = self.run_cmd(
                vault, "plan", "--manifest", "manifest.json",
                "--move", "a.md::one.md", "--move", "a.md::two.md",
            )
            payload = json.loads(duplicate.stdout)
            self.assertFalse(payload["ready_to_apply"])
            self.assertTrue(any("duplicate_source" in item for item in payload["blockers"]))

    def test_fixed_temp_symlink_does_not_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            vault.mkdir()
            outside = Path(temporary) / "outside.txt"
            outside.write_text("safe\n", encoding="utf-8")
            (vault / "a.md").write_text("a", encoding="utf-8")
            (vault / "manifest.json.tmp").symlink_to(outside)
            self.run_cmd(vault, "plan", "--manifest", "manifest.json", "--move", "a.md::archive/a.md")
            self.assertEqual(outside.read_text(encoding="utf-8"), "safe\n")

    def test_evidence_cannot_be_moved_into_knowledge(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            source = vault / "30_日志与思考/审计.md"
            source.parent.mkdir(parents=True)
            source.write_text("# evidence\n", encoding="utf-8")
            manifest = vault / "manifest.json"
            planned = self.run_cmd(
                vault,
                "plan", "--manifest", "manifest.json",
                "--move", "30_日志与思考/审计.md::20_资料库/方法.md",
            )
            payload = json.loads(planned.stdout)
            self.assertFalse(payload["ready_to_apply"])
            self.assertTrue(any("evidence_to_knowledge_requires_extract" in item for item in payload["blockers"]))

            tampered = json.loads(manifest.read_text(encoding="utf-8"))
            tampered["ready_to_apply"] = True
            manifest.write_text(json.dumps(tampered), encoding="utf-8")
            applied = self.run_cmd(vault, "apply", "--manifest", "manifest.json", check=False)
            self.assertNotEqual(applied.returncode, 0)
            self.assertTrue(source.is_file())

    def test_incoming_refs_do_not_confuse_same_basename_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "a").mkdir()
            (vault / "b").mkdir()
            (vault / "a/同名.md").write_text("a\n", encoding="utf-8")
            (vault / "b/同名.md").write_text("b\n", encoding="utf-8")
            (vault / "wrong.md").write_text("[[b/同名]]\n", encoding="utf-8")
            (vault / "short.md").write_text("[[同名]]\n", encoding="utf-8")
            (vault / "exact.md").write_text("[[a/同名]]\n", encoding="utf-8")
            self.run_cmd(
                vault, "plan", "--manifest", "manifest.json",
                "--move", "a/同名.md::archive/同名.md",
            )
            data = json.loads((vault / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(data["actions"][0]["incoming_refs"], ["exact.md", "short.md"])

    def test_plan_reads_moves_file_with_single_reference_index_and_batch_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "source/alpha").mkdir(parents=True)
            (vault / "source/beta").mkdir(parents=True)
            (vault / "source/alpha/a.md").write_text("# a\n", encoding="utf-8")
            (vault / "source/beta/b.md").write_text("# b\n", encoding="utf-8")
            (vault / "refs.md").write_text(
                "[[source/alpha/a]]\n[[source/beta/b]]\n", encoding="utf-8"
            )
            moves_file = vault / "moves.txt"
            moves_file.write_text(
                "# bulk plan\n"
                "source/alpha/a.md::archive/10_alpha/a.md\n"
                "\n"
                "source/beta/b.md::archive/20_beta/b.md\n",
                encoding="utf-8",
            )

            result = self.run_cmd(
                vault,
                "plan",
                "--manifest", "manifest.json",
                "--moves-file", str(moves_file),
            )
            payload = json.loads(result.stdout)
            data = json.loads((vault / "manifest.json").read_text(encoding="utf-8"))

            self.assertTrue(payload["ready_to_apply"])
            self.assertEqual(data["plan_type"], "moves-file")
            self.assertEqual(data["summary"]["actions"], 2)
            self.assertEqual(data["summary"]["reference_scan"]["markdown_files_scanned"], 3)
            self.assertEqual(
                [(batch["source"], batch["target"], batch["actions"])
                 for batch in data["summary"]["batches"]],
                [("alpha", "10_alpha", 1), ("beta", "20_beta", 1)],
            )
            self.assertEqual(data["actions"][0]["incoming_refs"], ["refs.md"])
            self.assertEqual(data["actions"][1]["incoming_refs"], ["refs.md"])
            self.assertTrue((vault / "source/alpha/a.md").is_file())
            self.assertFalse((vault / "archive/10_alpha/a.md").exists())

    def test_moves_file_preserves_trailing_spaces_in_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            source = vault / "source/name .md"
            source.parent.mkdir()
            source.write_text("# source\n", encoding="utf-8")
            moves_file = vault / "moves.txt"
            moves_file.write_text(
                "source/name .md::archive/name .md\n", encoding="utf-8"
            )

            self.run_cmd(
                vault,
                "plan",
                "--manifest", "manifest.json",
                "--moves-file", str(moves_file),
            )
            data = json.loads((vault / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(data["actions"][0]["source"], "source/name .md")
            self.assertEqual(data["actions"][0]["target"], "archive/name .md")

    def test_tree_plan_recursively_maps_files_without_applying(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "source/nested").mkdir(parents=True)
            (vault / "source/a.md").write_text("# a\n", encoding="utf-8")
            (vault / "source/nested/image.png").write_bytes(b"png")
            (vault / "index.md").write_text("[[source/a]]\n", encoding="utf-8")

            self.run_cmd(
                vault,
                "tree-plan",
                "--manifest", "manifest.json",
                "--source-root", "source",
                "--target-root", "archive/imported",
            )
            data = json.loads((vault / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(data["plan_type"], "tree")
            self.assertEqual(data["summary"]["actions"], 2)
            self.assertEqual(data["summary"]["source_root"], "source")
            self.assertEqual(data["summary"]["target_root"], "archive/imported")
            self.assertEqual(
                [(item["source"], item["target"]) for item in data["actions"]],
                [
                    ("source/a.md", "archive/imported/a.md"),
                    ("source/nested/image.png", "archive/imported/nested/image.png"),
                ],
            )
            self.assertTrue((vault / "source/a.md").is_file())
            self.assertTrue((vault / "source/nested/image.png").is_file())
            self.assertFalse((vault / "archive").exists())

    def test_tree_plan_rejects_overlapping_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary)
            (vault / "source").mkdir()
            (vault / "source/a.md").write_text("a\n", encoding="utf-8")
            result = self.run_cmd(
                vault,
                "tree-plan",
                "--manifest", "manifest.json",
                "--source-root", "source",
                "--target-root", "source/archive",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((vault / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
