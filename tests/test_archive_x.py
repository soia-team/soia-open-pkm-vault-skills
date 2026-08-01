"""Regression tests for X archive layout and Article media extraction."""

from __future__ import annotations

import importlib.util
import sys
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


if __name__ == "__main__":
    unittest.main()
