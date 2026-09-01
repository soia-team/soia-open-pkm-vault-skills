"""Regression tests for X archive layout and Article media extraction."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "soia-pkm-clip-x" / "scripts" / "archive_x.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("archive_x", SCRIPT)
assert SPEC and SPEC.loader
archive_x = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = archive_x
SPEC.loader.exec_module(archive_x)


class ArchiveXTests(unittest.TestCase):
    def test_archive_month_dir_uses_zero_padded_year_and_month(self) -> None:
        root = Path("/vault/articles")
        dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.assertEqual(archive_x.archive_month_dir(root, dt), root / "2026" / "08")

    def test_collect_media_includes_article_entities_and_deduplicates(self) -> None:
        image_url = "https://pbs.twimg.com/media/article-image.jpg"
        media = archive_x.collect_media(
            [{"media": {"photos": [{"url": image_url}]}}],
            {
                "media_entities": [
                    {"media_info": {"original_img_url": image_url}},
                    {"media_info": {"original_img_url": "https://pbs.twimg.com/media/article-2.jpg"}},
                ]
            },
        )
        self.assertEqual(
            media,
            [
                {"type": "image", "url": image_url},
                {"type": "image", "url": "https://pbs.twimg.com/media/article-2.jpg"},
            ],
        )

    def test_expanded_tweet_text_uses_fxtwitter_url_facets(self) -> None:
        tweet = {
            "raw_text": {
                "text": "论文下载：https://t.co/abc123",
                "facets": [
                    {
                        "type": "url",
                        "original": "https://t.co/abc123",
                        "replacement": "https://arxiv.org/abs/1234.5678",
                    }
                ],
            }
        }
        self.assertEqual(
            archive_x.expanded_tweet_text(tweet),
            "论文下载：https://arxiv.org/abs/1234.5678",
        )

    def test_find_existing_archive_prefers_source_over_translation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="clip-x-") as temp:
            root = Path(temp)
            (root / "2026-01-01-source.md").write_text(
                'url: https://x.com/user/status/123\n', encoding="utf-8"
            )
            (root / "2026-01-01-source-中文版.md").write_text(
                'url: https://x.com/user/status/123\n', encoding="utf-8"
            )
            self.assertEqual(
                archive_x.find_existing_archive(root, "123"),
                root / "2026-01-01-source.md",
            )


if __name__ == "__main__":
    unittest.main()
