#!/usr/bin/env python3
"""Plan, apply, or check an AI-native Markdown vault scaffold."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).with_name("default_config.json")
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets/vault"


def read_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("YAML config requires PyYAML; use JSON for zero-dependency setup") from exc
        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be an object: {path}")
    if int(data.get("schema_version", 0)) not in {1, 2}:
        raise ValueError("config schema_version must be 1 or 2")
    return data


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def directory_path(value: Any) -> str:
    """Accept current string paths and the legacy v1 {parts:[...]} shape."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = value.get("parts")
        if isinstance(parts, list) and parts and all(isinstance(item, str) and item for item in parts):
            return "/".join(item.strip("/") for item in parts)
    raise ValueError("directory entries must be strings or legacy objects with non-empty string parts")


def file_entries(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [{"path": path, "content": content} for path, content in value.items()]
    if isinstance(value, list):
        entries = []
        for item in value:
            if not isinstance(item, dict) or "path" not in item:
                raise ValueError("files entries must be objects with a path field")
            entries.append(deepcopy(item))
        return entries
    raise ValueError("files must be a list or object")


def merge_file_entries(base: list[dict[str, Any]], override: Any) -> list[dict[str, Any]]:
    by_path = {entry["path"]: deepcopy(entry) for entry in base}
    if override is None:
        return list(by_path.values())
    if isinstance(override, list) or isinstance(override, dict) and "path" in override:
        for entry in file_entries(override if isinstance(override, list) else [override]):
            by_path[entry["path"]] = entry
        return list(by_path.values())
    if isinstance(override, dict):
        for path in override.get("remove", []):
            by_path.pop(path, None)
        for key in ("add", "replace"):
            for entry in file_entries(override.get(key)):
                by_path[entry["path"]] = entry
        return list(by_path.values())
    raise ValueError("files override must be a list or object")


def merge_directories(base: list[str], override: Any) -> list[str]:
    if override is None:
        return unique([directory_path(item) for item in base])
    if isinstance(override, list):
        return unique([directory_path(item) for item in override])
    if not isinstance(override, dict):
        raise ValueError("directories must be a list or object")
    dirs = [directory_path(item) for item in override.get("replace", base)]
    remove = {directory_path(item) for item in override.get("remove", [])}
    return unique([item for item in dirs if item not in remove] + [directory_path(item) for item in override.get("add", [])])


def merge_config(default: dict[str, Any], custom: dict[str, Any] | None) -> dict[str, Any]:
    if not custom:
        return deepcopy(default)
    cfg = deepcopy(default) if custom.get("extends_default", True) else {"schema_version": 2, "directories": [], "files": []}
    cfg["directories"] = merge_directories(cfg.get("directories", []), custom.get("directories"))
    cfg["files"] = merge_file_entries(file_entries(cfg.get("files")), custom.get("files"))
    for key, value in custom.items():
        if key not in {"schema_version", "extends_default", "directories", "files"}:
            cfg[key] = deepcopy(value)
    cfg["schema_version"] = 2
    return cfg


def confined(base: Path, rel: str) -> Path:
    value = Path(rel)
    if value.is_absolute() or not rel or rel in {".", ".."}:
        raise ValueError(f"path must be relative: {rel!r}")
    cursor = base
    for part in value.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink path is not managed: {rel}")
    target = (base / value).resolve(strict=False)
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {rel}") from exc
    return target


def render_entry(entry: dict[str, Any]) -> str:
    if "source" in entry:
        source = confined(ASSET_ROOT, str(entry["source"]))
        if not source.is_file():
            raise FileNotFoundError(f"asset not found: {entry['source']}")
        return source.read_text(encoding="utf-8")
    raw = entry.get("content", "")
    if isinstance(raw, list):
        return "\n".join(str(line) for line in raw) + "\n"
    if isinstance(raw, str):
        return raw
    raise ValueError("file content must be a string/list, or use a bundled source")


def build_plan(vault: Path, cfg: dict[str, Any], force: bool) -> dict[str, Any]:
    actions = []
    blockers = []
    directory_rels = [directory_path(item) for item in cfg.get("directories", [])]
    entries = file_entries(cfg.get("files"))
    file_rels = [str(entry["path"]) for entry in entries]
    for file_rel in file_rels:
        for directory_rel in directory_rels:
            if directory_rel == file_rel or directory_rel.startswith(file_rel.rstrip("/") + "/"):
                blockers.append(f"path_kind_conflict:{file_rel}:{directory_rel}")
        for other in file_rels:
            if other != file_rel and other.startswith(file_rel.rstrip("/") + "/"):
                blockers.append(f"file_ancestor_conflict:{file_rel}:{other}")
    blockers = list(dict.fromkeys(blockers))
    for rel in directory_rels:
        path = confined(vault, rel)
        if path.exists() and not path.is_dir():
            blockers.append(f"directory_conflict:{rel}")
            state = "conflict"
        else:
            state = "exists" if path.is_dir() else "create"
        actions.append({"kind": "directory", "path": rel, "state": state})
    for entry in entries:
        rel = str(entry["path"])
        path = confined(vault, rel)
        content = render_entry(entry)
        mode = str(entry.get("mode", "create_only"))
        if mode not in {"create_only", "managed"}:
            raise ValueError(f"unsupported file mode for {rel}: {mode}")
        if path.exists() and not path.is_file():
            state = "conflict"
            blockers.append(f"file_conflict:{rel}")
        elif not path.exists():
            state = "create"
        elif force:
            state = "overwrite"
        elif mode == "managed" and path.read_text(encoding="utf-8") != content:
            state = "drift"
        else:
            state = "skip"
        actions.append({"kind": "file", "path": rel, "state": state, "mode": mode})
    return {"schema_version": 2, "vault": str(vault), "ready": not blockers, "blockers": blockers, "actions": actions}


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def apply_plan(vault: Path, cfg: dict[str, Any], plan: dict[str, Any], force: bool) -> dict[str, int]:
    if not plan["ready"]:
        raise ValueError("plan is blocked")
    vault.mkdir(parents=True, exist_ok=True)
    counts = {"created_dirs": 0, "created_files": 0, "overwritten_files": 0, "skipped_files": 0}
    for action in plan["actions"]:
        if action["kind"] == "directory" and action["state"] == "create":
            path = confined(vault, action["path"])
            if path.exists() and not path.is_dir():
                raise FileExistsError(f"directory target appeared after plan: {action['path']}")
            path.mkdir(parents=True, exist_ok=True)
            counts["created_dirs"] += 1
    entries = {str(item["path"]): item for item in file_entries(cfg.get("files"))}
    for action in plan["actions"]:
        if action["kind"] != "file":
            continue
        if action["state"] in {"skip", "drift"}:
            counts["skipped_files"] += 1
            continue
        if action["state"] not in {"create", "overwrite"}:
            continue
        path = confined(vault, action["path"])
        if action["state"] == "create" and path.exists():
            raise FileExistsError(f"create-only target appeared after plan: {action['path']}")
        if action["state"] == "overwrite" and not force:
            raise ValueError(f"overwrite requires --force: {action['path']}")
        atomic_write(path, render_entry(entries[action["path"]]))
        counts["overwritten_files" if action["state"] == "overwrite" else "created_files"] += 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", nargs="?")
    parser.add_argument("--config")
    parser.add_argument("--apply", action="store_true", help="apply the displayed create-only plan")
    parser.add_argument("--check", action="store_true", help="report missing/conflicting/drifted managed files without writing")
    parser.add_argument("--force", action="store_true", help="overwrite existing seed files; requires --apply")
    parser.add_argument("--print-default-config", action="store_true")
    parser.add_argument("--no-obsidian", action="store_true", help="deprecated no-op; base defaults never create .obsidian")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    default_cfg = read_config(DEFAULT_CONFIG)
    if args.print_default_config:
        print(json.dumps(default_cfg, ensure_ascii=False, indent=2))
        return 0
    if not args.vault:
        raise ValueError("missing target vault path")
    if args.force and not args.apply:
        raise ValueError("--force requires --apply")
    custom = read_config(Path(args.config).expanduser()) if args.config else None
    cfg = merge_config(default_cfg, custom)
    vault = Path(args.vault).expanduser().resolve(strict=False)
    plan = build_plan(vault, cfg, args.force)
    if args.check:
        failures = [item for item in plan["actions"] if item["state"] in {"create", "conflict", "drift"}]
        print(json.dumps({**plan, "check_passed": not failures}, ensure_ascii=False, indent=2))
        return 0 if not failures else 2
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    counts = apply_plan(vault, cfg, plan, args.force)
    post = build_plan(vault, cfg, False)
    print(json.dumps({"applied": counts, "post_check": post}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
