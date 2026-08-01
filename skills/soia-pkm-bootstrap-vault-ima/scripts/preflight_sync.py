#!/usr/bin/env python3
"""Fail-closed privacy preflight for directory-based cloud sync allowlists."""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path


ALLOWED_SENSITIVITY = {"public", "internal"}
ALL_SENSITIVITY = ALLOWED_SENSITIVITY | {"private", "restricted"}
PRIVATE_PATH_RE = re.compile(r"(?:/[U]sers/|/[h]ome/[^/\s]+/)")
POSSIBLE_SECRET_RE = re.compile(
    r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|cookie)\b\s*[:=]\s*"
    r"(?!<|\{|YOUR_|EXAMPLE|example|placeholder|\*{4,}|x{4,}|null\b)[^\s#]{6,}"
)
SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules"}


def normalize(raw: str) -> str:
    value = raw.strip().replace("\\", "/").rstrip("/")
    parts = value.split("/")
    if not value or value.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe vault-relative allowlist path: {raw!r}")
    if len(parts) < 2 or parts[0].startswith("20_") and len(parts) < 3:
        raise ValueError(f"allowlist path is too broad: {raw!r}")
    if any("融合分类" in part or "历史导入" in part for part in parts):
        raise ValueError(f"historical/import path cannot be cloud-synced: {raw!r}")
    return "/".join(parts)


def confined(root: Path, rel: str) -> Path:
    cursor = root
    for part in Path(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"allowlist contains a symlink component: {rel}")
    path = (root / rel).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"allowlist escapes vault: {rel}") from exc
    if not path.is_dir():
        raise ValueError(f"allowlist is not a directory: {rel}")
    return path


def sensitivity(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    match = re.search(r"^sensitivity:[ \t]*(.*?)$", text[4:end], re.MULTILINE)
    return match.group(1).strip().strip('"\'') if match else None


def inspect(root: Path, prefixes: list[str]) -> dict:
    issues: list[dict[str, str]] = []
    distribution: Counter[str] = Counter()
    checked = 0
    for prefix in prefixes:
        folder = confined(root, prefix)
        for current, dirs, files in os.walk(folder, followlinks=False):
            kept = []
            for name in sorted(dirs):
                path = Path(current) / name
                rel = path.relative_to(root).as_posix()
                if path.is_symlink():
                    issues.append({"path": rel, "code": "symlink_present"})
                elif name not in SKIP_DIRS and not name.startswith("."):
                    kept.append(name)
            dirs[:] = kept
            for name in sorted(files):
                path = Path(current) / name
                rel = path.relative_to(root).as_posix()
                if name.startswith("."):
                    continue
                if path.is_symlink():
                    issues.append({"path": rel, "code": "symlink_present"})
                    continue
                checked += 1
                if path.suffix.lower() != ".md":
                    issues.append({"path": rel, "code": "unclassified_non_markdown"})
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    issues.append({"path": rel, "code": "unreadable"})
                    continue
                level = sensitivity(text)
                distribution[level or "missing"] += 1
                if level not in ALL_SENSITIVITY:
                    issues.append({"path": rel, "code": "missing_or_invalid_sensitivity"})
                elif level not in ALLOWED_SENSITIVITY:
                    issues.append({"path": rel, "code": f"sensitivity_blocked:{level}"})
                if PRIVATE_PATH_RE.search(text):
                    issues.append({"path": rel, "code": "private_absolute_path"})
                if POSSIBLE_SECRET_RE.search(text):
                    issues.append({"path": rel, "code": "possible_secret_value"})
    if not checked:
        issues.append({"path": ",".join(prefixes), "code": "empty_allowlist"})
    return {
        "ready": not issues,
        "allowlist": prefixes,
        "checked_files": checked,
        "sensitivity": dict(sorted(distribution.items())),
        "issues": issues,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--path-prefix", action="append", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.vault).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("vault is not a directory")
    prefixes = list(dict.fromkeys(normalize(raw) for raw in args.path_prefix))
    for index, left in enumerate(prefixes):
        for right in prefixes[index + 1:]:
            if left.startswith(right + "/") or right.startswith(left + "/"):
                raise ValueError(f"overlapping allowlist paths: {left!r}, {right!r}")
    payload = inspect(root, prefixes)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
