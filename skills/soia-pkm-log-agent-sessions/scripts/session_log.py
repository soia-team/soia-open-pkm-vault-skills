#!/usr/bin/env python3
"""Append a minimal, deduplicated git worktree snapshot to a vault log."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


AGENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NEW_CONFIG_ENV = "SOIA_PKM_AGENT_SESSION_CONFIG_FILE"
NEW_CONFIG = "~/.config/soia-skills/soia-pkm-log-agent-sessions/config.yml"
DEFAULT_LOG_DIR = "30_日志与思考/20_Agent工作日志/10_自动快照"


def parse_scalar(raw: str) -> str:
    value = raw.strip().split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def load_config() -> Path | None:
    candidates = []
    if os.environ.get(NEW_CONFIG_ENV):
        candidates.append(Path(os.environ[NEW_CONFIG_ENV]).expanduser())
    candidates.append(Path(NEW_CONFIG).expanduser())
    for path in candidates:
        if not path.is_file():
            continue
        in_env = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent == 0:
                in_env = stripped == "env:"
                continue
            if not in_env or indent < 2 or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            if KEY_RE.fullmatch(key):
                os.environ.setdefault(key, parse_scalar(value))
        return path
    return None


def confined(root: Path, rel: str) -> Path:
    value = Path(rel)
    if value.is_absolute() or not rel or rel in {".", ".."}:
        raise ValueError("log-dir must be a non-empty vault-relative path")
    cursor = root
    for part in value.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("log-dir contains a symlink")
    result = (root / value).resolve(strict=False)
    try:
        result.relative_to(root)
    except ValueError as exc:
        raise ValueError("log-dir escapes vault") from exc
    return result


def run_git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return result.stdout


def status_entries(root: Path, log_rel: str) -> list[tuple[str, str]]:
    output = run_git(root, "-c", "core.quotepath=false", "status", "--porcelain=v1", "--untracked-files=all").decode("utf-8", "replace")
    entries = []
    prefix = log_rel.strip("/") + "/"
    for line in output.splitlines():
        if len(line) < 4:
            continue
        code, raw_path = line[:2], line[3:]
        path = raw_path.rsplit(" -> ", 1)[-1]
        if path == log_rel or path.startswith(prefix):
            continue
        entries.append((code, path))
    return entries


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: Path, log_rel: str) -> tuple[str, list[tuple[str, str]]]:
    entries = status_entries(root, log_rel)
    digest = hashlib.sha256()
    for code, rel in entries:
        digest.update(code.encode())
        digest.update(b"\0")
        digest.update(rel.encode("utf-8", "surrogateescape"))
        path = (root / rel).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            digest.update(file_hash(path).encode())
        digest.update(b"\0")
    pathspec = f":(exclude){log_rel}"
    digest.update(run_git(root, "diff", "--binary", "--no-ext-diff", "--", ".", pathspec))
    digest.update(run_git(root, "diff", "--cached", "--binary", "--no-ext-diff", "--", ".", pathspec))
    return digest.hexdigest(), entries


def state_file(root: Path, agent: str, explicit: str | None) -> Path:
    if explicit:
        state_root = Path(explicit).expanduser().resolve(strict=False)
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        state_root = Path(xdg).expanduser() if xdg else Path.home() / ".local/state"
        state_root = state_root / "soia-pkm-log-agent-sessions"
    vault_id = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    return state_root / vault_id / f"{agent}.state"


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def append_log(path: Path, agent: str, entries: list[tuple[str, str]], include_paths: bool) -> None:
    now = dt.datetime.now().astimezone()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "tags: [Agent日志, 自动快照]\n"
            f"title: {agent} 会话改动日志 - {now.date().isoformat()}\n"
            f"agent: {agent}\n"
            f"date: {now.date().isoformat()}\n"
            "---\n\n"
            f"# {agent} 会话改动日志 ({now.date().isoformat()})\n",
            encoding="utf-8",
        )
    zones = Counter(rel.split("/", 1)[0] if "/" in rel else "<vault-root>" for _, rel in entries)
    lines = ["", f"## {now.strftime('%H:%M:%S')} 会话结束快照", "", f"- changed: {len(entries)}", "- by_zone:"]
    lines.extend(f"  - {name}: {count}" for name, count in sorted(zones.items()))
    if include_paths:
        lines.extend(["- paths:", *[f"  - `{code} {rel}`" for code, rel in entries]])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT"))
    parser.add_argument("--agent", default="Claude-Code")
    parser.add_argument("--log-dir", default=os.environ.get("SOIA_SESSION_LOG_DIR", DEFAULT_LOG_DIR))
    parser.add_argument("--state-dir", default=os.environ.get("SOIA_SESSION_STATE_DIR"))
    parser.add_argument("--include-paths", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.vault:
        raise ValueError("missing --vault or OBSIDIAN_VAULT")
    if not AGENT_RE.fullmatch(args.agent):
        raise ValueError("agent must be a safe 1-64 character slug")
    root = Path(args.vault).expanduser().resolve(strict=True)
    git_root = Path(run_git(root, "rev-parse", "--show-toplevel").decode("utf-8", "replace").strip()).resolve(strict=True)
    if git_root != root:
        raise ValueError("vault must be the Git worktree root; nested vault paths are not supported")
    log_root = confined(root, args.log_dir)
    log_rel = log_root.relative_to(root).as_posix()
    digest, entries = snapshot(root, log_rel)
    state = state_file(root, args.agent, args.state_dir)
    previous = state.read_text(encoding="utf-8").strip() if state.is_file() else None
    result = {"agent": args.agent, "changed": len(entries), "dry_run": args.dry_run, "deduplicated": False, "written": False, "log_dir": log_rel}
    if not entries:
        print(json.dumps(result))
        return 0
    if previous == digest:
        result["deduplicated"] = True
        print(json.dumps(result))
        return 0
    if args.dry_run:
        print(json.dumps(result))
        return 0
    today = dt.date.today()
    logfile = confined(root, f"{log_rel}/{today.year}/{args.agent}/{today.isoformat()}.md")
    append_log(logfile, args.agent, entries, args.include_paths)
    atomic_text(state, digest)
    result["written"] = True
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
