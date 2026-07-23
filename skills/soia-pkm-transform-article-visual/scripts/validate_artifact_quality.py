#!/usr/bin/env python3
"""Dependency-free mechanical quality gates for local transform artifacts."""

from __future__ import annotations

from pathlib import Path
import re

from article_packet import Article, Concept, qa_floor


def _chars(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return 0


def validate_bundle(article: Article, out_dir: Path, terms: list[Concept]) -> dict[str, object]:
    floor = qa_floor(article, terms)
    checks: dict[str, object] = {}
    required = ["report.md", "report.html", "data-table.csv", "quiz.md", "flashcards.md", "mindmap.mmd", "infographic.html", "deck.html"]
    checks["required_files"] = {name: (out_dir / name).is_file() and (out_dir / name).stat().st_size > 0 for name in required}
    checks["concept_count"] = {"actual": len(terms), "minimum": floor["min_terms"], "ok": len(terms) >= floor["min_terms"]}
    report_chars = _chars(out_dir / "report.md")
    checks["report_length"] = {"actual": report_chars, "minimum": floor["min_report_chars"], "ok": report_chars >= floor["min_report_chars"]}
    deck_html = (out_dir / "deck.html").read_text(encoding="utf-8") if (out_dir / "deck.html").is_file() else ""
    info_html = (out_dir / "infographic.html").read_text(encoding="utf-8") if (out_dir / "infographic.html").is_file() else ""
    deck_count = len(re.findall(r"class=['\"]slide\b", deck_html))
    info_count = len(re.findall(r"data-block=['\"]info['\"]", info_html))
    checks["deck_slides"] = {"actual": deck_count, "minimum": floor["min_slides"], "ok": deck_count >= floor["min_slides"]}
    checks["infographic_blocks"] = {"actual": info_count, "minimum": floor["min_infographic_blocks"], "ok": info_count >= floor["min_infographic_blocks"]}
    rendered = {}
    for name in ("infographic.png", "report.pdf", "deck.pdf"):
        path = out_dir / name
        rendered[name] = path.is_file() and path.stat().st_size > 10_000
    checks["rendered_files"] = rendered
    all_required = all(checks["required_files"].values())
    checks["ok"] = bool(all_required and checks["concept_count"]["ok"] and checks["report_length"]["ok"] and checks["deck_slides"]["ok"] and checks["infographic_blocks"]["ok"])
    return checks
