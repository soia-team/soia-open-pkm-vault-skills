#!/usr/bin/env python3
"""Archive a public JSON-LD PodcastEpisode and optionally download its audio.

The script deliberately keeps large media outside the vault. It writes one
Markdown note into the configured article directory and records the local
audio path plus a SHA-256 digest in frontmatter.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


USER_AGENT = "SOIA-PKM-Clip-Web/1.1"
DEFAULT_MAX_MEDIA_BYTES = 1024 * 1024 * 1024
BLOCK_SIZE = 1024 * 1024
PODCAST_TYPES = {"podcastepisode"}
TRANSPARENT_PROXY_FAKE_IP = ipaddress.ip_network("198.18.0.0/15")


class ArchiveError(RuntimeError):
    """A user-facing archive failure."""


@dataclass(frozen=True)
class Episode:
    canonical_url: str
    episode_id: str
    title: str
    description: str
    published_at: str
    duration_iso: str
    duration_seconds: int | None
    series_name: str
    series_url: str
    author: str
    source: str
    language: str
    cover_url: str
    media_url: str


@dataclass(frozen=True)
class MediaResult:
    path: Path
    sha256: str
    size: int
    mime_type: str
    engine: str = "urllib"


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.canonical_url = ""
        self.json_ld: list[str] = []
        self._json_ld_buffer: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "") for key, value in attrs}
        lowered = tag.lower()
        if lowered == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key and values.get("content") and key not in self.meta:
                self.meta[key] = values["content"]
        elif lowered == "link":
            rels = {item.lower() for item in values.get("rel", "").split()}
            if "canonical" in rels and values.get("href"):
                self.canonical_url = values["href"]
        elif lowered == "script":
            content_type = values.get("type", "").split(";", 1)[0].strip().lower()
            if content_type == "application/ld+json":
                self._json_ld_buffer = []

    def handle_data(self, data: str) -> None:
        if self._json_ld_buffer is not None:
            self._json_ld_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._json_ld_buffer is not None:
            document = "".join(self._json_ld_buffer).strip()
            if document:
                self.json_ld.append(document)
            self._json_ld_buffer = None


def iter_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nodes(child)


def node_types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    return {str(value).lower() for value in values if value}


def named_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    if isinstance(value, list):
        names = [named_value(item) for item in value]
        return "、".join(name for name in names if name)
    return ""


def url_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("contentUrl") or value.get("url") or "").strip()
    if isinstance(value, list):
        for item in value:
            result = url_value(item)
            if result:
                return result
    return ""


def clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = html.unescape(value).replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r"<[^>]+>", text):
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</(?:p|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def strip_query_and_fragment(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ArchiveError("URL 必须是有效的 http/https 地址")
    return urlunparse((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", "", "", ""))


def persistable_url(value: str) -> tuple[str, bool]:
    if not value:
        return "", False
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return "", False
    had_query = bool(parsed.query or parsed.fragment)
    clean = urlunparse((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", "", "", ""))
    return clean, had_query


def parse_duration_seconds(value: str) -> int | None:
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        value or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    parts = {key: int(raw or 0) for key, raw in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def parse_json_ld(documents: list[str]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for document in documents:
        try:
            decoded = json.loads(document)
        except json.JSONDecodeError:
            continue
        nodes.extend(iter_nodes(decoded))
    return nodes


def infer_source(canonical_url: str, meta: dict[str, str]) -> str:
    site_name = clean_text(meta.get("og:site_name", ""))
    if site_name:
        return site_name
    hostname = (urlparse(canonical_url).hostname or "").lower()
    if hostname == "xiaoyuzhoufm.com" or hostname.endswith(".xiaoyuzhoufm.com"):
        return "小宇宙"
    return hostname.removeprefix("www.") or "网页"


def episode_identifier(canonical_url: str) -> str:
    candidate = Path(urlparse(canonical_url).path).name
    if candidate and re.fullmatch(r"[A-Za-z0-9._-]+", candidate):
        return candidate
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:20]


def extract_episode(page_html: str, requested_url: str) -> Episode:
    parser = MetadataParser()
    parser.feed(page_html)
    nodes = parse_json_ld(parser.json_ld)
    episode_node = next((node for node in nodes if node_types(node) & PODCAST_TYPES), None)
    if episode_node is None:
        raise ArchiveError("页面没有公开的 JSON-LD PodcastEpisode；请回退到普通正文抽取并标记音频未捕获")

    canonical_candidate = parser.canonical_url or url_value(episode_node.get("url")) or requested_url
    canonical_url = strip_query_and_fragment(canonical_candidate)
    title = clean_text(episode_node.get("name")) or clean_text(parser.meta.get("og:title", ""))
    description = clean_text(episode_node.get("description"))
    if not title:
        raise ArchiveError("PodcastEpisode 缺少标题")
    if not description:
        raise ArchiveError("PodcastEpisode 缺少 shownotes，不能标记为完整内容")

    series = episode_node.get("partOfSeries")
    series_name = named_value(series)
    series_url = url_value(series)
    author = named_value(episode_node.get("author") or episode_node.get("creator")) or series_name
    media_url = url_value(episode_node.get("associatedMedia")) or parser.meta.get("og:audio", "").strip()
    if not media_url:
        raise ArchiveError("PodcastEpisode 没有公开音频地址")
    if urlparse(media_url).scheme.lower() not in {"http", "https"}:
        raise ArchiveError("音频地址不是 http/https")

    duration_iso = str(episode_node.get("timeRequired") or "").strip()
    cover_url = url_value(episode_node.get("image")) or parser.meta.get("og:image", "").strip()
    language = str(episode_node.get("inLanguage") or "zh").strip() or "zh"
    return Episode(
        canonical_url=canonical_url,
        episode_id=episode_identifier(canonical_url),
        title=title,
        description=description,
        published_at=str(episode_node.get("datePublished") or "").strip(),
        duration_iso=duration_iso,
        duration_seconds=parse_duration_seconds(duration_iso),
        series_name=series_name,
        series_url=series_url,
        author=author,
        source=infer_source(canonical_url, parser.meta),
        language=language,
        cover_url=cover_url,
        media_url=media_url,
    )


def validate_public_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ArchiveError("只允许公开的 http/https URL")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ArchiveError("拒绝访问本机地址")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ArchiveError(f"域名解析失败：{hostname}") from exc
    if not addresses:
        raise ArchiveError(f"域名没有可用地址：{hostname}")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        # Clash/Shadowrocket-style transparent proxies commonly answer public
        # DNS with RFC 2544 benchmarking addresses and route them through a
        # local TUN. This range is not a private service destination; allowing
        # it preserves public-web access without weakening RFC1918/loopback
        # protection.
        if ip in TRANSPARENT_PROXY_FAKE_IP:
            continue
        if not ip.is_global:
            raise ArchiveError("拒绝访问内网、环回、链路本地或保留地址")


class PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_public_url(url: str, *, accept: str, timeout: int, method: str = "GET"):
    validate_public_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept}, method=method)
    return build_opener(PublicRedirectHandler()).open(request, timeout=timeout)


def fetch_html(url: str, timeout: int) -> str:
    try:
        with open_public_url(url, accept="text/html,application/xhtml+xml", timeout=timeout) as response:
            final_url = response.geturl()
            validate_public_url(final_url)
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ArchiveError(f"页面响应不是 HTML：{content_type}")
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read(20 * 1024 * 1024 + 1)
            if len(raw) > 20 * 1024 * 1024:
                raise ArchiveError("页面超过 20 MiB，停止解析")
            return raw.decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ArchiveError(f"网页抓取失败：{exc}") from exc


def media_extension(media_url: str, mime_type: str) -> str:
    suffix = Path(urlparse(media_url).path).suffix.lower()
    if suffix in {".m4a", ".mp3", ".aac", ".ogg", ".opus", ".wav", ".flac", ".mp4"}:
        return suffix
    return {
        "audio/mp4": ".m4a",
        "audio/mpeg": ".mp3",
        "audio/aac": ".aac",
        "audio/ogg": ".ogg",
        "audio/opus": ".opus",
        "audio/wav": ".wav",
        "audio/flac": ".flac",
    }.get(mime_type, ".audio")


def inspect_media_headers(response: Any, media_url: str, max_bytes: int) -> tuple[str, str, int | None]:
    final_url = response.geturl()
    validate_public_url(final_url)
    mime_type = response.headers.get_content_type().lower()
    url_suffix = Path(urlparse(final_url).path).suffix.lower()
    if not mime_type.startswith("audio/") and url_suffix not in {".m4a", ".mp3", ".aac", ".ogg", ".opus", ".wav", ".flac"}:
        raise ArchiveError(f"媒体响应不像音频：{mime_type}")
    declared_raw = response.headers.get("Content-Length", "")
    declared = int(declared_raw) if declared_raw.isdigit() else None
    if declared is not None and declared > max_bytes:
        raise ArchiveError(f"音频超过大小上限：{declared} > {max_bytes} bytes")
    return final_url, mime_type, declared


def probe_media(media_url: str, *, max_bytes: int, timeout: int) -> tuple[str, str, int | None]:
    try:
        with open_public_url(media_url, accept="audio/*,application/octet-stream", timeout=timeout, method="HEAD") as response:
            return inspect_media_headers(response, media_url, max_bytes)
    except HTTPError as exc:
        if exc.code not in {405, 501}:
            raise ArchiveError(f"音频预检失败：HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise ArchiveError(f"音频预检失败：{exc}") from exc
    try:
        with open_public_url(media_url, accept="audio/*,application/octet-stream", timeout=timeout) as response:
            return inspect_media_headers(response, media_url, max_bytes)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ArchiveError(f"音频预检失败：{exc}") from exc


def download_media_urllib(
    media_url: str,
    destination_dir: Path,
    *,
    max_bytes: int,
    timeout: int,
) -> MediaResult:
    try:
        with open_public_url(media_url, accept="audio/*,application/octet-stream", timeout=timeout) as response:
            final_url, mime_type, declared = inspect_media_headers(response, media_url, max_bytes)

            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"audio{media_extension(final_url, mime_type)}"
            temporary = destination.with_suffix(destination.suffix + ".part")
            digest = hashlib.sha256()
            size = 0
            try:
                with temporary.open("wb") as handle:
                    while True:
                        block = response.read(BLOCK_SIZE)
                        if not block:
                            break
                        size += len(block)
                        if size > max_bytes:
                            raise ArchiveError(f"音频流超过大小上限：{max_bytes} bytes")
                        digest.update(block)
                        handle.write(block)
                if declared is not None and size != declared:
                    raise ArchiveError(f"音频下载不完整：期望 {declared} bytes，实际 {size} bytes")
                os.replace(temporary, destination)
            finally:
                if temporary.exists():
                    temporary.unlink()
            return MediaResult(destination.resolve(), digest.hexdigest(), size, mime_type)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ArchiveError(f"音频下载失败：{exc}") from exc


def download_media_aria2(
    media_url: str,
    destination_dir: Path,
    *,
    max_bytes: int,
    timeout: int,
) -> MediaResult:
    executable = shutil.which("aria2c")
    if not executable:
        raise ArchiveError("未找到 aria2c")
    final_url, mime_type, declared = probe_media(media_url, max_bytes=max_bytes, timeout=timeout)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"audio{media_extension(final_url, mime_type)}"
    temporary = destination.with_suffix(destination.suffix + ".part")
    control = Path(str(temporary) + ".aria2")
    if destination.is_file():
        size = destination.stat().st_size
        if size <= max_bytes and (declared is None or size == declared):
            digest = hashlib.sha256()
            with destination.open("rb") as handle:
                while block := handle.read(BLOCK_SIZE):
                    digest.update(block)
            return MediaResult(destination.resolve(), digest.hexdigest(), size, mime_type, "aria2c")
    command = [
        executable,
        "--input-file=-",
        f"--dir={destination_dir}",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "--continue=true",
        "--file-allocation=none",
        "--max-connection-per-server=8",
        "--split=8",
        "--min-split-size=1M",
        "--max-tries=3",
        "--retry-wait=2",
        f"--timeout={timeout}",
        "--connect-timeout=30",
        "--summary-interval=0",
        "--console-log-level=warn",
        "--download-result=hide",
        "--check-certificate=true",
    ]
    try:
        completed = subprocess.run(
            command,
            input=f"{media_url}\n  out={temporary.name}\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise ArchiveError(f"aria2c 并行下载失败（exit {completed.returncode}）")
        if not temporary.is_file():
            raise ArchiveError("aria2c 返回成功但没有生成音频文件")
        size = temporary.stat().st_size
        if size > max_bytes:
            raise ArchiveError(f"音频超过大小上限：{size} > {max_bytes} bytes")
        if declared is not None and size != declared:
            raise ArchiveError(f"音频下载不完整：期望 {declared} bytes，实际 {size} bytes")
        digest = hashlib.sha256()
        with temporary.open("rb") as handle:
            while block := handle.read(BLOCK_SIZE):
                digest.update(block)
        os.replace(temporary, destination)
        if control.exists():
            control.unlink()
        return MediaResult(destination.resolve(), digest.hexdigest(), size, mime_type, "aria2c")
    finally:
        if temporary.exists():
            temporary.unlink()
        if control.exists():
            control.unlink()


def download_media(
    media_url: str,
    destination_dir: Path,
    *,
    max_bytes: int,
    timeout: int,
    engine: str,
) -> MediaResult:
    selected = engine
    if selected == "auto":
        selected = "aria2c" if shutil.which("aria2c") else "urllib"
    if selected == "aria2c":
        return download_media_aria2(media_url, destination_dir, max_bytes=max_bytes, timeout=timeout)
    return download_media_urllib(media_url, destination_dir, max_bytes=max_bytes, timeout=timeout)


def safe_component(value: str, fallback: str) -> str:
    value = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "-", value)
    value = re.sub(r"\s+", "-", value).strip(" .-")
    return value or fallback


def truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    shortened = encoded[:max_bytes]
    while shortened:
        try:
            return shortened.decode("utf-8").rstrip(" .-")
        except UnicodeDecodeError:
            shortened = shortened[:-1]
    return "episode"


def publication_date(episode: Episode, captured_at: datetime) -> str:
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", episode.published_at)
    return "-".join(match.groups()) if match else captured_at.strftime("%Y-%m-%d")


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_note(
    episode: Episode,
    media: MediaResult | None,
    captured_at: datetime,
    *,
    media_vault_path: str = "",
    media_embed_path: str = "",
) -> str:
    stored_media_url, media_url_had_query = persistable_url(episode.media_url)
    stored_cover_url, _ = persistable_url(episode.cover_url)
    stored_series_url, _ = persistable_url(episode.series_url)
    media_path = str(media.path) if media else ""
    media_sha256 = media.sha256 if media else ""
    media_size = media.size if media else 0
    media_mime = media.mime_type if media else ""
    duration = "" if episode.duration_seconds is None else str(episode.duration_seconds)
    captured_value = captured_at.astimezone().strftime("%Y-%m-%d %H:%M")
    published_value = episode.published_at

    lines = [
        "---",
        "tags: [文章摘抄, 播客]",
        f"source: {yaml_string(episode.source)}",
        f"url: {yaml_string(episode.canonical_url)}",
        f"author: {yaml_string(episode.author)}",
        f"podcast: {yaml_string(episode.series_name)}",
        f"podcast_url: {yaml_string(stored_series_url)}",
        f"published_at: {yaml_string(published_value)}",
        f"captured_at: {yaml_string(captured_value)}",
        f"language: {yaml_string(episode.language)}",
        "type: podcast",
        "topics: []",
        "people: []",
        f"episode_id: {yaml_string(episode.episode_id)}",
        f"duration_iso: {yaml_string(episode.duration_iso)}",
        f"duration_seconds: {duration}",
        f"cover: {yaml_string(stored_cover_url)}",
        f"media_local_path: {yaml_string(media_path)}",
        f"media_vault_path: {yaml_string(media_vault_path)}",
        f"audio_embedded: {'true' if media_embed_path else 'false'}",
        f"media_fetched: {'true' if media else 'false'}",
        f"media_sha256: {yaml_string(media_sha256)}",
        f"media_bytes: {media_size}",
        f"media_mime_type: {yaml_string(media_mime)}",
        f"media_download_engine: {yaml_string(media.engine if media else '')}",
        f"media_source_url: {yaml_string(stored_media_url)}",
        f"media_source_url_had_query: {'true' if media_url_had_query else 'false'}",
        "content_complete: true",
        "transcript_status: not_provided_by_source",
        "---",
        "",
        f"# {episode.title}",
        "",
        "> [!source]- 来源信息",
        f"> **来源** ｜ [{episode.source}]({episode.canonical_url}) ｜ {published_value or '发布时间未核实'}",
        f"> **节目** ｜ {episode.series_name or '未核实'}",
        f"> **抓取方式** ｜ JSON-LD `PodcastEpisode`（页面 shownotes，不是音频转写）",
        f"> **媒体状态** ｜ {'已下载并校验 SHA-256' if media else '未下载'}",
        "",
        "## 摘要",
        "",
        "<!-- AI 补充：1-3 句话，区分节目主张与事实核验 -->",
        "",
        "## 🎧 收听本地音频",
        "",
        f"![[{media_embed_path}]]" if media_embed_path else "本地音频未写入 vault，无法在 Obsidian 内嵌播放。",
        "",
        f"- 本地文件：`{media_path}`" if media_path else "- 本地文件：未下载",
        f"- 文件大小：{media_size} bytes" if media else "- 文件大小：未核实",
        f"- SHA-256：`{media_sha256}`" if media else "- SHA-256：未计算",
        f"- 原始媒体：[在线播放]({stored_media_url})" if stored_media_url else "- 原始媒体：未持久化",
        "- 转写状态：来源页未提供逐字稿；下方为原始 shownotes",
        "",
        "## 原文",
        "",
        episode.description,
        "",
        "## 我的看法",
        "",
        "<!-- 留空给用户后续手写 -->",
        "",
        "## 关联",
        "",
    ]
    return "\n".join(lines)


def media_paths_for_note(vault: Path, note_path: Path, media_path: Path) -> tuple[str, str]:
    """Return vault-root and note-relative POSIX paths for an Obsidian embed."""
    resolved_vault = vault.expanduser().resolve()
    resolved_note = note_path.expanduser().resolve()
    resolved_media = media_path.expanduser().resolve()
    try:
        vault_relative = resolved_media.relative_to(resolved_vault)
    except ValueError as exc:
        raise ArchiveError(f"音频必须位于 vault 内才能生成 Obsidian 播放器：{resolved_media}") from exc
    embed_relative = Path(os.path.relpath(resolved_media, start=resolved_note.parent))
    return vault_relative.as_posix(), embed_relative.as_posix()


def note_destination(articles_root: Path, episode: Episode, captured_at: datetime) -> Path:
    date_value = publication_date(episode, captured_at)
    year, month, _ = date_value.split("-")
    source = safe_component(episode.source, "网页")
    series = safe_component(episode.series_name or episode.author, "播客")
    title = safe_component(episode.title, "未命名节目")
    base = truncate_utf8(f"{date_value}-{source}-{series}-{title}", 225)
    return articles_root / year / month / f"{base}.md"


def find_existing(articles_root: Path, canonical_url: str) -> Path | None:
    needle = f"url: {yaml_string(canonical_url)}"
    for path in articles_root.rglob("*.md"):
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for _ in range(50):
                    line = handle.readline()
                    if not line:
                        break
                    if line.rstrip("\n") == needle:
                        return path
        except OSError:
            continue
    return None


def confined_child(root: Path, child: Path) -> Path:
    root = root.expanduser().resolve()
    child = child.expanduser().resolve()
    try:
        child.relative_to(root)
    except ValueError as exc:
        raise ArchiveError(f"目标路径越出 vault：{child}") from exc
    return child


def write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_vault(value: str | None) -> Path:
    raw = value or os.environ.get("OBSIDIAN_VAULT", "")
    if not raw:
        raise ArchiveError("请用 --vault 或 OBSIDIAN_VAULT 指定 vault")
    vault = Path(raw).expanduser().resolve()
    if not vault.is_dir():
        raise ArchiveError(f"vault 不存在：{vault}")
    return vault


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="public podcast episode URL")
    parser.add_argument("--vault", help="vault root; defaults to OBSIDIAN_VAULT")
    parser.add_argument(
        "--articles-dir",
        default=os.environ.get("SOIA_PKM_ARTICLES_DIR", "Articles"),
        help="article directory relative to vault (default: SOIA_PKM_ARTICLES_DIR or Articles)",
    )
    parser.add_argument(
        "--media-dir",
        default="_attachments/podcasts",
        help="audio directory relative to the vault (default: _attachments/podcasts)",
    )
    parser.add_argument("--metadata-only", action="store_true", help="archive shownotes without downloading audio")
    parser.add_argument("--max-media-bytes", type=int, default=DEFAULT_MAX_MEDIA_BYTES)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--download-engine",
        choices=("auto", "urllib", "aria2c"),
        default="auto",
        help="audio downloader (default: aria2c when installed, otherwise urllib)",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault = resolve_vault(args.vault)
    articles_root = confined_child(vault, vault / args.articles_dir)
    if args.max_media_bytes <= 0:
        raise ArchiveError("--max-media-bytes 必须大于 0")
    if args.timeout <= 0:
        raise ArchiveError("--timeout 必须大于 0")

    page_html = fetch_html(args.url, args.timeout)
    episode = extract_episode(page_html, args.url)
    existing = find_existing(articles_root, episode.canonical_url) if articles_root.exists() else None
    if existing:
        return {"status": "skipped", "reason": "already_archived", "note_path": str(existing.resolve())}

    captured_at = datetime.now().astimezone()
    destination = confined_child(vault, note_destination(articles_root, episode, captured_at))
    if destination.exists():
        raise ArchiveError(f"目标笔记已存在但 canonical URL 不同，拒绝覆盖：{destination}")

    media = None
    media_vault_path = ""
    media_embed_path = ""
    if not args.metadata_only:
        media_dir = Path(args.media_dir).expanduser()
        media_root_base = media_dir if media_dir.is_absolute() else vault / media_dir
        media_root = confined_child(vault, media_root_base / episode.episode_id)
        media = download_media(
            episode.media_url,
            media_root,
            max_bytes=args.max_media_bytes,
            timeout=args.timeout,
            engine=args.download_engine,
        )
        media_vault_path, media_embed_path = media_paths_for_note(vault, destination, media.path)

    write_note(
        destination,
        render_note(
            episode,
            media,
            captured_at,
            media_vault_path=media_vault_path,
            media_embed_path=media_embed_path,
        ),
    )
    return {
        "status": "created",
        "note_path": str(destination),
        "media_local_path": str(media.path) if media else "",
        "media_vault_path": media_vault_path,
        "media_embed_path": media_embed_path,
        "audio_embedded": bool(media_embed_path),
        "media_bytes": media.size if media else 0,
        "media_sha256": media.sha256 if media else "",
        "media_download_engine": media.engine if media else "",
        "content_complete": True,
        "transcript_status": "not_provided_by_source",
    }


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run(args)
    except ArchiveError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
