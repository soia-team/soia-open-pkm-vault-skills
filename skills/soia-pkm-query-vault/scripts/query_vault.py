#!/usr/bin/env python3
"""Read-only search for Markdown/Obsidian vaults; never persists an index."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".claude", ".codex", ".agents"}
TEXT_EXTS = {".md", ".base"}
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FIELD_RE = re.compile(r"^([A-Za-z0-9_.-]+):[ \t]*(.*?)$", re.MULTILINE)
LIST_ITEM_RE = re.compile(r"^[ \t]+-[ \t]+(.*?)$")
STABLE_KNOWLEDGE_PREFIXES = (
    "20_资料库/10_主题知识",
    "20_资料库/20_规范与手册",
    "20_资料库/30_学习指南",
)


def zone(path: str) -> tuple[int, str]:
    top = path.split("/", 1)[0]
    if top.startswith("10_"):
        return 0, "current"
    if top.startswith("20_"):
        if any(prefix_match(path, prefix) for prefix in STABLE_KNOWLEDGE_PREFIXES):
            return 1, "stable"
        # A file does not become trusted knowledge merely because it sits under
        # 20_.  Legacy imports and still-unclassified material rank below the
        # curated/evidence/specialized layers until explicitly distilled.
        return 4, "imported"
    if top.startswith("30_"):
        return 2, "evidence"
    if top.startswith(("40_", "50_", "60_")):
        return 3, "specialized"
    if top.startswith("90_"):
        return 5, "history"
    return 6, "other"


def normalize_prefix(raw: str) -> str:
    value = raw.strip().replace("\\", "/")
    if not value or value.startswith("/"):
        raise ValueError(f"path prefix must be vault-relative: {raw!r}")
    parts = value.rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe path prefix: {raw!r}")
    return "/".join(parts)


def prefix_match(rel: str, prefix: str) -> bool:
    return rel == prefix or rel.startswith(prefix + "/")


def selected(rel: str, includes: list[str], excludes: list[str]) -> bool:
    if includes and not any(prefix_match(rel, prefix) for prefix in includes):
        return False
    return not any(prefix_match(rel, prefix) for prefix in excludes)


def iter_files(root: Path, includes: list[str], excludes: list[str]):
    for current, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS
            and not d.startswith(".")
            and not (Path(current) / d).is_symlink()
        ]
        for filename in sorted(files):
            if filename.startswith("."):
                continue
            path = Path(current) / filename
            if path.is_symlink():
                continue
            rel = path.relative_to(root).as_posix()
            if selected(rel, includes, excludes):
                yield path, rel


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end >= 0 else ""


def fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    active_list: str | None = None
    for line in frontmatter(text).splitlines():
        match = FIELD_RE.fullmatch(line)
        if match:
            key, value = match.groups()
            result[key] = value.strip().strip('"\'')
            active_list = key if not value.strip() else None
            continue
        item = LIST_ITEM_RE.fullmatch(line)
        if active_list and item:
            value = item.group(1).strip().strip('"\'')
            result[active_list] = ",".join(filter(None, (result[active_list], value)))
            continue
        if line and not line[0].isspace():
            active_list = None
    return result


def tag_values(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [item.strip().strip('"\'') for item in value.split(",") if item.strip()]


def snippet(line: str, query: str, width: int = 180) -> str:
    clean = " ".join(line.strip().split())
    pos = clean.casefold().find(query.casefold())
    start = max(0, pos - 60) if pos >= 0 else 0
    return clean[start:start + width]


def backlinks_match(text: str, query: str) -> bool:
    wanted = query.replace("\\", "/").removesuffix(".md")
    wanted_base = Path(wanted).name
    wanted_is_path = "/" in wanted
    for raw in WIKILINK_RE.findall(text):
        target = raw.split("|", 1)[0].split("#", 1)[0].rstrip("\\").strip()
        normalized = target.replace("\\", "/").removesuffix(".md")
        if normalized == wanted or not wanted_is_path and "/" not in normalized and Path(normalized).name == wanted_base:
            return True
    return False


def search(root: Path, args: argparse.Namespace) -> dict:
    matches = []
    unreadable = []
    scanned = 0
    inventory_zone = collections.Counter()
    inventory_ext = collections.Counter()
    query = (args.query or "").casefold()

    def output_snippet(value: str) -> str | None:
        return None if args.no_snippets else value

    for path, rel in iter_files(root, args.path_prefix, args.exclude_prefix):
        inventory_zone[rel.split("/", 1)[0] if "/" in rel else "<vault-root>"] += 1
        inventory_ext[path.suffix.lower() or "<none>"] += 1
        if args.mode == "inventory":
            scanned += 1
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            if args.mode in {"all", "filename"} and query in path.name.casefold():
                rank, source_layer = zone(rel)
                matches.append({"path": rel, "layer": source_layer, "kind": "filename", "line": None, "snippet": output_snippet(path.name), "_rank": rank})
            continue
        scanned += 1
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError):
            unreadable.append(rel)
            continue
        fm = fields(text)
        rank, source_layer = zone(rel)
        if args.mode == "backlinks":
            if backlinks_match(text, args.query):
                matches.append({"path": rel, "layer": source_layer, "kind": "backlink", "line": None, "snippet": output_snippet(f"links to {args.query}"), "_rank": rank})
            continue
        if args.mode == "tag":
            if any(item.casefold() == query for item in tag_values(fm.get("tags", ""))):
                matches.append({"path": rel, "layer": source_layer, "kind": "tag", "line": None, "snippet": output_snippet(fm.get("tags", "")), "_rank": rank})
            continue
        if args.mode == "frontmatter":
            selected = fm.get(args.field, "") if args.field else " ".join(f"{k}:{v}" for k, v in fm.items())
            if query in selected.casefold():
                matches.append({"path": rel, "layer": source_layer, "kind": "frontmatter", "line": None, "snippet": output_snippet(snippet(selected, args.query)), "_rank": rank})
            continue
        if args.mode in {"all", "filename"} and query in path.name.casefold():
            matches.append({"path": rel, "layer": source_layer, "kind": "filename", "line": None, "snippet": output_snippet(path.name), "_rank": rank})
            if args.mode == "filename":
                continue
        if args.mode in {"all", "content"}:
            for lineno, line in enumerate(text.splitlines(), 1):
                if query in line.casefold():
                    matches.append({"path": rel, "layer": source_layer, "kind": "content", "line": lineno, "snippet": output_snippet(snippet(line, args.query)), "_rank": rank})

    matches.sort(key=lambda item: (item["_rank"], item["path"], item["line"] or 0, item["kind"]))
    total = len(matches)
    matches = matches[:args.limit]
    for item in matches:
        item.pop("_rank", None)
    return {
        "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": args.mode,
        "query": args.query,
        "path_prefix": args.path_prefix,
        "exclude_prefix": args.exclude_prefix,
        "snippets": not args.no_snippets,
        "scanned_files": scanned,
        "matches": matches,
        "match_count": total,
        "truncated": total > args.limit,
        "unreadable": unreadable,
        "inventory": {
            "zones": dict(sorted(inventory_zone.items())),
            "extensions": dict(sorted(inventory_ext.items())),
        } if args.mode == "inventory" else None,
    }


def render_markdown(payload: dict) -> str:
    lines = ["# Vault Query", "", f"- mode: `{payload['mode']}`", f"- query: `{payload['query'] or ''}`", f"- matches: {payload['match_count']}", f"- truncated: {str(payload['truncated']).lower()}", ""]
    if payload["inventory"] is not None:
        lines.append("## Zones")
        lines.extend(f"- `{key}`: {value}" for key, value in payload["inventory"]["zones"].items())
    elif payload["matches"]:
        for item in payload["matches"]:
            at = f":{item['line']}" if item["line"] else ""
            suffix = f" — {item['snippet']}" if item["snippet"] is not None else ""
            lines.append(f"- [{item['layer']}/{item['kind']}] `{item['path']}{at}`{suffix}")
    else:
        lines.append("无匹配")
    if payload["unreadable"]:
        lines.extend(["", f"Unreadable: {len(payload['unreadable'])}"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--mode", choices=("all", "filename", "content", "tag", "frontmatter", "backlinks", "inventory"), default="all")
    parser.add_argument("--query")
    parser.add_argument("--field")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--path-prefix", action="append", default=[], help="include only this vault-relative path (repeatable)")
    parser.add_argument("--exclude-prefix", action="append", default=[], help="exclude this vault-relative path (repeatable)")
    parser.add_argument("--no-snippets", action="store_true", help="return paths and match metadata without matched text")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.mode != "inventory" and not args.query:
        parser.error("--query is required unless --mode inventory")
    if args.limit < 1 or args.limit > 1000:
        parser.error("--limit must be between 1 and 1000")
    try:
        args.path_prefix = [normalize_prefix(value) for value in args.path_prefix]
        args.exclude_prefix = [normalize_prefix(value) for value in args.exclude_prefix]
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main() -> int:
    args = parse_args()
    root = Path(args.vault).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("vault is not a directory")
    payload = search(root, args)
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render_markdown(payload), end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
