from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "soia-pkm-clip-wechat-account" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import clip_gzh_env  # noqa: E402
import fetch_api  # noqa: E402
import fetch_mp  # noqa: E402


ENV_KEYS_TO_CLEAR = {
    "SOIA_PKM_CLIP_WECHAT_ACCOUNT_CONFIG_FILE",
    "SOIA_PKM_CLIP_GZH_ENV_FILE",
    "SOIA_SKILLS_CONFIG_HOME",
    "XDG_CONFIG_HOME",
    "WECHAT_APP_ID",
    "WECHAT_APP_SECRET",
    "WECHAT_MP_TOKEN",
    "WECHAT_MP_COOKIE",
    "WECHAT_MP_FAKEID",
    "WECHAT_BIZ",
    "WECHAT_KEY",
    "WECHAT_PASS_TICKET",
    "WECHAT_APPMSG_TOKEN",
    "WECHAT_COOKIE",
    "WECHAT_UIN",
    "WECHAT_ACCOUNT_NAME",
    "OBSIDIAN_VAULT",
    "OBSIDIAN_GZH_OUT",
}


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS_TO_CLEAR}
    if extra:
        env.update(extra)
    return env


class ClipWeChatMultiAccountEnvTests(unittest.TestCase):
    def test_inline_multi_account_fail_closed_and_route_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "soia-pkm-clip-wechat-account"
            cfg_dir.mkdir(parents=True)
            cfg = cfg_dir / "config.yml"
            cfg.write_text(
                "\n".join(
                    [
                        "accounts:",
                        "  yuanbaobiji:",
                        '    name: "示例号一"',
                        '    wechat_id: "ybb_id"',
                        '    out: "Inbox/gzh/ybb"',
                        '    app_id: "wx_1"',
                        '    app_secret: "sec_1"',
                        '    mp_token: "mp_tok_1"',
                        '    mp_cookie: "mp_ck_1"',
                        "  zbt:",
                        '    name: "示例号二"',
                        '    wechat_id: "zbt_id"',
                        '    out: "Inbox/gzh/zbt"',
                        '    app_id: "wx_2"',
                        '    app_secret: "<YOUR_ZBT_APP_SECRET>"',
                        '    biz: "MzAwMDA="',
                        '    key: "k2"',
                        '    pass_ticket: "pt2"',
                        '    cookie: "ck2"',
                        '    appmsg_token: "amt2"',
                        "env:",
                        f'  OBSIDIAN_VAULT: "{tmp}"',
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, _clean_env({"SOIA_SKILLS_CONFIG_HOME": tmp}), clear=True):
                listed = clip_gzh_env.list_accounts()
                self.assertEqual(len(listed), 2)
                by_alias = {item["alias"]: item for item in listed}
                self.assertEqual(by_alias["yuanbaobiji"]["routes"], ["api", "mp"])
                self.assertEqual(by_alias["zbt"]["routes"], ["cookie"])
                for item in listed:
                    self.assertNotIn("app_secret", item)
                    self.assertNotIn("mp_cookie", item)

                with self.assertRaises(ValueError):
                    clip_gzh_env.load_account_env()
                with self.assertRaises(ValueError):
                    clip_gzh_env.load_account_env(account="nonexistent")

                _, chosen = clip_gzh_env.load_account_env(account="zbt_id")
                self.assertEqual(chosen, "zbt")
                self.assertEqual(os.environ.get("WECHAT_ACCOUNT_NAME"), "示例号二")
                self.assertEqual(os.environ.get("OBSIDIAN_GZH_OUT"), "Inbox/gzh/zbt")
                self.assertEqual(os.environ.get("WECHAT_APP_ID"), "wx_2")
                self.assertIsNone(os.environ.get("WECHAT_APP_SECRET"))
                self.assertEqual(os.environ.get("OBSIDIAN_VAULT"), tmp)

    def test_sidecar_multi_yml_files_and_shared_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "soia-pkm-clip-wechat-account"
            (cfg_dir / "accounts").mkdir(parents=True)
            (cfg_dir / "config.yml").write_text(
                f"env:\n  OBSIDIAN_VAULT: \"{tmp}\"\n",
                encoding="utf-8",
            )
            (cfg_dir / "config.zbt.yml").write_text(
                "env:\n  WECHAT_ACCOUNT_NAME: \"示例甲\"\n  WECHAT_MP_TOKEN: \"tok_a\"\n  WECHAT_MP_COOKIE: \"ck_a\"\n",
                encoding="utf-8",
            )
            (cfg_dir / "accounts" / "ybb.yml").write_text(
                "env:\n  WECHAT_ACCOUNT_NAME: \"示例乙\"\n  WECHAT_APP_ID: \"wx_b\"\n  WECHAT_APP_SECRET: \"sec_b\"\n",
                encoding="utf-8",
            )
            (cfg_dir / "config.example.yml").write_text(
                "env:\n  WECHAT_ACCOUNT_NAME: \"模板\"\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, _clean_env({"SOIA_SKILLS_CONFIG_HOME": tmp}), clear=True):
                listed = clip_gzh_env.list_accounts()
                self.assertEqual([a["alias"] for a in listed], ["zbt", "ybb"])
                with self.assertRaises(ValueError):
                    clip_gzh_env.load_account_env()

                _, chosen = clip_gzh_env.load_account_env(account="zbt")
                self.assertEqual(chosen, "zbt")
                self.assertEqual(os.environ.get("WECHAT_MP_TOKEN"), "tok_a")
                self.assertEqual(os.environ.get("OBSIDIAN_VAULT"), tmp)

            with mock.patch.dict(os.environ, _clean_env({"SOIA_SKILLS_CONFIG_HOME": tmp}), clear=True):
                _, chosen = clip_gzh_env.load_account_env(config_file="accounts/ybb.yml" if False else "ybb.yml")
                self.assertEqual(chosen, "ybb")
                self.assertEqual(os.environ.get("WECHAT_APP_ID"), "wx_b")


class ClipWeChatCLITests(unittest.TestCase):
    def test_cli_list_accounts_across_all_three_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "soia-pkm-clip-wechat-account"
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "config.zbt.yml").write_text(
                "env:\n  WECHAT_ACCOUNT_NAME: \"示例甲\"\n  WECHAT_MP_TOKEN: \"tok_secret\"\n  WECHAT_MP_COOKIE: \"ck_secret\"\n",
                encoding="utf-8",
            )
            env = _clean_env({"SOIA_SKILLS_CONFIG_HOME": tmp})
            for script in ("fetch_api.py", "fetch_mp.py", "fetch_cookie.py"):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPTS_DIR / script), "--list-accounts"],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, msg=f"{script} stderr={proc.stderr}")
                self.assertIn("zbt: 示例甲", proc.stdout)
                self.assertNotIn("tok_secret", proc.stdout)
                self.assertNotIn("ck_secret", proc.stdout)

    def test_fetch_api_redacts_secret_and_fetch_mp_dry_run_uses_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "soia-pkm-clip-wechat-account"
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "config.zbt.yml").write_text(
                "\n".join(
                    [
                        "env:",
                        '  WECHAT_ACCOUNT_NAME: "示例甲"',
                        '  WECHAT_APP_ID: "wx_a"',
                        '  WECHAT_APP_SECRET: "super_secret_token"',
                        '  WECHAT_MP_TOKEN: "123456"',
                        '  WECHAT_MP_COOKIE: "session=abc"',
                    ]
                ),
                encoding="utf-8",
            )

            # 1. fetch_api HTTP error must redact secret=
            err = urllib.error.HTTPError(
                url="https://api.weixin.qq.com/cgi-bin/token?secret=super_secret_token",
                code=500,
                msg="Server Error",
                hdrs=None,
                fp=io.BytesIO(b"bad"),
            )
            with mock.patch("urllib.request.urlopen", side_effect=err):
                with self.assertRaises(SystemExit) as ctx:
                    fetch_api._http_json("https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=wx_a&secret=super_secret_token")
                self.assertNotIn("super_secret_token", str(ctx.exception))
                self.assertIn("<REDACTED>", str(ctx.exception))

            # 2. fetch_mp --account zbt --dry-run resolves zbt credentials cleanly
            class FakeResp:
                def __init__(self, payload: dict) -> None:
                    self._data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

                def read(self) -> bytes:
                    return self._data

                def __enter__(self) -> "FakeResp":
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

            publish_page = json.dumps(
                {
                    "total_count": 1,
                    "publish_list": [
                        {
                            "publish_info": json.dumps(
                                {
                                    "appmsgex": [
                                        {
                                            "title": "自省第一篇",
                                            "link": "https://mp.weixin.qq.com/s/demo",
                                            "update_time": 1731724800,
                                        }
                                    ]
                                }
                            )
                        }
                    ],
                }
            )
            with mock.patch.dict(os.environ, _clean_env({"SOIA_SKILLS_CONFIG_HOME": tmp}), clear=True):
                with mock.patch(
                    "urllib.request.urlopen",
                    return_value=FakeResp({"base_resp": {"ret": 0}, "publish_page": publish_page}),
                ):
                    with mock.patch.object(sys, "argv", ["fetch_mp.py", "--account", "zbt", "--dry-run"]):
                        out = io.StringIO()
                        with redirect_stdout(out):
                            fetch_mp.main()
            self.assertIn("自省第一篇", out.getvalue())


if __name__ == "__main__":
    unittest.main()
