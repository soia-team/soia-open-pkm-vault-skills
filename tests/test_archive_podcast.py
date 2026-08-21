"""Regression tests for public JSON-LD podcast capture."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "soia-pkm-clip-web"
    / "scripts"
    / "archive_podcast.py"
)
SPEC = importlib.util.spec_from_file_location("archive_podcast", SCRIPT)
assert SPEC and SPEC.loader
archive_podcast = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = archive_podcast
SPEC.loader.exec_module(archive_podcast)


PAGE = r"""<!doctype html>
<html><head>
<link rel="canonical" href="https://podcast.example/episode/episode-123">
<meta property="og:site_name" content="Example Podcast">
<meta property="og:image" content="https://cdn.example/cover.jpg?size=large">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "PodcastEpisode",
  "url": "https://podcast.example/episode/episode-123",
  "name": "A real episode",
  "datePublished": "2026-08-17T09:30:00Z",
  "timeRequired": "PT2H51M",
  "description": "Line one.\n\n00:10 First topic",
  "associatedMedia": {
    "@type": "MediaObject",
    "contentUrl": "https://cdn.example/audio.m4a?token=runtime-only"
  },
  "partOfSeries": {
    "@type": "PodcastSeries",
    "name": "Example Show",
    "url": "https://podcast.example/show/example?ref=share"
  }
}
</script>
</head><body></body></html>"""


class ArchivePodcastTests(unittest.TestCase):
    def test_extracts_podcast_episode_and_duration(self) -> None:
        episode = archive_podcast.extract_episode(PAGE, "https://podcast.example/share?tracking=secret")
        self.assertEqual(episode.canonical_url, "https://podcast.example/episode/episode-123")
        self.assertEqual(episode.episode_id, "episode-123")
        self.assertEqual(episode.series_name, "Example Show")
        self.assertEqual(episode.author, "Example Show")
        self.assertEqual(episode.duration_seconds, 10260)
        self.assertEqual(episode.description, "Line one.\n\n00:10 First topic")

    def test_rendered_note_does_not_persist_query_bearing_media_or_share_tokens(self) -> None:
        episode = archive_podcast.extract_episode(PAGE, "https://podcast.example/share?tracking=secret")
        media = archive_podcast.MediaResult(Path("/tmp/audio.m4a"), "a" * 64, 1234, "audio/mp4")
        note = archive_podcast.render_note(
            episode,
            media,
            datetime(2026, 8, 21, tzinfo=timezone.utc),
            media_vault_path="_attachments/podcasts/episode-123/audio.m4a",
            media_embed_path="../../../../_attachments/podcasts/episode-123/audio.m4a",
        )
        self.assertIn('media_source_url: "https://cdn.example/audio.m4a"', note)
        self.assertIn("media_source_url_had_query: true", note)
        self.assertIn("transcript_status: not_provided_by_source", note)
        self.assertIn("## 🎧 收听本地音频", note)
        self.assertIn("![[../../../../_attachments/podcasts/episode-123/audio.m4a]]", note)
        self.assertIn('media_vault_path: "_attachments/podcasts/episode-123/audio.m4a"', note)
        self.assertIn("audio_embedded: true", note)
        self.assertNotIn("runtime-only", note)
        self.assertNotIn("tracking=secret", note)
        self.assertNotIn("ref=share", note)

    def test_filename_uses_published_month_and_stays_within_byte_limit(self) -> None:
        episode = archive_podcast.extract_episode(PAGE, "https://podcast.example/share")
        destination = archive_podcast.note_destination(
            Path("/vault/articles"), episode, datetime(2026, 8, 21, tzinfo=timezone.utc)
        )
        self.assertEqual(destination.parent, Path("/vault/articles/2026/08"))
        self.assertLessEqual(len(destination.stem.encode("utf-8")), 225)

    def test_media_paths_are_vault_relative_and_note_relative(self) -> None:
        vault = Path("/vault")
        note = vault / "40_图书视频馆" / "10_文章摘抄" / "2026" / "08" / "episode.md"
        media = vault / "_attachments" / "podcasts" / "episode-123" / "audio.m4a"
        vault_path, embed_path = archive_podcast.media_paths_for_note(vault, note, media)
        self.assertEqual(vault_path, "_attachments/podcasts/episode-123/audio.m4a")
        self.assertEqual(embed_path, "../../../../_attachments/podcasts/episode-123/audio.m4a")

    def test_media_paths_reject_audio_outside_vault(self) -> None:
        with self.assertRaisesRegex(archive_podcast.ArchiveError, "必须位于 vault 内"):
            archive_podcast.media_paths_for_note(
                Path("/vault"),
                Path("/vault/articles/episode.md"),
                Path("/tmp/audio.m4a"),
            )

    def test_rejects_non_podcast_json_ld(self) -> None:
        page = '<script type="application/ld+json">{"@type":"Article","name":"Not a podcast"}</script>'
        with self.assertRaisesRegex(archive_podcast.ArchiveError, "PodcastEpisode"):
            archive_podcast.extract_episode(page, "https://example.com/article")

    def test_duration_parser_does_not_invent_invalid_values(self) -> None:
        self.assertEqual(archive_podcast.parse_duration_seconds("PT171M"), 10260)
        self.assertIsNone(archive_podcast.parse_duration_seconds("171 minutes"))

    def test_public_url_gate_allows_transparent_proxy_fake_ip(self) -> None:
        resolved = [(2, 1, 6, "", ("198.18.0.42", 443))]
        with mock.patch.object(archive_podcast.socket, "getaddrinfo", return_value=resolved):
            archive_podcast.validate_public_url("https://public.example/episode")

    def test_public_url_gate_rejects_private_and_loopback_targets(self) -> None:
        for address in ("127.0.0.1", "10.0.0.8", "169.254.1.1"):
            resolved = [(2, 1, 6, "", (address, 443))]
            with self.subTest(address=address):
                with mock.patch.object(archive_podcast.socket, "getaddrinfo", return_value=resolved):
                    with self.assertRaisesRegex(archive_podcast.ArchiveError, "拒绝访问"):
                        archive_podcast.validate_public_url("https://public.example/episode")

    def test_auto_download_engine_prefers_aria2c_when_available(self) -> None:
        expected = archive_podcast.MediaResult(Path("/tmp/audio.m4a"), "b" * 64, 42, "audio/mp4", "aria2c")
        with mock.patch.object(archive_podcast.shutil, "which", return_value="/usr/bin/aria2c"):
            with mock.patch.object(archive_podcast, "download_media_aria2", return_value=expected) as aria2:
                actual = archive_podcast.download_media(
                    "https://cdn.example/audio.m4a",
                    Path("/tmp/example"),
                    max_bytes=100,
                    timeout=30,
                    engine="auto",
                )
        self.assertEqual(actual, expected)
        aria2.assert_called_once()

    def test_aria2c_reuses_a_complete_local_audio_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "audio.m4a"
            destination.write_bytes(b"complete-audio")
            with mock.patch.object(archive_podcast.shutil, "which", return_value="/usr/bin/aria2c"):
                with mock.patch.object(
                    archive_podcast,
                    "probe_media",
                    return_value=("https://cdn.example/audio.m4a", "audio/mp4", len(b"complete-audio")),
                ):
                    with mock.patch.object(archive_podcast.subprocess, "run") as runner:
                        result = archive_podcast.download_media_aria2(
                            "https://cdn.example/audio.m4a",
                            Path(temporary),
                            max_bytes=100,
                            timeout=30,
                        )
        self.assertEqual(result.size, len(b"complete-audio"))
        self.assertEqual(result.engine, "aria2c")
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
