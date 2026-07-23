#!/usr/bin/env python3
"""Small, dependency-free article packet used by the local visual smoke test."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


Concept = tuple[str, str, str]


@dataclass(frozen=True)
class Article:
    path: Path
    title: str
    author: str = ""
    published_at: str = ""
    url: str = ""
    sections: list[tuple[str, str]] | None = None
    plain_text: str = ""

    def __post_init__(self) -> None:
        if self.sections is None:
            object.__setattr__(self, "sections", [])


def _frontmatter_and_body(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.S)
        if match:
            return match.group(1), match.group(2)
    return "", text


def _scalar(frontmatter: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", frontmatter)
    if not match:
        return ""
    return match.group(1).strip().strip('"').strip("'")


def _clean(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^>.*$", " ", text, flags=re.M)
    text = re.sub(r"[*_`#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_article(path: Path) -> Article:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _frontmatter_and_body(text)
    # X articles often encode section headings as bold numbered lines rather
    # than Markdown headings. Treat both forms as source sections so the
    # visual output follows the article's real information architecture.
    heading_pattern = r"(?m)^(?:#{1,6}\s+(.+?)|\*\*([一二三四五六七八九十百\d]+[\.、．)]\s*[^*\n]+)\*\*)\s*$"
    headings = list(re.finditer(heading_pattern, body))
    sections: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        title = _clean(heading.group(1) or heading.group(2)) or "未命名章节"
        content = _clean(body[start:end])
        if content or index == 0:
            sections.append((title, content))
    if not sections:
        sections = [(path.stem, _clean(body))]
    title = sections[0][0] if sections else path.stem
    return Article(
        path=path,
        title=title,
        author=_scalar(frontmatter, "author"),
        published_at=_scalar(frontmatter, "published_at"),
        url=_scalar(frontmatter, "url"),
        sections=sections,
        plain_text=_clean(body),
    )


def section_excerpt(text: str, limit: int) -> str:
    text = _clean(text)
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def _add(items: list[Concept], seen: set[str], term: str, section: str, definition: str) -> None:
    term = re.sub(r"\s+", " ", term).strip(" -—:：,，。；;")
    if len(term) < 2 or len(term) > 64 or term in seen:
        return
    seen.add(term)
    items.append((term, section, section_excerpt(definition, 180)))


def matched_terms(article: Article) -> list[Concept]:
    terms: list[Concept] = []
    seen: set[str] = set()
    for title, content in article.sections:
        _add(terms, seen, title, title, content)
        for match in re.finditer(r"\*\*([^*\n]{2,64})\*\*|`([^`\n]{2,64})`", content):
            _add(terms, seen, match.group(1) or match.group(2), title, content)
        for match in re.finditer(r"\b(?:[A-Z][A-Za-z0-9+-]{2,}|[A-Z]{2,}[A-Za-z0-9+-]*)\b", content):
            _add(terms, seen, match.group(0), title, content)
    return terms


def theme_rows(terms: list[Concept]) -> list[tuple[str, list[Concept]]]:
    rows: dict[str, list[Concept]] = {}
    for term in terms:
        rows.setdefault(term[1] or "未分类", []).append(term)
    return list(rows.items())


def qa_floor(article: Article, terms: list[Concept]) -> dict[str, int]:
    section_count = len(article.sections)
    return {
        "min_terms": max(12, min(24, section_count * 2)),
        "min_slides": max(14, min(18, section_count + 8)),
        "max_slides": 18,
        "min_infographic_blocks": 12,
        "min_questions": max(8, min(12, len(terms))),
        "min_report_chars": max(2400, min(7000, len(article.plain_text) // 2)),
        "min_podcast_chars": 1800,
        "min_video_scenes": max(8, min(12, section_count + 4)),
    }
