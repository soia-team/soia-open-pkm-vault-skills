#!/usr/bin/env python3
"""Download and verify PDF sources into a controlled vault directory.

The command deliberately treats a URL as an input source, not as a filename:
it validates the HTTP(S) URL, streams through a bounded temporary file, checks
the PDF magic bytes, atomically installs the artifact, and reports SHA-256 and
optional Poppler metadata.  Text extraction is opt-in and also atomic.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


DEFAULT_MAX_BYTES = 100 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._()\-一-鿿 ]+")


@dataclass
class PdfResult:
    source_url: str
    resolved_url: str = ""
    final_url: str = ""
    status: str = ""
    target: str = ""
    text_target: str | None = None
    bytes: int = 0
    sha256: str = ""
    text_bytes: int = 0
    text_sha256: str = ""
    pages: int | None = None
    encrypted: str | None = None
    content_type: str = ""
    error: str = ""


def validate_http_url(url: str) -> str:
    value = url.strip()
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("PDF source must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("PDF source URL must not contain credentials")
    return value


class _PdfLinkParser(HTMLParser):
    """Collect common PDF link declarations from an HTML landing page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        href = values.get("href", "")
        content = values.get("content", "")
        name = values.get("name", "").lower()
        rel = values.get("rel", "").lower()
        typ = values.get("type", "").lower()
        if tag == "meta" and name in {"citation_pdf_url", "og:pdf"} and content:
            self.candidates.append(content)
        elif tag == "link" and href and ("pdf" in typ or ("alternate" in rel and ".pdf" in href.lower())):
            self.candidates.append(href)
        elif tag == "a" and href:
            parsed = urllib.parse.urlsplit(href)
            if parsed.path.lower().endswith(".pdf") or "pdf" in parsed.query.lower():
                self.candidates.append(href)


def _read_bounded_bytes(response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise ValueError(f"response exceeds max bytes ({max_bytes})")
        chunks.append(chunk)
    return b"".join(chunks)


def discover_pdf_url(source_url: str, *, timeout: int = 60, max_bytes: int = 5 * 1024 * 1024) -> str:
    """Resolve a paper landing page to a likely PDF URL.

    arXiv's ``abs`` pages have a deterministic PDF endpoint.  Other landing
    pages are inspected for standard citation/link declarations; the eventual
    download still checks the PDF magic bytes, so a false candidate fails
    closed rather than producing a mislabeled HTML file.
    """
    source_url = validate_http_url(source_url)
    parsed = urllib.parse.urlsplit(source_url)
    if parsed.path.lower().endswith(".pdf"):
        return source_url
    if parsed.netloc.lower() in {"arxiv.org", "www.arxiv.org"}:
        match = re.match(r"^/abs/([^/]+)$", parsed.path)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}.pdf"

    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "soia-pkm-clip-drive/1.1", "Accept": "text/html,application/xhtml+xml"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        html = _read_bounded_bytes(response, max_bytes).decode("utf-8", errors="replace")
        base_url = validate_http_url(response.geturl())
    parser = _PdfLinkParser()
    parser.feed(html)
    seen: set[str] = set()
    for candidate in parser.candidates:
        try:
            resolved = validate_http_url(urllib.parse.urljoin(base_url, candidate))
        except ValueError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        return resolved
    raise RuntimeError("no PDF link found on landing page")


def safe_output_name(name: str, source_url: str) -> str:
    candidate = Path(urllib.parse.unquote(name)).name.strip() if name else ""
    if not candidate:
        path_name = Path(urllib.parse.unquote(urllib.parse.urlsplit(source_url).path)).name
        candidate = path_name or "downloaded.pdf"
    candidate = SAFE_NAME_RE.sub("-", candidate).strip(" .")
    if not candidate:
        candidate = "downloaded.pdf"
    if not candidate.lower().endswith(".pdf"):
        candidate += ".pdf"
    return candidate


