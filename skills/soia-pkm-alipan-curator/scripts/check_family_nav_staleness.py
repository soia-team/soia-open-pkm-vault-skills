#!/usr/bin/env python3
"""检测家庭导航是否可能因云盘内容变化而过期。

用法：
  check_family_nav_staleness.py register --registry ... --guide-id ... \
    --scope-root ... --scan ... --nav-file-path ... --generated-at ...
  check_family_nav_staleness.py check --registry ... --scan ... [--guide-id ...] [--json]

本脚本只登记基准并报告差异，不重新生成或上传家庭导航。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from build_family_nav_inputs import (
    GUIDE_ID_PATTERN,
    InputError,
    child_path,
    index_scan,
    normalize_cloud_path,
    path_is_within,
    read_jsonl,
    strict_descendant,
    write_json_atomically,
)


FINGERPRINT_FIELDS = ("file_count", "dir_count", "total_size", "max_mtime")


def validate_guide_id(value: str) -> str:
    guide_id = value.strip()
    if GUIDE_ID_PATTERN.fullmatch(guide_id) is None:
        raise InputError("--guide-id must contain only ASCII letters, digits, _ or -")
    return guide_id


def validate_generated_at(value: str) -> str:
    generated_at = value.strip()
    if not generated_at:
        raise InputError("--generated-at must be a non-empty ISO8601 timestamp")
    candidate = generated_at[:-1] + "+00:00" if generated_at.endswith("Z") else generated_at
    try:
        datetime.fromisoformat(candidate)
    except ValueError as error:
        raise InputError("--generated-at must be a valid ISO8601 timestamp") from error
    return generated_at


def load_registry(path: Path, *, allow_missing: bool) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        if allow_missing:
            return {"guides": {}}
        raise InputError(f"registry does not exist: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read registry {path}: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("guides"), dict):
        raise InputError("registry must be an object with a guides object")
    return document


def validate_fingerprint(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{label} must be an object")
    fingerprint: dict[str, Any] = {}
    for field in ("file_count", "dir_count", "total_size"):
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise InputError(f"{label}.{field} must be a non-negative integer")
        fingerprint[field] = item
    max_mtime = value.get("max_mtime")
    if max_mtime is not None and (not isinstance(max_mtime, str) or not max_mtime):
        raise InputError(f"{label}.max_mtime must be a non-empty string or null")
    fingerprint["max_mtime"] = max_mtime
    return fingerprint


def validate_registry_guide(guide_id: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"registry guide {guide_id!r} must be an object")
    scope_root = normalize_cloud_path(
        value.get("scope_root"), f"registry guide {guide_id!r}.scope_root"
    )
    nav_file_path = normalize_cloud_path(
        value.get("nav_file_path"), f"registry guide {guide_id!r}.nav_file_path"
    )
    if not strict_descendant(nav_file_path, scope_root):
        raise InputError(
            f"registry guide {guide_id!r}.nav_file_path must be within scope_root"
        )
    return {
        **value,
        "scope_root": scope_root,
        "nav_file_path": nav_file_path,
        "fingerprint": validate_fingerprint(
            value.get("fingerprint"), f"registry guide {guide_id!r}.fingerprint"
        ),
    }


def load_scan_entries(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    index_scan(rows)
    entries: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        full_path = child_path(
            normalize_cloud_path(row.get("path"), f"scan row {index}.path"),
            row.get("name"),
            f"scan row {index}.name",
        )
        size = row.get("size")
        if row["dir"] is False:
            if size is None:
                size = 0
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise InputError(f"scan row {index}.size must be a non-negative integer or null")
        mtime = row.get("mtime")
        if mtime is not None and (not isinstance(mtime, str) or not mtime):
            raise InputError(f"scan row {index}.mtime must be a non-empty string or null")
        entries.append({**row, "_path": full_path, "_size": size, "_mtime": mtime})
    return entries


def calculate_fingerprint(
    entries: list[dict[str, Any]], scope_root: str, nav_file_path: str
) -> tuple[dict[str, Any], bool]:
    covered = any(path_is_within(entry["_path"], scope_root) for entry in entries)
    scoped = [
        entry
        for entry in entries
        if strict_descendant(entry["_path"], scope_root)
        and not path_is_within(entry["_path"], nav_file_path)
    ]
    mtimes = [entry["_mtime"] for entry in scoped if entry["_mtime"] is not None]
    fingerprint = {
        "file_count": sum(entry["dir"] is False for entry in scoped),
        "dir_count": sum(entry["dir"] is True for entry in scoped),
        "total_size": sum(
            entry["_size"] for entry in scoped if entry["dir"] is False
        ),
        "max_mtime": max(mtimes) if mtimes else None,
    }
    return fingerprint, covered


def fingerprint_diff(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for field in ("file_count", "dir_count", "total_size"):
        if baseline[field] != current[field]:
            diff[field] = {"baseline": baseline[field], "current": current[field]}
    if (
        baseline["max_mtime"] is not None
        and current["max_mtime"] is not None
        and baseline["max_mtime"] != current["max_mtime"]
    ):
        diff["max_mtime"] = {
            "baseline": baseline["max_mtime"],
            "current": current["max_mtime"],
        }
    return diff


def register(args: argparse.Namespace) -> int:
    guide_id = validate_guide_id(args.guide_id)
    scope_root = normalize_cloud_path(args.scope_root, "--scope-root")
    nav_file_path = normalize_cloud_path(args.nav_file_path, "--nav-file-path")
    if not strict_descendant(nav_file_path, scope_root):
        raise InputError("--nav-file-path must be within --scope-root")
    generated_at = validate_generated_at(args.generated_at)
    entries = load_scan_entries(args.scan)
    fingerprint, _ = calculate_fingerprint(entries, scope_root, nav_file_path)
    registry = load_registry(args.registry, allow_missing=True)
    registry["guides"][guide_id] = {
        "scope_root": scope_root,
        "nav_file_path": nav_file_path,
        "fingerprint": fingerprint,
        "generated_at": generated_at,
    }
    write_json_atomically(args.registry, registry)
    print(
        json.dumps(
            {
                "status": "registered",
                "guide_id": guide_id,
                "fingerprint": fingerprint,
                "registry": str(args.registry.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


def select_guides(
    registry: dict[str, Any], requested_ids: list[str] | None
) -> list[tuple[str, dict[str, Any]]]:
    guides = registry["guides"]
    if requested_ids:
        selected_ids: list[str] = []
        for raw_guide_id in requested_ids:
            guide_id = validate_guide_id(raw_guide_id)
            if guide_id not in guides:
                raise InputError(f"guide_id is not registered: {guide_id}")
            if guide_id not in selected_ids:
                selected_ids.append(guide_id)
    else:
        selected_ids = sorted(guides, key=str.casefold)
    return [
        (guide_id, validate_registry_guide(guide_id, guides[guide_id]))
        for guide_id in selected_ids
    ]


def check(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry, allow_missing=False)
    guides = select_guides(registry, args.guide_ids)
    entries = load_scan_entries(args.scan)
    results: list[dict[str, Any]] = []
    for guide_id, guide in guides:
        current, covered = calculate_fingerprint(
            entries, guide["scope_root"], guide["nav_file_path"]
        )
        if not covered:
            results.append(
                {
                    "guide_id": guide_id,
                    "status": "unknown",
                    "baseline": guide["fingerprint"],
                    "current": None,
                    "diff": {"reason": "scan 未覆盖该 scope_root"},
                }
            )
            continue
        diff = fingerprint_diff(guide["fingerprint"], current)
        results.append(
            {
                "guide_id": guide_id,
                "status": "stale" if diff else "fresh",
                "baseline": guide["fingerprint"],
                "current": current,
                "diff": diff,
            }
        )

    if args.json_output:
        print(json.dumps({"guides": results}, ensure_ascii=False, indent=2))
    else:
        print_human_table(results)

    if any(result["status"] == "stale" for result in results):
        return 1
    if any(result["status"] == "unknown" for result in results):
        return 2
    return 0


def diff_summary(diff: dict[str, Any]) -> str:
    if not diff:
        return "-"
    if "reason" in diff:
        return str(diff["reason"])
    return "; ".join(
        f"{field}: {change['baseline']} -> {change['current']}"
        for field, change in diff.items()
    )


def print_human_table(results: list[dict[str, Any]]) -> None:
    rows = [
        (result["guide_id"], result["status"], diff_summary(result["diff"]))
        for result in results
    ]
    headers = ("guide_id", "状态", "差异摘要")
    widths = [
        max([len(headers[index]), *(len(row[index]) for row in rows)], default=len(headers[index]))
        for index in range(3)
    ]
    print("  ".join(headers[index].ljust(widths[index]) for index in range(3)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(3)))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="登记并检测家庭导航的轻量内容指纹；不会重新生成或上传导航。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="登记一次已验证生成的基准")
    register_parser.add_argument("--registry", required=True, type=Path)
    register_parser.add_argument("--guide-id", required=True)
    register_parser.add_argument("--scope-root", required=True)
    register_parser.add_argument("--scan", required=True, type=Path)
    register_parser.add_argument("--nav-file-path", required=True)
    register_parser.add_argument("--generated-at", required=True)
    register_parser.set_defaults(handler=register)

    check_parser = subparsers.add_parser("check", help="用新鲜 scan 检测已登记导航")
    check_parser.add_argument("--registry", required=True, type=Path)
    check_parser.add_argument("--scan", required=True, type=Path)
    check_parser.add_argument("--guide-id", action="append", dest="guide_ids")
    check_parser.add_argument("--json", action="store_true", dest="json_output")
    check_parser.set_defaults(handler=check)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return args.handler(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
