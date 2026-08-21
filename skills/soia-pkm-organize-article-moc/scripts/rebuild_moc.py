#!/usr/bin/env python3
"""Safely synchronize the two-level MOC for an Obsidian article vault.

Single-article archival uses ``--article`` and only upserts that article into
the affected level-1 and level-2 MOCs. Destructive full regeneration is kept
behind the explicit ``--full-rebuild`` flag, scans before clearing, and refuses
unknown topics unless the caller explicitly accepts them.

This is the mechanical layer under `soia-pkm-organize-article-moc`. It is vault-agnostic:
pass `--vault` (or set OBSIDIAN_VAULT). The category→topic table has a sensible
built-in default and can be overridden per-vault with a JSON file — see --help.

Usage:
    python3 rebuild_moc.py --vault /path/to/vault --article Articles/2026/08/note.md
    python3 rebuild_moc.py --vault /path/to/vault --full-rebuild --dry-run
    python3 rebuild_moc.py --vault /path/to/vault --full-rebuild

Per-vault category override (optional):
    Put `<vault>/<articles-subdir>/_MOC/.categories.json` shaped like
    {"AI编程": ["Agent开发", ...], "产品与商业": [...]} to replace the default table.
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from collections import defaultdict

from organize_env import load_private_env

# ── Default category → topic table ───────────────────────────────────────────
# Vault-agnostic default. Override per-vault via _MOC/.categories.json.

DEFAULT_CATEGORY_TOPICS = {
    "AI编程": [
        "AI与LLM", "Agent开发", "Claude Code", "AI编程", "Codex", "Skills",
        "Prompt工程", "多Agent", "Harness工程", "MCP", "AI工程师",
        "Vibe Coding", "Anthropic", "DeepSeek", "OpenAI", "Qwen", "Ollama",
    ],
    "AI应用": [
        "视频生成", "本地大模型", "图像生成", "数字人", "视频翻译",
        "音视频处理", "AI工具", "GEO", "预言与趋势",
    ],
    "技术与开源": [
        "开源项目", "GitHub", "自动化", "前端", "架构设计", "爬虫与抓取",
        "API中转", "源码分析", "工作流", "组件库", "半导体", "网络安全",
        "OCR", "数据分析", "云服务器", "Cloudflare", "GitHub Pages",
        "域名与DNS", "SEO", "Schema标记", "云计算", "反代",
        "Google", "Reddit",
    ],
    "产品与商业": [
        "内容创作", "一人公司", "副业", "出海", "行业观察", "创业与商业",
        "变现", "战略与战术", "自媒体", "支付与开卡", "中国经济", "职业发展",
        "投资理财", "YouTube", "订阅与账号", "中文创作者", "人物访谈",
        "公众号", "Twitter运营", "赚钱思维", "股票投资", "黄金与避险",
        "小红书", "产品与设计", "亚马逊", "闲鱼", "公司治理", "跨境金融",
        "跨境公司注册", "Stripe", "远程办公", "加密货币", "UI设计", "数字身份",
    ],
    "效率与工具": [
        "效率工具", "知识管理", "Obsidian", "代理与VPN", "第二大脑",
        "macOS工具", "精力管理", "PPT", "PARA", "飞书", "微信读书",
        "Mac", "PDF", "工具", "Telegram", "科学上网", "路由器",
    ],
    "学习": [
        "教育", "英语学习", "读书", "心理学", "少儿编程", "学习资源", "职场",
    ],
    "社会": [
        "制度问题", "历史", "国际关系", "育儿", "澳洲", "食品安全",
        "移民与海外", "健康", "家庭关系", "香港", "美国", "英国",
        "新加坡", "政治", "社会观察",
    ],
}

# ── Runtime config (populated in main) ───────────────────────────────────────

ARTICLES_DIR: Path
MOC_DIR: Path
TODAY: str
CATEGORY_TOPICS: dict
TOPIC_TO_CATEGORY: dict = {}


class MocError(RuntimeError):
    """Raised when a requested MOC operation is unsafe or invalid."""


def load_category_topics(articles_dir: Path) -> dict:
    """Load per-vault override from _MOC/.categories.json, else built-in default."""
    override = articles_dir / "_MOC" / ".categories.json"
    if override.is_file():
        try:
            data = json.loads(override.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                print(f"Using category override: {override}")
                return data
        except Exception as e:
            print(f"  WARN: bad .categories.json ({e}); using default table")
    return DEFAULT_CATEGORY_TOPICS


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter as raw dict (minimal parser, no pyyaml needed)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip()
    result = {}
    lines = fm_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\w[\w_-]*):\s*(.*)', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val == "" or val is None:
                items = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i].startswith("- ")):
                    sub = lines[i].strip()
                    if sub.startswith("- "):
                        items.append(sub[2:].strip().strip('"').strip("'"))
                    i += 1
                result[key] = items
                continue
            else:
                result[key] = val
        i += 1
    return result


def parse_topics(text: str) -> list:
    """
    Parse topics from article frontmatter. Supports:
    - Multi-line:  topics:\n  - "[[Topic]]"\n  - "[[Topic2]]"
    - Single-line: topics: ["[[Topic]]", "[[Topic2]]"]
    Returns list of plain topic names (no [[ ]]).
    """
    topics = []
    m = re.search(r'^topics:[ \t]*', text, re.MULTILINE)
    if not m:
        return topics

    rest = text[m.end():]
    first_line = rest.split('\n')[0].strip()

    if first_line.startswith("["):
        for item in re.findall(r'\[\[([^\]]+)\]\]', first_line):
            topics.append(item.strip())
    else:
        candidate_lines = []
        if first_line.startswith("- "):
            candidate_lines.append(first_line)
        for line in rest.split('\n')[1:]:
            stripped = line.strip()
            if stripped.startswith("- "):
                candidate_lines.append(stripped)
            elif stripped == "":
                continue
            else:
                break

        for stripped in candidate_lines:
            inner = stripped[2:].strip().strip('"').strip("'")
            found = re.findall(r'\[\[([^\]]+)\]\]', inner)
            if found:
                topics.extend(t.strip() for t in found)
            elif inner:
                topics.append(inner)

    return topics


def extract_title(text: str) -> str:
    """Extract first H1 heading from article body (after frontmatter)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            if len(title) > 40:
                title = title[:40] + "…"
            return title
    return "(无标题)"


