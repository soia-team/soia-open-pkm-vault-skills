#!/usr/bin/env python3
"""Verify a vault map and Bases database after a lifecycle change."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


SKIP = {".obsidian", ".git", ".trash", "node_modules", ".DS_Store"}
BASE_ROOT_RE = re.compile(r'file\.inFolder\("([^"]+)"\)')
MAP_STATS_RE = re.compile(r"全库约\s*([\d,]+)\s*文件\s*/\s*([\d,]+)\s*目录")
MAP_UPDATED_RE = re.compile(r"^updated:\s*([^\n]+)$", re.MULTILINE)


def vault_stats(vault: Path) -> tuple[int, int]:
    files = 0
    dirs = 0

    def walk(path: Path) -> None:
        nonlocal files, dirs
        try:
            entries = sorted(path.iterdir(), key=lambda item: item.name)
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink() or entry.name in SKIP or entry.name.startswith("."):
                continue
            if entry.is_dir():
                dirs += 1
                walk(entry)
            elif entry.is_file():
                files += 1

    walk(vault)
    return files, dirs


def confined(vault: Path, value: str) -> Path:
    path = (vault / value).resolve(strict=False)
    path.relative_to(vault)
    return path


def verify(args: argparse.Namespace) -> int:
    vault = Path(args.vault).expanduser().resolve(strict=True)
    errors: list[str] = []
    base = confined(vault, args.base)
    map_path = confined(vault, args.map)
    if not base.is_file():
        errors.append(f"base_missing:{args.base}")
        base_text = ""
    else:
        base_text = base.read_text(encoding="utf-8")
    base_roots = BASE_ROOT_RE.findall(base_text)
    if not base_roots:
        errors.append("base_has_no_file_inFolder")
    base_root_status = {}
    for value in base_roots:
        target = confined(vault, value)
        exists = target.is_dir()
        base_root_status[value] = exists
        if not exists:
            errors.append(f"base_root_missing:{value}")
    if not map_path.is_file():
        errors.append(f"map_missing:{args.map}")
        map_text = ""
    else:
        map_text = map_path.read_text(encoding="utf-8")
    if not MAP_UPDATED_RE.search(map_text):
        errors.append("map_missing_updated")
    files, dirs = vault_stats(vault)
    match = MAP_STATS_RE.search(map_text)
    map_stats = None
    if not match:
        errors.append("map_missing_stats")
    else:
        map_stats = {"files": int(match.group(1).replace(",", "")), "dirs": int(match.group(2).replace(",", ""))}
        if map_stats["files"] != files or map_stats["dirs"] != dirs:
            errors.append(f"map_stats_drift:map={map_stats['files']}/{map_stats['dirs']},actual={files}/{dirs}")
    result = {
        "verified": not errors,
        "vault": str(vault),
        "base": args.base,
        "map": args.map,
        "base_roots": base_root_status,
        "map_stats": map_stats,
        "actual_stats": {"files": files, "dirs": dirs},
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--base", default="20_资料库/资料库.base")
    parser.add_argument("--map", default="20_资料库/OB知识库地图.md")
    return verify(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
