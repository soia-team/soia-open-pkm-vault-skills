#!/usr/bin/env python3
"""Plan, apply, verify, or roll back move-only vault lifecycle manifests."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path


ALLOWED_STATUS = {
    "inbox", "backlog", "active", "waiting_user", "blocked", "review",
    "done", "archived",
}
OPEN_ITEM_RE = re.compile(r"^[ \t]*[-*][ \t]+\[[ \t]\]", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules"}


def evidence_to_knowledge(source_rel: str, target_rel: str) -> bool:
    source_top = source_rel.split("/", 1)[0]
    target_top = target_rel.split("/", 1)[0]
    return source_top.startswith("30_") and target_top.startswith("20_")


def vault_fingerprint(root: Path) -> str:
    return hashlib.sha256(str(root).encode()).hexdigest()[:16]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def confined(root: Path, value: str, *, must_exist: bool = False) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or not value or value in {".", ".."}:
        raise ValueError(f"path must be vault-relative: {value!r}")
    cursor = root
    for part in candidate.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink path is not managed: {value}")
    resolved = (root / candidate).resolve(strict=must_exist)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes vault: {value}") from exc
    return resolved


def read_frontmatter_status(path: Path) -> str | None:
    if path.suffix.lower() != ".md":
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    match = re.search(r"^status:[ \t]*(.*?)$", text[4:end], re.MULTILINE)
    return match.group(1).strip().strip('"\'') if match else None


def open_item_count(path: Path) -> int:
    if path.suffix.lower() != ".md":
        return 0
    try:
        return len(OPEN_ITEM_RE.findall(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError):
        return 0


def iter_markdown(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in files:
            path = Path(current) / filename
            if filename.lower().endswith(".md") and not path.is_symlink():
                yield path


def incoming_refs(root: Path, source_rel: str) -> list[str]:
    source_no_ext = source_rel[:-3] if source_rel.lower().endswith(".md") else source_rel
    basename = Path(source_no_ext).name
    hits = []
    for path in iter_markdown(root):
        rel = path.relative_to(root).as_posix()
        if rel == source_rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for raw in WIKILINK_RE.findall(text):
            target = raw.split("|", 1)[0].split("#", 1)[0].rstrip("\\").strip()
            normalized = target.replace("\\", "/").removesuffix(".md")
            if normalized == source_no_ext or "/" not in normalized and normalized == basename:
                hits.append(rel)
                break
    return sorted(hits)


def parse_move(raw: str) -> tuple[str, str]:
    if "::" not in raw:
        raise ValueError(f"move must use SOURCE::TARGET: {raw!r}")
    source, target = (part.strip() for part in raw.split("::", 1))
    if not source or not target or source == target:
        raise ValueError(f"invalid move: {raw!r}")
    return source, target


def move_no_overwrite(source: Path, target: Path) -> None:
    """Move one regular file without rename(2)'s overwrite behavior."""
    linked = False
    try:
        os.link(source, target, follow_symlinks=False)
        linked = True
        source.unlink()
    except Exception:
        if linked:
            target.unlink(missing_ok=True)
        raise


