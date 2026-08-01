#!/usr/bin/env python3
"""Plan/apply/check a merge-only Obsidian configuration."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


CSS_SOURCE = Path(__file__).resolve().parents[1] / "assets/wide-page.css"
VAULT_ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets/vault"
BASE_SEEDS = (
    "10_工作台/10_总控/工作台.base",
    "20_资料库/资料库.base",
    "90_系统归档/10_工作台历史/工作台历史.base",
)


def confined(root: Path, rel: str) -> Path:
    value = Path(rel)
    if value.is_absolute() or not rel or rel in {".", ".."}:
        raise ValueError(f"path must be vault-relative: {rel!r}")
    lexical = root / value
    cursor = root
    for part in value.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink path is not managed: {rel}")
    target = lexical.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes vault: {rel}") from exc
    return target


def load_json(path: Path, expected, default_factory):
    if not path.exists():
        return default_factory()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, expected):
        raise ValueError(f"unexpected JSON shape: {path.name}")
    return data


def desired_files(vault: Path, args: argparse.Namespace):
    changes = []

    if args.enable_bases:
        core_path = confined(vault, ".obsidian/core-plugins.json")
        core = load_json(core_path, (dict, list), dict)
        if isinstance(core, dict):
            merged_core = dict(core)
            merged_core["bases"] = True
        else:
            merged_core = list(core)
            if "bases" not in merged_core:
                merged_core.append("bases")
        changes.append((core_path, json.dumps(merged_core, ensure_ascii=False, indent=2) + "\n", "json"))
        for rel in BASE_SEEDS:
            source = VAULT_ASSET_ROOT / rel
            changes.append((confined(vault, rel), source.read_text(encoding="utf-8"), "create_only"))

    if args.enable_wide_page:
        appearance_path = confined(vault, ".obsidian/appearance.json")
        appearance = load_json(appearance_path, dict, dict)
        merged_appearance = dict(appearance)
        snippets = merged_appearance.get("enabledCssSnippets", [])
        if not isinstance(snippets, list):
            raise ValueError("appearance.json enabledCssSnippets must be a list")
        if "wide-page" not in snippets:
            merged_appearance["enabledCssSnippets"] = [*snippets, "wide-page"]
        changes.append((appearance_path, json.dumps(merged_appearance, ensure_ascii=False, indent=2) + "\n", "json"))
        css_path = confined(vault, ".obsidian/snippets/wide-page.css")
        changes.append((css_path, CSS_SOURCE.read_text(encoding="utf-8"), "managed"))

    if args.link_format:
        app_path = confined(vault, ".obsidian/app.json")
        app = load_json(app_path, dict, dict)
        merged_app = dict(app)
        merged_app["newLinkFormat"] = args.link_format
        changes.append((app_path, json.dumps(merged_app, ensure_ascii=False, indent=2) + "\n", "json"))

    return changes


def build_plan(vault: Path, args: argparse.Namespace):
    actions = []
    blockers = []
    for path, desired, kind in desired_files(vault, args):
        rel = path.relative_to(vault).as_posix()
        if path.exists() and not path.is_file():
            state = "conflict"
            blockers.append(f"file_conflict:{rel}")
        elif not path.exists():
            state = "create"
        else:
            current = path.read_text(encoding="utf-8")
            if current == desired:
                state = "skip"
            elif kind == "json" and json.loads(current) == json.loads(desired):
                state = "skip"
            elif kind == "create_only":
                state = "skip"
            elif kind == "managed" and not args.force_managed:
                state = "drift"
            else:
                state = "update"
        actions.append({"path": rel, "state": state, "kind": kind})
    return {"ready": not blockers, "blockers": blockers, "actions": actions}


def atomic_write(path: Path, value: str):
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


def apply(vault: Path, args: argparse.Namespace, plan):
    if not plan["ready"]:
        raise ValueError("plan is blocked")
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_root = confined(vault, f".obsidian/.soia-backups/{timestamp}")
    desired = {path.relative_to(vault).as_posix(): (path, content) for path, content, _ in desired_files(vault, args)}
    counts = {"created": 0, "updated": 0, "skipped": 0, "drift": 0, "backed_up": 0}
    for action in plan["actions"]:
        state = action["state"]
        if state in {"skip", "drift"}:
            counts[state] += 1
            continue
        path, content = desired[action["path"]]
        if state == "create" and path.exists():
            raise FileExistsError(f"create-only target appeared after plan: {action['path']}")
        if path.is_file():
            rel = path.relative_to(vault).as_posix()
            backup_rel = rel.removeprefix(".obsidian/")
            destination = confined(vault, f".obsidian/.soia-backups/{timestamp}/{backup_rel}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            counts["backed_up"] += 1
        atomic_write(path, content)
        counts["created" if state == "create" else "updated"] += 1
    return counts, backup_root if counts["backed_up"] else None


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--enable-bases", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-wide-page", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--link-format", choices=("relative", "absolute", "shortest"))
    parser.add_argument("--force-managed", action="store_true")
    args = parser.parse_args()
    if args.force_managed and not args.apply:
        parser.error("--force-managed requires --apply")
    return args


def main():
    args = parse_args()
    vault = Path(args.vault).expanduser().resolve(strict=True)
    if not vault.is_dir():
        raise ValueError("vault is not a directory")
    plan = build_plan(vault, args)
    if args.check:
        bad = [item for item in plan["actions"] if item["state"] != "skip"]
        print(json.dumps({**plan, "check_passed": not bad}, ensure_ascii=False, indent=2))
        return 0 if not bad else 2
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    counts, backup = apply(vault, args, plan)
    post = build_plan(vault, argparse.Namespace(**{**vars(args), "force_managed": False}))
    print(json.dumps({"applied": counts, "backup": backup.relative_to(vault).as_posix() if backup else None, "post_check": post}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
