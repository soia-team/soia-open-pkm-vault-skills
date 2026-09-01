"""Safety regressions for WeChat article archival (URL identity dedup + block detection)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "soia-pkm-clip-wechat-article"
    / "scripts"
    / "archive_wechat.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("archive_wechat", SCRIPT)
assert SPEC and SPEC.loader
archive_wechat = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = archive_wechat
SPEC.loader.exec_module(archive_wechat)


class DedupIdentityTests(unittest.TestCase):
    """Tracking/session query params must not break URL identity dedup."""

    def test_same_article_clean_vs_click_id(self):
        clean = "https://mp.weixin.qq.com/s/_-G3W6NJqRVUOOgNTkWnqA"
        with_click = "https://mp.weixin.qq.com/s/_-G3W6NJqRVUOOgNTkWnqA?click_id=1460551714"
        self.assertEqual(
            archive_wechat.dedup_identity_url(clean),
            archive_wechat.dedup_identity_url(with_click),
        )

    def test_tracking_params_dropped(self):
        url = (
            "https://mp.weixin.qq.com/s/abc?scene=21&poc_token=secret&click_id=9"
        )
        self.assertEqual(
            archive_wechat.dedup_identity_url(url),
            "https://mp.weixin.qq.com/s/abc",
        )

    def test_s_biz_form_keeps_identity_params(self):
        url = (
            "https://mp.weixin.qq.com/s?__biz=MzA3NjgwMTY4Mw==&mid=2456752804"
            "&idx=1&sn=442dc0c9b2a29649a6fd3cfe02759c46&scene=21&poc_token=x"
        )
        got = archive_wechat.dedup_identity_url(url)
        self.assertIn("__biz=", got)
        self.assertIn("sn=", got)
        self.assertNotIn("scene=", got)
        self.assertNotIn("poc_token", got)

    def test_normalize_canonical_drops_tracking(self):
        self.assertEqual(
            archive_wechat.normalize_canonical_url("", "https://mp.weixin.qq.com/s/a?click_id=1"),
            "https://mp.weixin.qq.com/s/a",
        )


class BlockDetectionTests(unittest.TestCase):
    def test_captcha(self):
        html = "<html>wappoc_appmsgcaptcha challenge</html>"
        self.assertEqual(
            archive_wechat._detect_block_reason(html, "", False, ["blocked_page_marker"]),
            "wechat_captcha",
        )

    def test_param_error(self):
        html = "<title>参数错误</title>"
        self.assertEqual(
            archive_wechat._detect_block_reason(html, "", False, ["blocked_page_marker"]),
            "wechat_param_error",
        )

    def test_deleted(self):
        html = "该内容已被发布者删除"
        self.assertEqual(
            archive_wechat._detect_block_reason(html, "", False, ["blocked_page_marker"]),
            "deleted",
        )

    def test_healthy_page_no_block(self):
        self.assertEqual(
            archive_wechat._detect_block_reason(
                "<div id='js_content'>lots of text</div>", "text", True, []
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