def write_manifest(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"manifest already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temp = Path(handle.name)
        if path.exists():
            raise FileExistsError(f"manifest appeared during plan: {path.name}")
        move_no_overwrite(temp, path)
        temp = None
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def plan(args: argparse.Namespace, root: Path, manifest_path: Path) -> int:
    actions = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    global_blockers = []
    for raw in args.move:
        source_rel, target_rel = parse_move(raw)
        source = confined(root, source_rel, must_exist=True)
        target = confined(root, target_rel)
        source_rel = source.relative_to(root).as_posix()
        target_rel = target.relative_to(root).as_posix()
        if source == target:
            raise ValueError(f"source and target resolve to the same path: {source_rel}")
        if source == manifest_path or target == manifest_path:
            raise ValueError("manifest path must not overlap a move source or target")
        blockers = []
        if not source.is_file():
            blockers.append("source_not_file")
        if target.exists():
            blockers.append("target_exists")
        if source in seen_sources:
            blockers.append("duplicate_source")
        if target in seen_targets:
            blockers.append("duplicate_target")
        if evidence_to_knowledge(source_rel, target_rel):
            blockers.append("evidence_to_knowledge_requires_extract")
        seen_sources.add(source)
        seen_targets.add(target)
        status = read_frontmatter_status(source)
        if status and status not in ALLOWED_STATUS:
            blockers.append(f"unknown_status:{status}")
        open_items = open_item_count(source)
        if open_items and not args.allow_open_items:
            blockers.append(f"open_items:{open_items}")
        action = {
            "action": "move",
            "source": source_rel,
            "target": target_rel,
            "size": source.stat().st_size,
            "sha256": sha256(source),
            "status": status,
            "open_items": open_items,
            "incoming_refs": incoming_refs(root, source_rel),
            "blockers": blockers,
        }
        actions.append(action)
        global_blockers.extend(f"{source_rel}:{item}" for item in blockers)
    payload = {
        "schema_version": 1,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "vault_fingerprint": vault_fingerprint(root),
        "policy": "move-only; no delete; no overwrite",
        "ready_to_apply": not global_blockers,
        "blockers": global_blockers,
        "actions": actions,
    }
    write_manifest(manifest_path, payload)
    print(json.dumps({
        "manifest": manifest_path.relative_to(root).as_posix(),
        "actions": len(actions),
        "ready_to_apply": payload["ready_to_apply"],
        "blockers": global_blockers,
    }, ensure_ascii=False))
    return 0


def load_manifest(path: Path, root: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("actions"), list):
        raise ValueError("unsupported lifecycle manifest")
    if data.get("vault_fingerprint") != vault_fingerprint(root):
        raise ValueError("manifest belongs to a different vault path")
    return data


def prepare_actions(data: dict, root: Path, manifest_path: Path) -> list[tuple[Path, Path, dict]]:
    prepared = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    for item in data["actions"]:
        if item.get("action") != "move":
            raise ValueError("manifest contains a non-move action")
        source = confined(root, item["source"])
        target = confined(root, item["target"])
        if source == target or source == manifest_path or target == manifest_path:
            raise ValueError("manifest contains an overlapping source, target, or manifest path")
        source_rel = source.relative_to(root).as_posix()
        target_rel = target.relative_to(root).as_posix()
        if evidence_to_knowledge(source_rel, target_rel):
            raise ValueError("30 evidence cannot be moved into 20 knowledge; preserve the source and extract a new note")
        if source in seen_sources:
            raise ValueError(f"duplicate source in manifest: {item['source']}")
        if target in seen_targets:
            raise ValueError(f"duplicate target in manifest: {item['target']}")
        seen_sources.add(source)
        seen_targets.add(target)
        prepared.append((source, target, item))
    return prepared


def apply(args: argparse.Namespace, root: Path, manifest_path: Path) -> int:
    data = load_manifest(manifest_path, root)
    if not data.get("ready_to_apply"):
        raise ValueError("manifest is blocked; create a new reviewed plan")
    prepared = prepare_actions(data, root, manifest_path)
    for source, target, item in prepared:
        if not source.is_file() or source.stat().st_size != item["size"] or sha256(source) != item["sha256"]:
            raise ValueError(f"source drift: {item['source']}")
        if target.exists():
            raise FileExistsError(item["target"])
    completed = []
    try:
        for source, target, item in prepared:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(item["target"])
            move_no_overwrite(source, target)
            completed.append((source, target, item))
            if target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
                raise ValueError(f"post-move hash mismatch: {item['target']}")
    except Exception as exc:
        rollback_errors = []
        for source, target, item in reversed(completed):
            try:
                if source.exists() or not target.is_file():
                    raise ValueError("source/target state is not reversible")
                if target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
                    raise ValueError("target hash drift")
                source.parent.mkdir(parents=True, exist_ok=True)
                move_no_overwrite(target, source)
            except Exception as rollback_exc:
                rollback_errors.append(f"{item['target']}:{rollback_exc}")
        if rollback_errors:
            raise RuntimeError(f"apply failed ({exc}); automatic rollback incomplete: {rollback_errors}") from exc
        raise RuntimeError(f"apply failed; completed moves rolled back: {exc}") from exc
    print(json.dumps({"applied": len(prepared), "manifest": manifest_path.relative_to(root).as_posix()}))
    return 0


def verify(args: argparse.Namespace, root: Path, manifest_path: Path) -> int:
    data = load_manifest(manifest_path, root)
    prepared = prepare_actions(data, root, manifest_path)
    errors = []
    for source, target, item in prepared:
        if source.exists():
            errors.append(f"source_exists:{item['source']}")
        if not target.is_file():
            errors.append(f"target_missing:{item['target']}")
        elif target.stat().st_size != item["size"] or sha256(target) != item["sha256"]:
            errors.append(f"target_drift:{item['target']}")
    print(json.dumps({"verified": not errors, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 2


def rollback(args: argparse.Namespace, root: Path, manifest_path: Path) -> int:
    data = load_manifest(manifest_path, root)
    prepared = []
    untouched = 0
    for source, target, item in reversed(prepare_actions(data, root, manifest_path)):
        source_ok = source.is_file() and source.stat().st_size == item["size"] and sha256(source) == item["sha256"]
        target_ok = target.is_file() and target.stat().st_size == item["size"] and sha256(target) == item["sha256"]
        if source_ok and not target.exists():
            untouched += 1
            continue
        if not source.exists() and target_ok:
            prepared.append((source, target))
            continue
        raise ValueError(f"move is not safely reversible: {item['source']}::{item['target']}")
    for source, target in prepared:
        source.parent.mkdir(parents=True, exist_ok=True)
        move_no_overwrite(target, source)
    print(json.dumps({"rolled_back": len(prepared), "already_at_source": untouched}))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "verify", "rollback"))
    parser.add_argument("--vault", required=True)
    parser.add_argument("--manifest", required=True, help="vault-relative JSON path")
    parser.add_argument("--move", action="append", default=[], help="SOURCE::TARGET; repeatable")
    parser.add_argument("--allow-open-items", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.vault).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("vault is not a directory")
    manifest_path = confined(root, args.manifest)
    if args.command == "plan":
        if not args.move:
            raise ValueError("plan requires at least one --move")
        if manifest_path.exists():
            raise FileExistsError(f"manifest already exists: {args.manifest}")
        return plan(args, root, manifest_path)
    if not manifest_path.is_file():
        raise FileNotFoundError(args.manifest)
    return globals()[args.command](args, root, manifest_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