ARTICLE_LINK_RE = re.compile(r"^- \[\[([^\]]+)\]\](?: — (.*))?$", re.MULTILINE)
LEVEL2_SECTION_RE = re.compile(r"(?ms)^## 文章列表（共 \d+ 篇）\n.*?(?=^## |\Z)")


def atomic_write_text(path: Path, content: str) -> None:
    """Write one generated Markdown file without exposing a partial result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def article_record(md_file: Path) -> tuple[dict, list[str]]:
    text = md_file.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    record = {
        "filename": md_file.stem,
        "title": extract_title(text),
        "captured_at": str(fm.get("captured_at", "")).strip(),
        "published_at": str(fm.get("published_at", "")).strip(),
    }
    return record, parse_topics(text)


def update_moc_date(text: str) -> str:
    return re.sub(r"(?m)^updated:\s*.*$", f"updated: {TODAY}", text, count=1)


def level2_article_matches(text: str) -> list[re.Match]:
    section = LEVEL2_SECTION_RE.search(text)
    return list(ARTICLE_LINK_RE.finditer(section.group(0))) if section else []


def render_level2_content(category: str, topic: str, article_lines: list[str]) -> str:
    lines = [
        "---",
        "tags: [MOC]",
        f"topic: {topic}",
        "level: 2",
        f'parent: "[[{category}]]"',
        f"updated: {TODAY}",
        "---",
        "",
        f"# MOC · {topic}",
        "",
        f"> 上级：[[{category}]]",
        "",
        f"## 文章列表（共 {len(article_lines)} 篇）",
        "",
        *article_lines,
        "",
    ]
    return "\n".join(lines)


def upsert_level2_content(existing: str, category: str, topic: str, article: dict) -> str:
    new_line = f"- [[{article['filename']}]] — {article['title']}"
    if not existing:
        return render_level2_content(category, topic, [new_line])

    article_matches = level2_article_matches(existing)
    article_lines = [match.group(0) for match in article_matches]
    if not any(match.group(1) == article["filename"] for match in article_matches):
        article_lines.insert(0, new_line)
    section = "\n".join([
        f"## 文章列表（共 {len(article_lines)} 篇）",
        "",
        *article_lines,
    ])
    if LEVEL2_SECTION_RE.search(existing):
        updated = LEVEL2_SECTION_RE.sub(section + "\n", existing, count=1)
    else:
        updated = existing.rstrip() + "\n\n" + section + "\n"
    return update_moc_date(updated)


def render_level1_content(category: str, topic_sections: list[str]) -> str:
    return "\n".join([
        "---",
        "tags: [MOC]",
        f"category: {category}",
        "level: 1",
        f"updated: {TODAY}",
        "---",
        "",
        f"# MOC · {category}",
        "",
        *topic_sections,
        "",
    ])


def topic_section(category: str, topic: str, level2_content: str) -> str:
    article_lines = [match.group(0) for match in level2_article_matches(level2_content)]
    return "\n".join([
        f"## {topic}（{len(article_lines)} 篇）→ [[{category}/{topic}]]",
        "",
        *article_lines[:3],
    ])


def upsert_level1_content(existing: str, category: str, topic: str, level2_content: str) -> str:
    section = topic_section(category, topic, level2_content)
    if not existing:
        return render_level1_content(category, [section])

    heading = re.compile(
        rf"(?ms)^## {re.escape(topic)}（\d+ 篇）→ \[\[{re.escape(category)}/{re.escape(topic)}\]\]\n.*?(?=^## |\Z)"
    )
    if heading.search(existing):
        updated = heading.sub(section + "\n\n", existing, count=1)
    else:
        updated = existing.rstrip() + "\n\n" + section + "\n"
    return update_moc_date(updated)


def resolve_article_path(vault: Path, raw_value: str) -> Path:
    raw = Path(raw_value).expanduser()
    candidates = [raw] if raw.is_absolute() else [vault / raw, ARTICLES_DIR / raw]
    article = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
    if article is None:
        raise MocError(f"article not found: {raw_value}")
    try:
        article.relative_to(ARTICLES_DIR.resolve())
    except ValueError as exc:
        raise MocError(f"article is outside articles dir: {article}") from exc
    if MOC_DIR.resolve() in article.parents:
        raise MocError(f"article points into _MOC: {article}")
    return article


def sync_single_article(article_path: Path, dry_run: bool) -> list[Path]:
    article, topics = article_record(article_path)
    if not topics:
        raise MocError(f"article has no topics: {article_path}")
    unknown = sorted({topic for topic in topics if topic not in TOPIC_TO_CATEGORY})
    if unknown:
        raise MocError("unknown topics; no MOC files changed: " + ", ".join(unknown))

    planned: dict[Path, str] = {}
    for topic in dict.fromkeys(topics):
        category = TOPIC_TO_CATEGORY[topic]
        level2_path = MOC_DIR / category / f"{topic}.md"
        existing_level2 = planned.get(
            level2_path,
            level2_path.read_text(encoding="utf-8") if level2_path.is_file() else "",
        )
        updated_level2 = upsert_level2_content(existing_level2, category, topic, article)
        planned[level2_path] = updated_level2

        level1_path = MOC_DIR / f"{category}.md"
        existing_level1 = planned.get(
            level1_path,
            level1_path.read_text(encoding="utf-8") if level1_path.is_file() else "",
        )
        planned[level1_path] = upsert_level1_content(
            existing_level1, category, topic, updated_level2
        )

    changed = [
        path for path, content in planned.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
    for path in changed:
        action = "Would update" if dry_run else "Updated"
        print(f"  {action}: {path}")
        if not dry_run:
            atomic_write_text(path, planned[path])
    return changed


# ── Full-rebuild preflight scan ───────────────────────────────────────────────

def scan_articles() -> tuple[dict, dict]:
    """Return topic map and a report. Scans every four-digit year directory."""
    topic_map = defaultdict(list)
    year_dirs = sorted(
        d for d in ARTICLES_DIR.iterdir()
        if d.is_dir() and re.fullmatch(r'\d{4}', d.name)
    )

    skipped_no_topics = 0
    unknown_topics = []
    total_files = 0
    total_pairs = 0

    for year_dir in year_dirs:
        for md_file in sorted(year_dir.rglob("*.md")):
            total_files += 1
            try:
                article, topics = article_record(md_file)
            except Exception as e:
                print(f"  WARN: cannot read {md_file.name}: {e}")
                continue
            if not topics:
                skipped_no_topics += 1
                continue

            for topic in topics:
                if topic not in TOPIC_TO_CATEGORY:
                    unknown_topics.append({"path": str(md_file), "topic": topic})
                    continue
                topic_map[topic].append(article)
                total_pairs += 1

    print(f"\nScan complete: {total_files} files, {total_pairs} article-topic pairs")
    print(f"  Skipped (no topics): {skipped_no_topics}")
    print(f"  Unknown topic placements: {len(unknown_topics)}")
    report = {
        "total_files": total_files,
        "total_pairs": total_pairs,
        "skipped_no_topics": skipped_no_topics,
        "unknown_topics": unknown_topics,
    }
    return topic_map, report


# ── Step 3: Generate level-2 MOC files ───────────────────────────────────────

def generate_level2(topic_map: dict) -> dict:
    category_stats = defaultdict(dict)

    for cat, topics in CATEGORY_TOPICS.items():
        cat_dir = MOC_DIR / cat
        cat_dir.mkdir(parents=True, exist_ok=True)

        for topic in topics:
            articles = topic_map.get(topic, [])
            if not articles:
                continue

            sorted_articles = sorted(
                articles,
                key=lambda a: (a.get("captured_at") or a.get("published_at") or ""),
                reverse=True,
            )

            count = len(sorted_articles)
            category_stats[cat][topic] = count

            lines = [
                "---",
                "tags: [MOC]",
                f"topic: {topic}",
                "level: 2",
                f'parent: "[[{cat}]]"',
                f"updated: {TODAY}",
                "---",
                "",
                f"# MOC · {topic}",
                "",
                f"> 上级：[[{cat}]]",
                "",
                f"## 文章列表（共 {count} 篇）",
                "",
            ]
            for art in sorted_articles:
                lines.append(f"- [[{art['filename']}]] — {art['title']}")
            lines.append("")

            (cat_dir / f"{topic}.md").write_text("\n".join(lines), encoding="utf-8")

    return category_stats


# ── Step 4: Generate level-1 MOC files ───────────────────────────────────────

def generate_level1(topic_map: dict, category_stats: dict):
    for cat, topic_counts in category_stats.items():
        if not topic_counts:
            continue

        lines = [
            "---",
            "tags: [MOC]",
            f"category: {cat}",
            "level: 1",
            f"updated: {TODAY}",
            "---",
            "",
            f"# MOC · {cat}",
            "",
        ]
        for topic in CATEGORY_TOPICS[cat]:
            count = topic_counts.get(topic)
            if count is None:
                continue
            articles = topic_map.get(topic, [])
            sorted_articles = sorted(
                articles,
                key=lambda a: (a.get("captured_at") or a.get("published_at") or ""),
                reverse=True,
            )
            lines.append(f"## {topic}（{count} 篇）→ [[{cat}/{topic}]]")
            lines.append("")
            for art in sorted_articles[:3]:
                lines.append(f"- [[{art['filename']}]] — {art['title']}")
            lines.append("")

        (MOC_DIR / f"{cat}.md").write_text("\n".join(lines), encoding="utf-8")
        print(f"  Written level-1: {cat}.md")


def full_rebuild_transaction(topic_map: dict) -> dict:
    """Generate beside the live MOC and atomically swap only after success."""
    global MOC_DIR

    live_dir = MOC_DIR
    staging_dir = live_dir.parent / f".{live_dir.name}.staging-{os.getpid()}"
    backup_dir = live_dir.parent / f".{live_dir.name}.backup-{os.getpid()}"
    if staging_dir.exists() or backup_dir.exists():
        raise MocError("stale staging or backup path exists; refusing full rebuild")

    staging_dir.mkdir(parents=True)
    override = live_dir / ".categories.json"
    if override.is_file():
        shutil.copy2(override, staging_dir / override.name)

    category_stats = None
    try:
        MOC_DIR = staging_dir
        category_stats = generate_level2(topic_map)
        generate_level1(topic_map, category_stats)
        MOC_DIR = live_dir

        if live_dir.exists():
            live_dir.rename(backup_dir)
        try:
            staging_dir.rename(live_dir)
        except Exception:
            if backup_dir.exists() and not live_dir.exists():
                backup_dir.rename(live_dir)
            raise
    except Exception:
        MOC_DIR = live_dir
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise

    if backup_dir.exists():
        try:
            shutil.rmtree(backup_dir)
        except OSError as exc:
            print(f"  WARN: old MOC backup retained at {backup_dir}: {exc}", file=sys.stderr)
    assert category_stats is not None
    return category_stats


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    global ARTICLES_DIR, MOC_DIR, TODAY, CATEGORY_TOPICS, TOPIC_TO_CATEGORY

    load_private_env()
    parser = argparse.ArgumentParser(description="Safely synchronize two-level MOCs for an Obsidian article vault.")
    parser.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT"),
                        help="vault root (or set OBSIDIAN_VAULT)")
    parser.add_argument("--articles-subdir", default="Articles",
                        help="articles dir relative to vault (default: Articles)")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="date stamp written into MOC frontmatter (default: today)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--article",
        help="incrementally upsert one article; accepts an absolute, vault-relative, or articles-relative path",
    )
    mode.add_argument(
        "--full-rebuild",
        action="store_true",
        help="explicitly clear and regenerate all managed MOCs after a successful preflight scan",
    )
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing files")
    parser.add_argument(
        "--allow-unknown-topics",
        action="store_true",
        help="full rebuild only: explicitly accept omitted unknown-topic placements",
    )
    args = parser.parse_args()

    if not args.vault:
        parser.error("no vault given: pass --vault or set OBSIDIAN_VAULT")

    vault = Path(args.vault).expanduser().resolve()
    ARTICLES_DIR = vault / args.articles_subdir
    MOC_DIR = ARTICLES_DIR / "_MOC"
    TODAY = args.date

    if not ARTICLES_DIR.is_dir():
        parser.error(f"articles dir not found: {ARTICLES_DIR}")

    CATEGORY_TOPICS = load_category_topics(ARTICLES_DIR)
    TOPIC_TO_CATEGORY = {t: cat for cat, topics in CATEGORY_TOPICS.items() for t in topics}

    if args.allow_unknown_topics and not args.full_rebuild:
        parser.error("--allow-unknown-topics is only valid with --full-rebuild")

    print("=" * 60)
    print(f"Synchronize Obsidian MOC · {vault.name}")
    print("=" * 60)

    if args.article:
        try:
            article_path = resolve_article_path(vault, args.article)
            changed = sync_single_article(article_path, args.dry_run)
        except (MocError, OSError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"\nIncremental sync complete: {len(changed)} file(s) {'would change' if args.dry_run else 'changed'}.")
        return 0

    print("\n[Preflight] Scanning all articles before any deletion ...")
    topic_map, scan_report = scan_articles()
    unknown_topics = scan_report["unknown_topics"]
    if unknown_topics:
        for item in unknown_topics[:20]:
            print(f"  UNKNOWN: {item['topic']} · {item['path']}", file=sys.stderr)
        if len(unknown_topics) > 20:
            print(f"  ... and {len(unknown_topics) - 20} more", file=sys.stderr)
        if not args.allow_unknown_topics:
            print(
                "ERROR: full rebuild blocked before clearing _MOC; classify the unknown topics "
                "or explicitly pass --allow-unknown-topics.",
                file=sys.stderr,
            )
            return 2

    if args.dry_run:
        print(
            f"\nDry-run only: would rebuild {len(topic_map)} topic MOCs from "
            f"{scan_report['total_pairs']} article-topic pairs; _MOC was not changed."
        )
        return 0

    print("\n[Commit] Generating a complete staged MOC tree before atomic swap ...")
    try:
        category_stats = full_rebuild_transaction(topic_map)
    except (MocError, OSError) as exc:
        print(f"ERROR: staged full rebuild failed; live _MOC retained: {exc}", file=sys.stderr)
        return 2

    print("\n" + "=" * 60)
    print("Final Report")
    print("=" * 60)
    grand_total_topics = 0
    grand_total_pairs = 0
    for cat in CATEGORY_TOPICS:
        stats = category_stats.get(cat, {})
        grand_total_topics += len(stats)
        grand_total_pairs += sum(stats.values())
        if stats:
            print(f"\n{cat}:  {len(stats)} topics, {sum(stats.values())} pairs")
            for topic, cnt in sorted(stats.items(), key=lambda x: -x[1]):
                print(f"    {topic}: {cnt} 篇")
    print(f"\n{'─'*40}")
    print(f"Grand total: {grand_total_topics} topics, {grand_total_pairs} article-topic pairs")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
