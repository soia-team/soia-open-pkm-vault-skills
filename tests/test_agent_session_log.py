import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/soia-pkm-log-agent-sessions/scripts/session_log.py"


class AgentSessionLogTests(unittest.TestCase):
    def git(self, root, *args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    def run_log(self, vault, state, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("SOIA_") and key != "OBSIDIAN_VAULT"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(vault), "--agent", "Codex", "--state-dir", str(state), *args],
            check=True, capture_output=True, text=True, env=env,
        )
        return json.loads(result.stdout)

    def test_deduplicates_but_detects_second_edit_same_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            state = Path(temporary) / "state"
            root.mkdir()
            self.git(root, "init")
            (root / "note.md").write_text("one\n", encoding="utf-8")
            self.git(root, "add", "note.md")
            self.git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init")
            (root / "note.md").write_text("two\n", encoding="utf-8")
            first = self.run_log(root, state)
            self.assertTrue(first["written"])
            second = self.run_log(root, state)
            self.assertTrue(second["deduplicated"])
            (root / "note.md").write_text("three\n", encoding="utf-8")
            third = self.run_log(root, state)
            self.assertTrue(third["written"])
            logfile = next((root / "30_日志与思考").rglob("*.md"))
            text = logfile.read_text(encoding="utf-8")
            self.assertIn("tags: [Agent日志, 自动快照]", text)
            self.assertNotIn("two", text)
            self.assertNotIn("three", text)

    def test_dry_run_and_agent_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            self.git(root, "init")
            (root / "new.md").write_text("x", encoding="utf-8")
            payload = self.run_log(root, Path(temporary) / "state", "--dry-run")
            self.assertFalse(payload["written"])
            self.assertFalse((root / "30_日志与思考").exists())
            bad = subprocess.run([sys.executable, str(SCRIPT), "--vault", str(root), "--agent", "../bad"], capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)

    def test_nested_vault_is_rejected_without_logging_parent_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            vault = repo / "vault"
            vault.mkdir(parents=True)
            self.git(repo, "init")
            (repo / "private.txt").write_text("private\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--vault", str(vault), "--state-dir", str(Path(temporary) / "state")],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((vault / "30_日志与思考").exists())


if __name__ == "__main__":
    unittest.main()
