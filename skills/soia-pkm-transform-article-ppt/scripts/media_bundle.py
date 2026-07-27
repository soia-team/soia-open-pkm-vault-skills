#!/usr/bin/env python3
"""Plan and validate an article-to-PPT media bundle using only stdlib."""

from __future__ import annotations

import argparse
import binascii
import json
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
REVIEW_MODES = {"standard", "thorough"}
REQUIRED_PLANNING_ROLES = {"content_plan", "design_plan", "contract_card"}
REQUIRED_QA_ROLES = {"signature_proof", "content_critic", "design_critic", "host_validation"}
ALLOWED_HOSTS = {"microsoft_powerpoint", "apple_keynote", "libreoffice"}
MIN_PREVIEW_WIDTH = 320
MIN_PREVIEW_HEIGHT = 180
MAX_PNG_DECODED_BYTES = 256 * 1024 * 1024
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
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


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    article = Path(args.article).expanduser().resolve()
    if not article.is_file():
        raise FileNotFoundError(f"Article does not exist: {article}")
    if args.provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {args.provider}")
    review_mode = getattr(args, "review_mode", "standard")
    if review_mode not in REVIEW_MODES:
        raise ValueError(f"Unsupported review mode: {review_mode}")

    source = extract_source(article)
    slide_count = infer_slide_count(source) if args.slide_count == "auto" else int(args.slide_count)
    if slide_count < 1:
        raise ValueError("slide_count must be positive")
    if args.image_count < 0:
        raise ValueError("image_count cannot be negative")
    main_verdict = str(args.main_verdict).strip()
    if not main_verdict:
        raise ValueError("main_verdict must be non-empty")

    provider = "local_editable" if args.provider == "auto" else args.provider
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = article.stem
    local_required = provider in {"local_editable", "hybrid", "open_design"}
    notebook_required = provider in {"notebooklm", "hybrid"}

    prompt_entries = []
    if local_required:
        prompt_entries.append(expected_entry("prompts/ppt-local.txt", True, role="editable_pptx"))
    if notebook_required:
        prompt_entries.append(expected_entry("prompts/ppt-notebooklm.txt", True, role="notebooklm_pptx"))
    for index in range(1, args.image_count + 1):
        prompt_entries.append(expected_entry(f"prompts/image-{index:02d}.txt", True, role="visual_asset"))
    if args.infographic:
        prompt_entries.append(expected_entry("prompts/infographic.txt", True, role="infographic"))

    expected = {
        "editable_pptx": expected_entry(
            f"{stem}-editable.pptx",
            local_required,
            min_slides=max(1, slide_count - 2),
            editable_required=True,
            preview_dir="previews/editable",
        ),
        "notebooklm_pptx": expected_entry(
            f"{stem}-notebooklm.pptx",
            notebook_required,
            min_slides=max(1, slide_count - 4),
            editable_required=False,
            preview_dir="previews/notebooklm",
        ),
        "infographic": expected_entry(
            f"{stem}-infographic.png",
            bool(args.infographic),
            min_width=800,
            min_height=800,
        ),
        "visual_assets": {
            "directory": "assets/imagegen",
            "required": args.image_count > 0,
            "minimum_count": args.image_count,
            "min_width": 768,
            "min_height": 512,
        },
        "prompts": prompt_entries,
        "planning": [
            expected_entry("planning/content-plan.json", True, role="content_plan"),
            expected_entry("planning/design-plan.json", True, role="design_plan"),
            expected_entry("planning/contract-card.json", True, role="contract_card"),
        ],
        "qa": [
            expected_entry("qa/signature-proof.json", True, role="signature_proof"),
            expected_entry("qa/critic-content.json", True, role="content_critic"),
            expected_entry("qa/critic-design.json", True, role="design_critic"),
            expected_entry("qa/host-validation.json", True, role="host_validation"),
        ],
    }

    return {
        "schema_version": 2,
        "planned_at": now_iso(),
        "source": source,
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


def inspect_pptx(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "valid_ooxml": False,
        "slides": 0,
        "text_slides": 0,
        "image_only_slides": 0,
        "editable_ratio": 0.0,
        "banned_text_matches": [],
    }
    if not path.is_file() or not zipfile.is_zipfile(path):
        return result

    with zipfile.ZipFile(path) as archive:
        names = sorted(
            [name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)],
            key=natural_slide_key,
        )
        result["slides"] = len(names)
        text_slides = 0
        image_only = 0
        matches: set[str] = set()
        for name in names:
            root = ET.fromstring(archive.read(name))
            texts = [(node.text or "") for node in root.findall(".//a:t", NS)]
            pictures = root.findall(".//p:pic", NS)
            shapes = root.findall(".//p:sp", NS)
            joined = " ".join(texts)
            if joined.strip():
                text_slides += 1
            if pictures and not joined.strip() and not shapes:
                image_only += 1
            matches.update(match.group(0) for match in BANNED_TEXT.finditer(joined))

        result.update(
            {
                "valid_ooxml": len(names) > 0,
                "text_slides": text_slides,
                "image_only_slides": image_only,
                "editable_ratio": round(text_slides / len(names), 3) if names else 0.0,
                "banned_text_matches": sorted(matches),
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


def resolve(out_dir: Path, entry: dict[str, Any]) -> Path:
    path = resolve_inside(out_dir, entry["path"])
    if path is None:
        raise ValueError(f"Artifact path escapes output directory: {entry.get('path')}")
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
    for field in (
        "source",
        "audience",
        "purpose",
        "delivery_context",
        "language",
        "editability",
        "review_mode",
        "output_scope",
    ):
        value = payload.get(field)
        if value in (None, "", [], {}):
            add_problem(errors, f"contract_card_missing_{field}", f"Contract card must declare {field}")
        elif field in {"audience", "purpose", "delivery_context", "language"} and value == "auto":
            add_problem(errors, f"contract_card_unresolved_{field}", f"Contract card must resolve {field}")

    request = manifest["request"]
    expected_values = {
        "audience": request["audience"],
        "purpose": request["purpose"],
        "delivery_context": request["delivery_context"],
        "language": request["language"],
        "editability": "editable_pptx"
        if manifest["expected"]["editable_pptx"]["required"]
        else "non_editable_pptx",
        "review_mode": request["review_mode"],
    }
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
    if schema_version not in {1, 2}:
        add_problem(errors, "manifest_schema_invalid", "Manifest schema_version must be 1 or 2")
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
            "Schema v2 requires a non-empty request.main_verdict",
        )
    for field, required_roles in (
        ("planning", REQUIRED_PLANNING_ROLES),
        ("qa", REQUIRED_QA_ROLES),
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
                "Strict delivery validation requires schema v2; re-plan this bundle before release",
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
        path = resolve(out_dir, entry)
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
    infographic_path = resolve(out_dir, infographic)
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
        path = resolve(out_dir, entry)
        if entry["required"] and (not path.is_file() or not read_text(path).strip()):
            add_problem(errors, "missing_prompt", f"Missing or empty prompt: {path}")

    planning_payloads: dict[str, dict[str, Any] | None] = {}
    for entry in expected.get("planning", []):
        payload = read_json_artifact(resolve(out_dir, entry), errors, entry["role"])
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
        payload = read_json_artifact(resolve(out_dir, entry), errors, entry["role"])
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
    plan.add_argument("--article", required=True)
    plan.add_argument("--out-dir", required=True)
    plan.add_argument("--provider", choices=sorted(PROVIDERS), default="auto")
    plan.add_argument("--audience", default="auto")
    plan.add_argument("--style", default="auto")
    plan.add_argument("--slide-count", default="auto")
    plan.add_argument("--image-count", type=int, default=3)
    plan.add_argument("--infographic", action="store_true")
    plan.add_argument("--main-verdict", required=True)
    plan.add_argument("--purpose", default="auto")
    plan.add_argument("--delivery-context", default="auto")
    plan.add_argument("--language", default="auto")
    plan.add_argument("--review-mode", choices=sorted(REVIEW_MODES), default="standard")
    plan.add_argument("--json", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate files declared by media-manifest.json")
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--visual-reviewed", action="store_true")
    validate.add_argument("--source-facts-reviewed", action="store_true")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "plan":
            manifest = build_manifest(args)
            output = Path(args.out_dir).expanduser().resolve() / "media-manifest.json"
            write_json(output, manifest)
            write_planning_templates(output.parent, manifest)
            result = {"status": "planned", "manifest": str(output), "payload": manifest}
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else str(output))
            return 0

        report, exit_code = validate_manifest(args)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["status"])
        return exit_code
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ET.ParseError, zipfile.BadZipFile) as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
