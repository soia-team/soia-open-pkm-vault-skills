"""Regression tests for bounded PDF URL archiving."""

from __future__ import annotations

import hashlib
import http.server
import tempfile
import threading
import unittest
from pathlib import Path

import importlib.util
import sys
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "soia-pkm-clip-drive" / "scripts" / "archive_pdf.py"
SPEC = importlib.util.spec_from_file_location("archive_pdf", SCRIPT)
assert SPEC and SPEC.loader
archive_pdf = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = archive_pdf
SPEC.loader.exec_module(archive_pdf)


PDF_BYTES = b"%PDF-1.4\n%fixture\n"


class ArchivePdfTests(unittest.TestCase):
    def test_safe_output_name_rejects_path_components(self) -> None:
        self.assertEqual(
            archive_pdf.safe_output_name("../GPT-1.pdf", "https://example.com/file"),
            "GPT-1.pdf",
        )

    def test_discover_pdf_url_maps_arxiv_abs_to_pdf(self) -> None:
        self.assertEqual(
            archive_pdf.discover_pdf_url("https://arxiv.org/abs/1706.03762"),
            "https://arxiv.org/pdf/1706.03762.pdf",
        )

    def test_discover_pdf_url_reads_citation_meta(self) -> None:
        class Response:
            headers = type("Headers", (), {"get_content_type": lambda self: "text/html"})()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def geturl(self):
                return "https://example.com/paper"

            def read(self, _size):
                data, self._sent = getattr(self, "_sent", False), True
                return b'<meta name="citation_pdf_url" content="/download/paper.pdf">' if not data else b""

        with mock.patch.object(archive_pdf.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(
                archive_pdf.discover_pdf_url("https://example.com/paper"),
                "https://example.com/download/paper.pdf",
            )

    def test_archive_one_downloads_pdf_and_preserves_hash(self) -> None:
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(PDF_BYTES)))
                self.end_headers()
                self.wfile.write(PDF_BYTES)

            def log_message(self, *_args):
                return

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="clip-pdf-") as temp:
                result = archive_pdf.archive_one(
                    f"http://127.0.0.1:{server.server_port}/paper.pdf",
                    Path(temp),
                )
                self.assertEqual(result.status, "archived")
                target = Path(result.target)
                self.assertEqual(target.read_bytes(), PDF_BYTES)
                self.assertEqual(result.sha256, hashlib.sha256(PDF_BYTES).hexdigest())
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_dry_run_does_not_create_output_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="clip-pdf-") as temp:
            target_dir = Path(temp) / "not-created"
            original = archive_pdf.urllib.request.urlopen

            class Response:
                headers = type("Headers", (), {"get_content_type": lambda self: "application/pdf"})()

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def geturl(self):
                    return "https://example.com/paper.pdf"

                def read(self, _size):
                    data, self._sent = getattr(self, "_sent", False), True
                    return b"" if data else PDF_BYTES

            archive_pdf.urllib.request.urlopen = lambda *_args, **_kwargs: Response()
            try:
                result = archive_pdf.archive_one(
                    "https://example.com/paper.pdf", target_dir, dry_run=True
                )
            finally:
                archive_pdf.urllib.request.urlopen = original
            self.assertEqual(result.status, "dry_run")
            self.assertFalse(target_dir.exists())


if __name__ == "__main__":
    unittest.main()
