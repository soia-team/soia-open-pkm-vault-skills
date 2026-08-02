#!/usr/bin/env python3
"""Plan, apply, verify, or roll back move-only vault lifecycle manifests."""
from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath


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


def build_reference_index(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, int]]:
    """Index wikilinks once so bulk plans do not rescan the vault per action."""
    exact: dict[str, set[str]] = defaultdict(set)
    short: dict[str, set[str]] = defaultdict(set)
    markdown_files_scanned = 0
    wikilinks_indexed = 0
    for path in iter_markdown(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        markdown_files_scanned += 1
        for raw in WIKILINK_RE.findall(text):
            target = raw.split("|", 1)[0].split("#", 1)[0].rstrip("\\").strip()
            normalized = target.replace("\\", "/").removesuffix(".md")
            if not normalized:
                continue
            wikilinks_indexed += 1
            if "/" in normalized:
                exact[normalized].add(rel)
            else:
                short[normalized].add(rel)
    return exact, short, {
        "markdown_files_scanned": markdown_files_scanned,
        "wikilinks_indexed": wikilinks_indexed,
    }


def incoming_refs(
    reference_index: tuple[dict[str, set[str]], dict[str, set[str]], dict[str, int]],
    source_rel: str,
) -> list[str]:
    source_no_ext = source_rel[:-3] if source_rel.lower().endswith(".md") else source_rel
    basename = Path(source_no_ext).name
    exact, short, _stats = reference_index
    hits = set(exact.get(source_no_ext, set()))
    hits.update(short.get(basename, set()))
    hits.discard(source_rel)
    return sorted(hits)


def parse_move(raw: str | tuple[str, str]) -> tuple[str, str]:
    if isinstance(raw, tuple):
        source, target = raw
        if not source or not target or source == target:
            raise ValueError(f"invalid move: {raw!r}")
        return source, target
    if "::" not in raw:
        raise ValueError(f"move must use SOURCE::TARGET: {raw!r}")
    source, target = (part.strip() for part in raw.split("::", 1))
    if not source or not target or source == target:
        raise ValueError(f"invalid move: {raw!r}")
    return source, target


def read_moves_file(path_value: str) -> list[tuple[str, str]]:
    path = Path(path_value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"moves file is not a regular file: {path.name}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"moves file must be UTF-8: {path.name}") from exc
    moves = []
    for line_number, line in enumerate(lines, start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if "::" not in line:
            raise ValueError(
                f"invalid moves file line {line_number}: move must use SOURCE::TARGET"
            )
        source, target = line.split("::", 1)
        try:
            move = parse_move((source, target))
        except ValueError as exc:
            raise ValueError(f"invalid moves file line {line_number}: {exc}") from exc
        moves.append(move)
    return moves


def raise_walk_error(error: OSError) -> None:
    raise error


def tree_moves(
    root: Path, source_value: str, target_value: str
) -> tuple[list[tuple[str, str]], str, str]:
    source_root = confined(root, source_value, must_exist=True)
    target_root = confined(root, target_value)
    if not source_root.is_dir():
        raise ValueError("tree-plan source root must be a directory")
    if source_root == target_root:
        raise ValueError("tree-plan source and target roots must differ")
    if target_root.is_relative_to(source_root) or source_root.is_relative_to(target_root):
        raise ValueError("tree-plan source and target roots must not overlap")

    moves = []
    for current, dirs, files in os.walk(
        source_root, followlinks=False, onerror=raise_walk_error
    ):
        dirs.sort()
        files.sort()
        current_path = Path(current)
        for dirname in dirs:
            if (current_path / dirname).is_symlink():
                raise ValueError("tree-plan does not manage symlink directories")
        for filename in files:
            source = current_path / filename
            if source.is_symlink() or not source.is_file():
                raise ValueError("tree-plan only manages regular files")
            relative = source.relative_to(source_root)
            target = target_root / relative
            moves.append((
                source.relative_to(root).as_posix(),
                target.relative_to(root).as_posix(),
            ))
    if not moves:
        raise ValueError("tree-plan source root contains no regular files")
    return (
        moves,
        source_root.relative_to(root).as_posix(),
        target_root.relative_to(root).as_posix(),
    )


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


def common_parent(paths: list[str]) -> PurePosixPath:
    parts = [PurePosixPath(value).parts for value in paths]
    common = []
    for candidates in zip(*parts):
        if len(set(candidates)) != 1:
            break
        common.append(candidates[0])
    if len(paths) == 1 and len(common) == len(parts[0]):
        common = common[:-1]
    return PurePosixPath(*common) if common else PurePosixPath(".")


def first_child(path_value: str, parent: PurePosixPath) -> str:
    relative = PurePosixPath(path_value).relative_to(parent)
    return relative.parts[0] if len(relative.parts) > 1 else "_root"


def build_summary(
    actions: list[dict],
    reference_stats: dict[str, int],
    *,
    source_root: str | None = None,
    target_root: str | None = None,
) -> dict:
    source_parent = PurePosixPath(source_root) if source_root else common_parent(
        [item["source"] for item in actions]
    )
    target_parent = PurePosixPath(target_root) if target_root else common_parent(
        [item["target"] for item in actions]
    )
    grouped: dict[tuple[str, str], dict[str, int | str]] = {}
    incoming_ref_files = set()
    for item in actions:
        source_batch = first_child(item["source"], source_parent)
        target_batch = first_child(item["target"], target_parent)
        key = (source_batch, target_batch)
        batch = grouped.setdefault(key, {
            "source": source_batch,
            "target": target_batch,
            "actions": 0,
            "bytes": 0,
            "blockers": 0,
        })
        batch["actions"] += 1
        batch["bytes"] += item["size"]
        batch["blockers"] += len(item["blockers"])
        incoming_ref_files.update(item["incoming_refs"])
    return {
        "actions": len(actions),
        "bytes": sum(item["size"] for item in actions),
        "markdown_actions": sum(item["source"].lower().endswith(".md") for item in actions),
        "actions_with_incoming_refs": sum(bool(item["incoming_refs"]) for item in actions),
        "incoming_ref_files": len(incoming_ref_files),
        "blockers": sum(len(item["blockers"]) for item in actions),
        "source_root": source_parent.as_posix(),
        "target_root": target_parent.as_posix(),
        "batches": [grouped[key] for key in sorted(grouped)],
        "reference_scan": reference_stats,
    }


def plan(
    args: argparse.Namespace,
    root: Path,
    manifest_path: Path,
    raw_moves: list[str | tuple[str, str]],
    *,
    plan_type: str = "moves",
    source_root: str | None = None,
    target_root: str | None = None,
) -> int:
    actions = []
    seen_sources: set[Path] = set()
    seen_targets: set[Path] = set()
    global_blockers = []
    reference_index = build_reference_index(root)
    for raw in raw_moves:
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
        if status and status not in ALLOWED_STATUS and not args.allow_unknown_status:
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
            "incoming_refs": incoming_refs(reference_index, source_rel),
            "blockers": blockers,
        }
        actions.append(action)
        global_blockers.extend(f"{source_rel}:{item}" for item in blockers)
    summary = build_summary(
        actions,
        reference_index[2],
        source_root=source_root,
        target_root=target_root,
    )
    payload = {
        "schema_version": 1,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "vault_fingerprint": vault_fingerprint(root),
        "policy": "move-only; no delete; no overwrite",
        "plan_type": plan_type,
        "ready_to_apply": not global_blockers,
        "blockers": global_blockers,
        "summary": summary,
        "actions": actions,
    }
    write_manifest(manifest_path, payload)
    print(json.dumps({
        "manifest": manifest_path.relative_to(root).as_posix(),
        "actions": len(actions),
        "summary": summary,
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
    parser.add_argument("command", choices=("plan", "tree-plan", "apply", "verify", "rollback"))
    parser.add_argument("--vault", required=True)
    parser.add_argument("--manifest", required=True, help="vault-relative JSON path")
    parser.add_argument("--move", action="append", default=[], help="SOURCE::TARGET; repeatable")
    parser.add_argument("--moves-file", help="UTF-8 file with one SOURCE::TARGET move per line")
    parser.add_argument("--source-root", help="vault-relative source directory for tree-plan")
    parser.add_argument("--target-root", help="vault-relative target directory for tree-plan")
    parser.add_argument("--allow-open-items", action="store_true")
    parser.add_argument(
        "--allow-unknown-status",
        action="store_true",
        help="plan with unknown frontmatter status while preserving it in the manifest",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.vault).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("vault is not a directory")
    manifest_path = confined(root, args.manifest)
    if args.command in {"plan", "tree-plan"}:
        if manifest_path.exists():
            raise FileExistsError(f"manifest already exists: {args.manifest}")
        if args.command == "tree-plan":
            if args.move or args.moves_file:
                raise ValueError("tree-plan does not accept --move or --moves-file")
            if not args.source_root or not args.target_root:
                raise ValueError("tree-plan requires --source-root and --target-root")
            moves, source_root, target_root = tree_moves(root, args.source_root, args.target_root)
            return plan(
                args,
                root,
                manifest_path,
                moves,
                plan_type="tree",
                source_root=source_root,
                target_root=target_root,
            )
        if args.source_root or args.target_root:
            raise ValueError("--source-root and --target-root require tree-plan")
        moves = list(args.move)
        if args.moves_file:
            moves.extend(read_moves_file(args.moves_file))
        if not moves:
            raise ValueError("plan requires at least one --move or --moves-file")
        return plan(
            args,
            root,
            manifest_path,
            moves,
            plan_type="moves-file" if args.moves_file else "moves",
        )
    if not manifest_path.is_file():
        raise FileNotFoundError(args.manifest)
    return globals()[args.command](args, root, manifest_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