def parse_url_file(path: Path) -> list[tuple[str, str | None]]:
    rows: list[tuple[str, str | None]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t", 1)
        try:
            url = validate_http_url(parts[0])
        except ValueError as exc:
            raise ValueError(f"{path}:{lineno}: {exc}") from exc
        rows.append((url, parts[1].strip() if len(parts) == 2 and parts[1].strip() else None))
    return rows


def iter_inputs(urls: Iterable[str], url_file: Path | None) -> list[tuple[str, str | None]]:
    result: list[tuple[str, str | None]] = []
    for url in urls:
        result.append((validate_http_url(url), None))
    if url_file:
        result.extend(parse_url_file(url_file))
    if not result:
        raise ValueError("provide at least one URL or --url-file")
    return result


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _read_bounded(response, max_bytes: int, temp_path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with temp_path.open("wb") as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise ValueError(f"response exceeds max bytes ({max_bytes})")
            stream.write(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _pdfinfo(path: Path) -> tuple[int | None, str | None]:
    try:
        proc = subprocess.run(
            ["pdfinfo", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None, None
    if proc.returncode != 0:
        return None, None
    pages: int | None = None
    encrypted: str | None = None
    for line in proc.stdout.splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        if key.strip() == "Pages":
            try:
                pages = int(value)
            except ValueError:
                pass
        elif key.strip() == "Encrypted":
            encrypted = value.lower()
    return pages, encrypted


def _extract_text(pdf_path: Path, text_path: Path) -> tuple[int, str]:
    text_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".pdf-text-", suffix=".part", dir=text_path.parent, delete=False
    ) as stream:
        temp_text = Path(stream.name)
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(temp_text)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or "pdftotext failed").strip()
            raise RuntimeError(detail[:400])
        os.replace(temp_text, text_path)
        return _sha256(text_path)
    finally:
        temp_text.unlink(missing_ok=True)


def archive_one(
    source_url: str,
    output_dir: Path,
    name: str | None = None,
    *,
    extract: bool = False,
    force: bool = False,
    dry_run: bool = False,
    timeout: int = 60,
    max_bytes: int = DEFAULT_MAX_BYTES,
    deep: bool = False,
    text_dir: Path | None = None,
) -> PdfResult:
    source_url = validate_http_url(source_url)
    result = PdfResult(source_url=source_url)
    resolved_url = source_url
    if deep:
        try:
            resolved_url = discover_pdf_url(source_url, timeout=timeout)
            result.resolved_url = resolved_url
        except Exception as exc:
            result.status = "failed"
            result.error = str(exc)
            return result
    output_dir = output_dir.expanduser().resolve()
    dry_dir: Path | None = None
    work_dir = output_dir
    if dry_run:
        dry_dir = Path(tempfile.mkdtemp(prefix="clip-pdf-dry-run-"))
        work_dir = dry_dir
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / safe_output_name(name or "", source_url)
    result.target = str(target)
    text_target = (text_dir or output_dir) / f"{target.stem}-extracted.txt"
    if target.exists() and not force and not dry_run:
        result.status = "conflict"
        result.error = f"target exists: {target}"
        return result
    if extract and text_target.exists() and not force and not dry_run:
        result.status = "conflict"
        result.error = f"text target exists: {text_target}"
        return result

    temp_path: Path | None = None
    try:
        request = urllib.request.Request(
            resolved_url,
            headers={"User-Agent": "soia-pkm-clip-drive/1.1", "Accept": "application/pdf,*/*"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result.final_url = validate_http_url(response.geturl())
            result.content_type = response.headers.get_content_type()
            with tempfile.NamedTemporaryFile(
                prefix=".pdf-download-", suffix=".part", dir=work_dir, delete=False
            ) as stream:
                temp_path = Path(stream.name)
            size, sha = _read_bounded(response, max_bytes, temp_path)
        with temp_path.open("rb") as stream:
            if stream.read(len(PDF_MAGIC)) != PDF_MAGIC:
                raise ValueError("response is not a PDF (missing %PDF- magic bytes)")
        result.bytes, result.sha256 = size, sha
        result.pages, result.encrypted = _pdfinfo(temp_path)
        if dry_run:
            result.status = "dry_run"
            return result
        os.replace(temp_path, target)
        temp_path = None
        if extract:
            text_bytes, text_sha = _extract_text(target, text_target)
            result.text_target = str(text_target)
            result.text_bytes, result.text_sha256 = text_bytes, text_sha
        result.status = "archived"
        return result
    except Exception as exc:
        result.status = "failed"
        result.error = str(exc)
        return result
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        if dry_dir:
            shutil.rmtree(dry_dir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Download and verify PDF sources into a vault directory.")
    ap.add_argument("urls", nargs="*", help="HTTP(S) PDF URLs")
    ap.add_argument("--url-file", type=Path, help="UTF-8 file: URL or URL<TAB>filename per line")
    ap.add_argument("--output-dir", required=True, type=Path, help="destination directory")
    ap.add_argument("--text-dir", type=Path, help="optional directory for extracted text")
    ap.add_argument("--name", help="filename for a single positional URL")
    ap.add_argument("--extract", action="store_true", help="run pdftotext -layout and write -extracted.txt")
    ap.add_argument("--deep", action="store_true", help="resolve paper landing pages to a PDF before downloading")
    ap.add_argument("--force", action="store_true", help="replace existing targets")
    ap.add_argument("--dry-run", action="store_true", help="download and inspect without installing")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = ap.parse_args()
    try:
        inputs = iter_inputs(args.urls, args.url_file)
    except ValueError as exc:
        ap.error(str(exc))
    if args.name and len(inputs) != 1:
        ap.error("--name is valid only with one URL")
    results = [
        archive_one(
            url,
            args.output_dir,
            name=args.name or name,
            extract=args.extract,
            force=args.force,
            dry_run=args.dry_run,
            timeout=args.timeout,
            max_bytes=args.max_bytes,
            deep=args.deep,
            text_dir=args.text_dir,
        )
        for url, name in inputs
    ]
    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for result in results:
            suffix = f" error={result.error}" if result.error else ""
            print(f"{result.status}: {result.source_url} -> {result.target}{suffix}")
    return 0 if all(r.status in {"archived", "dry_run"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
