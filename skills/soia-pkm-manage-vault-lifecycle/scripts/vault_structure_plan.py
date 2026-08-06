#!/usr/bin/env python3
"""Plan and safely apply vault structure cleanup and semantic directory numbering.

The planner is intentionally conservative: date/month and attachment/resource
directories are exceptions, while semantic directories get a unique numeric
prefix within each parent.  File contents are moved byte-for-byte; only
explicitly empty notes, OS metadata, and empty directories can be deleted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath


SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules"}
RESOURCE_NAMES = {
    "images", "image", "_image", "_images", "resources", "_resources",
    "attachments", "_attachments", "@resources", "help_images",
}
TEMPORAL = re.compile(
    r"^(?:\d{4}|\d{1,2}月|第.+周|\d{4}[-_.]\d{1,2}(?:[-_.]\d{1,2})?)$"
)
NUMBERED = re.compile(r"^(\d{1,2})_(.+)$")
DOT_NUMBERED = re.compile(r"^(\d{1,2})[.]\s*(.+)$")
DASH_NUMBERED = re.compile(r"^(\d{1,2})[-]\s*(.+)$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
GENERATED_REFERENCE_SOURCES = {"20_资料库/OB知识库地图.md"}
PREFERRED_SEMANTIC_ORDER = {
    # Stable top-level order for the historical snapshot namespace.  The
    # fallback remains lexical, so callers do not need to provide a taxonomy
    # for every private module.
    "工作": 10,
    "技术": 20,
    "日记": 30,
    "生活": 40,
    "写作": 50,
}


def fingerprint(root: Path) -> str:
    return hashlib.sha256(str(root).encode()).hexdigest()[:16]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def confined(root: Path, value: str, *, must_exist: bool = False) -> Path:
    raw = Path(value)
    if raw.is_absolute() or not value or value in {".", ".."}:
        raise ValueError(f"path must be vault-relative: {value!r}")
    cursor = root
    for part in raw.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink path is not managed: {value}")
    resolved = (root / raw).resolve(strict=must_exist)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes vault: {value}") from exc
    return resolved


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_resource_or_temporal(name: str) -> bool:
    # Only hidden state, explicitly-known resource folders, and temporal buckets
    # are exceptions.  Ordinary semantic folders (including technical/module
    # names such as "AI安全" or "技术组件") must receive a numeric prefix.
    return name.startswith(".") or name in RESOURCE_NAMES or bool(TEMPORAL.fullmatch(name))


def has_visible_file(path: Path) -> bool:
    for current, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        if any(not name.startswith(".") for name in files):
            return True
    return False


def iter_dirs(root: Path):
    for current, dirs, _files in os.walk(root, followlinks=False):
        # Hidden state folders (for example .metion plugin metadata) are kept
        # as path-attached state: they move with their parent but are never
        # candidates for numbering on their own.
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        current_path = Path(current)
        for dirname in dirs:
            child = current_path / dirname
            if child.is_symlink():
                raise ValueError(f"symlink directory is not managed: {child}")
            yield child


def iter_files(root: Path):
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        current_path = Path(current)
        for filename in sorted(files):
            path = current_path / filename
            if path.is_symlink():
                raise ValueError(f"symlink file is not managed: {path}")
            if path.is_file():
                yield path


def empty_body(path: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    stripped = text.strip()
    if stripped.startswith("---\n"):
        end = stripped.find("\n---", 4)
        if end >= 0:
            stripped = stripped[end + 4 :].strip()
    return not stripped


def build_link_index(root: Path) -> dict[str, set[str]]:
    links: dict[str, set[str]] = {}
    for path in iter_files(root):
        if path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        source = rel(path, root)
        if source in GENERATED_REFERENCE_SOURCES:
            continue
        for raw in WIKILINK_RE.findall(text):
            target = raw.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
            target = target.removesuffix(".md")
            if target:
                links.setdefault(target, set()).add(source)
    return links


def incoming_refs(path_value: str, index: dict[str, set[str]]) -> list[str]:
    no_ext = path_value.removesuffix(".md")
    base = PurePosixPath(no_ext).name
    hits = set(index.get(no_ext, set()))
    for target, sources in index.items():
        if "/" not in target and PurePosixPath(target).name == base:
            hits.update(sources)
    hits.discard(path_value)
    return sorted(hits)


def next_number(used: set[int]) -> int:
    # Keep the normal 10-step sequence first.  99 is reserved for the
    # historical local-supplement bucket; overflow uses 98..91 before falling
    # back to 01..09, and every assignment remains unique within its parent.
    for number in list(range(10, 100, 10)) + list(range(98, 90, -1)) + list(range(1, 10)):
        if number == 99:
            continue
        if number not in used:
            return number
    raise ValueError("no free two-digit directory number")


def desired_name(name: str) -> tuple[str, int | None, bool]:
    """Return desired name, numeric prefix, and whether it is a semantic candidate."""
    match = NUMBERED.fullmatch(name)
    if match:
        return name, int(match.group(1)), False
    match = DOT_NUMBERED.fullmatch(name) or DASH_NUMBERED.fullmatch(name)
    if match and not is_resource_or_temporal(name):
        number = int(match.group(1)) * 10 if int(match.group(1)) < 10 else int(match.group(1))
        number = min(number, 98)
        return f"{number:02d}_{match.group(2).strip()}", number, True
    if is_resource_or_temporal(name):
        return name, None, False
    return name, None, True


def semantic_sort_key(path: Path) -> tuple[int, int, str]:
    """Sort existing numeric names first, then known semantic order, then name."""
    name = path.name
    numbered = NUMBERED.fullmatch(name)
    if numbered:
        return (0, int(numbered.group(1)), name)
    dotted = DOT_NUMBERED.fullmatch(name) or DASH_NUMBERED.fullmatch(name)
    if dotted:
        return (0, int(dotted.group(1)) * 10, name)
    return (1, PREFERRED_SEMANTIC_ORDER.get(name, 1000), name)


def build_directory_map(root: Path, scope: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    directories = sorted(iter_dirs(scope), key=lambda p: (len(p.relative_to(scope).parts), p.as_posix()))
    for parent in sorted({p.parent for p in directories}, key=lambda p: p.as_posix()):
        # Hidden archive/state trees are path-attached implementation details,
        # not semantic vault modules.  In particular, historical snapshots may
        # contain note-package directories such as ``.Archive/2021-08-11.md``;
        # treating those as modules exhausts the finite numbering slots and can
        # make an otherwise valid plan fail with ``no free two-digit directory
        # number``.  Keep the whole hidden subtree opaque and let its parent
        # move with the files unchanged.
        try:
            parent_rel = parent.relative_to(scope)
        except ValueError:
            parent_rel = parent.relative_to(root)
        if any(part.startswith(".") for part in parent_rel.parts):
            continue
        children = sorted((p for p in parent.iterdir() if p.is_dir()), key=semantic_sort_key)
        if not children:
            continue
        planned: list[tuple[Path, str, int | None, bool]] = []
        for child in children:
            name, number, candidate = desired_name(child.name)
            planned.append((child, name, number, candidate))
        used = {number for _child, _name, number, _candidate in planned if number is not None}
        used_names = {name for _child, name, _number, _candidate in planned}
        # Unnumbered semantic folders receive the first free 10-step number.
        for index, (child, name, number, candidate) in enumerate(planned):
            if not candidate or number is not None:
                continue
            number = next_number(used)
            used.add(number)
            name = f"{number:02d}_{child.name}"
            while name in used_names:
                number = next_number(used)
                used.add(number)
                name = f"{number:02d}_{child.name}"
            used_names.add(name)
            planned[index] = (child, name, number, candidate)
        # Resolve duplicate numeric prefixes, retaining the explicit local supplement as 99.
        groups: dict[int, list[int]] = {}
        for index, (_child, name, number, _candidate) in enumerate(planned):
            if number is not None:
                groups.setdefault(number, []).append(index)
        for number, indexes in groups.items():
            if len(indexes) < 2:
                continue
            keep = next((i for i in indexes if planned[i][0].name == "99_本地补录"), indexes[0])
            for index in indexes:
                if index == keep:
                    continue
                child, _name, _number, candidate = planned[index]
                replacement = next_number(used)
                used.add(replacement)
                planned[index] = (child, f"{replacement:02d}_{child.name.split('_', 1)[-1]}", replacement, candidate)
        for child, name, _number, _candidate in planned:
            if child.name != name:
                mapping[rel(child, root)] = name
    return mapping


def mapped_path(path_value: str, mapping: dict[str, str]) -> str:
    parts = PurePosixPath(path_value).parts
    original: list[str] = []
    output: list[str] = []
    for part in parts:
        original.append(part)
        key = "/".join(original)
        output.append(mapping.get(key, part))
    return "/".join(output)


def plan(args: argparse.Namespace) -> int:
    root = Path(args.vault).expanduser().resolve(strict=True)
    scope = confined(root, args.scope, must_exist=True)
    if not scope.is_dir():
        raise ValueError("scope must be a directory")
    manifest = confined(root, args.manifest)
    if manifest.exists():
        raise FileExistsError(f"manifest already exists: {args.manifest}")
    cleanup_roots = [scope]
    for value in args.cleanup_root:
        cleanup = confined(root, value, must_exist=True)
        if not cleanup.is_dir():
            raise ValueError(f"cleanup root must be a directory: {value}")
        if cleanup not in cleanup_roots:
            cleanup_roots.append(cleanup)
    explicit_metadata = []
    for value in args.cleanup_file:
        path = confined(root, value, must_exist=True)
        if not path.is_file() or path.name != ".DS_Store":
            raise ValueError(f"cleanup-file must be an existing .DS_Store file: {value}")
        explicit_metadata.append(path)
    mapping = build_directory_map(root, scope)
    link_index = build_link_index(root)
    move_actions = []
    delete_files = []
    blockers = []
    all_files = []
    for cleanup_root in cleanup_roots:
        all_files.extend(iter_files(cleanup_root))
    for path in all_files:
        source = rel(path, root)
        if path.name == ".DS_Store":
            delete_files.append({"path": source, "size": path.stat().st_size, "sha256": sha256(path), "reason": "os_metadata"})
            continue
        if empty_body(path):
            refs = incoming_refs(source, link_index)
            if refs:
                blockers.append({"path": source, "reason": "empty_note_has_incoming_refs", "incoming_refs": refs})
            else:
                delete_files.append({"path": source, "size": path.stat().st_size, "sha256": sha256(path), "reason": "empty_markdown"})
            continue
        target = mapped_path(source, mapping) if path.is_relative_to(scope) else source
        if target != source:
            move_actions.append({"action": "move_file", "source": source, "target": target, "size": path.stat().st_size, "sha256": sha256(path), "incoming_refs": incoming_refs(source, link_index)})
    listed = {item["path"] for item in delete_files}
    for path in explicit_metadata:
        source = rel(path, root)
        if source not in listed:
            delete_files.append({"path": source, "size": path.stat().st_size, "sha256": sha256(path), "reason": "explicit_os_metadata"})
    sources = {item["source"] for item in move_actions}
    targets = set()
    for item in move_actions:
        if item["target"] in targets:
            blockers.append({"path": item["target"], "reason": "duplicate_target"})
        targets.add(item["target"])
        target_path = root / item["target"]
        if target_path.exists() and item["target"] not in sources:
            blockers.append({"path": item["target"], "reason": "target_exists"})
    # A directory can be removed when no non-deleted file will remain below it.
    deleted = {item["path"] for item in delete_files}
    final_files = {mapped_path(rel(path, root), mapping) for path in all_files if rel(path, root) not in deleted}
    delete_dirs = []
    if not args.preserve_empty_dirs:
        all_dirs = list(cleanup_roots)
        for cleanup_root in cleanup_roots:
            all_dirs.extend(iter_dirs(cleanup_root))
        for path in sorted(all_dirs, key=lambda p: (len(p.relative_to(root).parts), p.as_posix()), reverse=True):
            path_rel = rel(path, root)
            if path == scope:
                continue
            prefix = path_rel.rstrip("/") + "/"
            if not any(value.startswith(prefix) for value in final_files):
                delete_dirs.append(path_rel)
    actions = move_actions + [{"action": "delete_file", **item} for item in delete_files] + [{"action": "delete_dir", "path": path} for path in delete_dirs]
    move_bytes = sum(item["size"] for item in move_actions)
    payload = {
        "schema_version": 1,
        "tool": "soia-pkm-manage-vault-lifecycle/vault_structure_plan",
        "plan_type": "directory-numbering",
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "vault_fingerprint": fingerprint(root),
        "scope": rel(scope, root),
        "cleanup_files": [rel(path, root) for path in explicit_metadata],
        "policy": "semantic-numbering; preserve temporal/resource directories; delete only explicit empty objects and OS metadata",
        "ready_to_apply": not blockers,
        "blockers": blockers,
        "directory_renames": [{"source": source, "target": mapped_path(source, mapping)} for source in sorted(mapping)],
        "actions": actions,
        "summary": {
            "directory_renames": len(mapping),
            "move_files": len(move_actions),
            "move_bytes": move_bytes,
            "delete_files": len(delete_files),
            "delete_dirs": len(delete_dirs),
            "blockers": len(blockers),
            "batches": [{
                "scope": rel(scope, root),
                "directory_renames": len(mapping),
                "move_files": len(move_actions),
                "move_bytes": move_bytes,
            }],
        },
        "reference_scan": {
            "incoming_refs": sum(len(item.get("incoming_refs", [])) for item in move_actions),
            "moves_with_incoming_refs": sum(bool(item.get("incoming_refs")) for item in move_actions),
            "generated_sources_excluded": sorted(GENERATED_REFERENCE_SOURCES),
        },
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": args.manifest, "summary": payload["summary"], "ready_to_apply": payload["ready_to_apply"], "blockers": blockers[:20]}, ensure_ascii=False))
    return 0


def load(args: argparse.Namespace) -> tuple[Path, dict]:
    root = Path(args.vault).expanduser().resolve(strict=True)
    manifest = confined(root, args.manifest, must_exist=True)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("vault_fingerprint") != fingerprint(root):
        raise ValueError("manifest schema or vault fingerprint mismatch")
    return root, data


def move_no_overwrite(source: Path, target: Path) -> None:
    linked = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target, follow_symlinks=False)
        linked = True
        source.unlink()
    except Exception:
        if linked:
            target.unlink(missing_ok=True)
        raise


def apply(args: argparse.Namespace) -> int:
    root, data = load(args)
    if not data.get("ready_to_apply"):
        raise ValueError("manifest is blocked; review blockers and create a new plan")
    actions = data["actions"]
    moves = [item for item in actions if item.get("action") == "move_file"]
    deletes = [item for item in actions if item.get("action") == "delete_file"]
    dirs = [item for item in actions if item.get("action") == "delete_dir"]
    move_sources = {item["source"] for item in moves}
    for item in moves:
        source = confined(root, item["source"], must_exist=True)
        target = confined(root, item["target"])
        if source.stat().st_size != item["size"] or sha256(source) != item["sha256"]:
            raise ValueError(f"source drift: {item['source']}")
        if target.exists() and item["target"] not in move_sources:
            raise FileExistsError(item["target"])
    for item in deletes:
        path = confined(root, item["path"], must_exist=True)
        if path.stat().st_size != item["size"] or sha256(path) != item["sha256"]:
            raise ValueError(f"delete target drift: {item['path']}")
    scheduled_dirs = {item["path"] for item in dirs}
    scheduled_files = {item["source"] for item in moves} | {item["path"] for item in deletes}
    for item in dirs:
        path = confined(root, item["path"], must_exist=True)
        unexpected = [
            child for child in path.iterdir()
            if rel(child, root) not in scheduled_dirs and rel(child, root) not in scheduled_files
        ]
        if unexpected:
            raise ValueError(f"directory is no longer empty: {item['path']}")
    for item in deletes:
        confined(root, item["path"], must_exist=True).unlink()
    for item in moves:
        move_no_overwrite(confined(root, item["source"], must_exist=True), confined(root, item["target"]))
    for item in sorted(dirs, key=lambda x: len(PurePosixPath(x["path"]).parts), reverse=True):
        path = confined(root, item["path"])
        if path.exists():
            if any(path.iterdir()):
                raise ValueError(f"directory became non-empty during apply: {item['path']}")
            path.rmdir()
    data["applied_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = confined(root, args.manifest)
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"applied": len(actions), "manifest": args.manifest}, ensure_ascii=False))
    return 0


def verify(args: argparse.Namespace) -> int:
    root, data = load(args)
    errors = []
    for item in data["actions"]:
        if item.get("action") == "move_file":
            source = confined(root, item["source"])
            target = confined(root, item["target"])
            if source.exists():
                errors.append(f"source_exists:{item['source']}")
            if not target.is_file() or target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
                errors.append(f"target_drift:{item['target']}")
        elif item.get("action") == "delete_file" and confined(root, item["path"]).exists():
            errors.append(f"file_exists:{item['path']}")
        elif item.get("action") == "delete_dir" and confined(root, item["path"]).exists():
            errors.append(f"dir_exists:{item['path']}")
    print(json.dumps({"verified": not errors, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "verify"))
    parser.add_argument("--vault", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--scope", default="20_资料库/90_历史导入")
    parser.add_argument("--cleanup-root", action="append", default=[], help="additional vault-relative root for empty-object cleanup (repeatable)")
    parser.add_argument("--cleanup-file", action="append", default=[], help="explicit .DS_Store metadata file to delete (repeatable)")
    parser.add_argument("--preserve-empty-dirs", action="store_true", help="plan renames/moves without deleting empty directories")
    args = parser.parse_args()
    if args.command == "plan":
        return plan(args)
    if args.command == "apply":
        return apply(args)
    return verify(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
