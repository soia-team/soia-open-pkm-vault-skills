#!/usr/bin/env python3
"""Collect, query, summarize, and optionally transform a public X profile.

The default provider is FxTwitter's documented v2 profile endpoint.  The
script is deliberately bounded: it fetches a finite newest-first window,
records the cursor/coverage, and never claims that a profile export is
complete when the provider returned only a partial window.

The default output is a research summary.  Image Prompt Deck compilation is an
explicit output mode, so account research does not silently become a GPT2
workflow.  All output stays JSON/YAML/Markdown and uses only the standard
library.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable


CST = timezone(timedelta(hours=8))
FXTWITTER_BASE = "https://api.fxtwitter.com"
PROFILE_URL_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([^/?#]+)", re.I)
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,30}$")
GPT2_RE = re.compile(r"\bGPT\s*[-_]?\s*2\b|GPT[-_]?image2", re.I)
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


FAMILY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("presentation_grid", ("ppt", "演示", "presentation", "大字报", "信息图")),
    ("celebration_ceremony", ("生日", "婚礼", "周年", "birthday", "wedding")),
    ("hospitality_food", ("酒店", "食物", "饮料", "餐厅", "hotel", "food", "beverage")),
    ("portrait_identity", ("人像", "写真", "锁脸", "锁定五官", "portrait", "身份")),
    ("morning_city", ("早安", "good morning", "城市", "方言", "city")),
    ("event_people", ("活动", "会议", "展会", "博览会", "演出", "戏剧节", "conference", "event")),
    ("travel_publication", ("旅行", "旅游", "travel")),
    ("archival_print", ("票据", "古籍", "档案", "拓印", "archival")),
    ("pixel_play", ("像素", "pixel")),
    ("poster_type_stage", ("海报", "poster", "大字", "巨字", "留白", "色块", "壁纸")),
]

IMAGE_FAMILIES = {"morning_city", "poster_type_stage", "presentation_grid", "travel_publication", "portrait_identity", "event_people", "celebration_ceremony", "hospitality_food", "archival_print", "pixel_play"}


def parse_handle(value: str) -> str:
    value = value.strip().rstrip("/")
    match = PROFILE_URL_RE.fullmatch(value)
    handle = match.group(1) if match else value.lstrip("@").split("/", 1)[0]
    if not HANDLE_RE.fullmatch(handle):
        raise ValueError(f"invalid X profile handle: {value}")
    return handle


def parse_month(value: str | None) -> tuple[datetime, datetime] | None:
    if not value:
        return None
    if not MONTH_RE.fullmatch(value):
        raise ValueError("month must use YYYY-MM")
    year, month = (int(part) for part in value.split("-"))
    if not 1 <= month <= 12:
        raise ValueError("month must use a calendar month")
    start = datetime(year, month, 1, tzinfo=CST)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=CST)
    return start, end


def parse_boundary(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    """Parse a local CST date or ISO datetime boundary.

    Date-only ``--since`` values start at midnight.  Date-only ``--until``
    values are inclusive for callers, so they become the next midnight and
    are used as an exclusive internal bound.
    """
    if not value:
        return None
    raw = value.strip()
    if DATE_RE.fullmatch(raw):
        try:
            parsed = date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("date must use a valid YYYY-MM-DD value") from exc
        dt = datetime(parsed.year, parsed.month, parsed.day, tzinfo=CST)
        return dt + timedelta(days=1) if end_of_day else dt
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("boundary must use YYYY-MM-DD or ISO datetime") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.astimezone(CST)


def period_bounds(month: str | None, since: str | None, until: str | None) -> tuple[datetime | None, datetime | None]:
    if month and (since or until):
        raise ValueError("--month cannot be combined with --since/--until")
    if month:
        parsed = parse_month(month)
        assert parsed is not None
        return parsed
    start = parse_boundary(since)
    end = parse_boundary(until, end_of_day=True)
    if start and end and start >= end:
        raise ValueError("--since must be earlier than --until")
    return start, end


def published_datetime(status: dict[str, Any]) -> datetime | None:
    timestamp = status.get("created_timestamp")
    if isinstance(timestamp, (int, float)) and timestamp:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(CST)
    normalized = str(status.get("published_at") or "").strip()
    if normalized:
        try:
            dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(CST)
        except ValueError:
            pass
    raw = str(status.get("created_at") or "").strip()
    if not raw:
        return None
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(CST)
        except ValueError:
            continue
    return None


def http_json(url: str, timeout: float) -> tuple[int, dict[str, Any] | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "soia-pkm-clip-x-profile/0.2 (+https://github.com/soia-team/soia-open-pkm-vault-skills)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = None
        return exc.code, payload
    except Exception as exc:
        print(f"WARN: request failed {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0, None


def profile_url(handle: str, path: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    return f"{FXTWITTER_BASE}/2/profile/{urllib.parse.quote(handle)}{path}" + (f"?{query}" if query else "")


def load_fixture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {}, payload
    if not isinstance(payload, dict):
        raise ValueError("source JSON must be a list or an object containing results/pages")
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    if isinstance(payload.get("results"), list):
        return profile, payload["results"]
    rows: list[dict[str, Any]] = []
    for page in payload.get("pages", []):
        if isinstance(page, dict) and isinstance(page.get("results"), list):
            rows.extend(item for item in page["results"] if isinstance(item, dict))
    if not rows:
        raise ValueError("source JSON has no results")
    return profile, rows


def fetch_profile(
    handle: str,
    limit: int,
    include_replies: bool,
    max_pages: int,
    timeout: float,
    sleep_seconds: float,
    month_scope: str,
    month: str | None,
    since: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    profile_status, profile = http_json(profile_url(handle, "", {"about_account": "1"}), timeout)
    profile = (profile or {}).get("user") if isinstance(profile, dict) else {}
    if not isinstance(profile, dict):
        profile = {}
    rows: list[dict[str, Any]] = []
    pages = 0
    cursors: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    month_bounds = parse_month(month)
    stop_start = month_bounds[0] if month_bounds else parse_boundary(since)

    while pages < max_pages and (len(rows) < limit or month_scope == "all"):
        params: dict[str, Any] = {
            "count": min(100, max(1, limit)),
            "with_replies": "1" if include_replies else "0",
            "groupthreads": "0",
        }
        if cursor:
            params["cursor"] = cursor
        status_code, payload = http_json(profile_url(handle, "/statuses", params), timeout)
        pages += 1
        if status_code == 204:
            break
        if status_code != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"FxTwitter profile statuses failed (HTTP {status_code or 'network'})")
        page_rows = payload.get("results") or []
        if not isinstance(page_rows, list):
            raise RuntimeError("FxTwitter profile response has no results list")
        added = 0
        for row in page_rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id") or row.get("url") or "")
            if not row_id or row_id in seen:
                continue
            seen.add(row_id)
            rows.append(row)
            added += 1
        page_cursor = payload.get("cursor")
        if isinstance(page_cursor, dict):
            cursors.append(page_cursor)
            next_cursor = page_cursor.get("bottom") or page_cursor.get("next")
        else:
            next_cursor = page_cursor
        print(f"page={pages} received={len(page_rows)} added={added} total={len(rows)}", file=sys.stderr)
        if len(rows) >= limit and month_scope == "latest-window":
            break
        if stop_start and month_scope == "all" and rows:
            oldest = min((published_datetime(row) for row in rows), default=None)
            if oldest and oldest < stop_start:
                break
        if not next_cursor or next_cursor == cursor or added == 0:
            break
        cursor = str(next_cursor)
        if sleep_seconds:
            time.sleep(sleep_seconds)

    oldest_seen = min((published_datetime(row) for row in rows), default=None)
    return profile, rows[:limit] if month_scope == "latest-window" else rows, {
        "profile_http_status": profile_status,
        "pages": pages,
        "cursors": cursors,
        "last_cursor": cursor,
        "reached_limit": len(rows) >= limit,
        "hit_page_cap": pages >= max_pages,
        "stopped_at_period_start": bool(stop_start and oldest_seen and oldest_seen < stop_start),
    }


def media_items(status: dict[str, Any]) -> list[dict[str, Any]]:
    media = status.get("media") or {}
    if not isinstance(media, dict):
        return []
    source = media.get("photos") or media.get("all") or []
    if not isinstance(source, list):
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in source:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("url") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        items.append({
            "id": item.get("id", ""),
            "type": item.get("type", "photo"),
            "url": item.get("url", ""),
            "width": item.get("width"),
            "height": item.get("height"),
            "alt_text": item.get("altText") or item.get("alt_text") or "",
        })
    return items


def normalize_status(status: dict[str, Any]) -> dict[str, Any]:
    text = str(status.get("text") or (status.get("raw_text") or {}).get("text") or "").strip()
    media = media_items(status)
    alt_texts = [str(item["alt_text"]).strip() for item in media if item.get("alt_text")]
    evidence = "\n\n".join(part for part in [text, *alt_texts] if part)
    dt = published_datetime(status)
    author = status.get("author") if isinstance(status.get("author"), dict) else {}
    title = text.splitlines()[0].strip() if text else ""
    return {
        "id": str(status.get("id") or ""),
        "url": status.get("url") or "",
        "published_at": dt.isoformat() if dt else status.get("created_at", ""),
        "published_local": dt.strftime("%Y-%m-%d %H:%M") if dt else "",
        "title": title,
        "text": text,
        "author": {
            "handle": author.get("screen_name", ""),
            "name": author.get("name", ""),
        },
        "media": media,
        "media_count": len(media),
        "alt_text_count": len(alt_texts),
        "alt_texts": alt_texts,
        "prompt_evidence": evidence,
        "created_timestamp": status.get("created_timestamp"),
        "replying_to": status.get("replying_to"),
        "metrics": {
            key: status.get(key, 0)
            for key in ("views", "likes", "bookmarks", "replies", "reposts", "quotes")
        },
        "raw_type": status.get("type", "status"),
    }


def classify(record: dict[str, Any]) -> dict[str, Any]:
    title_haystack = str(record.get("title", "")).lower()
    evidence_haystack = (record.get("title", "") + "\n" + record.get("prompt_evidence", "")).lower()
    title_matches = [family for family, keywords in FAMILY_RULES if any(keyword.lower() in title_haystack for keyword in keywords)]
    matches = title_matches or [family for family, keywords in FAMILY_RULES if any(keyword.lower() in evidence_haystack for keyword in keywords)]
    primary = matches[0] if matches else "other"
    gpt2 = bool(GPT2_RE.search(evidence_haystack))
    tags = ["gpt2_prompt"] if gpt2 else []
    tags.extend(matches)
    if record.get("alt_text_count"):
        tags.append("image_alt_prompt")
    return {
        "primary_category": primary,
        "category_tags": list(dict.fromkeys(tags)),
        "is_gpt2": gpt2,
        "evidence_source": "image_alt_text" if record.get("alt_text_count") else ("post_text" if record.get("text") else "none"),
    }


def infer_axes(record: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    source_family = classification["primary_category"]
    family = source_family if source_family in IMAGE_FAMILIES else "poster_type_stage"
    title = record.get("title", "")
    evidence = record.get("prompt_evidence", "")
    haystack = f"{title}\n{evidence}".lower()
    mechanism = "typographic_mask" if "字体蒙版" in haystack or family == "morning_city" else "modular_grid" if family == "presentation_grid" else "identity_lock" if family == "portrait_identity" else "color_field_stage" if family in {"event_people", "hospitality_food"} else "travel_editorial_narrative" if family == "travel_publication" else "oversized_type" if any(token in haystack for token in ("大字", "巨字", "大字报")) else "foreground_depth"
    aesthetic = {
        "morning_city": "editorial_aesthetic",
        "presentation_grid": "bright_modern",
        "portrait_identity": "portrait_editorial",
        "event_people": "bright_modern",
        "celebration_ceremony": "ceremonial_soft",
        "hospitality_food": "hospitality_premium",
        "travel_publication": "travel_publication",
        "archival_print": "archival_historical",
        "pixel_play": "playful_pixel",
    }.get(family, "editorial_aesthetic")
    use_case = {
        "morning_city": "good_morning",
        "presentation_grid": "presentation",
        "portrait_identity": "portrait",
        "event_people": "event_poster",
        "celebration_ceremony": "birthday_poster" if "生日" in haystack else "event_poster",
        "hospitality_food": "hospitality_poster",
        "archival_print": "archival_print",
    }.get(family, "foreground_story")
    batch = bool(re.search(r"批量|第\s*\d+\s*弹|\b\d+\s*(?:张|页|个|套|cities|slides?)", haystack, re.I))
    aspect = "16:9" if re.search(r"16\s*[:：]\s*9", haystack) else "4:5"
    return {
        "preset": "auto",
        "family": family,
        "use_case": use_case,
        "information_structure": "deck_series" if batch or family == "presentation_grid" else "knowledge_card" if family == "morning_city" else "single_hook",
        "asset_role": "reference_subject" if family == "portrait_identity" else "none",
        "visual_mechanism": mechanism,
        "aesthetic_system": aesthetic,
        "text_strategy": "cjk_exact_text" if re.search(r"[\u4e00-\u9fff]", title) else "exact_text",
        "model_adapter": "external_gpt_image_label" if classification["is_gpt2"] else "auto",
        "batch_strategy": "series" if batch else "single",
        "output_mode": "carousel" if batch else "poster",
        "render_mode": "hybrid_exact_text",
        "aspect": aspect,
        "series_id": f"x-profile-{record.get('id', '')}" if batch else None,
        "source_category": source_family,
    }


def compile_prompt(record: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    axes = infer_axes(record, classification)
    source_url = record.get("url") or ""
    prompt = record.get("prompt_evidence") or record.get("text") or ""
    title = record.get("title") or f"X post {record.get('id', '')}"
    visible_title = re.sub(r"^\s*GPT\s*[-_]?\s*2\s*x\s*", "", title, flags=re.I).strip(" xX") or title
    model_note = "GPT2 只是来源帖子中的模型标签" if classification["is_gpt2"] else "来源帖子未声明可用的图像模型"
    source_facts = [
        f"题目/原始标题：{title}",
        f"来源状态：{source_url}",
        f"发布时间（本地）：{record.get('published_local', '未核实')}",
        f"媒体数量：{record.get('media_count', 0)}；含 ALT 提示词：{record.get('alt_text_count', 0)} 条",
    ]
    if record.get("text"):
        source_facts.append("推文正文可作为主题、系列变量和 CTA 的来源，不把作者评论扩写成事实")
    if record.get("alt_text_count"):
        source_facts.append("图片 ALT 是原作者提示词证据；只做结构化编译，不改写其视觉意图")
    layout = {
        "morning_city": "顶部窄体问候与日期；中心巨型字形蒙版；字腔内嵌城市/代表元素；底部保留系列标记与比例安全区",
        "presentation_grid": "以模块网格和基线网格组织标题、图像、正文和页脚；系列页保持列宽、边距、页码和节奏一致",
        "portrait_identity": "主体人物占据第一视觉焦点；身份参考图只用于保持可识别特征；标题与辅助信息放在安全留白区",
    }.get(axes["family"], "先建立一个清晰主焦点，再用分区、留白和一条阅读动线承载主题信息")
    style = {
        "morning_city": "明亮、清透、编辑式城市刊物；高明度主题色、近白字形、少量高饱和城市元素",
        "presentation_grid": "现代国际主义版式；明快色场、清晰圆角模块、纪实影像与信息图并置",
        "portrait_identity": "日系/编辑式人像摄影；自然肤质、受控光线、克制背景和可读的标题层级",
    }.get(axes["family"], "基于来源主题提取色彩和材质，保持清晰层级、可读边界与克制装饰")
    return {
        "source_status_id": record.get("id", ""),
        "source_url": source_url,
        "visible_title": visible_title,
        "source_prompt": prompt,
        "classification": classification,
        "composition_axes": axes,
        "prompt_blocks": {
            "source_grounding": "\n".join(f"- {fact}" for fact in source_facts),
            "primary_task": f"将“{title}”编译为一张可复用的 {axes['family']} 图片 Prompt；保留来源主题和视觉意图。{model_note}，不把来源模型标签当成技能依赖。",
            "composition_and_layout": layout,
            "visual_style_and_materials": style,
            "exact_text": f"建议画面主题文字：{visible_title}\n来源标题只作 provenance，不默认把模型标签画进图片；除非客户明确要求显示标签。其他文字仅在来源明确提供时使用；禁止随机生成品牌、数字、URL 或人物身份。",
            "aspect_and_output": f"输出 {axes['aspect']} 位图；用途={axes['output_mode']}；render_mode={axes['render_mode']}。先落盘 Prompt，再调用 imagegen，生成后必须 view_image 验收。",
            "constraints_and_avoid": "不伪造二维码、安装命令、URL、技能数量或原作者不存在的证据；不把来源模型标签写成 image 技能依赖；中文精确字段失败时只做确定性文字层校正。",
        },
    }


def slugify(value: str, limit: int = 60) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-")
    return (value or "x-post")[:limit]


def write_json_yaml(path: Path, data: Any) -> None:
    """Write valid YAML using JSON's subset; no PyYAML runtime dependency."""
    path.write_text("# JSON-compatible YAML; parse with any YAML 1.2 loader.\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_prompt_markdown(number: int, compiled: dict[str, Any]) -> str:
    axes = compiled["composition_axes"]
    blocks = compiled["prompt_blocks"]
    lines = [
        f"# {number:03d} · {compiled['source_status_id']} · {axes['family']}",
        "",
        "> This file is a complete image-skill Prompt Deck entry compiled from a public X source.",
        "",
        "## composition_axes",
        "",
        "```yaml",
        json.dumps(axes, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    for key in ("source_grounding", "primary_task", "composition_and_layout", "visual_style_and_materials", "exact_text", "aspect_and_output", "constraints_and_avoid"):
        lines.extend([f"## {key}", "", blocks[key], ""])
    lines.extend([
        "## Source prompt evidence (verbatim)",
        "",
        "```text",
        compiled["source_prompt"],
        "```",
        "",
    ])
    lines.extend([
        "## Source evidence",
        "",
        f"- URL: {compiled['source_url']}",
        f"- Source status id: `{compiled['source_status_id']}`",
        f"- Original prompt evidence is retained in `image-prompts.yml` under `source_prompt`.",
        "",
    ])
    return "\n".join(lines)


def filter_month(records: Iterable[dict[str, Any]], month: str | None) -> list[dict[str, Any]]:
    start, end = period_bounds(month, None, None)
    if not start and not end:
        return list(records)
    assert start is not None and end is not None
    selected: list[dict[str, Any]] = []
    for record in records:
        dt = published_datetime(record)
        if dt and start <= dt < end:
            selected.append(record)
    return selected


def record_search_text(record: dict[str, Any]) -> str:
    """Return the searchable public evidence for one normalized status."""
    return "\n".join(
        str(value)
        for value in (
            record.get("title", ""),
            record.get("text", ""),
            *record.get("alt_texts", []),
        )
        if value
    ).casefold()


def filter_records(
    records: Iterable[dict[str, Any]],
    *,
    month: str | None = None,
    since: str | None = None,
    until: str | None = None,
    queries: Iterable[str] = (),
    query_mode: str = "any",
    categories: Iterable[str] = (),
    only_gpt2: bool = False,
    has_media: bool = False,
    has_alt: bool = False,
) -> list[dict[str, Any]]:
    """Apply period, text, evidence, and topic conditions to statuses.

    Query terms are case-insensitive substring matches against title, post
    text, and image ALT text.  ``query_mode=all`` requires every term; the
    default ``any`` is useful when a customer names alternate spellings.
    """
    start, end = period_bounds(month, since, until)
    terms = [str(term).strip().casefold() for term in queries if str(term).strip()]
    wanted_categories = {str(category).strip() for category in categories if str(category).strip()}
    selected: list[dict[str, Any]] = []
    for record in records:
        dt = published_datetime(record)
        if start and (not dt or dt < start):
            continue
        if end and (not dt or dt >= end):
            continue
        if terms:
            haystack = record_search_text(record)
            matches = [term in haystack for term in terms]
            matches_ok = all(matches) if query_mode == "all" else any(matches)
            if not matches_ok:
                continue
        classification = classify(record)
        if wanted_categories and classification["primary_category"] not in wanted_categories:
            continue
        if only_gpt2 and not classification["is_gpt2"]:
            continue
        if has_media and not record.get("media_count"):
            continue
        if has_alt and not record.get("alt_text_count"):
            continue
        selected.append(record)
    return selected


def filter_metadata(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "month": args.month,
        "since": args.since,
        "until": args.until,
        "queries": list(args.queries),
        "query_mode": args.query_mode,
        "categories": list(args.categories),
        "only_gpt2": args.only_gpt2,
        "has_media": args.has_media,
        "has_alt": args.has_alt,
    }


def render_summary_markdown(
    handle: str,
    profile: dict[str, Any],
    records: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    args: argparse.Namespace,
    fetch_meta: dict[str, Any],
) -> str:
    """Render a bounded, evidence-linked account research summary."""
    counts = Counter(item["primary_category"] for item in classifications)
    gpt2_count = sum(1 for item in classifications if item["is_gpt2"])
    alt_count = sum(1 for record in selected if record.get("alt_text_count"))
    name = profile.get("name") or handle
    lines = [
        f"# X 账号研究摘要：@{handle}",
        "",
        f"- 账号：{name} ([原始主页](https://x.com/{handle}))",
        f"- 采集窗口：最新 {args.limit} 条；实际获取 {len(records)} 条；分页 {fetch_meta.get('pages', 0)} 页",
        f"- 条件：{format_filters(args)}",
        f"- 命中：{len(selected)} 条；GPT2/图像模型线索 {gpt2_count} 条；含图片 ALT {alt_count} 条",
        "",
        "> 这是基于公开帖子和 provider 返回字段的有限窗口摘要，不等同于账号历史全量，也不把推断写成作者事实。",
        "",
        "## 主题分布",
        "",
    ]
    if counts:
        lines.extend(f"- `{category}`：{count}" for category, count in counts.most_common())
    else:
        lines.append("- 没有命中帖子")
    lines.extend(["", "## 命中帖子", ""])
    if not selected:
        lines.append("没有帖子满足当前筛选条件。")
    else:
        for record, classification in zip(selected[:50], classifications[:50]):
            title = record.get("title") or record.get("text", "").splitlines()[0] or f"X post {record.get('id', '')}"
            title = " ".join(title.split())[:160]
            evidence = []
            if classification["is_gpt2"]:
                evidence.append("GPT2")
            if record.get("alt_text_count"):
                evidence.append(f"ALT {record['alt_text_count']}")
            label = f"；标签：{', '.join(evidence)}" if evidence else ""
            lines.append(f"- {record.get('published_local', '未核实')} · [{title}]({record.get('url', '')}) · `{classification['primary_category']}`{label}")
    if len(selected) > 50:
        lines.extend(["", f"仅展示前 50 条，完整规范化状态见 `filtered.json`（共 {len(selected)} 条）。"])
    lines.extend([
        "",
        "## 下一步路由",
        "",
        "- 继续研究：调整时间、`--query/--topic`、分类或媒体条件后重跑。",
        "- 转 image 技能：明确 `--output-mode image-prompts`，只对当前命中集编译 Prompt Deck。",
        "- 需要位图：把 Prompt Deck 交给 `soia-media-generate-article-image` 的 L0→L3 流程，不把文本转换回账号采集阶段。",
    ])
    return "\n".join(lines) + "\n"


def format_filters(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.month:
        parts.append(f"month={args.month}")
    if args.since:
        parts.append(f"since={args.since}")
    if args.until:
        parts.append(f"until={args.until}")
    if args.queries:
        parts.append(f"query({args.query_mode})={' | '.join(args.queries)}")
    if args.categories:
        parts.append(f"category={','.join(args.categories)}")
    if args.only_gpt2:
        parts.append("only_gpt2=true")
    if args.has_media:
        parts.append("has_media=true")
    if args.has_alt:
        parts.append("has_alt=true")
    return ", ".join(parts) if parts else "无额外筛选"


def write_bundle(
    output: Path,
    handle: str,
    profile: dict[str, Any],
    raw_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    period_selected: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    compiled: list[dict[str, Any]],
    fetch_meta: dict[str, Any],
    args: argparse.Namespace,
    source_path: Path | None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    classifications: list[dict[str, Any]] = [{"id": record["id"], **classify(record)} for record in period_selected]
    selected_classifications: list[dict[str, Any]] = [{"id": record["id"], **classify(record)} for record in selected]
    artifacts = ["profile.yml", "latest-window.json", "filtered.json", "classification.yml", "summary.md", "manifest.yml"]

    write_json_yaml(output / "profile.yml", {
        "handle": handle,
        "profile_url": f"https://x.com/{handle}",
        "display_name": profile.get("name", ""),
        "profile_id": profile.get("id", ""),
        "provider_profile": profile,
    })
    (output / "latest-window.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "filtered.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Keep the old filename as a compatibility alias for existing consumers.
    (output / "month-filter.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifacts.append("month-filter.json")
    write_json_yaml(output / "classification.yml", {
        "schema_version": 2,
        "source": f"https://x.com/{handle}",
        "classification_basis": "title + post text + image ALT text",
        "filters": filter_metadata(args),
        "coverage": {"period_selected": len(period_selected), "filtered_selected": len(selected)},
        "items": classifications,
        "counts": dict(Counter(item["primary_category"] for item in classifications)),
    })
    (output / "summary.md").write_text(
        render_summary_markdown(handle, profile, records, selected, selected_classifications, args, fetch_meta),
        encoding="utf-8",
    )

    if args.output_mode in {"image-prompts", "all"}:
        prompts_dir = output / "prompts"
        prompts_dir.mkdir(exist_ok=True)
        for idx, item in enumerate(compiled, 1):
            prompt_path = prompts_dir / f"{idx:03d}-{slugify(item['composition_axes']['family'])}-{slugify(item['source_status_id'])}.md"
            prompt_path.write_text(render_prompt_markdown(idx, item), encoding="utf-8")
        prompt_index = {
            "schema_version": 2,
            "image_skill": "soia-media-generate-article-image",
            "source_skill": "soia-pkm-clip-x-profile",
            "source_profile": f"https://x.com/{handle}",
            "selection": {
                "requested_latest": args.limit,
                "fetched": len(records),
                "period_selected": len(period_selected),
                "selected": len(selected),
                "filters": filter_metadata(args),
            },
            "prompt_contract": ["source_grounding", "primary_task", "composition_and_layout", "visual_style_and_materials", "exact_text", "aspect_and_output", "constraints_and_avoid"],
            "items": [
                {
                    "source_status_id": item["source_status_id"],
                    "source_url": item["source_url"],
                    "visible_title": item["visible_title"],
                    "family": item["composition_axes"]["family"],
                    "is_gpt2": item["classification"]["is_gpt2"],
                    "prompt_file": f"prompts/{idx:03d}-{slugify(item['composition_axes']['family'])}-{slugify(item['source_status_id'])}.md",
                    "source_prompt": item["source_prompt"],
                    "composition_axes": item["composition_axes"],
                }
                for idx, item in enumerate(compiled, 1)
            ],
        }
        write_json_yaml(output / "image-prompts.yml", prompt_index)
        artifacts.extend(["image-prompts.yml", "prompts/"])

    manifest = {
        "schema_version": 2,
        "skill": "soia-pkm-clip-x-profile",
        "run_mode": "fixture" if source_path else "network",
        "source": f"https://x.com/{handle}",
        "provider": "fixture-json" if source_path else "fxtwitter-v2-profile-statuses",
        "request": {
            "limit": args.limit,
            "fetch_scope": args.month_scope,
            "output_mode": args.output_mode,
            "filters": filter_metadata(args),
        },
        "coverage": {
            "requested_latest": args.limit,
            "requested_limit": args.limit,
            "fetched": len(records),
            "selected": len(selected),
            "period_selected": len(period_selected),
            "selected_after_month_filter": len(period_selected),
            "month": args.month,
            "month_scope": args.month_scope,
            "complete": bool(fetch_meta.get("reached_limit")) if args.month_scope == "latest-window" else bool(fetch_meta.get("stopped_at_period_start")),
        },
        "classification_counts": dict(Counter(item["primary_category"] for item in classifications)),
        "gpt2": {
            "detected": sum(1 for item in classifications if item["is_gpt2"]),
            "converted": len(compiled),
            "with_image_alt": sum(1 for item in selected if item.get("alt_text_count")),
        },
        "fetch": fetch_meta,
        "artifacts": artifacts,
        "source_fixture": str(source_path) if source_path else None,
    }
    write_json_yaml(output / "manifest.yml", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research a bounded public X profile and optionally compile selected posts for the SOIA image skill.")
    parser.add_argument("profile", help="X profile URL or handle")
    parser.add_argument("--limit", type=int, default=100, help="newest statuses to inspect (1-100; default: 100)")
    parser.add_argument("--month", help="local CST month filter, e.g. 2026-07")
    parser.add_argument("--since", help="inclusive CST start date/datetime, e.g. 2026-07-01")
    parser.add_argument("--until", help="inclusive CST end date/datetime, e.g. 2026-07-31")
    parser.add_argument("--month-scope", "--fetch-scope", dest="month_scope", choices=("latest-window", "all"), default="latest-window", help="filter the newest window, or page until the period start is crossed")
    parser.add_argument("--query", "--topic", dest="queries", action="append", default=[], help="case-insensitive topic/text term; repeat for multiple terms")
    parser.add_argument("--query-mode", choices=("any", "all"), default="any", help="whether repeated query terms use OR (any) or AND (all)")
    parser.add_argument("--category", dest="categories", action="append", default=[], help="optional visual/topic family filter; repeatable")
    parser.add_argument("--has-media", action="store_true", help="keep only posts with media")
    parser.add_argument("--has-alt", action="store_true", help="keep only posts with image ALT evidence")
    parser.add_argument("--output", type=Path, help="run bundle directory (required unless --dry-run)")
    parser.add_argument("--source-json", type=Path, help="offline fixture; skips network and uses results/pages from JSON")
    parser.add_argument("--include-replies", action="store_true", help="ask the provider to include replies")
    parser.add_argument("--max-pages", type=int, default=12, help="hard page cap to prevent hangs")
    parser.add_argument("--timeout", type=float, default=20.0, help="per-request timeout in seconds")
    parser.add_argument("--sleep", type=float, default=0.15, help="delay between provider pages")
    parser.add_argument("--only-gpt2", action="store_true", help="keep only posts whose public text/ALT evidence mentions GPT2 or GPT-image2")
    parser.add_argument("--output-mode", choices=("summary", "classification", "image-prompts", "all"), default="summary", help="summary by default; image conversion is explicit")
    parser.add_argument("--convert-to-image", action="store_true", help="shortcut for --output-mode image-prompts")
    parser.add_argument("--dry-run", action="store_true", help="fetch/filter and print counts without writing a bundle")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.limit <= 100:
        raise SystemExit("--limit must be between 1 and 100")
    if args.max_pages < 1:
        raise SystemExit("--max-pages must be positive")
    if args.query_mode not in {"any", "all"}:
        raise SystemExit("--query-mode must be any or all")
    if args.convert_to_image:
        args.output_mode = "image-prompts"
    try:
        handle = parse_handle(args.profile)
        period_bounds(args.month, args.since, args.until)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    source_path = args.source_json.resolve() if args.source_json else None
    if source_path:
        profile, raw_rows = load_fixture(source_path)
        fetch_meta = {
            "pages": 1,
            "profile_http_status": None,
            "last_cursor": None,
            "reached_limit": len(raw_rows) >= args.limit,
            "hit_page_cap": False,
            "stopped_at_period_start": False,
        }
        if args.month_scope == "latest-window":
            raw_rows = raw_rows[:args.limit]
    else:
        profile, raw_rows, fetch_meta = fetch_profile(
            handle,
            args.limit,
            args.include_replies,
            args.max_pages,
            args.timeout,
            args.sleep,
            args.month_scope,
            args.month,
            args.since,
        )
    records = [normalize_status(row) for row in raw_rows]
    period_selected = filter_records(
        records,
        month=args.month,
        since=args.since,
        until=args.until,
    )
    selected = filter_records(
        records,
        month=args.month,
        since=args.since,
        until=args.until,
        queries=args.queries,
        query_mode=args.query_mode,
        categories=args.categories,
        only_gpt2=args.only_gpt2,
        has_media=args.has_media,
        has_alt=args.has_alt,
    )
    conversion_rows = selected if args.output_mode in {"image-prompts", "all"} else []
    compiled = [compile_prompt(record, classify(record)) for record in conversion_rows]
    counts = Counter(classify(record)["primary_category"] for record in selected)
    print(json.dumps({
        "handle": handle,
        "fetched": len(records),
        "selected": len(selected),
        "filters": filter_metadata(args),
        "categories": dict(counts),
        "gpt2_detected": sum(1 for record in selected if classify(record)["is_gpt2"]),
        "image_prompts_compiled": len(compiled),
        "output_mode": args.output_mode,
    }, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    if not args.output:
        raise SystemExit("--output is required unless --dry-run is used")
    manifest = write_bundle(args.output.resolve(), handle, profile, raw_rows, records, period_selected, selected, compiled, fetch_meta, args, source_path)
    print(json.dumps({"output": str(args.output.resolve()), "manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
