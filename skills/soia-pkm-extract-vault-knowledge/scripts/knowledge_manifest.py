#!/usr/bin/env python3
"""Plan or verify source-preserving extraction of long-term vault knowledge."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


TYPES = {"concept", "guide", "reference", "checklist", "pattern"}
STATES = {"draft", "stable", "needs_review", "deprecated"}
SENSITIVITY = {"public", "internal", "private", "restricted"}
FORBIDDEN_FIELDS = {"status", "priority", "project", "owner", "next_action"}
OPEN_ITEM_RE = re.compile(r"^[ \t]*[-*][ \t]+\[[ \t]\]", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRIVATE_PATH_RE = re.compile(r"(?:/[U]sers/|/[h]ome/[^/\s]+/)")
POSSIBLE_SECRET_RE = re.compile(
    r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|cookie)\b\s*[:=]\s*"
    r"(?!<|\{|YOUR_|EXAMPLE|example|placeholder|\*{4,}|x{4,}|null\b)[^\s#]{6,}"
)


def fingerprint(root: Path) -> str:
    return hashlib.sha256(str(root).encode()).hexdigest()[:16]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def confined(root: Path, raw: str, *, must_exist: bool = False) -> Path:
    value = Path(raw)
    if value.is_absolute() or not raw or raw in {".", ".."}:
        raise ValueError(f"path must be vault-relative: {raw!r}")
    cursor = root
    for part in value.parts:
        if part in {"", ".", ".."}:
            raise ValueError(f"unsafe path: {raw!r}")
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink path is not managed: {raw}")
    result = (root / value).resolve(strict=must_exist)
    try:
        result.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes vault: {raw}") from exc
    return result


def frontmatter(text: str) -> tuple[str, dict[str, str | list[str]]]:
    if not text.startswith("---\n"):
        return "", {}
    end = text.find("\n---", 4)
    if end < 0:
        return "", {}
    raw = text[4:end]
    result: dict[str, str | list[str]] = {}
    active: str | None = None
    for line in raw.splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_.-]+):[ \t]*(.*?)", line)
        if match:
            key, value = match.groups()
            result[key] = value.strip().strip('"\'')
            active = key if not value.strip() else None
            continue
        item = re.fullmatch(r"[ \t]+-[ \t]+(.*?)", line)
        if active and item:
            previous = result.get(active)
            if not isinstance(previous, list):
                previous = []
                result[active] = previous
            previous.append(item.group(1).strip().strip('"\''))
            continue
        if line and not line[0].isspace():
            active = None
    return raw, result


def tag_values(value: str | list[str] | None) -> set[str]:
    if isinstance(value, list):
        return {item.strip() for item in value if item.strip()}
    if not isinstance(value, str):
        return set()
    raw = value.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return {item.strip().strip('"\'') for item in raw.split(",") if item.strip()}


def normalized_links(text: str) -> set[str]:
    links = set()
    for raw in WIKILINK_RE.findall(text):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
        links.add(target.removesuffix(".md"))
    return links


def atomic_manifest(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"manifest already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        if path.exists():
            raise FileExistsError(f"manifest appeared during plan: {path.name}")
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def plan(args: argparse.Namespace, root: Path, manifest: Path) -> int:
    target = confined(root, args.target)
    target_rel = target.relative_to(root).as_posix()
    if target.suffix.lower() != ".md" or not target_rel.split("/", 1)[0].startswith("20_"):
        raise ValueError("target must be a Markdown file in the vault's 20 knowledge zone")
    sources = []
    seen: set[Path] = set()
    for raw in args.source:
        source = confined(root, raw, must_exist=True)
        if not source.is_file() or source in seen:
            raise ValueError(f"source must be a unique regular file: {raw}")
        seen.add(source)
        rel = source.relative_to(root).as_posix()
        sources.append({
            "path": rel,
            "size": source.stat().st_size,
            "sha256": digest(source),
            "expected_link": rel.removesuffix(".md"),
        })
    blockers = ["target_exists"] if target.exists() else []
    payload = {
        "schema_version": 1,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "vault_fingerprint": fingerprint(root),
        "policy": "source-preserving; create-only target; no secret values in manifest",
        "ready_to_write": not blockers,
        "blockers": blockers,
        "target": target_rel,
        "expected_type": args.type,
        "expected_sensitivity": args.sensitivity,
        "sources": sources,
    }
    atomic_manifest(manifest, payload)
    print(json.dumps({
        "manifest": manifest.relative_to(root).as_posix(),
        "sources": len(sources),
        "target": target_rel,
        "ready_to_write": not blockers,
        "blockers": blockers,
    }, ensure_ascii=False))
    return 0


def load_manifest(path: Path, root: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("vault_fingerprint") != fingerprint(root):
        raise ValueError("unsupported manifest or different vault")
    if not isinstance(payload.get("sources"), list):
        raise ValueError("manifest sources are invalid")
    return payload


def verify(args: argparse.Namespace, root: Path, manifest: Path) -> int:
    payload = load_manifest(manifest, root)
    issues: list[dict[str, str]] = []
    if not payload.get("ready_to_write"):
        issues.append({"path": payload.get("target", ""), "code": "plan_blocked"})
    expected_links = set()
    for item in payload["sources"]:
        source = confined(root, item["path"])
        expected_links.add(item["expected_link"])
        if not source.is_file():
            issues.append({"path": item["path"], "code": "source_missing"})
        elif source.stat().st_size != item["size"] or digest(source) != item["sha256"]:
            issues.append({"path": item["path"], "code": "source_drift"})

    target = confined(root, payload["target"])
    if not target.is_file():
        issues.append({"path": payload["target"], "code": "target_missing"})
    else:
        text = target.read_text(encoding="utf-8")
        raw_fm, fields = frontmatter(text)
        tags = tag_values(fields.get("tags"))
        required = {"title", "type", "knowledge_state", "sensitivity", "created", "updated"}
        for key in sorted(required):
            if not fields.get(key):
                issues.append({"path": payload["target"], "code": f"missing_field:{key}"})
        if not {"资料库", "长期知识"}.issubset(tags):
            issues.append({"path": payload["target"], "code": "missing_required_tags"})
        if fields.get("type") not in TYPES or fields.get("type") != payload.get("expected_type"):
            issues.append({"path": payload["target"], "code": "invalid_or_unexpected_type"})
        if fields.get("knowledge_state") not in STATES:
            issues.append({"path": payload["target"], "code": "invalid_knowledge_state"})
        if fields.get("sensitivity") not in SENSITIVITY or fields.get("sensitivity") != payload.get("expected_sensitivity"):
            issues.append({"path": payload["target"], "code": "invalid_or_unexpected_sensitivity"})
        for key in ("created", "updated"):
            if fields.get(key) and not DATE_RE.fullmatch(str(fields[key])):
                issues.append({"path": payload["target"], "code": f"invalid_date:{key}"})
        for key in sorted(FORBIDDEN_FIELDS.intersection(fields)):
            issues.append({"path": payload["target"], "code": f"forbidden_field:{key}"})
        source_fields = "\n".join(
            [str(fields.get("source", ""))]
            + ([*fields.get("sources", [])] if isinstance(fields.get("sources"), list) else [str(fields.get("sources", ""))])
        )
        if not expected_links.issubset(normalized_links(source_fields)):
            issues.append({"path": payload["target"], "code": "missing_exact_source_link"})
        if len(expected_links) == 1 and not fields.get("source"):
            issues.append({"path": payload["target"], "code": "single_source_requires_source"})
        if len(expected_links) > 1 and not fields.get("sources"):
            issues.append({"path": payload["target"], "code": "multiple_sources_require_sources"})
        if OPEN_ITEM_RE.search(text):
            issues.append({"path": payload["target"], "code": "open_item"})
        if PRIVATE_PATH_RE.search(text):
            issues.append({"path": payload["target"], "code": "private_absolute_path"})
        if POSSIBLE_SECRET_RE.search(text):
            issues.append({"path": payload["target"], "code": "possible_secret_value"})
        if not raw_fm:
            issues.append({"path": payload["target"], "code": "missing_frontmatter"})

    result = {"verified": not issues, "issues": issues, "target": payload["target"], "sources": len(payload["sources"])}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not issues else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "verify"))
    parser.add_argument("--vault", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--target")
    parser.add_argument("--type", choices=sorted(TYPES), default="guide")
    parser.add_argument("--sensitivity", choices=sorted(SENSITIVITY), default="internal")
    args = parser.parse_args()
    if args.command == "plan" and (not args.source or not args.target):
        parser.error("plan requires --source and --target")
    return args


def main() -> int:
    args = parse_args()
    root = Path(args.vault).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("vault is not a directory")
    manifest = confined(root, args.manifest)
    if args.command == "plan":
        if manifest.exists():
            raise FileExistsError(f"manifest already exists: {args.manifest}")
        return plan(args, root, manifest)
    if not manifest.is_file():
        raise FileNotFoundError(args.manifest)
    return verify(args, root, manifest)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
