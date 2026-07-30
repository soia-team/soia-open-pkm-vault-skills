#!/usr/bin/env python3
"""Plan and validate an article-to-PPT media bundle using only stdlib."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import posixpath
import re
import struct
import sys
import zipfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


PROVIDERS = {"auto", "local_editable", "notebooklm", "hybrid", "open_design"}
PROVIDER_CAPABILITIES = {
    "local_editable": {"local_editable"},
    "notebooklm": {"notebooklm"},
    "hybrid": {"local_editable", "notebooklm"},
    "open_design": {"open_design"},
}
KNOWN_PROVIDER_CAPABILITIES = {
    "local_editable",
    "officecli",
    "notebooklm",
    "open_design",
    "imagegen",
}
NETWORK_PROVIDERS = {"notebooklm", "open_design", "imagegen"}
PRIVACY_CLASSIFICATIONS = {"public", "internal", "confidential"}
NETWORK_POLICIES = {"allow", "deny"}
PERSISTENCE_MODES = {"bundle", "private_state"}
TEMPLATE_MODES = {"none", "strict_following"}
REVIEW_MODES = {"standard", "thorough"}
REQUIRED_PLANNING_ROLES = {"content_plan", "design_plan", "contract_card"}
REQUIRED_QA_ROLES = {"signature_proof", "content_critic", "design_critic", "host_validation"}
ALLOWED_HOSTS = {"microsoft_powerpoint", "apple_keynote", "libreoffice"}
CONFIG_ENV_VAR = "SOIA_PKM_ARTICLE_PPT_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path(
    "~/.config/soia-skills/soia-open-pkm-vault-skills/soia-pkm/"
    "soia-pkm-transform-article-ppt/config.yml"
).expanduser()
MIN_PREVIEW_WIDTH = 320
MIN_PREVIEW_HEIGHT = 180
MAX_PNG_DECODED_BYTES = 256 * 1024 * 1024
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
# The user-path patterns are written with [/] and [\\] character classes on
# purpose: regex semantics are identical, but the source line must not contain
# a literal `/Users/` or the repo audit's hardcoded-absolute-path check
# (scripts/audit_skills.py ABSOLUTE_PATH_RE) flags this detection pattern
# itself as a violation. Do not "simplify" back to plain slashes.
BANNED_TEXT = re.compile(
    r"(?:\b(?:notebook|source|artifact)_id\b|download_path|\[[A-Z0-9_]*PLACEHOLDER[A-Z0-9_]*\]|"
    r"[A-Z0-9_]+_PLACEHOLDER|[/]Users[/][^/\s]+[/]|[A-Za-z]:[\\]Users[\\])",
    re.IGNORECASE,
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_yaml_comment(raw: str) -> str:
    quote = ""
    escaped = False
    for index, character in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote == '"':
            escaped = True
            continue
        if character in {'"', "'"}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
            continue
        if character == "#" and not quote and (index == 0 or raw[index - 1].isspace()):
            return raw[:index].rstrip()
    return raw.rstrip()


def split_yaml_inline_list(raw: str) -> list[str]:
    values: list[str] = []
    start = 0
    quote = ""
    escaped = False
    for index, character in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote == '"':
            escaped = True
            continue
        if character in {'"', "'"}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
        elif character == "," and not quote:
            values.append(raw[start:index].strip())
            start = index + 1
    values.append(raw[start:].strip())
    return [value for value in values if value]


def parse_yaml_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_yaml_scalar(item) for item in split_yaml_inline_list(inner)]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def load_simple_yaml(path: Path) -> dict[str, Any]:
    """Load the documented config subset without adding a PyYAML dependency."""
    logical_lines: list[tuple[int, str, int]] = []
    for line_number, raw in enumerate(read_text(path).splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError(f"Config uses a tab for indentation at line {line_number}")
        content = strip_yaml_comment(raw).rstrip()
        if not content.strip():
            continue
        logical_lines.append((len(content) - len(content.lstrip(" ")), content.strip(), line_number))

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    for index, (indent, content, line_number) in enumerate(logical_lines):
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"Config list item has no list parent at line {line_number}")
            parent.append(parse_yaml_scalar(content[2:]))
            continue
        if ":" not in content or not isinstance(parent, dict):
            raise ValueError(f"Unsupported config syntax at line {line_number}")
        key, raw_value = content.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise ValueError(f"Invalid config key at line {line_number}: {key}")
        raw_value = raw_value.strip()
        if raw_value:
            parent[key] = parse_yaml_scalar(raw_value)
            continue
        next_is_list = bool(
            index + 1 < len(logical_lines)
            and logical_lines[index + 1][0] > indent
            and logical_lines[index + 1][1].startswith("- ")
        )
        child: Any = [] if next_is_list else {}
        parent[key] = child
        stack.append((indent, child))
    return root


def load_private_config(args: argparse.Namespace) -> dict[str, Any]:
    explicit = getattr(args, "config", None)
    environment = os.environ.get(CONFIG_ENV_VAR)
    raw_path = explicit or environment
    path = Path(str(raw_path)).expanduser() if raw_path else DEFAULT_CONFIG_FILE
    required = bool(explicit or environment)
    if not path.is_file():
        if required:
            raise FileNotFoundError(f"Private config does not exist: {path}")
        return {}
    config = load_simple_yaml(path.resolve())
    if config.get("schema_version") != 2:
        raise ValueError("Private config schema_version must be 2")
    return config


def nested_config(config: dict[str, Any], section: str, field: str) -> Any:
    bucket = config.get(section, {})
    return bucket.get(field) if isinstance(bucket, dict) else None


def apply_plan_config(args: argparse.Namespace, config: dict[str, Any]) -> argparse.Namespace:
    builtins = {
        "provider": "auto",
        "audience": "auto",
        "style": "auto",
        "slide_count": "auto",
        "image_count": 3,
        "infographic": False,
        "purpose": "auto",
        "delivery_context": "auto",
        "language": "auto",
        "review_mode": "standard",
        "template_mode": "none",
        "template_alias": "",
        "template_file": None,
        "template_sha256": "",
        "allowed_font": [],
        "privacy_classification": "public",
        "network": "auto",
        "provider_allowlist": "",
        "persist_intermediates": "auto",
        "state_root": None,
        "output_root": None,
    }
    mappings = {
        "provider": ("defaults", "provider"),
        "style": ("defaults", "style"),
        "slide_count": ("defaults", "slide_count"),
        "image_count": ("defaults", "image_count"),
        "infographic": ("defaults", "infographic"),
        "purpose": ("defaults", "purpose"),
        "delivery_context": ("defaults", "delivery_context"),
        "language": ("defaults", "language"),
        "review_mode": ("defaults", "review_mode"),
        "template_mode": ("template", "mode"),
        "template_alias": ("template", "alias"),
        "privacy_classification": ("privacy", "classification"),
        "network": ("privacy", "network"),
        "provider_allowlist": ("privacy", "provider_allowlist"),
        "persist_intermediates": ("privacy", "persist_intermediates"),
        "state_root": ("paths", "state_root"),
        "output_root": ("paths", "output_root"),
    }
    for argument, (section, field) in mappings.items():
        current = getattr(args, argument, None)
        configured = nested_config(config, section, field)
        setattr(args, argument, current if current is not None else configured)

    configured_alias = nested_config(config, "template", "alias")
    selected_alias = getattr(args, "template_alias", None)
    may_bind_config_template = not selected_alias or selected_alias == configured_alias
    template_mappings = {
        "template_file": "path",
        "template_sha256": "sha256",
        "allowed_font": "allowed_fonts",
    }
    for argument, field in template_mappings.items():
        current = getattr(args, argument, None)
        configured = nested_config(config, "template", field) if may_bind_config_template else None
        setattr(args, argument, current if current is not None else configured)

    for argument, default in builtins.items():
        if getattr(args, argument, None) is None:
            setattr(args, argument, default)
    args._private_config = config
    return args


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip().strip('"\'')
        fields[match.group(1)] = value
    return fields, text[end + 5 :]


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = re.sub(r"\s+", " ", value).strip(" ：:。.-")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def extract_source(article: Path) -> dict[str, Any]:
    raw = read_text(article)
    frontmatter, body = parse_frontmatter(raw)
    headings = unique(
        [match.group(2) for match in re.finditer(r"^(#{1,4})\s+(.+?)\s*$", body, re.MULTILINE)]
    )
    title_match = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    title = frontmatter.get("title") or (title_match.group(1).strip() if title_match else article.stem)

    concepts: list[str] = []
    patterns = [
        r"\*\*\s*\d+[\.、]\s*([^*（(\n]{1,80})(?:[（(][^）)\n]+[）)])?\s*\*\*",
        r"^\s*[-*+]\s+\*\*([^*\n]{2,80})\*\*",
    ]
    for pattern in patterns:
        concepts.extend(match.group(1) for match in re.finditer(pattern, body, re.MULTILINE))
    concepts = unique(concepts)

    return {
        "path": str(article.resolve()),
        "title": title,
        "author": frontmatter.get("author", ""),
        "url": frontmatter.get("url", ""),
        "published_at": frontmatter.get("published_at", ""),
        "sections": headings[:40],
        "concepts": concepts[:200],
        "contains_cjk": bool(re.search(r"[\u3400-\u9fff]", body)),
    }


def infer_slide_count(source: dict[str, Any]) -> int:
    concept_count = len(source["concepts"])
    section_count = len(source["sections"])
    if concept_count >= 12 or section_count >= 8:
        return 18
    if concept_count >= 6 or section_count >= 5:
        return 14
    return 10


def expected_entry(path: str, required: bool, **extra: Any) -> dict[str, Any]:
    return {"path": path, "required": required, **extra}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_provider_allowlist(raw: Any, classification: str) -> set[str]:
    if isinstance(raw, (list, tuple, set)):
        values = {str(item).strip() for item in raw if str(item).strip()}
    else:
        values = {item.strip() for item in str(raw or "").split(",") if item.strip()}
    if not values:
        values = (
            {"local_editable", "officecli"}
            if classification == "confidential"
            else set(KNOWN_PROVIDER_CAPABILITIES)
        )
    unknown = values - KNOWN_PROVIDER_CAPABILITIES
    if unknown:
        raise ValueError(f"Unsupported provider allowlist entries: {', '.join(sorted(unknown))}")
    return values


def git_checkout_root(path: Path) -> Path | None:
    """Return the containing Git checkout without invoking Git or following repo config."""
    candidate = path.expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / ".git").exists():
            return parent
    return None


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def paths_overlap(left: Path, right: Path) -> bool:
    return is_within(left, right) or is_within(right, left)


def build_privacy_contract(
    args: argparse.Namespace, provider: str, out_dir: Path
) -> tuple[dict[str, Any], dict[str, str]]:
    classification = str(getattr(args, "privacy_classification", "public"))
    if classification not in PRIVACY_CLASSIFICATIONS:
        raise ValueError(f"Unsupported privacy classification: {classification}")
    network = str(getattr(args, "network", "auto"))
    if network == "auto":
        network = "deny" if classification == "confidential" else "allow"
    if network not in NETWORK_POLICIES:
        raise ValueError(f"Unsupported network policy: {network}")
    persistence = str(getattr(args, "persist_intermediates", "auto"))
    if persistence == "auto":
        persistence = "private_state" if classification == "confidential" else "bundle"
    if persistence not in PERSISTENCE_MODES:
        raise ValueError(f"Unsupported intermediate persistence mode: {persistence}")

    allowlist = parse_provider_allowlist(getattr(args, "provider_allowlist", ""), classification)
    required_providers = set(PROVIDER_CAPABILITIES[provider])
    if int(getattr(args, "image_count", 0)) > 0:
        required_providers.add("imagegen")
    missing = required_providers - allowlist
    if missing:
        raise ValueError(
            f"Selected workflow requires providers outside the allowlist: {', '.join(sorted(missing))}"
        )
    networked = required_providers & NETWORK_PROVIDERS
    if network == "deny" and networked:
        raise ValueError(
            f"network=deny rejects network providers: {', '.join(sorted(networked))}"
        )

    raw_state_root = getattr(args, "state_root", None)
    raw_output_root = getattr(args, "output_root", None)
    if classification == "confidential":
        forbidden_allowlist = allowlist & NETWORK_PROVIDERS
        if forbidden_allowlist:
            raise ValueError(
                "confidential provider_allowlist cannot include network providers: "
                + ", ".join(sorted(forbidden_allowlist))
            )
        for label, raw in (
            ("out_dir", getattr(args, "out_dir", "")),
            ("state_root", raw_state_root),
            ("output_root", raw_output_root),
        ):
            if not raw or not Path(str(raw)).expanduser().is_absolute():
                raise ValueError(f"confidential mode requires an absolute {label}")
        if network != "deny":
            raise ValueError("confidential mode requires network=deny")
        if persistence != "private_state":
            raise ValueError("confidential mode requires persist_intermediates=private_state")

    state_root = Path(str(raw_state_root)).expanduser().resolve() if raw_state_root else out_dir
    output_root = Path(str(raw_output_root)).expanduser().resolve() if raw_output_root else out_dir
    if classification == "confidential":
        if not is_within(out_dir, state_root):
            raise ValueError("confidential out_dir must stay inside state_root")
        if paths_overlap(state_root, output_root):
            raise ValueError("confidential state_root and output_root must be separate trees")
        for label, path in (
            ("out_dir", out_dir),
            ("state_root", state_root),
            ("output_root", output_root),
        ):
            checkout = git_checkout_root(path)
            if checkout:
                raise ValueError(f"confidential {label} cannot be inside a Git checkout: {checkout}")

    privacy = {
        "classification": classification,
        "network": network,
        "provider_allowlist": sorted(allowlist),
        "persist_intermediates": persistence,
    }
    storage = {
        "state_root": str(state_root),
        "run_dir": str(out_dir),
        "output_root": str(output_root),
    }
    return privacy, storage


def build_template_contract(args: argparse.Namespace, classification: str) -> dict[str, Any]:
    mode = str(getattr(args, "template_mode", "none"))
    if mode not in TEMPLATE_MODES:
        raise ValueError(f"Unsupported template mode: {mode}")
    if mode == "none":
        return {"mode": "none"}

    alias = str(getattr(args, "template_alias", "")).strip()
    raw_path = str(getattr(args, "template_file", "") or "")
    declared_hash = str(getattr(args, "template_sha256", "") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", alias):
        raise ValueError("strict_following requires a lowercase template_alias using letters, digits, _ or -")
    if not raw_path or not Path(raw_path).expanduser().is_absolute():
        raise ValueError("strict_following requires an absolute template_file")
    template_path = Path(raw_path).expanduser().resolve()
    if not template_path.is_file() or template_path.suffix.lower() != ".pptx":
        raise ValueError("strict_following template_file must be an existing PPTX")
    if not inspect_pptx(template_path)["valid_ooxml"]:
        raise ValueError("strict_following template_file must be a valid PPTX OOXML package")
    if not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
        raise ValueError("strict_following requires a 64-character template_sha256")
    actual_hash = sha256_file(template_path)
    if actual_hash != declared_hash:
        raise ValueError("template_sha256 does not match template_file")
    if classification == "confidential":
        checkout = git_checkout_root(template_path)
        if checkout:
            raise ValueError(f"confidential template_file cannot be inside a Git checkout: {checkout}")
    raw_allowed_fonts = getattr(args, "allowed_font", None) or []
    if isinstance(raw_allowed_fonts, str):
        raw_allowed_fonts = [raw_allowed_fonts]
    allowed_fonts = sorted(
        {
            str(item).strip()
            for item in raw_allowed_fonts
            if str(item).strip()
        }
    )
    return {
        "mode": mode,
        "alias": alias,
        "sha256": actual_hash,
        "verified": True,
        "allowed_fonts": allowed_fonts,
    }


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    article = Path(args.article).expanduser().resolve()
    if not article.is_file():
        raise FileNotFoundError(f"Article does not exist: {article}")
    if args.provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {args.provider}")
    review_mode = getattr(args, "review_mode", "standard")
    if review_mode not in REVIEW_MODES:
        raise ValueError(f"Unsupported review mode: {review_mode}")

    provider = "local_editable" if args.provider == "auto" else args.provider
    out_dir_raw = Path(args.out_dir).expanduser()
    out_dir = out_dir_raw.resolve()
    privacy, storage = build_privacy_contract(args, provider, out_dir)
    template = build_template_contract(args, privacy["classification"])
    source = extract_source(article)
    slide_count = infer_slide_count(source) if args.slide_count == "auto" else int(args.slide_count)
    if slide_count < 1:
        raise ValueError("slide_count must be positive")
    if args.image_count < 0:
        raise ValueError("image_count cannot be negative")
    main_verdict = str(args.main_verdict).strip()
    if not main_verdict:
        raise ValueError("main_verdict must be non-empty")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = article.stem
    local_required = provider in {"local_editable", "hybrid", "open_design"}
    notebook_required = provider in {"notebooklm", "hybrid"}

    prompt_entries = []
    if local_required:
        prompt_entries.append(
            expected_entry("prompts/ppt-local.txt", True, role="editable_pptx", base="state")
        )
    if notebook_required:
        prompt_entries.append(
            expected_entry("prompts/ppt-notebooklm.txt", True, role="notebooklm_pptx", base="state")
        )
    for index in range(1, args.image_count + 1):
        prompt_entries.append(
            expected_entry(
                f"prompts/image-{index:02d}.txt", True, role="visual_asset", base="state"
            )
        )
    if args.infographic:
        prompt_entries.append(
            expected_entry("prompts/infographic.txt", True, role="infographic", base="state")
        )

    delivery_base = "delivery" if privacy["classification"] == "confidential" else "state"
    qa_entries = [
        expected_entry("qa/signature-proof.json", True, role="signature_proof", base="state"),
        expected_entry("qa/critic-content.json", True, role="content_critic", base="state"),
        expected_entry("qa/critic-design.json", True, role="design_critic", base="state"),
        expected_entry("qa/host-validation.json", True, role="host_validation", base="state"),
    ]
    if template["mode"] == "strict_following":
        qa_entries.append(
            expected_entry(
                "qa/template-fidelity.json", True, role="template_fidelity", base="state"
            )
        )
    expected = {
        "editable_pptx": expected_entry(
            f"{stem}-editable.pptx",
            local_required,
            base=delivery_base,
            min_slides=max(1, slide_count - 2),
            editable_required=True,
            preview_dir="previews/editable",
        ),
        "notebooklm_pptx": expected_entry(
            f"{stem}-notebooklm.pptx",
            notebook_required,
            base=delivery_base,
            min_slides=max(1, slide_count - 4),
            editable_required=False,
            preview_dir="previews/notebooklm",
        ),
        "infographic": expected_entry(
            f"{stem}-infographic.png",
            bool(args.infographic),
            base=delivery_base,
            min_width=800,
            min_height=800,
        ),
        "visual_assets": {
            "directory": "assets/imagegen",
            "base": "state",
            "required": args.image_count > 0,
            "minimum_count": args.image_count,
            "min_width": 768,
            "min_height": 512,
        },
        "prompts": prompt_entries,
        "planning": [
            expected_entry(
                "planning/content-plan.json", True, role="content_plan", base="state"
            ),
            expected_entry(
                "planning/design-plan.json", True, role="design_plan", base="state"
            ),
            expected_entry(
                "planning/contract-card.json", True, role="contract_card", base="state"
            ),
        ],
        "qa": qa_entries,
    }

    return {
        "schema_version": 3,
        "planned_at": now_iso(),
        "source": source,
        "template": template,
        "privacy": privacy,
        "storage": storage,
        "request": {
            "provider": provider,
            "audience": args.audience,
            "style": args.style,
            "slide_count": slide_count,
            "image_count": args.image_count,
            "infographic": bool(args.infographic),
            "main_verdict": main_verdict,
            "purpose": getattr(args, "purpose", "auto"),
            "delivery_context": getattr(args, "delivery_context", "auto"),
            "language": getattr(args, "language", "auto"),
            "review_mode": review_mode,
        },
        "expected": expected,
    }


def write_planning_templates(out_dir: Path, manifest: dict[str, Any]) -> None:
    """Create non-destructive planning and QA templates for the agent to complete."""
    request = manifest["request"]
    source = manifest["source"]
    expected = manifest["expected"]
    output_scope = [
        role
        for role in ("editable_pptx", "notebooklm_pptx", "infographic")
        if expected[role]["required"]
    ]
    if expected["visual_assets"]["required"]:
        output_scope.append("visual_assets")
    primary_preview_dir = (
        expected["editable_pptx"]["preview_dir"]
        if expected["editable_pptx"]["required"]
        else expected["notebooklm_pptx"]["preview_dir"]
    )
    templates = {
        "planning/content-plan.json": {
            "schema_version": 1,
            "status": "draft",
            "main_verdict": request["main_verdict"],
            "claim_ledger": [],
            "narrative_arc": [],
            "slide_plan": [],
            "open_questions": [],
        },
        "planning/design-plan.json": {
            "schema_version": 1,
            "status": "draft",
            "design_language": "",
            "boldness": "balanced+",
            "signature_move": "",
            "signature_slides": [],
            "semantic_colors": {},
            "slide_shapes": [],
            "rhythm_map": [],
        },
        "planning/contract-card.json": {
            "schema_version": 1,
            "status": "draft",
            "source": source["path"],
            "audience": request["audience"],
            "purpose": request["purpose"],
            "delivery_context": request["delivery_context"],
            "language": request["language"],
            "editability": "editable_pptx"
            if expected["editable_pptx"]["required"]
            else "non_editable_pptx",
            "review_mode": request["review_mode"],
            "output_scope": output_scope,
            "template_mode": manifest["template"]["mode"],
            "template_alias": manifest["template"].get("alias", ""),
            "privacy_classification": manifest["privacy"]["classification"],
            "network": manifest["privacy"]["network"],
        },
        "qa/signature-proof.json": {
            "schema_version": 1,
            "status": "pending",
            "signature_move": "",
            "slides": [],
            "preview_paths": [],
            "reason": "",
        },
        "qa/critic-content.json": {
            "schema_version": 1,
            "status": "pending",
            "lens": "content",
            "reviewer": "",
            "independent_of_builder": False,
            "round": 0,
            "verdict": "",
            "blockers": [],
            "majors": [],
            "advisories": [],
        },
        "qa/critic-design.json": {
            "schema_version": 1,
            "status": "pending",
            "lens": "design",
            "reviewer": "",
            "independent_of_builder": False,
            "round": 0,
            "verdict": "",
            "blockers": [],
            "majors": [],
            "advisories": [],
        },
        "qa/host-validation.json": {
            "schema_version": 1,
            "status": "pending",
            "host": "",
            "preview_dir": primary_preview_dir,
            "rendered_slide_count": 0,
            "cjk_checked": False,
            "cjk_passed": False,
            "notes": "",
        },
    }
    if manifest["template"]["mode"] == "strict_following":
        templates["qa/template-fidelity.json"] = {
            "schema_version": 1,
            "status": "pending",
            "template_alias": manifest["template"]["alias"],
            "template_sha256": manifest["template"]["sha256"],
            "allowed_fonts": manifest["template"].get("allowed_fonts", []),
            "expected_editable_charts": 0,
            "expected_native_tables": 0,
            "table_pagination_required": False,
            "table_page_groups": [],
            "notes": "",
        }
    for relative_path, payload in templates.items():
        path = out_dir / relative_path
        if not path.exists():
            write_json(path, payload)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def natural_slide_key(name: str) -> tuple[int, str]:
    match = re.search(r"slide(\d+)\.xml$", name)
    return (int(match.group(1)) if match else 10**9, name)


def ooxml_parts_digest(archive: zipfile.ZipFile, names: list[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        payload = archive.read(name)
        try:
            root = ET.fromstring(payload)
            relationship_prefix = f"{{{NS['r']}}}"
            for node in root.iter():
                for attribute in tuple(node.attrib):
                    if attribute.startswith(relationship_prefix):
                        node.attrib.pop(attribute, None)
                attributes = sorted(node.attrib.items())
                node.attrib.clear()
                node.attrib.update(attributes)
            payload = ET.tostring(root, encoding="utf-8")
        except ET.ParseError:
            pass
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def shape_overflows_slide(node: ET.Element, slide_size: tuple[int, int] | None) -> bool:
    if slide_size is None:
        return False
    xfrm = node.find("./p:xfrm", NS)
    if xfrm is None:
        xfrm = node.find("./p:spPr/a:xfrm", NS)
    if xfrm is None:
        return False
    offset = xfrm.find("./a:off", NS)
    extent = xfrm.find("./a:ext", NS)
    if offset is None or extent is None:
        return False
    try:
        x = int(offset.get("x", "0"))
        y = int(offset.get("y", "0"))
        cx = int(extent.get("cx", "0"))
        cy = int(extent.get("cy", "0"))
    except ValueError:
        return True
    return x < 0 or y < 0 or cx < 0 or cy < 0 or x + cx > slide_size[0] or y + cy > slide_size[1]


def inspect_pptx(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "valid_ooxml": False,
        "slides": 0,
        "text_slides": 0,
        "image_only_slides": 0,
        "editable_ratio": 0.0,
        "banned_text_matches": [],
        "slide_size": None,
        "master_count": 0,
        "layout_count": 0,
        "master_digest": "",
        "layout_digest": "",
        "fonts": [],
        "chart_references": 0,
        "bound_chart_count": 0,
        "unbound_chart_references": 0,
        "chart_parts": 0,
        "table_count": 0,
        "slide_table_counts": {},
        "overflow_count": 0,
        "orphan_connector_count": 0,
        "parse_errors": [],
    }
    if not path.is_file() or not zipfile.is_zipfile(path):
        return result

    with zipfile.ZipFile(path) as archive:
        archive_names = set(archive.namelist())
        names = sorted(
            [name for name in archive_names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)],
            key=natural_slide_key,
        )
        masters = sorted(
            name
            for name in archive_names
            if re.fullmatch(r"ppt/slideMasters/slideMaster\d+\.xml", name)
        )
        layouts = sorted(
            name
            for name in archive_names
            if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", name)
        )
        conventional_charts = sorted(
            name for name in archive_names if re.fullmatch(r"ppt/charts/chart\d+\.xml", name)
        )
        result["slides"] = len(names)
        result["master_count"] = len(masters)
        result["layout_count"] = len(layouts)
        result["master_digest"] = ooxml_parts_digest(archive, masters) if masters else ""
        result["layout_digest"] = ooxml_parts_digest(archive, layouts) if layouts else ""
        text_slides = 0
        image_only = 0
        matches: set[str] = set()
        fonts: set[str] = set()
        parse_errors: list[str] = []
        if "[Content_Types].xml" in archive_names:
            try:
                ET.fromstring(archive.read("[Content_Types].xml"))
            except ET.ParseError:
                parse_errors.append("[Content_Types].xml")
        presentation_root: ET.Element | None = None
        if "ppt/presentation.xml" in archive_names:
            try:
                presentation_root = ET.fromstring(archive.read("ppt/presentation.xml"))
            except ET.ParseError:
                parse_errors.append("ppt/presentation.xml")
        if presentation_root is not None:
            size = presentation_root.find(".//p:sldSz", NS)
            if size is not None:
                try:
                    result["slide_size"] = [int(size.get("cx", "0")), int(size.get("cy", "0"))]
                except ValueError:
                    parse_errors.append("ppt/presentation.xml:sldSz")

        slide_table_counts: dict[str, int] = {}
        overflow_count = 0
        orphan_connector_count = 0
        chart_references = 0
        bound_chart_count = 0
        unbound_chart_references = 0
        discovered_chart_parts: set[str] = set(conventional_charts)
        for index, name in enumerate(names, 1):
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                parse_errors.append(name)
                continue
            texts = [(node.text or "") for node in root.findall(".//a:t", NS)]
            pictures = root.findall(".//p:pic", NS)
            shapes = root.findall(".//p:sp", NS)
            tables = root.findall(".//a:tbl", NS)
            connectors = root.findall(".//p:cxnSp", NS)
            chart_nodes = root.findall(".//c:chart", NS)
            chart_references += len(chart_nodes)
            relationship_name = (
                f"ppt/slides/_rels/{posixpath.basename(name)}.rels"
            )
            relationships: dict[str, str] = {}
            if relationship_name in archive_names:
                try:
                    relationship_root = ET.fromstring(archive.read(relationship_name))
                    for node in relationship_root.findall("./pr:Relationship", NS):
                        if not str(node.get("Type", "")).endswith("/chart"):
                            continue
                        target = str(node.get("Target", ""))
                        resolved_target = (
                            target.lstrip("/")
                            if target.startswith("/")
                            else posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                        )
                        relationships[str(node.get("Id", ""))] = resolved_target
                except ET.ParseError:
                    parse_errors.append(relationship_name)
            for chart_node in chart_nodes:
                relationship_id = str(chart_node.get(f"{{{NS['r']}}}id", ""))
                target = relationships.get(relationship_id, "")
                if target not in archive_names:
                    unbound_chart_references += 1
                    continue
                try:
                    chart_root = ET.fromstring(archive.read(target))
                except ET.ParseError:
                    parse_errors.append(target)
                    unbound_chart_references += 1
                    continue
                if chart_root.tag != f"{{{NS['c']}}}chartSpace":
                    unbound_chart_references += 1
                    continue
                discovered_chart_parts.add(target)
                bound_chart_count += 1
            slide_table_counts[str(index)] = len(tables)
            for node in (
                *shapes,
                *pictures,
                *root.findall(".//p:graphicFrame", NS),
                *connectors,
            ):
                if shape_overflows_slide(
                    node,
                    tuple(result["slide_size"]) if result["slide_size"] else None,
                ):
                    overflow_count += 1
            orphan_connector_count += sum(
                1
                for connector in connectors
                if connector.find(".//a:stCxn", NS) is None
                or connector.find(".//a:endCxn", NS) is None
            )
            joined = " ".join(texts)
            if joined.strip():
                text_slides += 1
            if pictures and not joined.strip() and not shapes:
                image_only += 1
            matches.update(match.group(0) for match in BANNED_TEXT.finditer(joined))

        font_parts = [
            name
            for name in archive_names
            if name.endswith(".xml")
            and name.startswith(
                ("ppt/slides/", "ppt/slideMasters/", "ppt/slideLayouts/", "ppt/theme/")
            )
        ]
        for name in sorted(font_parts):
            try:
                root = ET.fromstring(archive.read(name))
            except ET.ParseError:
                if name not in parse_errors:
                    parse_errors.append(name)
                continue
            for node in root.iter():
                typeface = str(node.attrib.get("typeface", "")).strip()
                if typeface and not typeface.startswith(("+mj-", "+mn-")):
                    fonts.add(typeface)

        for name in sorted(discovered_chart_parts):
            try:
                ET.fromstring(archive.read(name))
            except ET.ParseError:
                parse_errors.append(name)

        result.update(
            {
                "valid_ooxml": bool(
                    names
                    and masters
                    and layouts
                    and "[Content_Types].xml" in archive_names
                    and presentation_root is not None
                    and result["slide_size"]
                    and not parse_errors
                ),
                "text_slides": text_slides,
                "image_only_slides": image_only,
                "editable_ratio": round(text_slides / len(names), 3) if names else 0.0,
                "banned_text_matches": sorted(matches),
                "fonts": sorted(fonts),
                "chart_references": chart_references,
                "bound_chart_count": bound_chart_count,
                "unbound_chart_references": unbound_chart_references,
                "chart_parts": len(discovered_chart_parts),
                "table_count": sum(slide_table_counts.values()),
                "slide_table_counts": slide_table_counts,
                "overflow_count": overflow_count,
                "orphan_connector_count": orphan_connector_count,
                "parse_errors": sorted(set(parse_errors)),
            }
        )
    return result


def png_raster_is_decodable(
    compressed: bytes,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> bool:
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    allowed_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if not compressed or color_type not in channels or bit_depth not in allowed_depths[color_type]:
        return False
    bits_per_pixel = channels[color_type] * bit_depth
    passes = (
        ((0, 0, 1, 1),)
        if interlace == 0
        else (
            (0, 0, 8, 8),
            (4, 0, 8, 8),
            (0, 4, 4, 8),
            (2, 0, 4, 4),
            (0, 2, 2, 4),
            (1, 0, 2, 2),
            (0, 1, 1, 2),
        )
    )
    row_layout: list[tuple[int, int]] = []
    expected_size = 0
    for start_x, start_y, step_x, step_y in passes:
        pass_width = 0 if width <= start_x else (width - start_x + step_x - 1) // step_x
        pass_height = 0 if height <= start_y else (height - start_y + step_y - 1) // step_y
        if pass_width < 1 or pass_height < 1:
            continue
        row_bytes = (pass_width * bits_per_pixel + 7) // 8
        row_layout.append((pass_height, row_bytes))
        expected_size += pass_height * (row_bytes + 1)
        if expected_size > MAX_PNG_DECODED_BYTES:
            return False
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(compressed, expected_size + 1)
    except zlib.error:
        return False
    if (
        len(decoded) != expected_size
        or decoder.unconsumed_tail
        or decoder.unused_data
        or not decoder.eof
    ):
        return False
    offset = 0
    for row_count, row_bytes in row_layout:
        for _ in range(row_count):
            if decoded[offset] > 4:
                return False
            offset += row_bytes + 1
    return offset == len(decoded)


def png_dimensions(path: Path) -> tuple[int, int] | None:
    """Return dimensions only for a structurally complete PNG.

    This intentionally validates the full chunk envelope, CRCs, IDAT presence,
    and terminal IEND instead of trusting the first 24 bytes. It is not an image
    renderer, but it rejects truncated/header-only files as delivery evidence.
    """
    try:
        with path.open("rb") as handle:
            if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                return None
            dimensions: tuple[int, int] | None = None
            bit_depth = -1
            color_type = -1
            interlace = -1
            saw_plte = False
            saw_idat = False
            idat_ended = False
            idat_parts: list[bytes] = []
            idat_bytes = 0
            first_chunk = True
            while True:
                length_bytes = handle.read(4)
                if len(length_bytes) != 4:
                    return None
                length = struct.unpack(">I", length_bytes)[0]
                if length > 64 * 1024 * 1024:
                    return None
                chunk_type = handle.read(4)
                data = handle.read(length)
                crc_bytes = handle.read(4)
                if len(chunk_type) != 4 or len(data) != length or len(crc_bytes) != 4:
                    return None
                expected_crc = struct.unpack(">I", crc_bytes)[0]
                if (binascii.crc32(chunk_type + data) & 0xFFFFFFFF) != expected_crc:
                    return None
                if first_chunk:
                    if chunk_type != b"IHDR" or length != 13:
                        return None
                    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                        ">IIBBBBB", data
                    )
                    if (
                        width < 1
                        or height < 1
                        or color_type not in {0, 2, 3, 4, 6}
                        or compression != 0
                        or filtering != 0
                        or interlace not in {0, 1}
                    ):
                        return None
                    dimensions = (width, height)
                    first_chunk = False
                elif chunk_type == b"IHDR":
                    return None
                if chunk_type == b"IDAT":
                    if idat_ended:
                        return None
                    saw_idat = True
                    idat_bytes += len(data)
                    if idat_bytes > MAX_PNG_DECODED_BYTES:
                        return None
                    idat_parts.append(data)
                elif saw_idat:
                    idat_ended = True
                if chunk_type == b"PLTE":
                    if saw_idat or length < 3 or length > 768 or length % 3:
                        return None
                    saw_plte = True
                if chunk_type == b"IEND":
                    if (
                        length != 0
                        or not saw_idat
                        or (color_type == 3 and not saw_plte)
                        or handle.read(1)
                        or dimensions is None
                        or not png_raster_is_decodable(
                            b"".join(idat_parts),
                            dimensions[0],
                            dimensions[1],
                            bit_depth,
                            color_type,
                            interlace,
                        )
                    ):
                        return None
                    return dimensions
    except (OSError, struct.error):
        return None


def valid_preview_dimensions(path: Path) -> bool:
    dims = png_dimensions(path)
    return bool(dims and dims[0] >= MIN_PREVIEW_WIDTH and dims[1] >= MIN_PREVIEW_HEIGHT)


def resolve_inside(out_dir: Path, raw_path: Any) -> Path | None:
    """Resolve a relative artifact path without allowing escape from the bundle."""
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return None
    resolved = (out_dir / candidate).resolve()
    try:
        resolved.relative_to(out_dir.resolve())
    except ValueError:
        return None
    return resolved


def resolve_artifact(out_dir: Path, manifest: dict[str, Any], entry: dict[str, Any]) -> Path:
    base = entry.get("base", "state")
    if base == "state":
        root = out_dir
    elif base == "delivery":
        raw_root = manifest.get("storage", {}).get("output_root", "")
        root = Path(str(raw_root)).expanduser()
        if not root.is_absolute():
            raise ValueError("Delivery artifacts require an absolute storage.output_root")
        root = root.resolve()
    else:
        raise ValueError(f"Unsupported artifact base: {base}")
    path = resolve_inside(root, entry["path"])
    if path is None:
        raise ValueError(f"Artifact path escapes its {base} root: {entry.get('path')}")
    return path


def add_problem(bucket: list[dict[str, str]], code: str, message: str) -> None:
    bucket.append({"code": code, "message": message})


def read_json_artifact(path: Path, errors: list[dict[str, str]], code: str) -> dict[str, Any] | None:
    if not path.is_file():
        add_problem(errors, f"missing_{code}", f"Missing required file: {path}")
        return None
    try:
        payload = json.loads(read_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        add_problem(errors, f"invalid_{code}", f"Invalid JSON in {path}: {exc}")
        return None
    if not isinstance(payload, dict):
        add_problem(errors, f"invalid_{code}", f"Expected a JSON object in {path}")
        return None
    return payload


def validate_content_plan(
    payload: dict[str, Any], manifest: dict[str, Any], errors: list[dict[str, str]]
) -> None:
    if payload.get("status") != "approved":
        add_problem(errors, "content_plan_not_approved", "Content plan status must be approved")
    if not str(payload.get("main_verdict", "")).strip():
        add_problem(errors, "content_plan_missing_verdict", "Content plan must declare main_verdict")
    manifest_verdict = str(manifest.get("request", {}).get("main_verdict", "")).strip()
    if str(payload.get("main_verdict", "")).strip() != manifest_verdict:
        add_problem(
            errors,
            "content_plan_verdict_mismatch",
            "Content plan main_verdict does not match the manifest request",
        )

    claims = payload.get("claim_ledger")
    if not isinstance(claims, list) or not claims:
        add_problem(errors, "claim_ledger_empty", "Content plan must contain a non-empty claim_ledger")
    else:
        allowed_statuses = {"source-confirmed", "inference", "unverified"}
        allowed_treatments = {"label", "exclude", "verify"}
        for index, claim in enumerate(claims, 1):
            if not isinstance(claim, dict):
                add_problem(errors, "claim_ledger_invalid", f"Claim {index} must be an object")
                continue
            if not str(claim.get("claim", "")).strip():
                add_problem(errors, "claim_missing_text", f"Claim {index} has no claim text")
            status = claim.get("status")
            if status not in allowed_statuses:
                add_problem(errors, "claim_status_invalid", f"Claim {index} has invalid status: {status}")
            if status in {"source-confirmed", "inference"} and not str(claim.get("source_anchor", "")).strip():
                add_problem(errors, "claim_missing_anchor", f"Claim {index} has no source_anchor")
            if status == "unverified" and claim.get("treatment") not in allowed_treatments:
                add_problem(
                    errors,
                    "claim_unverified_without_treatment",
                    f"Claim {index} must be labelled, excluded, or verified",
                )

    slide_plan = payload.get("slide_plan")
    minimum = max(1, int(manifest["request"]["slide_count"]) - 2)
    if not isinstance(slide_plan, list) or len(slide_plan) < minimum:
        add_problem(
            errors,
            "slide_plan_too_short",
            f"Content plan has {len(slide_plan) if isinstance(slide_plan, list) else 0} slides; expected at least {minimum}",
        )
    elif any(
        not isinstance(slide, dict)
        or not str(slide.get("title", "")).strip()
        or not str(slide.get("page_job", "")).strip()
        or not str(slide.get("source_anchor", "")).strip()
        for slide in slide_plan
    ):
        add_problem(
            errors,
            "slide_plan_incomplete",
            "Every slide plan row needs title, page_job, and source_anchor",
        )


def validate_design_plan(
    payload: dict[str, Any], manifest: dict[str, Any], errors: list[dict[str, str]]
) -> None:
    if payload.get("status") != "approved":
        add_problem(errors, "design_plan_not_approved", "Design plan status must be approved")
    for field in ("design_language", "signature_move"):
        if not str(payload.get(field, "")).strip():
            add_problem(errors, f"design_plan_missing_{field}", f"Design plan must declare {field}")
    if not isinstance(payload.get("signature_slides"), list) or not payload["signature_slides"]:
        add_problem(errors, "design_plan_missing_signature_slides", "Design plan must name signature_slides")
    if not isinstance(payload.get("semantic_colors"), dict) or not payload["semantic_colors"]:
        add_problem(errors, "design_plan_missing_semantic_colors", "Design plan must define semantic_colors")
    if not isinstance(payload.get("rhythm_map"), list) or not payload["rhythm_map"]:
        add_problem(errors, "design_plan_missing_rhythm_map", "Design plan must define a rhythm_map")
    shapes = payload.get("slide_shapes")
    if int(manifest["request"]["slide_count"]) >= 8 and (
        not isinstance(shapes, list) or len(set(map(str, shapes))) < 4
    ):
        add_problem(errors, "design_plan_low_shape_variety", "Decks with 8+ slides need at least 4 slide shapes")


def expected_output_scope(manifest: dict[str, Any]) -> list[str]:
    expected = manifest["expected"]
    scope = [
        role
        for role in ("editable_pptx", "notebooklm_pptx", "infographic")
        if expected[role]["required"]
    ]
    if expected["visual_assets"]["required"]:
        scope.append("visual_assets")
    return scope


def validate_contract_card(
    payload: dict[str, Any], manifest: dict[str, Any], errors: list[dict[str, str]]
) -> None:
    if payload.get("status") != "approved":
        add_problem(errors, "contract_card_not_approved", "Contract card status must be approved")
    required_fields = [
        "source",
        "audience",
        "purpose",
        "delivery_context",
        "language",
        "editability",
        "review_mode",
        "output_scope",
    ]
    if int(manifest.get("schema_version", 1) or 1) >= 3:
        required_fields.extend(("template_mode", "privacy_classification", "network"))
    for field in required_fields:
        value = payload.get(field)
        if value in (None, "", [], {}):
            add_problem(errors, f"contract_card_missing_{field}", f"Contract card must declare {field}")
        elif field in {"audience", "purpose", "delivery_context", "language"} and value == "auto":
            add_problem(errors, f"contract_card_unresolved_{field}", f"Contract card must resolve {field}")

    request = manifest["request"]
    expected_values: dict[str, Any] = {
        "audience": request["audience"],
        "purpose": request["purpose"],
        "delivery_context": request["delivery_context"],
        "language": request["language"],
        "editability": "editable_pptx"
        if manifest["expected"]["editable_pptx"]["required"]
        else "non_editable_pptx",
        "review_mode": request["review_mode"],
    }
    if int(manifest.get("schema_version", 1) or 1) >= 3:
        expected_values.update(
            {
                "template_mode": manifest.get("template", {}).get("mode", "none"),
                "template_alias": manifest.get("template", {}).get("alias", ""),
                "privacy_classification": manifest.get("privacy", {}).get(
                    "classification", "public"
                ),
                "network": manifest.get("privacy", {}).get("network", "allow"),
            }
        )
    for field, expected_value in expected_values.items():
        if payload.get(field) != expected_value:
            add_problem(
                errors,
                f"contract_card_{field}_mismatch",
                f"Contract card {field} does not match the manifest",
            )
    source_value = payload.get("source")
    try:
        source_matches = Path(str(source_value)).expanduser().resolve() == Path(
            manifest["source"]["path"]
        ).expanduser().resolve()
    except (OSError, RuntimeError):
        source_matches = source_value == manifest["source"]["path"]
    if not source_matches:
        add_problem(
            errors,
            "contract_card_source_mismatch",
            "Contract card source does not match the manifest",
        )
    scope = payload.get("output_scope")
    if not isinstance(scope, list) or set(map(str, scope)) != set(expected_output_scope(manifest)):
        add_problem(
            errors,
            "contract_card_output_scope_mismatch",
            "Contract card output_scope does not match required manifest outputs",
        )


def validate_signature_proof(
    payload: dict[str, Any],
    design_plan: dict[str, Any] | None,
    manifest: dict[str, Any],
    out_dir: Path,
    errors: list[dict[str, str]],
) -> None:
    status = payload.get("status")
    if status == "skipped":
        if not str(payload.get("reason", "")).strip():
            add_problem(errors, "signature_proof_skip_without_reason", "Skipped signature proof needs a reason")
        slide_count = int(manifest["request"]["slide_count"])
        conservative = bool(design_plan and design_plan.get("boldness") == "conservative")
        if slide_count > 2 and not conservative:
            add_problem(
                errors,
                "signature_proof_skip_not_allowed",
                "Signature proof may be skipped only for a conservative design or a 1-2 slide task",
            )
        return
    if status != "passed":
        add_problem(errors, "signature_proof_pending", "Signature proof must pass or be explicitly skipped")
        return
    slides = payload.get("slides")
    previews = payload.get("preview_paths")
    if not isinstance(slides, list) or not slides or not isinstance(previews, list) or not previews:
        add_problem(errors, "signature_proof_incomplete", "Passed signature proof needs slides and preview_paths")
        return
    if design_plan:
        declared = {str(item) for item in design_plan.get("signature_slides", [])}
        proven = {str(item) for item in slides}
        if declared and not declared.intersection(proven):
            add_problem(errors, "signature_proof_mismatch", "Proof does not include a declared signature slide")
        if str(payload.get("signature_move", "")).strip() != str(
            design_plan.get("signature_move", "")
        ).strip():
            add_problem(
                errors,
                "signature_proof_move_mismatch",
                "Signature proof signature_move does not match the design plan",
            )
    resolved_previews = [(path, resolve_inside(out_dir, path)) for path in previews]
    primary_key = (
        "editable_pptx"
        if manifest.get("expected", {}).get("editable_pptx", {}).get("required") is True
        else "notebooklm_pptx"
    )
    primary_preview_dir = resolve_inside(
        out_dir,
        manifest.get("expected", {}).get(primary_key, {}).get("preview_dir", ""),
    )
    wrong_origin = [
        path
        for path, resolved in resolved_previews
        if primary_preview_dir is None
        or resolved is None
        or resolved.parent != primary_preview_dir.resolve()
    ]
    if wrong_origin:
        add_problem(
            errors,
            "signature_proof_preview_wrong_origin",
            f"Signature proof previews must come from the primary deck preview_dir: {wrong_origin}",
        )
    missing_previews = [path for path, resolved in resolved_previews if resolved is None or not resolved.is_file()]
    if missing_previews:
        add_problem(
            errors,
            "signature_proof_preview_missing",
            f"Signature proof preview does not exist: {missing_previews}",
        )
        return
    invalid_previews = [
        path
        for path, resolved in resolved_previews
        if resolved is None or not valid_preview_dimensions(resolved)
    ]
    if invalid_previews:
        add_problem(
            errors,
            "signature_proof_preview_invalid",
            f"Signature proof preview is not a valid, reasonably sized PNG: {invalid_previews}",
        )
    proven_slides: set[str] = set()
    invalid_slides: list[Any] = []
    for item in slides:
        try:
            number = int(item)
        except (TypeError, ValueError):
            invalid_slides.append(item)
            continue
        if number < 1:
            invalid_slides.append(item)
        else:
            proven_slides.add(str(number))
    preview_slides: set[str] = set()
    malformed_paths: list[str] = []
    for path in previews:
        match = re.fullmatch(r"slide-0*(\d+)\.png", Path(str(path)).name)
        if not match:
            malformed_paths.append(str(path))
        else:
            preview_slides.add(str(int(match.group(1))))
    if (
        invalid_slides
        or malformed_paths
        or len(proven_slides) != len(slides)
        or len(preview_slides) != len(previews)
        or preview_slides != proven_slides
    ):
        add_problem(
            errors,
            "signature_proof_slide_preview_mismatch",
            "Signature proof slides must map exactly to slide-N.png preview paths",
        )


def validate_critic(payload: dict[str, Any], lens: str, errors: list[dict[str, str]]) -> None:
    if payload.get("lens") != lens:
        add_problem(errors, f"critic_{lens}_wrong_lens", f"Critic artifact must declare lens={lens}")
    if not str(payload.get("reviewer", "")).strip() or payload.get("independent_of_builder") is not True:
        add_problem(
            errors,
            f"critic_{lens}_not_independent",
            f"{lens} critic must name a reviewer independent of the builder",
        )
    if payload.get("verdict") != "consent":
        add_problem(errors, f"critic_{lens}_not_consented", f"{lens} critic must consent")
    if int(payload.get("round", 0) or 0) < 1:
        add_problem(errors, f"critic_{lens}_no_round", f"{lens} critic must record at least one round")
    if payload.get("blockers"):
        add_problem(errors, f"critic_{lens}_blockers", f"{lens} critic has unresolved blockers")
    if payload.get("majors"):
        add_problem(errors, f"critic_{lens}_majors", f"{lens} critic has unresolved major findings")


def validate_template_fidelity(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    template_inspection: dict[str, Any] | None,
    output_inspection: dict[str, Any] | None,
    errors: list[dict[str, str]],
) -> None:
    template = manifest.get("template", {})
    if payload.get("status") != "passed":
        add_problem(errors, "template_fidelity_pending", "Template fidelity status must be passed")
    for field in ("template_alias", "template_sha256"):
        expected = template.get("alias" if field == "template_alias" else "sha256", "")
        if payload.get(field) != expected:
            add_problem(
                errors,
                f"template_fidelity_{field}_mismatch",
                f"Template fidelity {field} does not match the manifest",
            )
    allowed_fonts = payload.get("allowed_fonts")
    if not isinstance(allowed_fonts, list) or set(map(str, allowed_fonts)) != set(
        map(str, template.get("allowed_fonts", []))
    ):
        add_problem(
            errors,
            "template_fidelity_allowed_fonts_mismatch",
            "Template fidelity allowed_fonts does not match the manifest",
        )
    if not template_inspection or not template_inspection.get("valid_ooxml"):
        add_problem(
            errors,
            "template_fidelity_template_unavailable",
            "Template fidelity requires a valid rechecked template inspection",
        )
        return
    if not output_inspection or not output_inspection.get("valid_ooxml"):
        add_problem(
            errors,
            "template_fidelity_output_unavailable",
            "Template fidelity requires a valid editable PPTX inspection",
        )
        return
    if output_inspection.get("slide_size") != template_inspection.get("slide_size"):
        add_problem(
            errors,
            "template_fidelity_slide_size_mismatch",
            "Editable PPTX slide size does not match the template",
        )
    if output_inspection.get("master_digest") != template_inspection.get("master_digest"):
        add_problem(
            errors,
            "template_fidelity_masters_mismatch",
            "Editable PPTX masters do not match the template",
        )
    if output_inspection.get("layout_digest") != template_inspection.get("layout_digest"):
        add_problem(
            errors,
            "template_fidelity_layouts_mismatch",
            "Editable PPTX layouts do not match the template",
        )
    actual_fonts = set(map(str, output_inspection.get("fonts", [])))
    declared_fonts = set(map(str, template.get("allowed_fonts", [])))
    unexpected_fonts = sorted(actual_fonts - declared_fonts)
    if unexpected_fonts:
        add_problem(
            errors,
            "template_fidelity_unexpected_fonts",
            f"Editable PPTX uses fonts outside the allowlist: {unexpected_fonts}",
        )
    expected_charts = payload.get("expected_editable_charts")
    if not isinstance(expected_charts, int) or isinstance(expected_charts, bool) or expected_charts < 0:
        add_problem(
            errors,
            "template_fidelity_expected_charts_invalid",
            "expected_editable_charts must be a non-negative integer",
        )
    else:
        actual_charts = int(output_inspection.get("bound_chart_count", 0))
        if actual_charts < expected_charts:
            add_problem(
                errors,
                "template_fidelity_editable_charts_missing",
                f"Editable PPTX has {actual_charts} native charts; expected at least {expected_charts}",
            )
    if int(output_inspection.get("unbound_chart_references", 0)) != 0:
        add_problem(
            errors,
            "template_fidelity_unbound_charts",
            "Editable PPTX contains chart references not bound to chart parts",
        )
    expected_tables = payload.get("expected_native_tables")
    if not isinstance(expected_tables, int) or isinstance(expected_tables, bool) or expected_tables < 0:
        add_problem(
            errors,
            "template_fidelity_expected_tables_invalid",
            "expected_native_tables must be a non-negative integer",
        )
    elif int(output_inspection.get("table_count", 0)) < expected_tables:
        add_problem(
            errors,
            "template_fidelity_native_tables_missing",
            f"Editable PPTX has {output_inspection.get('table_count', 0)} native tables; expected at least {expected_tables}",
        )
    pagination_required = payload.get("table_pagination_required") is True
    groups = payload.get("table_page_groups")
    if not isinstance(groups, list):
        add_problem(
            errors,
            "template_fidelity_table_page_groups_invalid",
            "table_page_groups must be a list",
        )
    else:
        valid_groups = True
        table_counts = output_inspection.get("slide_table_counts", {})
        for group in groups:
            if (
                not isinstance(group, list)
                or len(group) < 2
                or any(
                    not isinstance(slide, int)
                    or isinstance(slide, bool)
                    or int(table_counts.get(str(slide), 0)) < 1
                    for slide in group
                )
            ):
                valid_groups = False
                break
        if not valid_groups or (pagination_required and not groups):
            add_problem(
                errors,
                "template_fidelity_table_pagination_invalid",
                "Every declared pagination group must contain 2+ slides with native tables",
            )
    if int(output_inspection.get("overflow_count", 0)) != 0:
        add_problem(errors, "template_fidelity_overflow", "Editable PPTX contains slide overflow")
    if int(output_inspection.get("orphan_connector_count", 0)) != 0:
        add_problem(
            errors,
            "template_fidelity_orphan_connectors",
            "Editable PPTX contains orphan connectors",
        )


def validate_privacy_contract(
    manifest: dict[str, Any], out_dir: Path, errors: list[dict[str, str]]
) -> None:
    privacy = manifest.get("privacy")
    storage = manifest.get("storage")
    template = manifest.get("template")
    schema_version = int(manifest.get("schema_version", 1) or 1)
    if schema_version < 3 and not any((privacy, storage, template)):
        return
    if not isinstance(privacy, dict):
        add_problem(errors, "manifest_privacy_missing", "Manifest must contain a privacy object")
        return
    if not isinstance(storage, dict):
        add_problem(errors, "manifest_storage_missing", "Manifest must contain a storage object")
        return
    if not isinstance(template, dict) or template.get("mode") not in TEMPLATE_MODES:
        add_problem(errors, "manifest_template_invalid", "Manifest must contain a valid template object")
        return

    classification = privacy.get("classification")
    network = privacy.get("network")
    persistence = privacy.get("persist_intermediates")
    allowlist = privacy.get("provider_allowlist")
    if classification not in PRIVACY_CLASSIFICATIONS:
        add_problem(errors, "manifest_privacy_classification_invalid", "Invalid privacy classification")
    if network not in NETWORK_POLICIES:
        add_problem(errors, "manifest_network_policy_invalid", "Invalid network policy")
    if persistence not in PERSISTENCE_MODES:
        add_problem(errors, "manifest_persistence_invalid", "Invalid intermediate persistence mode")
    if not isinstance(allowlist, list) or not allowlist:
        add_problem(errors, "manifest_provider_allowlist_invalid", "provider_allowlist must be non-empty")
        allowlist_set: set[str] = set()
    else:
        allowlist_set = {str(item) for item in allowlist}
        unknown = allowlist_set - KNOWN_PROVIDER_CAPABILITIES
        if unknown:
            add_problem(
                errors,
                "manifest_provider_allowlist_invalid",
                f"Unknown provider allowlist entries: {', '.join(sorted(unknown))}",
            )
    provider = manifest.get("request", {}).get("provider")
    required = set(PROVIDER_CAPABILITIES.get(str(provider), set()))
    if int(manifest.get("request", {}).get("image_count", 0) or 0) > 0:
        required.add("imagegen")
    if required - allowlist_set:
        add_problem(
            errors,
            "manifest_provider_not_allowed",
            "Manifest workflow requires a provider outside provider_allowlist",
        )
    if network == "deny" and required & NETWORK_PROVIDERS:
        add_problem(errors, "manifest_network_provider_forbidden", "network=deny forbids a selected provider")

    if template.get("mode") == "strict_following":
        if not str(template.get("alias", "")).strip():
            add_problem(errors, "manifest_template_alias_missing", "Strict template mode needs an alias")
        if not re.fullmatch(r"[0-9a-f]{64}", str(template.get("sha256", ""))):
            add_problem(errors, "manifest_template_sha256_invalid", "Strict template mode needs SHA-256")
        if template.get("verified") is not True:
            add_problem(errors, "manifest_template_unverified", "Strict template hash must be verified")
        if any("path" in str(key).lower() for key in template):
            add_problem(
                errors,
                "manifest_template_path_disclosed",
                "Manifest must not persist the source template path",
            )

    if classification != "confidential":
        return
    forbidden_allowlist = allowlist_set & NETWORK_PROVIDERS
    if forbidden_allowlist:
        add_problem(
            errors,
            "confidential_provider_allowlist_networked",
            "Confidential provider_allowlist cannot include network providers",
        )
    if network != "deny":
        add_problem(errors, "confidential_network_not_denied", "Confidential mode requires network=deny")
    if persistence != "private_state":
        add_problem(
            errors,
            "confidential_persistence_invalid",
            "Confidential mode requires private_state intermediates",
        )
    roots: dict[str, Path] = {}
    for label in ("state_root", "run_dir", "output_root"):
        raw = storage.get(label, "")
        candidate = Path(str(raw)).expanduser()
        if not candidate.is_absolute():
            add_problem(errors, f"confidential_{label}_relative", f"Confidential {label} must be absolute")
            continue
        roots[label] = candidate.resolve()
        checkout = git_checkout_root(roots[label])
        if checkout:
            add_problem(
                errors,
                f"confidential_{label}_in_git",
                f"Confidential {label} cannot be inside a Git checkout",
            )
    if roots.get("run_dir") != out_dir.resolve():
        add_problem(errors, "confidential_run_dir_mismatch", "Manifest must live in storage.run_dir")
    if roots.get("run_dir") and roots.get("state_root") and not is_within(
        roots["run_dir"], roots["state_root"]
    ):
        add_problem(errors, "confidential_run_outside_state", "run_dir must stay inside state_root")
    if roots.get("state_root") and roots.get("output_root") and paths_overlap(
        roots["state_root"], roots["output_root"]
    ):
        add_problem(errors, "confidential_roots_overlap", "State and final output roots must be separate")
    for role in ("editable_pptx", "notebooklm_pptx", "infographic"):
        if manifest.get("expected", {}).get(role, {}).get("base") != "delivery":
            add_problem(
                errors,
                f"confidential_{role}_not_delivery",
                f"Confidential {role} must resolve from the final delivery root",
            )
    expected = manifest.get("expected", {})
    state_entries = [
        *(expected.get("prompts") or []),
        *(expected.get("planning") or []),
        *(expected.get("qa") or []),
    ]
    for entry in state_entries:
        if isinstance(entry, dict) and entry.get("base", "state") != "state":
            add_problem(
                errors,
                "confidential_intermediate_not_state",
                "Confidential prompts, planning, and QA must resolve from private state",
            )
            break
    if expected.get("visual_assets", {}).get("base", "state") != "state":
        add_problem(
            errors,
            "confidential_visual_assets_not_state",
            "Confidential visual assets must resolve from private state",
        )


def validate_template_source(
    manifest: dict[str, Any],
    args: argparse.Namespace,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, Any] | None:
    template = manifest.get("template", {})
    if template.get("mode") != "strict_following":
        return None
    raw_path = getattr(args, "template_file", None)
    if not raw_path:
        config = getattr(args, "_private_config", {})
        configured_alias = nested_config(config, "template", "alias")
        configured_hash = str(nested_config(config, "template", "sha256") or "").lower()
        configured_path = nested_config(config, "template", "path")
        if configured_path and (
            configured_alias != template.get("alias") or configured_hash != template.get("sha256")
        ):
            bucket = errors if getattr(args, "strict", False) else warnings
            add_problem(
                bucket,
                "template_config_binding_mismatch",
                "Private config template alias and SHA-256 must match the manifest",
            )
            return None
        raw_path = configured_path
    if not raw_path:
        bucket = errors if getattr(args, "strict", False) else warnings
        add_problem(
            bucket,
            "template_source_recheck_missing",
            "Strict template validation needs --template-file to recheck SHA-256",
        )
        return None
    candidate = Path(str(raw_path)).expanduser()
    if not candidate.is_absolute():
        add_problem(errors, "template_source_relative", "Template recheck path must be absolute")
        return None
    candidate = candidate.resolve()
    if not candidate.is_file() or candidate.suffix.lower() != ".pptx":
        add_problem(errors, "template_source_invalid", "Template recheck file must be an existing PPTX")
        return None
    inspection = inspect_pptx(candidate)
    if not inspection["valid_ooxml"]:
        add_problem(
            errors,
            "template_source_invalid_ooxml",
            "Template recheck file must be a valid PPTX OOXML package",
        )
        return None
    if manifest.get("privacy", {}).get("classification") == "confidential" and git_checkout_root(
        candidate
    ):
        add_problem(
            errors,
            "confidential_template_source_in_git",
            "Confidential template recheck file cannot be inside a Git checkout",
        )
    if sha256_file(candidate) != template.get("sha256"):
        add_problem(
            errors,
            "template_source_sha256_mismatch",
            "Template bytes changed after planning or do not match the manifest SHA-256",
        )
    return inspection


def language_requires_cjk(language: Any) -> bool:
    normalized = str(language or "").strip().lower().replace("_", "-")
    return normalized.startswith(("zh", "ja", "ko")) or any(
        token in normalized for token in ("chinese", "japanese", "korean", "中文", "日文", "韩文")
    )


def validate_host(
    payload: dict[str, Any],
    slide_count: int,
    cjk_required: bool,
    out_dir: Path,
    primary_preview_dir: Path | None,
    errors: list[dict[str, str]],
) -> None:
    if payload.get("status") != "passed":
        add_problem(errors, "host_validation_pending", "Host validation status must be passed")
    host = payload.get("host")
    if host not in ALLOWED_HOSTS:
        add_problem(
            errors,
            "host_validation_invalid_host",
            f"Host must be one of: {', '.join(sorted(ALLOWED_HOSTS))}",
        )
    if host == "libreoffice" and not str(payload.get("notes", "")).strip():
        add_problem(
            errors,
            "host_validation_libreoffice_limit_missing",
            "LibreOffice validation must record the host limitation in notes",
        )
    if int(payload.get("rendered_slide_count", 0) or 0) != slide_count:
        add_problem(
            errors,
            "host_validation_slide_count",
            f"Host rendered {payload.get('rendered_slide_count', 0)} slides; expected {slide_count}",
        )
    preview_dir = resolve_inside(out_dir, payload.get("preview_dir", ""))
    if preview_dir is not None and (
        primary_preview_dir is None or preview_dir != primary_preview_dir.resolve()
    ):
        add_problem(
            errors,
            "host_validation_preview_origin_mismatch",
            "Host validation preview_dir must equal the primary deck preview_dir",
        )
    if preview_dir is None or not preview_dir.is_dir():
        add_problem(errors, "host_validation_preview_missing", "Host validation must reference a preview_dir inside the bundle")
    else:
        preview_paths = sorted(preview_dir.glob("slide-*.png"))
        actual_count = len(preview_paths)
        if actual_count != slide_count or actual_count != int(payload.get("rendered_slide_count", 0) or 0):
            add_problem(
                errors,
                "host_validation_preview_count",
                f"Host preview_dir contains {actual_count} slide previews; expected {slide_count}",
            )
        invalid_previews = [path.name for path in preview_paths if not valid_preview_dimensions(path)]
        if invalid_previews:
            add_problem(
                errors,
                "host_validation_preview_invalid",
                f"Host preview_dir contains invalid or undersized PNG files: {invalid_previews}",
            )
    if cjk_required and not (
        payload.get("cjk_checked") is True and payload.get("cjk_passed") is True
    ):
        add_problem(errors, "host_validation_cjk_failed", "CJK source requires a passed CJK render check")


def validate_manifest_contract(manifest: dict[str, Any], errors: list[dict[str, str]]) -> None:
    schema_version = manifest.get("schema_version")
    if schema_version not in {1, 2, 3}:
        add_problem(errors, "manifest_schema_invalid", "Manifest schema_version must be 1, 2, or 3")
    expected = manifest.get("expected")
    if not isinstance(expected, dict):
        add_problem(errors, "manifest_expected_missing", "Manifest must contain an expected object")
        return
    if schema_version == 1:
        return
    request = manifest.get("request")
    if not isinstance(request, dict):
        add_problem(errors, "manifest_request_missing", "Manifest must contain a request object")
    elif not str(request.get("main_verdict", "")).strip():
        add_problem(
            errors,
            "manifest_main_verdict_missing",
            "Schema v2+ requires a non-empty request.main_verdict",
        )
    required_qa_roles = set(REQUIRED_QA_ROLES)
    if manifest.get("template", {}).get("mode") == "strict_following":
        required_qa_roles.add("template_fidelity")
    for field, required_roles in (
        ("planning", REQUIRED_PLANNING_ROLES),
        ("qa", required_qa_roles),
    ):
        entries = expected.get(field)
        if not isinstance(entries, list):
            add_problem(errors, f"manifest_{field}_missing", f"Manifest must contain the required {field} entries")
            continue
        roles = {
            str(entry.get("role"))
            for entry in entries
            if isinstance(entry, dict) and entry.get("required") is True and str(entry.get("path", "")).strip()
        }
        for role in sorted(required_roles - roles):
            add_problem(
                errors,
                f"manifest_{field}_role_missing",
                f"Manifest {field} is missing required role: {role}",
            )


def validate_manifest(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = json.loads(read_text(manifest_path))
    out_dir = manifest_path.parent
    expected = manifest["expected"]
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    artifacts: dict[str, Any] = {}
    validate_manifest_contract(manifest, errors)
    validate_privacy_contract(manifest, out_dir, errors)
    template_inspection = validate_template_source(manifest, args, errors, warnings)
    legacy_schema = manifest.get("schema_version") == 1
    if legacy_schema:
        add_problem(
            warnings,
            "manifest_schema_legacy",
            "Schema v1 is readable for compatibility but does not satisfy v2 quality contracts",
        )
        if args.strict:
            add_problem(
                errors,
                "manifest_schema_legacy_strict_unsupported",
                "Strict delivery validation requires schema v2 or newer; re-plan this bundle before release",
            )
    required_preview_dirs: dict[str, Path] = {}
    for key in ("editable_pptx", "notebooklm_pptx"):
        entry = expected.get(key, {})
        if entry.get("required") is True:
            preview_dir = resolve_inside(out_dir, entry.get("preview_dir", ""))
            if preview_dir is not None:
                required_preview_dirs[key] = preview_dir
    if len(set(required_preview_dirs.values())) != len(required_preview_dirs):
        add_problem(
            errors,
            "manifest_preview_dir_conflict",
            "Each required deck must have its own preview_dir",
        )
    asset_root = resolve_inside(out_dir, expected.get("visual_assets", {}).get("directory", ""))
    if asset_root is not None:
        for key, preview_dir in required_preview_dirs.items():
            if preview_dir == asset_root or asset_root in preview_dir.parents:
                add_problem(
                    errors,
                    f"manifest_preview_dir_in_assets_{key}",
                    f"{key} preview_dir must not be inside the visual assets directory",
                )

    for key in ("editable_pptx", "notebooklm_pptx"):
        entry = expected[key]
        path = resolve_artifact(out_dir, manifest, entry)
        if not path.exists():
            if entry["required"]:
                add_problem(errors, f"missing_{key}", f"Missing required file: {path}")
            continue

        inspection = inspect_pptx(path)
        artifacts[key] = inspection
        if not inspection["valid_ooxml"]:
            add_problem(errors, f"invalid_{key}", f"Not a valid PPTX OOXML file: {path}")
            continue
        if inspection["slides"] < entry["min_slides"]:
            add_problem(
                errors,
                f"short_{key}",
                f"{path.name} has {inspection['slides']} slides; expected at least {entry['min_slides']}",
            )
        if inspection["banned_text_matches"]:
            add_problem(
                errors,
                f"runtime_metadata_{key}",
                f"{path.name} contains forbidden runtime metadata/placeholders: {inspection['banned_text_matches']}",
            )
        if entry.get("editable_required") and inspection["editable_ratio"] < 0.6:
            add_problem(
                errors,
                "editable_deck_is_flattened",
                f"{path.name} editable text ratio is {inspection['editable_ratio']:.0%}; expected at least 60%",
            )
        if key == "notebooklm_pptx" and inspection["editable_ratio"] < 0.2:
            add_problem(
                warnings,
                "notebooklm_deck_is_flattened",
                f"{path.name} appears image-only; report it as flattened/non-editable",
            )

        preview_dir = resolve_inside(out_dir, entry.get("preview_dir", ""))
        if preview_dir is None:
            add_problem(
                errors,
                f"preview_dir_escape_{key}",
                f"{key} preview_dir must stay inside the media bundle",
            )
            previews = []
        else:
            previews = sorted(preview_dir.glob("slide-*.png")) if preview_dir.is_dir() else []
        artifacts[f"{key}_previews"] = len(previews)
        if len(previews) != inspection["slides"]:
            add_problem(
                errors,
                f"preview_count_{key}",
                f"{path.name} has {inspection['slides']} slides but {len(previews)} rendered previews",
            )
        invalid_previews = [preview.name for preview in previews if not valid_preview_dimensions(preview)]
        if invalid_previews:
            add_problem(
                errors,
                f"invalid_preview_{key}",
                f"{path.name} has invalid or undersized PNG previews: {invalid_previews}",
            )

    infographic = expected["infographic"]
    infographic_path = resolve_artifact(out_dir, manifest, infographic)
    if infographic["required"] or infographic_path.exists():
        dims = png_dimensions(infographic_path)
        artifacts["infographic"] = {"path": str(infographic_path), "dimensions": dims}
        if dims is None:
            add_problem(errors, "invalid_infographic", f"Missing or invalid PNG: {infographic_path}")
        elif dims[0] < infographic["min_width"] or dims[1] < infographic["min_height"]:
            add_problem(errors, "small_infographic", f"Infographic is too small: {dims[0]}x{dims[1]}")

    assets = expected["visual_assets"]
    asset_dir = resolve_inside(out_dir, assets.get("directory", ""))
    if asset_dir is None:
        add_problem(errors, "visual_assets_directory_escape", "Visual assets directory must stay inside the media bundle")
        asset_paths = []
        asset_dir_label = str(assets.get("directory", ""))
    else:
        asset_paths = sorted(asset_dir.glob("*.png")) if asset_dir.is_dir() else []
        asset_dir_label = str(asset_dir)
    artifacts["visual_assets"] = []
    if assets["required"] and len(asset_paths) < assets["minimum_count"]:
        add_problem(
            errors,
            "missing_visual_assets",
            f"Expected at least {assets['minimum_count']} PNG assets in {asset_dir_label}; found {len(asset_paths)}",
        )
    for path in asset_paths:
        dims = png_dimensions(path)
        artifacts["visual_assets"].append({"path": str(path), "dimensions": dims})
        if dims is None:
            add_problem(errors, "invalid_visual_asset", f"Invalid PNG: {path}")
        elif dims[0] < assets["min_width"] or dims[1] < assets["min_height"]:
            add_problem(warnings, "small_visual_asset", f"Visual asset is small: {path.name} {dims[0]}x{dims[1]}")

    for entry in expected["prompts"]:
        path = resolve_artifact(out_dir, manifest, entry)
        if entry["required"] and (not path.is_file() or not read_text(path).strip()):
            add_problem(errors, "missing_prompt", f"Missing or empty prompt: {path}")

    planning_payloads: dict[str, dict[str, Any] | None] = {}
    for entry in expected.get("planning", []):
        payload = read_json_artifact(resolve_artifact(out_dir, manifest, entry), errors, entry["role"])
        planning_payloads[entry["role"]] = payload
    content_plan = planning_payloads.get("content_plan")
    design_plan = planning_payloads.get("design_plan")
    contract_card = planning_payloads.get("contract_card")
    if content_plan:
        validate_content_plan(content_plan, manifest, errors)
    if design_plan:
        validate_design_plan(design_plan, manifest, errors)
    if contract_card:
        validate_contract_card(contract_card, manifest, errors)

    qa_payloads: dict[str, dict[str, Any] | None] = {}
    for entry in expected.get("qa", []):
        payload = read_json_artifact(resolve_artifact(out_dir, manifest, entry), errors, entry["role"])
        qa_payloads[entry["role"]] = payload
    if qa_payloads.get("signature_proof"):
        validate_signature_proof(qa_payloads["signature_proof"], design_plan, manifest, out_dir, errors)
    if qa_payloads.get("content_critic"):
        validate_critic(qa_payloads["content_critic"], "content", errors)
    if qa_payloads.get("design_critic"):
        validate_critic(qa_payloads["design_critic"], "design", errors)
    if qa_payloads.get("host_validation"):
        primary_key = (
            "editable_pptx"
            if expected.get("editable_pptx", {}).get("required") is True
            else "notebooklm_pptx"
        )
        primary_deck = artifacts.get(primary_key) or {}
        primary_preview_dir = resolve_inside(
            out_dir, expected.get(primary_key, {}).get("preview_dir", "")
        )
        rendered_count = int(primary_deck.get("slides", 0))
        validate_host(
            qa_payloads["host_validation"],
            rendered_count,
            bool(manifest.get("source", {}).get("contains_cjk"))
            or language_requires_cjk(manifest.get("request", {}).get("language")),
            out_dir,
            primary_preview_dir,
            errors,
        )
    if qa_payloads.get("template_fidelity"):
        validate_template_fidelity(
            qa_payloads["template_fidelity"],
            manifest,
            template_inspection,
            artifacts.get("editable_pptx"),
            errors,
        )

    if args.strict and not args.visual_reviewed:
        add_problem(errors, "visual_review_pending", "Strict validation requires --visual-reviewed")
    elif not args.visual_reviewed:
        add_problem(warnings, "visual_review_pending", "Manual slide/image review is still required")
    if args.strict and not args.source_facts_reviewed:
        add_problem(errors, "source_facts_review_pending", "Strict validation requires --source-facts-reviewed")
    elif not args.source_facts_reviewed:
        add_problem(warnings, "source_facts_review_pending", "Source author/time/claims review is still required")

    report = {
        "schema_version": 1,
        "validated_at": now_iso(),
        "manifest": str(manifest_path),
        "status": "failed" if errors else ("legacy" if legacy_schema else "passed"),
        "artifacts": artifacts,
        "errors": errors,
        "warnings": warnings,
        "manual_gates": {
            "visual_reviewed": bool(args.visual_reviewed),
            "source_facts_reviewed": bool(args.source_facts_reviewed),
            "content_plan_approved": bool(content_plan and content_plan.get("status") == "approved"),
            "design_plan_approved": bool(design_plan and design_plan.get("status") == "approved"),
            "dual_lens_consented": bool(
                (qa_payloads.get("content_critic") or {}).get("verdict") == "consent"
                and (qa_payloads.get("design_critic") or {}).get("verdict") == "consent"
            ),
            "host_validated": bool(
                (qa_payloads.get("host_validation") or {}).get("status") == "passed"
            ),
        },
    }
    write_json(out_dir / "media-validation.json", report)
    return report, 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Create media-manifest.json from a Markdown source")
    plan.add_argument("--config", help=f"Private schema-v2 config; overrides {CONFIG_ENV_VAR}")
    plan.add_argument("--article", required=True)
    plan.add_argument("--out-dir", required=True)
    plan.add_argument("--provider", choices=sorted(PROVIDERS))
    plan.add_argument("--audience")
    plan.add_argument("--style")
    plan.add_argument("--slide-count")
    plan.add_argument("--image-count", type=int)
    plan.add_argument("--infographic", action=argparse.BooleanOptionalAction, default=None)
    plan.add_argument("--main-verdict", required=True)
    plan.add_argument("--purpose")
    plan.add_argument("--delivery-context")
    plan.add_argument("--language")
    plan.add_argument("--review-mode", choices=sorted(REVIEW_MODES))
    plan.add_argument("--template-mode", choices=sorted(TEMPLATE_MODES))
    plan.add_argument("--template-alias")
    plan.add_argument("--template-file")
    plan.add_argument("--template-sha256")
    plan.add_argument("--allowed-font", action="append")
    plan.add_argument(
        "--privacy-classification",
        choices=sorted(PRIVACY_CLASSIFICATIONS),
    )
    plan.add_argument("--network", choices=["auto", *sorted(NETWORK_POLICIES)])
    plan.add_argument("--provider-allowlist")
    plan.add_argument(
        "--persist-intermediates",
        choices=["auto", *sorted(PERSISTENCE_MODES)],
    )
    plan.add_argument("--state-root")
    plan.add_argument("--output-root")
    plan.add_argument("--json", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate files declared by media-manifest.json")
    validate.add_argument("--config", help=f"Private schema-v2 config; overrides {CONFIG_ENV_VAR}")
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--visual-reviewed", action="store_true")
    validate.add_argument("--source-facts-reviewed", action="store_true")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--template-file")
    validate.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = load_private_config(args)
        if args.command == "plan":
            apply_plan_config(args, config)
            manifest = build_manifest(args)
            output = Path(args.out_dir).expanduser().resolve() / "media-manifest.json"
            write_json(output, manifest)
            write_planning_templates(output.parent, manifest)
            result = {"status": "planned", "manifest": str(output), "payload": manifest}
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else str(output))
            return 0

        args._private_config = config
        report, exit_code = validate_manifest(args)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["status"])
        return exit_code
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ET.ParseError, zipfile.BadZipFile) as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
